#!/usr/bin/env python3
"""tts.py - the voiceover for a script, with word timings, one beat at a time.

    python3 scripts/tts.py --script work/script.json --out work/voice.mp3 --timestamps work/voice-timestamps.json
    ... --engine say      # macOS voice, English only, estimated timings - for testing the pipeline

Engines:
  elevenlabs  (default) voice from config voiceover.voice_id, model from voiceover.model
              (default eleven_multilingual_v2), ELEVENLABS_API_KEY in .env. Uses the
              /with-timestamps endpoint, so word timings are the engine's own.
  kokoro      free, local Kokoro-82M (scripts/kokoro_tts.py in .venv-tts). Voice from config
              voiceover.kokoro_voice (default am_michael). English/Hindi; real word timings in English.
  say         macOS `say`. Timings are estimated from word length - good enough to test the
              pipeline, not to publish.

Each beat is synthesised separately (a bad beat can be redone alone), joined with a short breath,
then loudness-normalised to -16 LUFS. The chosen hook (hook_choice) replaces beat 1's text when the
script's beat 1 is the hook.

    voice-timestamps.json: {"duration", "beats": [{"id", "start", "end"}], "words": [{"w", "start", "end", "beat"}]}
"""
import argparse, base64, json, os, re, shutil, subprocess, sys, tempfile, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from imagegen import env  # noqa: E402

CONFIG = os.environ.get("YTA_CONFIG") or os.path.join(ROOT, "config", "channel.json")
GAP = 0.28   # breath between beats, seconds


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def words_from_chars(chars, starts, ends):
    out, cur, s0, e0 = [], "", None, None
    for c, s, e in zip(chars, starts, ends):
        if c.isspace():
            if cur:
                out.append({"w": cur, "start": s0, "end": e0})
            cur, s0 = "", None
            continue
        if not cur:
            s0 = s
        cur += c
        e0 = e
    if cur:
        out.append({"w": cur, "start": s0, "end": e0})
    return out


def eleven(text, prev, nxt, voice, model, key, wav):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_128"
    body = {"text": text, "model_id": model}
    if prev:
        body["previous_text"] = prev
    if nxt:
        body["next_text"] = nxt
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "xi-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"ElevenLabs error {e.code}: {e.read().decode(errors='replace')[:400]}")
    mp3 = wav + ".mp3"
    open(mp3, "wb").write(base64.b64decode(d["audio_base64"]))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp3, "-ac", "1", "-ar", "48000", wav], check=True)
    al = d.get("alignment") or d.get("normalized_alignment")
    return words_from_chars(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"])


def say(text, wav):
    aiff = wav + ".aiff"
    subprocess.run(["say", "-v", "Rishi", "-r", "180", "-o", aiff, text], check=True)
    # trim the silence `say` leaves at both ends so the estimate spreads over speech only
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", aiff, "-af",
                    "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse",
                    "-ac", "1", "-ar", "48000", wav], check=True)
    total = duration(wav)
    ws = text.split()
    weights = [len(w) + 2 + (4 if re.search(r"[.,?!]$", w) else 0) for w in ws]
    unit, t, out = total / sum(weights), 0.0, []
    for w, k in zip(ws, weights):
        out.append({"w": w, "start": round(t, 3), "end": round(t + k * unit * 0.9, 3)})
        t += k * unit
    return out


def kokoro(text, voice, speed, wav):
    py = os.path.join(ROOT, ".venv-tts", "bin", "python")
    if not os.path.exists(py):
        sys.exit("Kokoro is not installed: python3.11 -m venv .venv-tts && .venv-tts/bin/pip install kokoro soundfile")
    raw, wjson = wav + ".kokoro.wav", wav + ".kokoro.json"
    r = subprocess.run([py, os.path.join(ROOT, "scripts", "kokoro_tts.py"), "--text", text, "--voice", voice,
                        "--speed", str(speed), "--out", raw, "--words", wjson], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Kokoro failed: {(r.stderr or r.stdout).strip()[-400:]}")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-ac", "1", "-ar", "48000", wav], check=True)
    return json.load(open(wjson))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--script", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--timestamps", required=True)
    p.add_argument("--engine", choices=["elevenlabs", "kokoro", "say"], default="elevenlabs")
    p.add_argument("--only", type=int, help="re-synthesise just this beat id, reuse the rest")
    a = p.parse_args()
    cfg = json.load(open(CONFIG)) if os.path.exists(CONFIG) else {}
    script = json.load(open(a.script))
    beats = list(script["beats"])
    if beats and beats[0].get("role") == "hook" and script.get("hooks"):
        beats[0] = dict(beats[0], say=script["hooks"][script.get("hook_choice", 0)]["text"])

    vo = cfg.get("voiceover", {})
    if a.engine == "elevenlabs":
        key = env("ELEVENLABS_API_KEY")
        if not key:
            sys.exit("ELEVENLABS_API_KEY is not set in .env")
        if not vo.get("voice_id"):
            sys.exit("voiceover.voice_id is empty in config/channel.json")
        model = vo.get("model") or "eleven_multilingual_v2"

    cache = os.path.join(os.path.dirname(os.path.abspath(a.out)), "voice-beats")
    os.makedirs(cache, exist_ok=True)
    pieces, timeline, words, t = [], [], [], 0.0
    silence = os.path.join(cache, "gap.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                    "-t", str(GAP), silence], check=True)
    for i, b in enumerate(beats):
        wav = os.path.join(cache, f"beat-{b['id']:03d}.wav")
        wjson = wav + ".words.json"
        if a.only is None or a.only == b["id"] or not os.path.exists(wav):
            text = b["say"].strip()
            if a.engine == "say":
                ws = say(text, wav)
            elif a.engine == "kokoro":
                ws = kokoro(text, vo.get("kokoro_voice") or "am_michael", vo.get("kokoro_speed") or 1.0, wav)
            else:
                prev = beats[i - 1]["say"] if i else None
                nxt = beats[i + 1]["say"] if i + 1 < len(beats) else None
                ws = eleven(text, prev, nxt, vo["voice_id"], model, key, wav)
            json.dump(ws, open(wjson, "w"), ensure_ascii=False)
        ws = json.load(open(wjson))
        d = duration(wav)
        timeline.append({"id": b["id"], "start": round(t, 3), "end": round(t + d, 3)})
        words += [{"w": w["w"], "start": round(t + w["start"], 3), "end": round(t + w["end"], 3), "beat": b["id"]} for w in ws]
        pieces += [wav, silence]
        t += d + GAP

    lst = os.path.join(cache, "concat.txt")
    open(lst, "w").write("".join(f"file '{x}'\n" for x in pieces[:-1]))
    joined = os.path.join(cache, "joined.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", joined], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-ar", "48000", "-ac", "2", "-b:a", "192k", a.out], check=True)
    total = duration(a.out)
    json.dump({"duration": round(total, 3), "engine": a.engine, "beats": timeline, "words": words},
              open(a.timestamps, "w"), ensure_ascii=False, indent=1)
    est = script.get("runtime_seconds")
    print(json.dumps({"voice": a.out, "duration": round(total, 2), "beats": len(timeline), "words": len(words),
                      "target": est, "off_by_pct": round((total - est) / est * 100, 1) if est else None}))


if __name__ == "__main__":
    main()
