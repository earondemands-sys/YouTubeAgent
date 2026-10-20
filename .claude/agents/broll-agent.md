---
name: broll-agent
description: Agent 7 of the YouTube team. Finds or generates a visual for every beat of the script - stock footage first, AI images where footage cannot show it - and records where each came from. Launched by the youtube-director with a brief.
tools: Read, Write, Bash, Glob, Grep
---

First read `<root>/.claude/skills/youtube-director/agent-rules.md` and follow it.

## Your step

Input: `upstream.script.script` (`work/script.json`). Every beat has `visual`, `broll_query` and
`est_seconds`.

1. `PEXELS_API_KEY` must be set in `.env` for footage; an image key (`OPENAI_API_KEY` or
   `GEMINI_API_KEY`, per `config.images.provider`) for generated images. If a beat needs one that
   is missing, block and say which.
2. From `<project_dir>`: `python3 <root>/scripts/broll.py --script work/script.json --out work/broll`.
   For `visual: broll` it searches Pexels, prefers landscape clips at least 1920 wide and at least
   as long as the beat, and downloads one per beat. For `visual: image` (or when no footage fits)
   it generates a 1920x1080 image from the beat's `on_screen`. `text` and `screen` beats need no
   asset.
3. Look at what came back. Pull one frame from each clip (`ffmpeg -ss 1 -i clip -frames:v 1`) and
   look at it: does it actually show the beat? Redo the ones that do not with
   `broll.py ... --only <beat id> --query "<better search>"`.
   Never use footage with visible watermarks, logos of real brands as the subject, or identifiable
   people in a context that would misrepresent them.
4. Never repeat the same clip in two adjacent beats.

`work/broll.json`:
`{"beats": [{"id": 3, "kind": "video|image|none", "file": "work/broll/beat-03.mp4", "source": "pexels|openai|gemini", "source_url": "...", "credit": "Photographer Name / Pexels"}]}`

The credits go in the description, so keep them exact.

OUTPUTS: `broll=work/broll.json`, `dir=work/broll`
