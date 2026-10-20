#!/usr/bin/env python3
"""transcribe.py - word-timed transcript of a recording, with Whisper, on this Mac.

    python3 scripts/transcribe.py <video-or-audio> --out projects/<slug>/work/transcript
    python3 scripts/transcribe.py raw.mp4 --out work/transcript --model base --language en

Writes <out>.json and <out>.srt. The JSON keeps Whisper's "segments" shape (so deadair.py and
chapters.py read it directly) and adds a flat "words" list:

    {"language": "te", "duration": 912.4, "model": "turbo",
     "segments": [{"start": 0.0, "end": 4.2, "text": "...", "words": [{"w": "...", "start": 0.1, "end": 0.4}]}],
     "words": [...]}

Model and language default to config/channel.json -> transcribe. With caption_script "roman", Telugu
script is romanised (scripts/telugu_roman.py) and the original kept in <out>.native.json.

The first run of a model downloads it (turbo is ~1.5GB). turbo on CPU runs at roughly a few times
real time on an M-series Mac, so a 15-minute recording takes minutes, not seconds.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from telugu_roman import has_telugu, romanize  # noqa: E402

CONFIG = os.environ.get("YTA_CONFIG") or os.path.join(ROOT, "config", "channel.json")


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(segments, path):
    with open(path, "w", encoding="utf-8") as f:
        for i, s in enumerate(segments, 1):
            f.write(f"{i}\n{srt_time(s['start'])} --> {srt_time(s['end'])}\n{s['text'].strip()}\n\n")


def main():
    cfg = json.load(open(CONFIG)) if os.path.exists(CONFIG) else {}
    tc = cfg.get("transcribe", {})
    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("--out", required=True, help="path without extension")
    p.add_argument("--model", default=tc.get("model", "turbo"))
    p.add_argument("--language", default=tc.get("language") or None)
    p.add_argument("--caption-script", default=tc.get("caption_script", "native"), choices=["native", "roman"])
    a = p.parse_args()

    if not shutil.which("whisper"):
        sys.exit("whisper is not installed: pipx install openai-whisper")
    if not os.path.exists(a.source):
        sys.exit(f"not found: {a.source}")
    tmp = tempfile.mkdtemp(prefix="yta-whisper-")
    cmd = ["whisper", a.source, "--model", a.model, "--output_dir", tmp, "--output_format", "json",
           "--word_timestamps", "True", "--fp16", "False", "--verbose", "False",
           "--condition_on_previous_text", "False"]
    if a.language:
        cmd += ["--language", a.language]
    r = subprocess.run(cmd, capture_output=True, text=True)
    produced = [f for f in os.listdir(tmp) if f.endswith(".json")]
    if r.returncode != 0 or not produced:
        sys.exit(f"whisper failed:\n{r.stderr[-1500:]}")
    raw = json.load(open(os.path.join(tmp, produced[0])))
    shutil.rmtree(tmp, ignore_errors=True)

    segments, words = [], []
    for s in raw.get("segments", []):
        ws = [{"w": w["word"].strip(), "start": round(float(w["start"]), 3), "end": round(float(w["end"]), 3)}
              for w in s.get("words", []) if w.get("word", "").strip()]
        seg = {"start": round(float(s["start"]), 3), "end": round(float(s["end"]), 3),
               "text": s.get("text", "").strip(), "words": ws}
        if ws:  # Whisper's segment bounds pad silence; the words are the truth
            seg["start"], seg["end"] = ws[0]["start"], ws[-1]["end"]
        segments.append(seg)
        words.extend(ws)

    dur = None
    pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.source],
                        capture_output=True, text=True)
    try:
        dur = round(float(pr.stdout.strip()), 3)
    except ValueError:
        pass
    out = {"language": raw.get("language", a.language), "duration": dur, "model": a.model,
           "segments": segments, "words": words}

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    if a.caption_script == "roman" and any(has_telugu(s["text"]) for s in segments):
        json.dump(out, open(a.out + ".native.json", "w"), ensure_ascii=False, indent=1)
        for s in segments:
            s["text"] = romanize(s["text"])
            for w in s["words"]:
                w["w"] = romanize(w["w"])
        out["romanized"] = True
    json.dump(out, open(a.out + ".json", "w"), ensure_ascii=False, indent=1)
    write_srt(segments, a.out + ".srt")
    print(json.dumps({"json": a.out + ".json", "srt": a.out + ".srt", "language": out["language"],
                      "segments": len(segments), "words": len(words), "duration": dur,
                      "romanized": out.get("romanized", False)}))


if __name__ == "__main__":
    main()
