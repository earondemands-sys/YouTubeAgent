#!/usr/bin/env python3
"""kokoro_tts.py - one beat of voiceover with the free, local Kokoro model, plus its word timings.

    .venv-tts/bin/python scripts/kokoro_tts.py --text "..." --voice am_michael --out beat.wav --words beat.words.json

Called by tts.py (--engine kokoro); it runs in its own venv (.venv-tts) because Kokoro needs torch.
Setup once: python3.11 -m venv .venv-tts && .venv-tts/bin/pip install kokoro soundfile; brew install espeak-ng.
Voices: a* = American English (am_michael, am_fenrir, af_heart), b* = British, h* = Hindi (hm_omega).
The word timings are Kokoro's own (English); for other languages they are spread over the audio.
"""
import argparse, json, os, re, sys, warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
SR = 24000


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--text", required=True)
    p.add_argument("--voice", default="am_michael")
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--out", required=True)
    p.add_argument("--words", required=True)
    a = p.parse_args()

    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    pipe = KPipeline(lang_code=a.voice[0], repo_id="hexgrad/Kokoro-82M")
    audio, words, offset = [], [], 0.0
    for r in pipe(a.text, voice=a.voice, speed=a.speed):
        if r.audio is None:
            continue
        chunk = r.audio.numpy() if hasattr(r.audio, "numpy") else np.asarray(r.audio)
        for t in (r.tokens or []):
            if t.start_ts is None or t.end_ts is None or not re.search(r"\w", t.text or ""):
                if words and t.text and not t.whitespace:   # glue punctuation onto the word before it
                    words[-1]["w"] += t.text
                continue
            words.append({"w": t.text, "start": round(offset + t.start_ts, 3), "end": round(offset + t.end_ts, 3)})
        audio.append(chunk)
        offset += len(chunk) / SR
    if not audio:
        sys.exit("Kokoro produced no audio for this text")
    sf.write(a.out, np.concatenate(audio), SR)
    if not words:   # no timings from the model (non-English): spread the words over the audio
        ws, unit = a.text.split(), offset / max(len(a.text.split()), 1)
        words = [{"w": w, "start": round(i * unit, 3), "end": round((i + 0.9) * unit, 3)} for i, w in enumerate(ws)]
    json.dump(words, open(a.words, "w"), ensure_ascii=False)


if __name__ == "__main__":
    main()
