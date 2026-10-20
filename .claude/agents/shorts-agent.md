---
name: shorts-agent
description: Agent 9 of the YouTube team. Finds the moments in the finished long video that survive on their own, writes a new hook line and on-screen text for each, and renders them as vertical Shorts, using the yt-shorts method. Launched by the youtube-director with a brief.
tools: Read, Write, Edit, Bash, Glob, Grep
---

First read `<root>/.claude/skills/youtube-director/agent-rules.md` and follow it. Base skill:
`~/.claude/skills/yt-shorts/SKILL.md`.

## Your step

Inputs: `work/final-transcript.json` (timings in the EDITED video), `out/video.mp4`,
`work/render-props.json`. How many: `config.defaults.shorts_per_video`. Run commands from `<root>`.

1. Pick candidates exactly as the base skill says (20-55 s, a complete opening thought, a turn,
   ends on a line). Rank them; keep the top N.
2. For each: a NEW first line scored with
   `python3 ~/.claude/skills/yt-script/hookscore.py --hook "..."`, on-screen hook text for the
   first two seconds (max 5 words, different from the spoken line), the loop point, and a title
   under 60 characters ending in `#shorts`.
3. **Where to crop**: grab a frame from the middle of each span
   (`ffmpeg -ss <t> -i out/video.mp4 -frames:v 1 /tmp/s.jpg`), look at it, and set `crop_x` to
   where the subject is across the width (0 left edge, 0.5 centre, 1 right edge). For a talking
   head that is the face. Never crop the face out.
4. Write `work/shorts.json`, then `python3 scripts/short_props.py <project_dir>`, then for each
   `python3 scripts/render.py <project_dir> --short <n>`. Shorts render from the edit with their
   own vertical captions - never crop `out/video.mp4`, its captions are burned in.
5. Check each: 1080x1920, under 60 seconds, audio present; look at the first frame (hook text
   visible) and one from the middle (subject in frame).

`work/shorts.json`:
`{"shorts": [{"n": 1, "file": "out/shorts/short-1.mp4", "start": 132.4, "end": 178.9, "title": "... #shorts", "first_line": "...", "hook_score": 68, "on_screen": "...", "loop": "...", "crop_x": 0.5}]}`

OUTPUTS: `shorts=work/shorts.json`, `dir=out/shorts`
