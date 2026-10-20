#!/usr/bin/env python3
"""imagegen.py - one AI image from a prompt, through whichever provider config/channel.json names.

    python3 scripts/imagegen.py --prompt "..." --out work/thumb/bg-1.png [--size landscape]

Providers (config images.provider, key in .env):
  openai  OPENAI_API_KEY   model from images.model, default gpt-image-1
  gemini  GEMINI_API_KEY   model from images.model, default gemini-2.5-flash-image

Model names change; if the default is retired, set images.model in config/channel.json. The key is
read from .env and never printed.
"""
import argparse, base64, json, os, sys, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.environ.get("YTA_CONFIG") or os.path.join(ROOT, "config", "channel.json")
DEFAULTS = {"openai": "gpt-image-1", "gemini": "gemini-2.5-flash-image"}
KEYS = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}


def env(name):
    if os.environ.get(name):
        return os.environ[name]
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        for line in open(path):
            k, _, v = line.strip().partition("=")
            if k == name and v.strip().strip("'\""):
                return v.strip().strip("'\"")
    return None


def post(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:400]
        sys.exit(f"image API error {e.code}: {detail}")


def generate(prompt, provider=None, model=None, size="landscape"):
    cfg = json.load(open(CONFIG)) if os.path.exists(CONFIG) else {}
    provider = provider or cfg.get("images", {}).get("provider")
    if provider not in KEYS:
        sys.exit("set images.provider to openai or gemini in config/channel.json")
    key = env(KEYS[provider])
    if not key:
        sys.exit(f"{KEYS[provider]} is not set in .env")
    model = model or cfg.get("images", {}).get("model") or DEFAULTS[provider]
    if provider == "openai":
        dims = {"landscape": "1536x1024", "portrait": "1024x1536", "square": "1024x1024"}[size]
        r = post("https://api.openai.com/v1/images/generations",
                 {"model": model, "prompt": prompt, "size": dims, "n": 1},
                 {"Authorization": f"Bearer {key}"})
        return base64.b64decode(r["data"][0]["b64_json"]), model
    aspect = {"landscape": "16:9", "portrait": "9:16", "square": "1:1"}[size]
    r = post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
             {"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect}}},
             {"x-goog-api-key": key})
    for cand in r.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            data = part.get("inlineData") or part.get("inline_data")
            if data:
                return base64.b64decode(data["data"]), model
    sys.exit(f"gemini returned no image: {json.dumps(r)[:300]}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--prompt", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--size", default="landscape", choices=["landscape", "portrait", "square"])
    p.add_argument("--provider")
    a = p.parse_args()
    img, model = generate(a.prompt + "\nNo text, no letters, no logos, no watermarks.", a.provider, size=a.size)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    open(a.out, "wb").write(img)
    print(json.dumps({"image": a.out, "bytes": len(img), "model": model}))


if __name__ == "__main__":
    main()
