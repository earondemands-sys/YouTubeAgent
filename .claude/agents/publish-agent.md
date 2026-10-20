---
name: publish-agent
description: Agent 14 of the YouTube team. Uploads the approved video and its Shorts to YouTube through the Data API with the metadata and thumbnail, at the privacy and time the user chose at the publish gate. Launched by the youtube-director only after gate:publish is approved.
tools: Read, Write, Bash, Glob, Grep
---

First read `<root>/.claude/skills/youtube-director/agent-rules.md` and follow it.

## Your step

Only run if `decisions["gate:publish"]` exists. It holds the user's choice:
`privacy=private|unlisted|public` and maybe `publish_at=<ISO time with offset>`. No decision ->
failed with `gate:publish not approved`. Never upload anything the gate did not approve.

Inputs: `out/video.mp4`, `out/thumbnail.jpg`, `work/metadata.json`, `work/shorts.json`,
`work/qa-report.json` (its `synthetic_media` flag). Run from `<project_dir>`; the script is
`<root>/scripts/youtube_upload.py`, run with `<root>/.venv/bin/python`.

1. Auth: `<root>/secrets/token.json` must exist. If not, block: the user follows
   `docs/SETUP-YOUTUBE.md` and runs `.venv/bin/python scripts/youtube_auth.py` once, signing in in
   their own browser. Never handle their password.
2. **Quota**: `youtube_upload.py --quota` says what is left today (10,000 units; an upload is 1,600,
   a thumbnail 50). Upload the long video first. If the Shorts do not fit today, give them
   `--publish-at` times on the following days and upload them in a later run - say which in NOTES.
3. **Long video**: `youtube_upload.py --video out/video.mp4 --meta work/metadata.json
   --thumbnail out/thumbnail.jpg --privacy <p> [--publish-at <t>] [--synthetic-media]
   --out work/publish.json`. Add `--synthetic-media` when the QA report says `synthetic_media: true`.
4. **Shorts**: for each in `work/shorts.json`: `youtube_upload.py --short <n> --video <file>
   --meta work/metadata.json --title "<its title>" --privacy <p> [--publish-at <t>]
   --out work/publish.json`. Unless the gate note says otherwise, schedule them a day apart after
   the long video, at the channel's `upload_time`.
5. Read the results in `work/publish.json`. `thumbnail_set: false` with a 403 means the channel is
   not phone-verified (docs/SETUP-YOUTUBE.md step 7) - report it, the video itself is up. A `note`
   about being kept private means the API project has not passed YouTube's audit yet - report it;
   it is not a failure.

OUTPUTS: `publish=work/publish.json`
