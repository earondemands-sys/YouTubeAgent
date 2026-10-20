#!/usr/bin/env python3
"""make_edl.py - turn deadair.py's cut list into the KEEP list the remotion agent plays.

    python3 scripts/make_edl.py projects/<slug> [--floor 0.45]

Reads work/transcript.srt and the source from state.json, runs the yt-edit skill's deadair.py,
merges overlapping cuts, drops slivers too short to keep, and writes:

    work/edl.json         {"source", "duration", "keep": [{start, end}], "cuts": [...], "removed", "out"}
    work/edit-report.md   what the user sees at the cuts gate

Long DEAD cuts (over 4s) are listed separately as `review`: a silent stretch can be a demo on
screen, not dead air. The editor agent looks at those frames before the gate.
"""
import json, os, subprocess, sys

DEADAIR = os.path.expanduser("~/.claude/skills/yt-edit/deadair.py")
MIN_KEEP = 0.25   # a keep shorter than this is a flash frame, not content
REVIEW_GAP = 4.0


def mmss(t):
    t = max(0, t)
    return f"{int(t // 60)}:{t % 60:05.2f}"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(1)
    pdir = os.path.abspath(args[0])
    floor = sys.argv[sys.argv.index("--floor") + 1] if "--floor" in sys.argv else "0.45"
    state = json.load(open(os.path.join(pdir, "state.json")))
    source = state["inputs"]["source"]
    srt = os.path.join(pdir, "work", "transcript.srt")
    tjson = os.path.join(pdir, "work", "transcript.json")

    r = subprocess.run([sys.executable, DEADAIR, srt, "--floor", floor, "--json"], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"deadair.py failed: {r.stdout[-400:]}{r.stderr[-400:]}")
    d = json.loads(r.stdout)

    duration = json.load(open(tjson)).get("duration") if os.path.exists(tjson) else None
    duration = duration or d["duration"]
    cuts = sorted(d["cuts"], key=lambda c: c["start"])
    # The tail after the last word is dead air too.
    last_word_end = d["duration"]
    if duration - last_word_end > float(floor):
        cuts.append({"kind": "DEAD", "start": round(last_word_end + float(floor) / 2, 3), "end": duration,
                     "why": "silence after the last word"})

    merged = []
    for c in cuts:
        if merged and c["start"] <= merged[-1]["end"] + 0.05:
            m = merged[-1]
            m["end"] = max(m["end"], c["end"])
            if c["kind"] not in m["kind"].split("+"):
                m["kind"] += "+" + c["kind"]
            m["why"] = f"{m['why']}; {c['why']}"
        else:
            merged.append(dict(c))

    keep, t = [], 0.0
    for c in merged:
        if c["start"] - t >= MIN_KEEP:
            keep.append({"start": round(t, 3), "end": round(c["start"], 3)})
        t = max(t, c["end"])
    if duration - t >= MIN_KEEP:
        keep.append({"start": round(t, 3), "end": round(duration, 3)})
    out_dur = sum(k["end"] - k["start"] for k in keep)
    removed = duration - out_dur
    review = [c for c in merged if c["kind"].startswith("DEAD") and c["end"] - c["start"] > REVIEW_GAP]

    edl = {"source": source, "duration": duration, "floor": float(floor), "keep": keep, "cuts": merged,
           "review": review, "removed": round(removed, 3), "out": round(out_dur, 3)}
    json.dump(edl, open(os.path.join(pdir, "work", "edl.json"), "w"), indent=1, ensure_ascii=False)

    biggest = sorted(merged, key=lambda c: c["start"] - c["end"])[:5]
    lines = [
        f"# Cut list - {state['slug']}",
        "",
        f"- Original: **{mmss(duration)}**",
        f"- Removed: **{removed:.1f}s** ({removed / duration * 100:.0f}%) in {len(merged)} cuts",
        f"- New runtime: **{mmss(out_dur)}**",
        "",
        "## Five largest cuts",
        "",
        "| At | Length | Kind | What |",
        "|---|---|---|---|",
        *[f"| {mmss(c['start'])} | {c['end'] - c['start']:.1f}s | {c['kind']} | {c['why'][:70]} |" for c in biggest],
    ]
    if review:
        lines += ["", "## Check these before approving",
                  "Silences over 4s. If something is happening on screen (a demo), they should stay.", ""]
        lines += [f"- {mmss(c['start'])} -> {mmss(c['end'])} ({c['end'] - c['start']:.1f}s)" for c in review]
    lines += ["", "The percentage is of speech gaps. Long silent demos make it look bigger than it is."]
    open(os.path.join(pdir, "work", "edit-report.md"), "w").write("\n".join(lines) + "\n")
    print(json.dumps({"keep": len(keep), "cuts": len(merged), "removed": round(removed, 2),
                      "out": round(out_dur, 2), "review": len(review)}))


if __name__ == "__main__":
    main()
