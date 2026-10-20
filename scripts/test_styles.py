#!/usr/bin/env python3
"""test_styles.py - render a few seconds of every style in config/styles.json, so none of them rots.

    python3 scripts/test_styles.py            # needs tests/sandbox projects (scripts/test_e2e.py makes them)

For each style: rebuild props for the matching sandbox project (recorded styles on the recorded
clip, faceless-only styles on the faceless one), render 4 seconds from the middle, check the file,
and save one frame to tests/sandbox/styles/<id>.jpg. Ends with a contact sheet of all ten.
"""
import json, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SANDBOX = os.path.join(ROOT, "tests", "sandbox")
OUT = os.path.join(SANDBOX, "styles")


def run(cmd, env):
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=ROOT)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout)[-1200:])
    return r.stdout


def main():
    styles = json.load(open(os.path.join(ROOT, "config", "styles.json")))["styles"]
    env = dict(os.environ, YTA_CONFIG=os.path.join(SANDBOX, "channel.json"), YTA_PROJECTS=os.path.join(SANDBOX, "projects"))
    os.makedirs(OUT, exist_ok=True)
    results = []
    for s in styles:
        mode = "recorded" if "recorded" in s["for"] else "faceless"
        src = os.path.join(SANDBOX, "projects", "e2e-recorded" if mode == "recorded" else "e2e-faceless")
        if not os.path.exists(src):
            sys.exit(f"missing {src}: run scripts/test_e2e.py first")
        proj = os.path.join(SANDBOX, "projects", f"style-{s['id']}")
        shutil.rmtree(proj, ignore_errors=True)
        shutil.copytree(src, proj, symlinks=True, ignore=shutil.ignore_patterns("out", "shorts", "thumb"))
        st = json.load(open(os.path.join(proj, "state.json")))
        st["slug"] = f"style-{s['id']}"
        st["inputs"]["style"] = s["id"]
        json.dump(st, open(os.path.join(proj, "state.json"), "w"))
        try:
            info = json.loads(run([sys.executable, "scripts/render_props.py", proj], env))
            mid = info["frames"] // 2
            run([sys.executable, "scripts/render.py", proj, "--frames", f"{mid}-{mid + 119}", "--out", "out/clip.mp4"], env)
            clip = os.path.join(proj, "out", "clip.mp4")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "2", "-i", clip, "-frames:v", "1",
                            "-vf", "scale=480:-1", os.path.join(OUT, f"{s['id']}.jpg")], check=True)
            results.append((s["id"], "ok", f"{info['captions']} captions, {info['zooms']} zooms, {info['overlays']} overlays"))
        except Exception as e:  # keep going: one broken style should not hide the state of the others
            results.append((s["id"], "FAIL", str(e).splitlines()[-1] if str(e) else "error"))
        print(f"  {results[-1][1]:<4} {s['id']:<20} {results[-1][2]}", flush=True)

    frames = [os.path.join(OUT, f"{r[0]}.jpg") for r in results if r[1] == "ok"]
    if len(frames) == 10:
        inputs = sum((["-i", f] for f in frames), [])
        grid = "".join(f"[{i}]" for i in range(10)) + "xstack=inputs=10:layout=" + "|".join(
            f"{(i % 5) * 480}_{(i // 5) * 270}" for i in range(10))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", grid,
                        os.path.join(OUT, "contact-sheet.jpg")], check=True)
    failed = [r for r in results if r[1] != "ok"]
    print(f"\n{len(results) - len(failed)}/{len(results)} styles render")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
