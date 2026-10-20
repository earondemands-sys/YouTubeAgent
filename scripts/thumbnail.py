#!/usr/bin/env python3
"""thumbnail.py - build one thumbnail for a packaging option: background, face, words, JPEG, preview.

    python3 scripts/thumbnail.py projects/<slug> --option 1 [--variant 1] [--bg ai|gradient|<file>]
                                 [--face auto|none|<file>] [--text "OVERRIDE"] [--layout face-right]

--option N     the option in work/package.json (its thumb_text and brief.image_prompt)
--bg ai        generate the background with scripts/imagegen.py (needs an image key); `gradient`
               uses the brand colours; a path uses that image. Default: ai if a key is set, else gradient.
--face auto    the first PNG in config brand.faces_dir (sorted); `none` for a faceless thumbnail.

Writes work/thumb/thumb-<option>-<variant>.jpg (1280x720, under 2MB) and a preview of it beside
itself at feed size (168x94), so the agent can check it still reads small.
"""
import argparse, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from imagegen import KEYS, env  # noqa: E402

CONFIG = os.environ.get("YTA_CONFIG") or os.path.join(ROOT, "config", "channel.json")


def link(pdir, target, name):
    links = os.path.join(pdir, "work", "links")
    os.makedirs(links, exist_ok=True)
    dest = os.path.join(links, name)
    if os.path.lexists(dest):
        os.remove(dest)
    os.symlink(os.path.abspath(target), dest)
    return os.path.relpath(dest, pdir)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("project")
    p.add_argument("--option", type=int, required=True)
    p.add_argument("--variant", type=int, default=1)
    p.add_argument("--bg")
    p.add_argument("--face", default="auto")
    p.add_argument("--text")
    p.add_argument("--layout")
    a = p.parse_args()
    pdir = os.path.abspath(a.project)
    cfg = json.load(open(CONFIG)) if os.path.exists(CONFIG) else {}
    pkg = json.load(open(os.path.join(pdir, "work", "package.json")))
    opt = next((o for o in pkg["options"] if o["n"] == a.option), None)
    if not opt:
        sys.exit(f"no option {a.option} in work/package.json")
    tag = f"{a.option}-{a.variant}"
    os.makedirs(os.path.join(pdir, "work", "thumb"), exist_ok=True)

    provider = cfg.get("images", {}).get("provider")
    has_key = provider in KEYS and env(KEYS[provider])
    bg_mode = a.bg or ("ai" if has_key else "gradient")
    background = None
    if bg_mode == "ai":
        if not has_key:
            sys.exit("--bg ai needs images.provider in config and its key in .env; use --bg gradient")
        prompt = opt.get("brief", {}).get("image_prompt") or opt.get("brief", {}).get("background")
        if not prompt:
            sys.exit(f"option {a.option} has no brief.image_prompt")
        bg = os.path.join("work", "thumb", f"bg-{tag}.png")
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "imagegen.py"), "--prompt", prompt,
                            "--out", os.path.join(pdir, bg)], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(r.stderr.strip() or r.stdout.strip())
        background = bg
    elif bg_mode != "gradient":
        background = link(pdir, bg_mode, f"thumb-bg-{tag}{os.path.splitext(bg_mode)[1]}")

    face = None
    if a.face == "auto":
        d = cfg.get("brand", {}).get("faces_dir", "assets/brand/faces")
        d = d if os.path.isabs(d) else os.path.join(ROOT, d)
        pngs = sorted(f for f in os.listdir(d) if f.lower().endswith(".png")) if os.path.isdir(d) else []
        if pngs:
            pick = pngs[(a.variant - 1) % len(pngs)]
            face = link(pdir, os.path.join(d, pick), f"face-{tag}.png")
    elif a.face != "none":
        face = link(pdir, a.face, f"face-{tag}.png")

    layout = a.layout or ("face-right" if face else "no-face")
    brand = cfg.get("brand", {})
    props = {"background": background, "face": face, "text": a.text or opt["thumb_text"], "layout": layout,
             "brand": {k: brand.get(k) for k in ("primary", "secondary", "accent", "text", "font_heading", "font_body")}}
    props_path = os.path.join(pdir, "work", "thumb", f"thumb-{tag}.props.json")
    json.dump(props, open(props_path, "w"), ensure_ascii=False)

    out = os.path.join("work", "thumb", f"thumb-{tag}.jpg")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "render.py"), pdir, "--thumbnail", props_path,
                        "--out", out], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(r.stderr.strip() or r.stdout.strip())
    preview = os.path.join("work", "thumb", f"preview-{tag}.jpg")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(pdir, out), "-filter_complex",
                    "[0]scale=640:360[big];[0]scale=168:94,pad=640:360:236:133:color=0x202020[small];[big][small]hstack",
                    os.path.join(pdir, preview)], check=True)
    print(json.dumps({"thumbnail": out, "preview": preview, "background": bg_mode, "face": bool(face),
                      "layout": layout, "bytes": os.path.getsize(os.path.join(pdir, out))}))


if __name__ == "__main__":
    main()
