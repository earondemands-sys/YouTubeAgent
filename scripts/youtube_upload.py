#!/usr/bin/env python3
"""youtube_upload.py - upload a video (or a Short) with its metadata and thumbnail.

    .venv/bin/python scripts/youtube_upload.py --video out/video.mp4 --meta work/metadata.json \\
        --thumbnail out/thumbnail.jpg --privacy private --out work/publish.json
    ... --privacy public --publish-at 2026-10-24T18:00:00+05:30     # scheduled (goes up private)
    ... --short 1 --video out/shorts/short-1.mp4 --title "... #shorts" --meta work/metadata.json
    .venv/bin/python scripts/youtube_upload.py --quota               # today's quota, used/left
    ... --dry-run                                                    # build the request, send nothing

Run from the project folder (paths are relative to it) or pass absolute paths.

Quota: a project gets 10,000 units a day, reset at midnight Pacific time. An upload is 1,600 and a
thumbnail 50. This script keeps its own ledger in secrets/quota.json so the publish agent can plan
around it; the ledger only knows about uploads made through this script.
"""
import argparse, datetime as dt, json, os, random, sys, time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "secrets", "quota.json")
DAILY, UPLOAD_COST, THUMB_COST = 10_000, 1_600, 50
RETRY_STATUS = {500, 502, 503, 504}


def pacific_day():
    return dt.datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()


def ledger():
    try:
        d = json.load(open(LEDGER))
    except (FileNotFoundError, json.JSONDecodeError):
        d = {}
    if d.get("date") != pacific_day():
        d = {"date": pacific_day(), "used": 0}
    return d


def spend(units):
    d = ledger()
    d["used"] += units
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    json.dump(d, open(LEDGER, "w"))
    return d


def to_utc(ts):
    t = dt.datetime.fromisoformat(ts)
    if t.tzinfo is None:
        sys.exit(f"--publish-at needs a timezone offset, e.g. 2026-10-24T18:00:00+05:30 (got {ts})")
    if t <= dt.datetime.now(dt.timezone.utc):
        sys.exit("--publish-at is in the past")
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def build_body(a, meta):
    title = a.title or meta.get("title", "")
    if a.short:
        desc = a.description if a.description is not None else short_description(meta)
    else:
        desc = meta.get("description", "")
    snippet = {"title": title[:100], "description": desc[:5000], "tags": meta.get("tags", []),
               "categoryId": str(meta.get("category_id", "22"))}
    lang = meta.get("default_language")
    if lang:
        snippet["defaultLanguage"] = lang
        snippet["defaultAudioLanguage"] = lang
    status = {"privacyStatus": a.privacy, "selfDeclaredMadeForKids": bool(meta.get("made_for_kids", False)),
              "containsSyntheticMedia": bool(a.synthetic_media)}
    if a.publish_at:
        status["privacyStatus"] = "private"   # YouTube only schedules private videos
        status["publishAt"] = to_utc(a.publish_at)
    return {"snippet": snippet, "status": status}


def short_description(meta):
    first = (meta.get("description") or "").split("\n\n")[0]
    return f"{first}\n\n#shorts".strip()


def upload(yt, path, body):
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    from httplib2 import HttpLib2Error  # DNS / socket failures surface as these, not as OSError
    media = MediaFileUpload(path, chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp, tries = None, 0
    while resp is None:
        try:
            status, resp = req.next_chunk()
            if status:
                print(f"  uploaded {int(status.progress() * 100)}%", file=sys.stderr)
        except HttpError as e:
            if e.resp.status not in RETRY_STATUS:
                raise
            tries += 1
            if tries > 8:
                raise
            time.sleep(min(60, 2 ** tries + random.random()))
        except (ConnectionError, TimeoutError, OSError, HttpLib2Error):
            # a home connection can drop for minutes; keep the resumable session alive that long
            tries += 1
            if tries > 20:
                raise
            time.sleep(min(60, 2 ** tries + random.random()))
    return resp


def set_thumbnail(yt, video_id, path):
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    try:
        yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(path, mimetype=mime)).execute()
        return True, None
    except HttpError as e:
        # 403 here is almost always an unverified channel: custom thumbnails need phone verification.
        return False, f"HTTP {e.resp.status}: {e.reason}"


def record(out_path, slot, entry):
    data = {}
    if out_path and os.path.exists(out_path):
        data = json.load(open(out_path))
    if slot == "long":
        data["long"] = entry
    else:
        shorts = [s for s in data.get("shorts", []) if s.get("n") != entry["n"]]
        data["shorts"] = sorted(shorts + [entry], key=lambda s: s["n"])
    data["quota_used"] = data.get("quota_used", 0) + entry.get("quota", 0)
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        json.dump(data, open(out_path, "w"), indent=2, ensure_ascii=False)
    return data


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--video")
    p.add_argument("--meta")
    p.add_argument("--thumbnail")
    p.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    p.add_argument("--publish-at")
    p.add_argument("--synthetic-media", action="store_true")
    p.add_argument("--short", type=int, metavar="N", help="this is Short number N")
    p.add_argument("--title")
    p.add_argument("--description")
    p.add_argument("--out")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--quota", action="store_true")
    a = p.parse_args()

    if a.quota:
        d = ledger()
        print(json.dumps({"date_pacific": d["date"], "used": d["used"], "left": DAILY - d["used"],
                          "uploads_left": (DAILY - d["used"]) // UPLOAD_COST}))
        return
    if not a.video or not a.meta:
        p.error("--video and --meta are required")
    for f in (a.video, a.meta) + ((a.thumbnail,) if a.thumbnail else ()):
        if not os.path.exists(f):
            sys.exit(f"not found: {f}")
    meta = json.load(open(a.meta))
    body = build_body(a, meta)
    cost = UPLOAD_COST + (THUMB_COST if a.thumbnail else 0)
    left = DAILY - ledger()["used"]
    if not a.dry_run and cost > left:
        sys.exit(f"quota: this needs {cost} units, {left} left today (resets midnight Pacific). "
                 "Schedule it for tomorrow instead.")

    slot = "long" if a.short is None else "short"
    if a.dry_run:
        vid = f"DRYRUN-{'long' if a.short is None else 'short-' + str(a.short)}"
        entry = {"id": vid, "url": f"https://youtu.be/{vid}", "privacy": body["status"]["privacyStatus"],
                 "publish_at": body["status"].get("publishAt"), "thumbnail_set": bool(a.thumbnail),
                 "dry_run": True, "request": body, "quota": 0}
    else:
        from youtube_auth import youtube
        yt = youtube()
        resp = upload(yt, a.video, body)
        spend(UPLOAD_COST)
        vid = resp["id"]
        thumb_ok, thumb_err = (None, None)
        if a.thumbnail:
            thumb_ok, thumb_err = set_thumbnail(yt, vid, a.thumbnail)
            if thumb_ok:
                spend(THUMB_COST)
        got = resp.get("status", {})
        entry = {"id": vid, "url": f"https://youtu.be/{vid}", "privacy": got.get("privacyStatus"),
                 "requested_privacy": a.privacy, "publish_at": got.get("publishAt"),
                 "upload_status": got.get("uploadStatus"), "thumbnail_set": thumb_ok,
                 "thumbnail_error": thumb_err, "quota": UPLOAD_COST + (THUMB_COST if thumb_ok else 0)}
        if a.privacy != "private" and got.get("privacyStatus") == "private" and not a.publish_at:
            entry["note"] = ("YouTube kept this private. Uploads from an API project that has not passed "
                             "YouTube's audit are locked private - see docs/SETUP-YOUTUBE.md, step 6.")
    if a.short is not None:
        entry["n"] = a.short
        entry["title"] = body["snippet"]["title"]
    record(a.out, slot, entry)
    print(json.dumps(entry, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
