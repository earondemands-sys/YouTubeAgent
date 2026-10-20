#!/usr/bin/env python3
"""instagram.py - post Reels, and read and answer what happens to them.

    python3 scripts/instagram.py check   <project_dir>                      # Reels limits, nothing sent
    python3 scripts/instagram.py publish <project_dir> --reel 1 --out work/ig-publish.json
    ... --reel 2 --at 2026-10-25T18:00:00+05:30    # queued: posted by `flush` once that time passes
    ... --dry-run                                  # check and build the request, send nothing
    python3 scripts/instagram.py flush   <project_dir> | --all              # post queued Reels that are due
    python3 scripts/instagram.py limit                                     # posts used in the last 24 h
    python3 scripts/instagram.py media    [--limit 25]                     # your recent posts
    python3 scripts/instagram.py comments <media_id> [--out f.json]
    python3 scripts/instagram.py insights <media_id>
    python3 scripts/instagram.py dms      [--hours 24]                     # recent DM threads

Needs the sign-in from scripts/instagram_auth.py. A Reel is published in four calls: create a
container, upload the file to it (resumable upload, so no public video URL is needed), wait for
Instagram to process it, publish. Instagram has no private or scheduled posts through the API:
whatever is published is public at once, which is why `--at` keeps a local queue instead.

reels.json (written by the reels agent):
  {"reels": [{"n": 1, "file": "out/shorts/short-1.mp4", "caption": "...", "thumb_offset_ms": 800,
              "share_to_feed": true}]}
"""
import argparse, datetime as dt, glob, json, os, sys, time, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from instagram_auth import IGError, api_version, call, http, token  # noqa: E402

PROJECTS = os.environ.get("YTA_PROJECTS") or os.path.join(ROOT, "projects")
POLL_EVERY, POLL_FOR = 10, 15 * 60


def now():
    return dt.datetime.now(dt.timezone.utc)


def parse_at(ts):
    t = dt.datetime.fromisoformat(ts)
    if t.tzinfo is None:
        sys.exit(f"--at needs a timezone offset, e.g. 2026-10-25T18:00:00+05:30 (got {ts})")
    return t


def reels_of(pdir):
    path = os.path.join(pdir, "work", "reels.json")
    if not os.path.exists(path):
        sys.exit(f"not found: {path} (the reels step writes it)")
    return {r["n"]: r for r in json.load(open(path)).get("reels", [])}


def preflight(pdir, reel=None):
    """Instagram's limits for every Reel (or one), using QA's checks. Returns the check rows."""
    from qa_check import Report, check_reels
    rep = Report()
    check_reels(rep, pdir, os.path.join(pdir, "work", "reels.json"))
    if reel is not None:
        rep.checks = [c for c in rep.checks if c["name"] in (f"reel {reel}", "reels")]
    return rep


def record(out_path, entry):
    data = json.load(open(out_path)) if out_path and os.path.exists(out_path) else {}
    reels = [r for r in data.get("reels", []) if r.get("n") != entry["n"]]
    data["reels"] = sorted(reels + [entry], key=lambda r: r["n"])
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        json.dump(data, open(out_path, "w"), indent=2, ensure_ascii=False)
    return data


def publish_limit():
    _, uid = token()
    r = call("GET", f"{uid}/content_publishing_limit", {"fields": "quota_usage,config"})
    row = (r.get("data") or [{}])[0]
    total = (row.get("config") or {}).get("quota_total", 100)
    return {"used_24h": row.get("quota_usage", 0), "limit_24h": total, "left": total - row.get("quota_usage", 0)}


def upload(uri, path):
    tok, _ = token()
    size = os.path.getsize(path)
    for attempt in range(5):
        try:
            with open(path, "rb") as f:
                return http("POST", uri, body=f, timeout=900, headers={
                    "Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size),
                    "Content-Length": str(size), "Content-Type": "application/octet-stream"})
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            if attempt == 4:
                raise
            print(f"  upload interrupted ({e}); retrying", file=sys.stderr)
            time.sleep(min(60, 5 * 2 ** attempt))
        except IGError as e:
            if attempt == 4 or e.status < 500:
                raise
            time.sleep(min(60, 5 * 2 ** attempt))


def wait_ready(container):
    t0 = time.time()
    while time.time() - t0 < POLL_FOR:
        r = call("GET", container, {"fields": "status_code,status"})
        code = r.get("status_code")
        if code in ("FINISHED", "PUBLISHED"):
            return
        if code in ("ERROR", "EXPIRED"):
            sys.exit(f"Instagram could not process the video: {r.get('status') or code}")
        print(f"  processing on Instagram ({code or 'waiting'})", file=sys.stderr)
        time.sleep(POLL_EVERY)
    sys.exit(f"Instagram was still processing after {POLL_FOR // 60} minutes - run publish again later")


def post_reel(pdir, reel):
    _, uid = token()
    f = os.path.join(pdir, reel["file"])
    data = {"media_type": "REELS", "upload_type": "resumable", "caption": reel["caption"],
            "share_to_feed": "true" if reel.get("share_to_feed", True) else "false"}
    if reel.get("thumb_offset_ms") is not None:
        data["thumb_offset"] = str(int(reel["thumb_offset_ms"]))
    c = call("POST", f"{uid}/media", data=data)
    container = c["id"]
    uri = c.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{api_version()}/{container}"
    print(f"  uploading {reel['file']} ({os.path.getsize(f) / 1048576:.1f}MB)", file=sys.stderr)
    upload(uri, f)
    wait_ready(container)
    for attempt in range(6):
        try:
            media = call("POST", f"{uid}/media_publish", data={"creation_id": container})["id"]
            break
        except IGError as e:
            if attempt == 5 or e.code not in (9007, 2207027):  # "media not ready yet"
                raise
            time.sleep(10)
    info = call("GET", media, {"fields": "permalink,shortcode,timestamp"})
    return {"id": media, "container": container, "permalink": info.get("permalink"),
            "published_at": info.get("timestamp") or now().isoformat()}


def cmd_check(a):
    rep = preflight(os.path.abspath(a.project_dir))
    print(json.dumps({"verdict": rep.verdict(), "checks": rep.checks}, indent=2, ensure_ascii=False))
    if rep.verdict() == "FAIL":
        sys.exit(1)


def publish_one(pdir, n, at, out, dry_run=False):
    reels = reels_of(pdir)
    if n not in reels:
        sys.exit(f"reel {n} is not in work/reels.json (have: {sorted(reels)})")
    reel = reels[n]
    rep = preflight(pdir, n)
    fails = [c for c in rep.checks if c["status"] == "FAIL"]
    if fails:
        sys.exit(f"reel {n} breaks Instagram's limits, not sent: " + "; ".join(c["detail"] for c in fails))
    base = {"n": n, "file": reel["file"], "caption_start": reel["caption"][:80]}
    if at and parse_at(at) > now():
        entry = {**base, "status": "queued", "at": parse_at(at).isoformat()}
    elif dry_run:
        entry = {**base, "status": "dry-run", "request": {"media_type": "REELS", "upload_type": "resumable",
                 "share_to_feed": reel.get("share_to_feed", True), "thumb_offset": reel.get("thumb_offset_ms"),
                 "caption_chars": len(reel["caption"])}}
    else:
        lim = publish_limit()
        if lim["left"] <= 0:
            sys.exit(f"Instagram's limit: {lim['used_24h']}/{lim['limit_24h']} posts in the last 24 h. Queue it with --at.")
        entry = {**base, "status": "published", **post_reel(pdir, reel)}
    record(out, entry)
    print(json.dumps(entry, indent=2, ensure_ascii=False))
    return entry


def cmd_publish(a):
    pdir = os.path.abspath(a.project_dir)
    out = a.out if os.path.isabs(a.out) else os.path.join(pdir, a.out)
    publish_one(pdir, a.reel, a.at, out, a.dry_run)


def cmd_flush(a):
    dirs = sorted(glob.glob(os.path.join(PROJECTS, "*"))) if a.all else [os.path.abspath(a.project_dir)]
    posted, waiting, failed = [], [], []
    for pdir in dirs:
        out = os.path.join(pdir, "work", "ig-publish.json")
        if not os.path.exists(out):
            continue
        for r in json.load(open(out)).get("reels", []):
            if r.get("status") != "queued":
                continue
            slug = os.path.basename(pdir)
            if parse_at(r["at"]) > now():
                waiting.append({"project": slug, "reel": r["n"], "at": r["at"]})
                continue
            try:
                e = publish_one(pdir, r["n"], None, out)
                posted.append({"project": slug, "reel": r["n"], "permalink": e.get("permalink")})
            except (SystemExit, IGError) as e:
                failed.append({"project": slug, "reel": r["n"], "reason": str(e)})
    print(json.dumps({"posted": posted, "waiting": waiting, "failed": failed}, indent=2, ensure_ascii=False))


def cmd_limit(a):
    print(json.dumps(publish_limit()))


def recent_media(limit=25):
    _, uid = token()
    r = call("GET", f"{uid}/media", {"fields": "id,caption,media_type,media_product_type,permalink,timestamp,comments_count,like_count",
                                     "limit": min(limit, 100)})
    return r.get("data", [])


def comments_of(media_id, limit=200):
    out, params = [], {"fields": "id,text,timestamp,username,like_count,hidden,replies{id,text,username,timestamp}", "limit": 50}
    r = call("GET", f"{media_id}/comments", params)
    while True:
        out += r.get("data", [])
        nxt = (r.get("paging") or {}).get("cursors", {}).get("after")
        if len(out) >= limit or not nxt or not (r.get("paging") or {}).get("next"):
            return out[:limit]
        r = call("GET", f"{media_id}/comments", {**params, "after": nxt})


def reply(comment_id, text):
    return call("POST", f"{comment_id}/replies", data={"message": text})["id"]


def hide(comment_id):
    return call("POST", comment_id, data={"hide": "true"}).get("success", True)


def conversations(hours=24):
    """DM threads updated in the last `hours`, newest first, each with its recent messages."""
    cutoff = now() - dt.timedelta(hours=hours)
    out, params = [], {"platform": "instagram", "fields": "id,updated_time", "limit": 25}
    r = call("GET", "me/conversations", params)
    while True:
        for c in r.get("data", []):
            if dt.datetime.fromisoformat(c["updated_time"].replace("+0000", "+00:00")) < cutoff:
                return out
            out.append({**c, "messages": messages_of(c["id"])})
        after = (r.get("paging") or {}).get("cursors", {}).get("after")
        if not after or not (r.get("paging") or {}).get("next"):
            return out
        r = call("GET", "me/conversations", {**params, "after": after})


def messages_of(conversation_id, limit=10):
    """The newest messages of one thread, newest first. Instagram returns details for the latest 20."""
    r = call("GET", conversation_id, {"fields": f"messages.limit({limit}){{id,created_time,from,to,message}}"})
    msgs = (r.get("messages") or {}).get("data", [])
    for i, m in enumerate(msgs):
        if "from" not in m:  # some API versions only list ids here
            msgs[i] = call("GET", m["id"], {"fields": "id,created_time,from,to,message"})
    return msgs


def send_dm(recipient_id, text):
    _, uid = token()
    r = call("POST", f"{uid}/messages", data={"recipient": json.dumps({"id": recipient_id}),
                                              "message": json.dumps({"text": text})})
    return r.get("message_id") or r.get("id")


def insights(media_id):
    metrics = ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions",
               "ig_reels_avg_watch_time", "ig_reels_video_view_total_time"]
    try:
        r = call("GET", f"{media_id}/insights", {"metric": ",".join(metrics)})
    except IGError:
        # Meta renames metrics now and then; fall back to the ones every post type has
        r = call("GET", f"{media_id}/insights", {"metric": "reach,likes,comments,shares,saved"})
    return {m["name"]: (m.get("values") or [{}])[0].get("value", m.get("total_value", {}).get("value"))
            for m in r.get("data", [])}


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("check")
    s.add_argument("project_dir")
    s.set_defaults(fn=cmd_check)
    s = sub.add_parser("publish")
    s.add_argument("project_dir")
    s.add_argument("--reel", type=int, required=True)
    s.add_argument("--at", help="ISO time with offset; in the future = queue it for flush")
    s.add_argument("--out", default="work/ig-publish.json")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_publish)
    s = sub.add_parser("flush")
    s.add_argument("project_dir", nargs="?")
    s.add_argument("--all", action="store_true", help="every project in projects/")
    s.set_defaults(fn=cmd_flush)
    sub.add_parser("limit").set_defaults(fn=cmd_limit)
    s = sub.add_parser("media")
    s.add_argument("--limit", type=int, default=25)
    s.set_defaults(fn=lambda a: print(json.dumps(recent_media(a.limit), indent=2, ensure_ascii=False)))
    s = sub.add_parser("comments")
    s.add_argument("media_id")
    s.add_argument("--out")
    s.set_defaults(fn=lambda a: dump(comments_of(a.media_id), a.out))
    s = sub.add_parser("dms")
    s.add_argument("--hours", type=float, default=24)
    s.set_defaults(fn=lambda a: print(json.dumps(conversations(a.hours), indent=2, ensure_ascii=False)))
    s = sub.add_parser("insights")
    s.add_argument("media_id")
    s.set_defaults(fn=lambda a: print(json.dumps(insights(a.media_id), indent=2)))
    a = p.parse_args()
    if a.cmd == "flush" and not (a.all or a.project_dir):
        p.error("flush needs a project folder or --all")
    try:
        a.fn(a)
    except IGError as e:
        sys.exit(str(e))


def dump(obj, out):
    if out:
        json.dump(obj, open(out, "w"), indent=1, ensure_ascii=False)
        print(json.dumps({"out": out, "count": len(obj)}))
    else:
        print(json.dumps(obj, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
