#!/usr/bin/env python3
"""doctor.py - what this Mac has, and which parts of the YouTube agent team can run.

    python3 scripts/doctor.py
    python3 scripts/doctor.py --json

Never prints a key's value - only whether it is set.
"""
import json, os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.expanduser("~/.claude/skills")
BASE_SKILLS = ["yt-audit", "yt-chapters", "yt-comment", "yt-edit", "yt-package", "yt-plan",
               "yt-retention", "yt-script", "yt-seo", "yt-shorts", "yt-viral"]


def version(cmd, args=("--version",)):
    if not shutil.which(cmd):
        return None
    try:
        out = subprocess.run([cmd, *args], capture_output=True, text=True, timeout=20)
        return (out.stdout or out.stderr).strip().splitlines()[0][:60]
    except Exception:
        return "installed"


def env_keys():
    path = os.path.join(ROOT, ".env")
    keys = {}
    if os.path.exists(path):
        for line in open(path):
            m = re.match(r"^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$", line)
            if m:
                keys[m.group(1)] = bool(m.group(2).strip("'\""))
    return keys


def main():
    keys = env_keys()
    cfg = {}
    try:
        cfg = json.load(open(os.path.join(ROOT, "config", "channel.json")))
    except Exception:
        pass
    node = version("node")
    node_ok = bool(node and re.match(r"v(\d+)", node) and int(re.match(r"v(\d+)", node).group(1)) >= 18)
    img = cfg.get("images", {}).get("provider", "")
    img_key = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}.get(img)

    checks = [
        # (group, name, ok, detail, how to fix)
        ("core", "python3", True, sys.version.split()[0], ""),
        ("core", "node >= 18", node_ok, node or "missing", "brew install node"),
        ("core", "ffmpeg", bool(shutil.which("ffmpeg")), version("ffmpeg", ("-version",)) or "missing", "brew install ffmpeg"),
        ("core", "ffprobe", bool(shutil.which("ffprobe")), "ok" if shutil.which("ffprobe") else "missing", "brew install ffmpeg"),
        ("core", "base yt-* skills (11)", all(os.path.exists(os.path.join(SKILLS, s, "SKILL.md")) for s in BASE_SKILLS),
         f"{sum(os.path.exists(os.path.join(SKILLS, s, 'SKILL.md')) for s in BASE_SKILLS)}/11 in ~/.claude/skills", "reinstall the yt-* skills"),
        ("setup", "channel.json filled", bool(cfg.get("channel", {}).get("name")), "channel.name set" if cfg.get("channel", {}).get("name") else "channel.name empty",
         "the Director asks on first run"),
        ("setup", "voice profile", os.path.exists(os.path.expanduser("~/.claude/youtube/voice.md")), "~/.claude/youtube/voice.md",
         "the Director builds it from 3 of your videos"),
        ("upload", "python venv", os.path.exists(os.path.join(ROOT, ".venv", "bin", "python")), ".venv",
         "python3 -m venv .venv && .venv/bin/pip install google-api-python-client google-auth-oauthlib"),
        ("upload", "Google OAuth client", os.path.exists(os.path.join(ROOT, "secrets", "client_secret.json")), "secrets/client_secret.json",
         "docs/SETUP-YOUTUBE.md steps 1-4"),
        ("upload", "YouTube sign-in", os.path.exists(os.path.join(ROOT, "secrets", "token.json")), "secrets/token.json",
         ".venv/bin/python scripts/youtube_auth.py (docs/SETUP-YOUTUBE.md step 5)"),
        ("instagram", "Instagram app keys", bool(keys.get("INSTAGRAM_APP_ID") and keys.get("INSTAGRAM_APP_SECRET")
                                                 and keys.get("INSTAGRAM_REDIRECT_URI")),
         "INSTAGRAM_APP_ID / _SECRET / _REDIRECT_URI", "docs/SETUP-INSTAGRAM.md steps 1-4, then add to .env"),
        ("instagram", "Instagram sign-in", os.path.exists(os.path.join(ROOT, "secrets", "instagram_token.json")),
         "secrets/instagram_token.json", "python3 scripts/instagram_auth.py (docs/SETUP-INSTAGRAM.md step 5)"),
        ("edit", "whisper", bool(shutil.which("whisper")), version("whisper", ("--help",)) and "installed" or "missing", "pipx install openai-whisper"),
        ("edit", "remotion project", os.path.isdir(os.path.join(ROOT, "remotion", "node_modules")), "remotion/node_modules", "cd remotion && npm install"),
        ("thumbnail", "image API key (optional)", bool(img_key and keys.get(img_key)), f"{img_key or 'images.provider not set'}",
         "set images.provider in config and the key in .env (optional: gradient fallback)"),
        ("thumbnail", "face cutouts", bool(os.path.isdir(os.path.join(ROOT, "assets", "brand", "faces")) and
                                         any(f.lower().endswith(".png") for f in os.listdir(os.path.join(ROOT, "assets", "brand", "faces")))),
         "assets/brand/faces/*.png", "add 3-5 transparent PNGs of your face"),
        ("faceless", "ElevenLabs key", bool(keys.get("ELEVENLABS_API_KEY")), "ELEVENLABS_API_KEY", "add to .env"),
        ("faceless", "voice id", bool(cfg.get("voiceover", {}).get("voice_id")), "voiceover.voice_id", "pick a voice in ElevenLabs"),
        ("faceless", "Pexels key", bool(keys.get("PEXELS_API_KEY")), "PEXELS_API_KEY", "free at pexels.com/api, add to .env"),
        ("research", "yt-dlp", bool(shutil.which("yt-dlp")), version("yt-dlp") or "missing (public pages work too)", "brew install yt-dlp"),
        ("music", "sound effects (optional)", bool(os.path.isdir(os.path.join(ROOT, "assets", "sfx")) and
                                         any(f.lower().endswith((".mp3", ".wav", ".m4a")) for f in os.listdir(os.path.join(ROOT, "assets", "sfx")))),
         "assets/sfx/ (whoosh*, pop*)", "add a few whoosh/pop sounds for the hype styles"),
        ("music", "background music (optional)", bool(os.path.isdir(os.path.join(ROOT, "assets", "music")) and
                                         any(f.lower().endswith((".mp3", ".wav", ".m4a")) for f in os.listdir(os.path.join(ROOT, "assets", "music")))),
         "assets/music/", "download from YouTube Audio Library"),
    ]

    groups = {}
    for g, *_rest in checks:
        groups.setdefault(g, [])
    for g, name, ok, detail, fix in checks:
        groups[g].append({"name": name, "ok": ok, "detail": detail, "fix": "" if ok else fix})
    ready = {g: all(c["ok"] for c in items if "(optional)" not in c["name"]) for g, items in groups.items()}

    if "--json" in sys.argv:
        print(json.dumps({"groups": groups, "ready": ready}, indent=2))
        return
    for g, items in groups.items():
        print(f"\n{g.upper()}  {'ready' if ready[g] else 'not ready'}")
        for c in items:
            mark = "✓" if c["ok"] else "✗"
            fix = f"  -> {c['fix']}" if c["fix"] else ""
            print(f"  {mark} {c['name']:<24} {c['detail']}{fix}")
    print()


if __name__ == "__main__":
    main()
