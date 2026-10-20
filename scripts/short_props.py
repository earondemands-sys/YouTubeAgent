#!/usr/bin/env python3
"""short_props.py - render props for each Short, from the long video's props and work/shorts.json.

    python3 scripts/short_props.py projects/<slug>            # every Short in work/shorts.json
    python3 scripts/short_props.py projects/<slug> --n 2      # just one

A Short is NOT cropped out of out/video.mp4: that file has the long video's captions burned in,
and a 9:16 crop cuts them in half. Instead the same composition renders a time window of the edit
in a vertical layout, with captions sized for it and the Short's own hook text for the first two
seconds. work/shorts.json entries need, in EDITED-video seconds:

    {"n": 1, "start": 132.4, "end": 178.9, "title": "... #shorts", "on_screen": "HOOK TEXT", "crop_x": 0.5}

crop_x is where the subject sits across the 16:9 frame (0 left, 1 right) - the shorts agent looks
at a frame to set it, so the speaker's face is never cropped out.

Writes work/shorts/short-<n>.props.json; render each with scripts/render.py <project> --short <n>.
"""
import argparse, json, os, sys

DROP = {"progress-bar", "letterbox", "lower-third", "title-card", "waveform"}
MAX_SECONDS = 180


def main():
    p = argparse.ArgumentParser()
    p.add_argument("project")
    p.add_argument("--n", type=int)
    a = p.parse_args()
    pdir = os.path.abspath(a.project)
    base = json.load(open(os.path.join(pdir, "work", "render-props.json")))
    shorts = json.load(open(os.path.join(pdir, "work", "shorts.json")))["shorts"]
    fps, total = base["fps"], base["durationInFrames"]
    os.makedirs(os.path.join(pdir, "work", "shorts"), exist_ok=True)
    made = []
    for s in shorts:
        if a.n is not None and s["n"] != a.n:
            continue
        start, end = int(round(s["start"] * fps)), int(round(s["end"] * fps))
        end = min(end, total)
        if end - start <= fps * 3:
            sys.exit(f"short {s['n']}: {s['start']}-{s['end']}s is too short or outside the video")
        if (end - start) / fps > MAX_SECONDS:
            sys.exit(f"short {s['n']}: {(end - start) / fps:.0f}s is over YouTube's {MAX_SECONDS}s Shorts limit")
        props = dict(base)
        props.update(
            width=1080, height=1920, layout="vertical", cropX=float(s.get("crop_x", 0.5)),
            frameRange=[start, end - 1],
            overlays=[o for o in base["overlays"] if o["type"] not in DROP and o["from"] < end and o["from"] + o["dur"] > start],
            hook={"text": s.get("on_screen") or s.get("first_line", ""), "from": start, "dur": 2 * fps} if (s.get("on_screen") or s.get("first_line")) else None,
        )
        # the long video's zooms were placed for 16:9; in a vertical crop they read as jitter
        props["zooms"] = [z for z in base["zooms"] if z["from"] + z["dur"] > start and z["from"] < end] if base["styleId"] in ("hormozi", "fast-hype") else []
        out = os.path.join(pdir, "work", "shorts", f"short-{s['n']}.props.json")
        json.dump(props, open(out, "w"), ensure_ascii=False)
        made.append({"n": s["n"], "props": os.path.relpath(out, pdir), "frames": [start, end - 1],
                     "seconds": round((end - start) / fps, 2)})
    if not made:
        sys.exit("no shorts matched")
    print(json.dumps({"shorts": made}))


if __name__ == "__main__":
    main()
