#!/usr/bin/env python3
"""render_props.py - everything the Remotion composition draws, frame by frame, for one project.

    python3 scripts/render_props.py projects/<slug>

Recorded: work/edl.json + work/transcript.json (source time) -> cut segments, captions re-timed to
the edit. Faceless: work/script.json + work/voice-timestamps.json + work/broll.json -> one visual per
beat over the voiceover. Either way the style (config/styles.json, by inputs.style) decides the
captions, zooms, transitions, overlays, music, sfx and grade.

Optional work/sections.json adds the things only a reader of the transcript knows:

    {"title": "...", "items": [
      {"at": 62.0, "type": "chapter", "title": "Assignment groups"},
      {"at": 62.0, "type": "step", "n": 2, "title": "Assign it"},
      {"at": 90.0, "type": "list", "n": 3, "title": "Priority"},
      {"at": 30.0, "dur": 4, "type": "callout", "text": "sys_id", "variant": "code-highlight"},
      {"at": 12.0, "type": "slam", "text": "PRIORITY ONE"}]}

`at` is in SOURCE time for recorded projects (read it off work/transcript.json) and in voice time
for faceless ones. Faceless beats can carry the same things inline: chapter, step_n, list_n,
overlay_text.

Writes work/render-props.json, work/final-transcript.json and work/final-transcript.srt (the words
in the EDITED timeline - chapters and Shorts are built from this, never from the raw transcript).
"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from transcribe import write_srt  # noqa: E402

CONFIG = os.environ.get("YTA_CONFIG") or os.path.join(ROOT, "config", "channel.json")
STYLES = os.path.join(ROOT, "config", "styles.json")
TRANSITION_FRAMES = 10
AUDIO_EXT = (".mp3", ".m4a", ".wav", ".aac", ".ogg")

# overlays drawn from the whole timeline, no data needed
AUTO_OVERLAYS = {"progress-bar", "letterbox", "lower-third-intro", "title-card", "waveform"}
# overlays that draw a sections.json item type
ITEM_OVERLAYS = {
    "chapter-card": "chapter", "topic-card": "chapter",
    "step-counter": "step", "checklist": "step",
    "number-card": "list", "countdown": "list", "rank-badge": "list",
    "text-slam": "slam",
    "callout-box": "callout", "keyboard-shortcut": "callout", "code-highlight": "callout",
    "map-callout": "callout", "lower-third-source": "callout", "date-stamp": "callout",
}
NOT_AVAILABLE = {"emoji-pop": "needs an emoji per word, which nothing produces yet",
                 "speaker-name": "needs speaker diarisation, which the transcript does not have",
                 "keyword-highlight": "covered by the caption highlight"}


def load(path, default=None):
    if not os.path.exists(path):
        if default is not None:
            return default
        sys.exit(f"missing: {path}")
    with open(path) as f:
        return json.load(f)


def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


class Project:
    def __init__(self, pdir):
        self.dir = os.path.abspath(pdir)
        self.state = load(os.path.join(self.dir, "state.json"))
        self.cfg = load(CONFIG, {})
        styles = {s["id"]: s for s in load(STYLES)["styles"]}
        sid = self.state["inputs"].get("style") or "clean-talking-head"
        if sid not in styles:
            sys.exit(f"unknown style '{sid}'")
        self.style = styles[sid]
        d = self.cfg.get("defaults", {})
        self.fps, self.w, self.h = d.get("fps", 30), d.get("width", 1920), d.get("height", 1080)
        self.warnings = []

    def p(self, *parts):
        return os.path.join(self.dir, *parts)

    def f(self, seconds):
        return int(round(seconds * self.fps))

    def link(self, target, name=None):
        """Expose a file outside the project to Remotion (whose public dir is the project folder)."""
        target = os.path.abspath(os.path.expanduser(target))
        links = self.p("work", "links")
        os.makedirs(links, exist_ok=True)
        dest = os.path.join(links, name or os.path.basename(target))
        if os.path.islink(dest) or os.path.exists(dest):
            if os.path.realpath(dest) == os.path.realpath(target):
                return os.path.relpath(dest, self.dir)
            os.remove(dest)
        os.symlink(target, dest)
        return os.path.relpath(dest, self.dir)

    def resolve(self, path):
        return path if os.path.isabs(path) else os.path.join(ROOT, path)


# ------------------------------------------------------------------ timelines

def recorded(pj):
    edl = load(pj.p("work", "edl.json"))
    tr = load(pj.p("work", "transcript.json"))
    ext = os.path.splitext(edl["source"])[1] or ".mp4"
    src = pj.link(edl["source"], "source" + ext)

    segs, cum, keeps = [], 0.0, []
    for i, k in enumerate(edl["keep"]):
        length = k["end"] - k["start"]
        a, b = pj.f(cum), pj.f(cum + length)
        if b - a <= 0:
            continue
        segs.append({"kind": "video", "src": src, "from": a, "dur": b - a, "trimBefore": pj.f(k["start"]),
                     "muted": False, "index": i})
        keeps.append((k["start"], k["end"], cum))
        cum += length

    def to_out(t):
        for s, e, c in keeps:
            if s <= t < e:
                return c + (t - s)
        return None

    words, segments = [], []
    for seg in tr["segments"]:
        cue = None
        for w in seg.get("words", []):
            mid = (w["start"] + w["end"]) / 2
            o = to_out(mid)
            if o is None:
                cue = None   # the word was cut; the next kept word starts a new cue
                continue
            k = next(k for k in keeps if k[0] <= mid < k[1])
            start = k[2] + (max(w["start"], k[0]) - k[0])
            end = k[2] + (min(w["end"], k[1]) - k[0])
            ow = {"w": w["w"], "start": round(start, 3), "end": round(max(end, start + 0.05), 3)}
            words.append(ow)
            if cue is None or cue["_keep"] is not k:
                cue = {"_keep": k, "words": []}
                segments.append(cue)
            cue["words"].append(ow)
    segments = [{"start": c["words"][0]["start"], "end": c["words"][-1]["end"],
                 "text": " ".join(w["w"] for w in c["words"]), "words": c["words"]} for c in segments]

    total = pj.f(cum)
    mapper = to_out
    return segs, words, segments, total, [], mapper


def faceless(pj):
    script = load(pj.p("work", "script.json"))
    vt = load(pj.p("work", "voice-timestamps.json"))
    broll = {b["id"]: b for b in load(pj.p("work", "broll.json"), {"beats": []}).get("beats", [])}
    beats = {b["id"]: b for b in script["beats"]}
    timing = sorted(vt["beats"], key=lambda b: b["start"])
    end_all = vt.get("duration") or timing[-1]["end"]
    total = pj.f(end_all + 0.5)

    segs, items = [], []
    for i, t in enumerate(timing):
        beat = beats.get(t["id"], {})
        start = t["start"] if i else 0.0
        end = timing[i + 1]["start"] if i + 1 < len(timing) else end_all + 0.5
        a, b = pj.f(start), pj.f(end)
        asset = broll.get(t["id"], {})
        file = asset.get("file")
        kind = asset.get("kind", "none")
        if kind in ("video", "image") and file and os.path.exists(pj.p(file)):
            seg = {"kind": kind, "src": file, "from": a, "dur": b - a, "index": i, "muted": True}
            if kind == "video":
                clip = probe_duration(pj.p(file)) or 0
                if clip and clip * pj.fps < b - a:
                    seg["loopFrames"] = max(1, int(clip * pj.fps) - 1)
        else:
            if kind in ("video", "image"):
                pj.warnings.append(f"beat {t['id']}: {kind} file missing, showing a text card")
            seg = {"kind": "card", "text": beat.get("overlay_text") or beat.get("on_screen") or "",
                   "from": a, "dur": b - a, "index": i}
        segs.append(seg)
        if beat.get("chapter"):
            items.append({"at": start, "type": "chapter", "title": beat["chapter"]})
        if beat.get("step_n"):
            items.append({"at": start, "type": "step", "n": beat["step_n"], "title": beat.get("step_title") or beat.get("chapter") or ""})
        if beat.get("list_n"):
            items.append({"at": start, "type": "list", "n": beat["list_n"], "title": beat.get("list_title") or beat.get("chapter") or ""})
        if beat.get("overlay_text") and kind in ("video", "image"):
            items.append({"at": start + 0.3, "type": "slam", "text": beat["overlay_text"], "soft": True})

    words = [{"w": w["w"], "start": w["start"], "end": w["end"]} for w in vt["words"]]
    segments = []
    for t in timing:
        ws = [w for w in vt["words"] if w.get("beat") == t["id"]]
        if ws:
            segments.append({"start": ws[0]["start"], "end": ws[-1]["end"],
                             "text": " ".join(w["w"] for w in ws), "words": ws})
    voice = load(pj.p("state.json"))["steps"].get("voiceover", {}).get("outputs", {}).get("voice", "work/voice.mp3")
    audio = [{"src": voice, "from": 0, "volume": 1}]
    return segs, words, segments, total, audio, (lambda t: t), items


# ------------------------------------------------------------------ style layers

def captions(pj, words):
    c = pj.style["captions"]
    if c["mode"] == "none" or not words:
        return []
    out, chunk = [], []

    def flush():
        if chunk:
            out.append({"from": pj.f(chunk[0]["start"]), "to": pj.f(chunk[-1]["end"]),
                        "words": [{"w": w["w"], "from": pj.f(w["start"]), "to": pj.f(w["end"])} for w in chunk]})
            chunk.clear()

    for i, w in enumerate(words):
        if chunk and (w["start"] - chunk[-1]["end"] > 0.6 or len(chunk) >= c["max_words"]):
            flush()
        chunk.append(w)
        if re.search(r"[.?!]$", w["w"]) or (c["mode"] == "line" and re.search(r",$", w["w"]) and len(chunk) >= 3):
            flush()
    flush()
    for i in range(len(out) - 1):
        # close gaps under 0.7s so captions do not blink between chunks; otherwise linger 0.4s
        gap = out[i + 1]["from"] - out[i]["to"]
        out[i]["to"] = out[i + 1]["from"] if gap <= pj.f(0.7) else out[i]["to"] + pj.f(0.4)
    if out:
        out[-1]["to"] += pj.f(0.4)
    return out


def zooms(pj, segs, total):
    z = pj.style.get("zoom", {})
    scale = z.get("scale", 1.0)
    every = z.get("punch_in_every")
    if z.get("follow_cursor"):
        pj.warnings.append("follow_cursor needs cursor data from the screen recorder; using timed punch-ins instead")
        every, scale = every or 10, min(scale, 1.15)
    if z.get("switch_on_speaker"):
        pj.warnings.append("switch_on_speaker needs speaker diarisation; no speaker zooms")
    if not every or scale <= 1.0:
        return []
    # toggle at every cut and every `every` seconds; a window is the stretch spent zoomed in
    marks = sorted({s["from"] for s in segs} | set(range(0, total, pj.f(every))))
    marks = [m for i, m in enumerate(marks) if i == 0 or m - marks[i - 1] >= pj.f(1.5)]
    windows = []
    for i, m in enumerate(marks):
        end = marks[i + 1] if i + 1 < len(marks) else total
        if i % 2 == 1 and end > m:
            windows.append({"from": m, "dur": end - m, "scale": scale, "shake": bool(z.get("shake"))})
    return windows


def overlays(pj, total, items, mapper, words):
    wanted = pj.style.get("overlays", [])
    out = []
    for name in wanted:
        if name in NOT_AVAILABLE:
            pj.warnings.append(f"overlay {name} skipped: {NOT_AVAILABLE[name]}")
    sections = load(pj.p("work", "sections.json"), {})
    title = sections.get("title") or pj.state["inputs"].get("topic")
    ch = pj.cfg.get("channel", {})

    if "progress-bar" in wanted:
        out.append({"type": "progress-bar", "from": 0, "dur": total})
    if "letterbox" in wanted:
        out.append({"type": "letterbox", "from": 0, "dur": total})
    if "waveform" in wanted:
        out.append({"type": "waveform", "from": 0, "dur": total, "src": waveform_audio(pj)})
    if "lower-third-intro" in wanted and ch.get("name"):
        sub = (ch.get("niche") or "").split("(")[0].strip()
        out.append({"type": "lower-third", "from": pj.f(1.0), "dur": pj.f(4.0), "title": ch["name"], "subtitle": sub})
    if "title-card" in wanted:
        if title:
            out.append({"type": "title-card", "from": 0, "dur": pj.f(3.0), "title": title})
        else:
            pj.warnings.append("title-card skipped: no title in sections.json and no topic")

    all_items = list(items)
    for it in sections.get("items", []):
        it = dict(it)
        o = mapper(it["at"]) if pj.state["mode"] == "recorded" else it["at"]
        if o is None:
            pj.warnings.append(f"sections item at {it['at']}s falls in a cut; dropped")
            continue
        it["at"] = o
        all_items.append(it)
    all_items.sort(key=lambda i: i["at"])

    used_types = {ITEM_OVERLAYS[n] for n in wanted if n in ITEM_OVERLAYS}
    steps = [i for i in all_items if i["type"] == "step"]
    lists = [i for i in all_items if i["type"] == "list"]
    for it in all_items:
        t, at = it["type"], pj.f(it["at"])
        if t not in used_types:
            continue
        if t == "chapter":
            out.append({"type": "chapter-card", "from": at, "dur": pj.f(2.5), "title": it["title"]})
        elif t == "step":
            nxt = next((s for s in steps if s["at"] > it["at"]), None)
            end = pj.f(nxt["at"]) if nxt else total
            out.append({"type": "step", "from": at, "dur": end - at, "n": it["n"], "of": len(steps),
                        "title": it.get("title", ""), "checklist": "checklist" in wanted,
                        "all": [s.get("title", "") for s in steps]})
        elif t == "list":
            nxt = next((s for s in lists if s["at"] > it["at"]), None)
            end = pj.f(nxt["at"]) if nxt else total
            out.append({"type": "list", "from": at, "dur": end - at, "n": it["n"], "title": it.get("title", ""),
                        "badge": "rank-badge" in wanted})
        elif t == "slam":
            if it.get("soft") and "text-slam" not in wanted:
                continue
            out.append({"type": "text-slam", "from": at, "dur": pj.f(1.6), "text": it["text"]})
        elif t == "callout":
            out.append({"type": "callout", "from": at, "dur": pj.f(it.get("dur", 4)), "text": it["text"],
                        "variant": it.get("variant", "callout-box")})
    return out


def waveform_audio(pj):
    if pj.state["mode"] == "faceless":
        return "work/voice.mp3"
    out = pj.p("work", "viz-audio.mp3")
    if not os.path.exists(out):
        edl = load(pj.p("work", "edl.json"))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", edl["source"], "-vn", "-ac", "1", "-ar", "22050",
                        "-b:a", "64k", out], check=True)
    return "work/viz-audio.mp3"


def music(pj):
    m = pj.style.get("music", {})
    if not m.get("enabled"):
        return None
    d = pj.resolve(pj.cfg.get("music", {}).get("dir", "assets/music"))
    files = sorted(f for f in os.listdir(d) if f.lower().endswith(AUDIO_EXT)) if os.path.isdir(d) else []
    if not files:
        pj.warnings.append(f"no background music in {d} - rendering without it")
        return None
    pick = files[sum(map(ord, pj.state["slug"])) % len(files)]   # stable per video, varies across videos
    return {"src": pj.link(os.path.join(d, pick), "music" + os.path.splitext(pick)[1]),
            "volume": m.get("volume", pj.cfg.get("music", {}).get("volume", 0.1)),
            "duck": bool(pj.cfg.get("music", {}).get("duck_under_voice", True))}


def sfx(pj, segs, zoom_windows, ovl):
    level = pj.style.get("sfx", "none")
    if level == "none":
        return []
    d = pj.resolve(pj.cfg.get("sfx", {}).get("dir", "assets/sfx"))
    files = sorted(f for f in os.listdir(d) if f.lower().endswith(AUDIO_EXT)) if os.path.isdir(d) else []
    if not files:
        pj.warnings.append(f"style wants {level} sfx but {d} has no sound files - rendering without them")
        return []
    pick = lambda kind: next((f for f in files if kind in f.lower()), files[0])
    whoosh, pop = pick("whoosh"), pick("pop")
    hits = []
    if pj.style["cuts"].get("transition", "none") != "none":
        hits += [(s["from"], whoosh) for s in segs[1:]]
    hits += [(o["from"], pop) for o in ovl if o["type"] in ("text-slam", "chapter-card", "list")]
    if level == "heavy":
        hits += [(z["from"], whoosh) for z in zoom_windows]
    if level == "ambient":
        hits = hits[:1]
    vol = {"subtle": 0.35, "heavy": 0.6, "ambient": 0.25}.get(level, 0.4)
    return [{"from": f, "src": pj.link(os.path.join(d, name)), "volume": vol} for f, name in sorted(hits)]


def main():
    if len(sys.argv) < 2 or not os.path.isdir(sys.argv[1]):
        print(__doc__)
        sys.exit(1)
    pj = Project(sys.argv[1])
    if pj.state["mode"] == "recorded":
        segs, words, segments, total, audio, mapper = recorded(pj)
        items = []
    else:
        segs, words, segments, total, audio, mapper, items = faceless(pj)

    transition = pj.style["cuts"].get("transition", "none")
    for s in segs[1:]:
        if transition != "none":
            s["enter"] = transition
            if pj.state["mode"] == "faceless":   # muted visuals can overlap; recorded audio must not
                s["from"] = max(0, s["from"] - TRANSITION_FRAMES)
                s["dur"] += TRANSITION_FRAMES
    if pj.style["zoom"].get("ken_burns"):
        for s in segs:
            if s["kind"] in ("image", "video") and pj.state["mode"] == "faceless":
                s["kenBurns"] = pj.style["zoom"].get("scale", 1.1)

    caps = captions(pj, words)
    zw = zooms(pj, segs, total)
    ovl = overlays(pj, total, items, mapper, words)
    brand = pj.cfg.get("brand", {})
    props = {
        "fps": pj.fps, "width": pj.w, "height": pj.h, "durationInFrames": total,
        "layout": "landscape", "cropX": 0.5, "frameRange": None,
        "mode": pj.state["mode"], "styleId": pj.style["id"], "style": pj.style,
        "brand": {k: brand.get(k) for k in ("primary", "secondary", "accent", "text", "font_heading", "font_body")},
        "segments": segs, "audio": audio, "music": music(pj), "sfx": sfx(pj, segs, zw, ovl),
        "captions": caps, "zooms": zw, "overlays": ovl, "hook": None,
        "transitionFrames": TRANSITION_FRAMES, "grade": pj.style.get("grade", "neutral"),
        "warnings": pj.warnings,
    }
    json.dump(props, open(pj.p("work", "render-props.json"), "w"), ensure_ascii=False)
    duration = total / pj.fps
    json.dump({"duration": round(duration, 3), "segments": segments, "words": words},
              open(pj.p("work", "final-transcript.json"), "w"), ensure_ascii=False, indent=1)
    write_srt(segments, pj.p("work", "final-transcript.srt"))
    print(json.dumps({"props": "work/render-props.json", "duration": round(duration, 2), "frames": total,
                      "segments": len(segs), "captions": len(caps), "zooms": len(zw), "overlays": len(ovl),
                      "warnings": pj.warnings}, ensure_ascii=False))


if __name__ == "__main__":
    main()
