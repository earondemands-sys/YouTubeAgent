#!/usr/bin/env python3
"""qa_check.py - every machine-checkable thing that can go wrong before an upload.

    python3 scripts/qa_check.py projects/<slug>            # human summary
    python3 scripts/qa_check.py projects/<slug> --json     # the report the qa agent extends

Reads the outputs recorded in state.json (falls back to the standard paths), and checks the video,
its loudness, black frames and silences, every Short, the thumbnail, the metadata limits YouTube
enforces, chapter validity, b-roll credits and whether AI-media disclosure is needed.

Every check has an `owner`: the step that must fix it. The Director sends a rejection there.
"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.environ.get("YTA_CONFIG") or os.path.join(ROOT, "config", "channel.json")
MAX_THUMB = 2 * 1024 * 1024


def ffprobe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    return json.loads(r.stdout)


def ffmpeg_stderr(args):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args], capture_output=True, text=True)
    return r.stderr


def fps_of(stream):
    num, _, den = (stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0/1").partition("/")
    try:
        return float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError):
        return 0.0


def streams(probe, kind):
    return [s for s in probe.get("streams", []) if s.get("codec_type") == kind]


def to_seconds(t):
    parts = [float(p) for p in str(t).split(":")]
    s = 0.0
    for p in parts:
        s = s * 60 + p
    return s


def tag_chars(tags):
    # YouTube counts a tag containing a space with its quotes, plus the commas between tags.
    return sum(len(t) + (2 if " " in t else 0) for t in tags) + max(len(tags) - 1, 0)


class Report:
    def __init__(self):
        self.checks = []

    def add(self, name, status, detail, owner):
        self.checks.append({"name": name, "status": status, "detail": detail, "owner": owner})

    def verdict(self):
        st = {c["status"] for c in self.checks}
        return "FAIL" if "FAIL" in st else "WARN" if "WARN" in st else "PASS"


def check_video(rep, path, cfg):
    d = cfg.get("defaults", {})
    if not os.path.exists(path):
        rep.add("video", "FAIL", f"missing: {path}", "remotion")
        return None
    p = ffprobe(path)
    if not p:
        rep.add("video", "FAIL", "ffprobe cannot read it", "remotion")
        return None
    v, a = streams(p, "video"), streams(p, "audio")
    dur = float(p["format"].get("duration", 0))
    problems = []
    if "mp4" not in p["format"].get("format_name", ""):
        problems.append(f"container {p['format'].get('format_name')}")
    if not v:
        problems.append("no video stream")
    else:
        v = v[0]
        if v.get("codec_name") != "h264":
            problems.append(f"video codec {v.get('codec_name')}")
        want = (d.get("width", 1920), d.get("height", 1080))
        if (v.get("width"), v.get("height")) != want:
            problems.append(f"{v.get('width')}x{v.get('height')}, config wants {want[0]}x{want[1]}")
        fps = fps_of(v)
        if abs(fps - d.get("fps", 30)) > 0.5:
            problems.append(f"{fps:.2f} fps, config wants {d.get('fps', 30)}")
    if not a:
        problems.append("no audio stream")
    elif a[0].get("codec_name") != "aac":
        problems.append(f"audio codec {a[0].get('codec_name')}")
    rep.add("video", "FAIL" if problems else "PASS",
            "; ".join(problems) or f"h264/aac mp4, {dur:.1f}s", "remotion")
    return {"duration": dur, "has_audio": bool(a)}


def check_loudness(rep, path):
    err = ffmpeg_stderr(["-i", path, "-vn", "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S)
    if not m:
        rep.add("loudness", "WARN", "could not measure loudness", "remotion")
        return
    j = json.loads(m.group(0))
    try:
        i, tp = float(j["input_i"]), float(j["input_tp"])
    except ValueError:
        rep.add("loudness", "FAIL", "audio is silent", "remotion")
        return
    bad = []
    if not -16 <= i <= -12:
        bad.append(f"integrated {i:.1f} LUFS (want -14 +/-2)")
    if tp > -1:
        bad.append(f"true peak {tp:.1f} dBTP (want <= -1)")
    rep.add("loudness", "FAIL" if bad else "PASS", "; ".join(bad) or f"{i:.1f} LUFS, peak {tp:.1f} dBTP", "remotion")


def check_edges(rep, path, dur):
    """Black frames at the very start or end. Only the first and last 5s are decoded."""
    found = []
    for label, args in (("start", ["-t", "5", "-i", path]), ("end", ["-sseof", "-5", "-i", path])):
        err = ffmpeg_stderr([*args, "-an", "-vf", "blackdetect=d=1:pix_th=0.10", "-f", "null", "-"])
        if "black_start" in err:
            found.append(label)
    rep.add("black frames", "FAIL" if found else "PASS",
            f"over 1s of black at the {' and '.join(found)}" if found else "clean start and end", "remotion")


def check_silence(rep, path):
    err = ffmpeg_stderr(["-i", path, "-vn", "-af", "silencedetect=n=-45dB:d=4", "-f", "null", "-"])
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", err)]
    if starts:
        where = ", ".join(f"{s:.0f}s" for s in starts[:5])
        rep.add("silence", "FAIL", f"{len(starts)} silences over 4s, at {where}", "remotion")
    else:
        rep.add("silence", "PASS", "no silence over 4s", "remotion")


def check_shorts(rep, pdir, shorts_json):
    if not shorts_json or not os.path.exists(shorts_json):
        return
    shorts = json.load(open(shorts_json)).get("shorts", [])
    for s in shorts:
        f = os.path.join(pdir, s["file"])
        name = f"short {s.get('n')}"
        p = ffprobe(f) if os.path.exists(f) else None
        if not p or not streams(p, "video"):
            rep.add(name, "FAIL", f"missing or unreadable: {s['file']}", "shorts")
            continue
        v = streams(p, "video")[0]
        dur = float(p["format"].get("duration", 0))
        w, h = v.get("width", 0), v.get("height", 1)
        bad, warn = [], []
        if abs(w / h - 9 / 16) > 0.01:
            bad.append(f"{w}x{h} is not 9:16")
        if dur > 180:
            bad.append(f"{dur:.0f}s is over YouTube's 180s Shorts limit")
        elif dur > 60:
            warn.append(f"{dur:.0f}s - Shorts under 60s travel further")
        if not streams(p, "audio"):
            bad.append("no audio")
        title = s.get("title", "")
        if not title or len(title) > 100:
            bad.append("title empty or over 100 characters")
        rep.add(name, "FAIL" if bad else "WARN" if warn else "PASS",
                "; ".join(bad + warn) or f"{w}x{h}, {dur:.0f}s", "shorts")


def check_thumbnail(rep, path):
    if not os.path.exists(path):
        rep.add("thumbnail", "FAIL", f"missing: {path}", "thumbnail")
        return
    size = os.path.getsize(path)
    p = ffprobe(path)
    bad = []
    if size >= MAX_THUMB:
        bad.append(f"{size / 1048576:.2f}MB, YouTube's limit is 2MB")
    if not p or not streams(p, "video"):
        bad.append("not a readable image")
    else:
        v = streams(p, "video")[0]
        if v.get("codec_name") not in ("mjpeg", "png"):
            bad.append(f"format {v.get('codec_name')}, want JPEG or PNG")
        if (v.get("width"), v.get("height")) != (1280, 720):
            bad.append(f"{v.get('width')}x{v.get('height')}, want 1280x720")
    rep.add("thumbnail", "FAIL" if bad else "PASS", "; ".join(bad) or f"1280x720, {size / 1024:.0f}KB", "thumbnail")


def check_metadata(rep, meta_path, video_dur, broll_path):
    if not os.path.exists(meta_path):
        rep.add("metadata", "FAIL", f"missing: {meta_path}", "seo")
        return
    m = json.load(open(meta_path))
    title, desc, tags = m.get("title", ""), m.get("description", ""), m.get("tags", [])

    bad, warn = [], []
    if not title.strip():
        bad.append("empty")
    if len(title) > 100:
        bad.append(f"{len(title)} characters, limit 100")
    elif len(title) > 60:
        warn.append(f"{len(title)} characters - desktop search cuts at 60")
    if re.search(r"[<>]", title):
        bad.append("contains < or >")
    rep.add("title", "FAIL" if bad else "WARN" if warn else "PASS", "; ".join(bad + warn) or f"{len(title)} chars", "seo")

    bad = []
    if len(desc) > 5000:
        bad.append(f"{len(desc)} characters, limit 5000")
    if re.search(r"[<>]", desc):
        bad.append("contains < or >")
    if not desc.strip():
        bad.append("empty")
    rep.add("description", "FAIL" if bad else "PASS", "; ".join(bad) or f"{len(desc)} chars", "seo")

    n = tag_chars(tags)
    rep.add("tags", "FAIL" if n > 500 else "PASS", f"{len(tags)} tags, {n}/500 characters", "seo")

    ch = m.get("chapters") or []
    if ch:
        bad = []
        starts = [to_seconds(c["t"]) for c in ch]
        if starts[0] != 0:
            bad.append("first chapter is not 00:00")
        if len(ch) < 3:
            bad.append(f"only {len(ch)} chapters, YouTube needs 3")
        ends = starts[1:] + [video_dur or starts[-1] + 10]
        short = [c["t"] for c, s, e in zip(ch, starts, ends) if e - s < 10]
        if short:
            bad.append(f"under 10s: {', '.join(short)}")
        if video_dur and starts[-1] >= video_dur:
            bad.append("a chapter starts after the video ends")
        if starts != sorted(starts):
            bad.append("not in order")
        missing = [c["t"] for c in ch if not re.search(rf"(?m)^\s*{re.escape(c['t'])}\b", desc)]
        if missing:
            bad.append(f"not in the description (YouTube reads them from there): {', '.join(missing[:3])}")
        rep.add("chapters", "FAIL" if bad else "PASS", "; ".join(bad) or f"{len(ch)} valid chapters", "seo")
    else:
        rep.add("chapters", "WARN", "no chapters", "seo")

    if broll_path and os.path.exists(broll_path):
        credits = [b["credit"] for b in json.load(open(broll_path)).get("beats", []) if b.get("credit")]
        missing = sorted({c for c in credits if c not in desc})
        rep.add("credits", "FAIL" if missing else "PASS",
                f"missing from description: {'; '.join(missing[:4])}" if missing else f"{len(set(credits))} credits present", "seo")


def synthetic_media(state, broll_path, cfg):
    rule = cfg.get("defaults", {}).get("synthetic_media_disclosure", "auto")
    if rule != "auto":
        return rule in (True, "true", "always")
    if state.get("steps", {}).get("voiceover", {}).get("status") == "done":
        return True
    if broll_path and os.path.exists(broll_path):
        return any(b.get("source") in ("openai", "gemini") for b in json.load(open(broll_path)).get("beats", []))
    return False


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args or not os.path.isdir(args[0]):
        print(__doc__)
        sys.exit(1)
    pdir = os.path.abspath(args[0])
    cfg = json.load(open(CONFIG)) if os.path.exists(CONFIG) else {}
    state = json.load(open(os.path.join(pdir, "state.json"))) if os.path.exists(os.path.join(pdir, "state.json")) else {}
    out = lambda step, key, default: os.path.join(
        pdir, state.get("steps", {}).get(step, {}).get("outputs", {}).get(key, default))

    rep = Report()
    video = out("remotion", "video", "out/video.mp4")
    info = check_video(rep, video, cfg)
    if info and info["has_audio"]:
        check_loudness(rep, video)
        check_silence(rep, video)
    if info:
        check_edges(rep, video, info["duration"])
    if state.get("steps", {}).get("shorts", {}).get("status") != "skipped":
        check_shorts(rep, pdir, out("shorts", "shorts", "work/shorts.json"))
    check_thumbnail(rep, out("thumbnail", "thumbnail", "out/thumbnail.jpg"))
    broll = out("broll", "broll", "work/broll.json") if state.get("mode") == "faceless" else None
    check_metadata(rep, out("seo", "metadata", "work/metadata.json"), info and info["duration"], broll)

    report = {"verdict": rep.verdict(), "synthetic_media": synthetic_media(state, broll, cfg), "checks": rep.checks}
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    print(f"\n  QA {report['verdict']}   synthetic media: {report['synthetic_media']}\n")
    for c in rep.checks:
        print(f"  {c['status']:<5} {c['name']:<13} {c['detail']}   [{c['owner']}]")
    print()


if __name__ == "__main__":
    main()
