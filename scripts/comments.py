#!/usr/bin/env python3
"""comments.py - answer the people who comment on your videos, on YouTube and Instagram.

    .venv/bin/python scripts/comments.py inbox [--platform all|youtube|instagram] [--days 14]
    .venv/bin/python scripts/comments.py post  [--dry-run] [--max 25] [--keys yt:abc,ig:123]
    .venv/bin/python scripts/comments.py ledger                      # what has been answered so far

`inbox` collects the comments that still need you: not yours, not already answered by you, not
handled in an earlier run. It writes engage/inbox.json. The engage agent reads that, triages it the
yt-comment way and writes engage/drafts.json:

  {"items": [{"key": "yt:Ugx...", "action": "reply|hide|skip", "text": "...", "pile": "question"}]}

`post` sends the drafts. It only acts on keys that are in the inbox, so a draft can never point a
reply somewhere else. Replies with links are refused. Every handled key goes into
engage/ledger.json, so nobody is answered twice and skipped comments are not triaged again.

Costs: a YouTube reply or hold is 50 quota units (shared with uploads, see youtube_upload.py).
Instagram has no unit cost but rate-limits bursts; replies are spaced out (engage.delay_seconds).
"hide" holds a YouTube comment for review in Studio, and hides an Instagram one (both reversible).
"""
import argparse, datetime as dt, glob, json, os, random, re, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.environ.get("YTA_CONFIG") or os.path.join(ROOT, "config", "channel.json")
PROJECTS = os.environ.get("YTA_PROJECTS") or os.path.join(ROOT, "projects")
ENGAGE = os.environ.get("YTA_ENGAGE") or os.path.join(ROOT, "engage")
INBOX, DRAFTS, LEDGER = (os.path.join(ENGAGE, f) for f in ("inbox.json", "drafts.json", "ledger.json"))
YT_ACTION_COST = 50
MAX_REPLY = 500
LINK = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(com|in|net|org|io|ly|me|link)\b", re.I)


def cfg():
    try:
        return json.load(open(CONFIG)).get("engage", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def read(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


def when(ts):
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00").replace("+0000", "+00:00"))


def project_index():
    """video/media id -> (slug, transcript path), so the agent can answer from what was said."""
    idx = {}
    for pdir in glob.glob(os.path.join(PROJECTS, "*")):
        slug = os.path.basename(pdir)
        srt = os.path.join(pdir, "work", "final-transcript.srt")
        srt = srt if os.path.exists(srt) else None
        yt = read(os.path.join(pdir, "work", "publish.json"), {})
        for v in [yt.get("long") or {}] + yt.get("shorts", []):
            if v.get("id"):
                idx[v["id"]] = (slug, srt)
        for r in read(os.path.join(pdir, "work", "ig-publish.json"), {}).get("reels", []):
            if r.get("id"):
                idx[r["id"]] = (slug, srt)
    return idx


# ---------------------------------------------------------------- YouTube

def yt_inbox(cutoff, done, idx):
    from youtube_auth import youtube
    yt = youtube()
    me = yt.channels().list(part="id", mine=True).execute()["items"][0]["id"]
    items, token = [], None
    while True:
        r = yt.commentThreads().list(part="snippet,replies", allThreadsRelatedToChannelId=me, order="time",
                                     maxResults=100, textFormat="plainText", pageToken=token).execute()
        older = False
        for t in r.get("items", []):
            top = t["snippet"]["topLevelComment"]
            s = top["snippet"]
            if when(s["publishedAt"]) < cutoff:
                older = True
                continue
            key = f"yt:{top['id']}"
            mine = (s.get("authorChannelId") or {}).get("value") == me
            answered = any((c["snippet"].get("authorChannelId") or {}).get("value") == me
                           for c in (t.get("replies") or {}).get("comments", []))
            if mine or answered or key in done or not t["snippet"].get("canReply", True):
                continue
            vid = s.get("videoId") or t["snippet"].get("videoId")
            slug, srt = idx.get(vid, (None, None))
            items.append({"key": key, "platform": "youtube", "comment_id": top["id"], "video_id": vid,
                          "author": s.get("authorDisplayName"), "text": s.get("textOriginal") or s.get("textDisplay"),
                          "likes": s.get("likeCount", 0), "published": s["publishedAt"],
                          "project": slug, "transcript": srt})
        token = r.get("nextPageToken")
        if older or not token:
            break
    titles = {}
    ids = sorted({i["video_id"] for i in items if i["video_id"]})
    for k in range(0, len(ids), 50):
        for v in yt.videos().list(part="snippet", id=",".join(ids[k:k + 50])).execute().get("items", []):
            titles[v["id"]] = v["snippet"]["title"]
    for i in items:
        i["on"] = titles.get(i["video_id"], "")
    return items


def yt_act(item, action, text):
    from youtube_upload import DAILY, ledger, spend
    if DAILY - ledger()["used"] < YT_ACTION_COST:
        raise RuntimeError("YouTube quota used up for today (resets midnight Pacific)")
    from youtube_auth import youtube
    yt = youtube()
    if action == "reply":
        r = yt.comments().insert(part="snippet", body={"snippet": {"parentId": item["comment_id"],
                                                                   "textOriginal": text}}).execute()
        spend(YT_ACTION_COST)
        return r["id"]
    yt.comments().setModerationStatus(id=item["comment_id"], moderationStatus="heldForReview").execute()
    spend(YT_ACTION_COST)
    return None


# ---------------------------------------------------------------- Instagram

def ig_inbox(cutoff, done, idx, posts):
    import instagram
    from instagram_auth import load
    me = (load() or {}).get("username")
    items = []
    for m in instagram.recent_media(posts):
        if not m.get("comments_count"):
            continue
        for c in instagram.comments_of(m["id"]):
            key = f"ig:{c['id']}"
            answered = any(r.get("username") == me for r in (c.get("replies") or {}).get("data", []))
            if (c.get("username") == me or answered or c.get("hidden") or key in done
                    or when(c["timestamp"]) < cutoff):
                continue
            slug, srt = idx.get(m["id"], (None, None))
            items.append({"key": key, "platform": "instagram", "comment_id": c["id"], "media_id": m["id"],
                          "author": c.get("username"), "text": c.get("text"), "likes": c.get("like_count", 0),
                          "published": c["timestamp"], "on": (m.get("caption") or "")[:150],
                          "permalink": m.get("permalink"), "project": slug, "transcript": srt})
    return items


def ig_act(item, action, text):
    import instagram
    if action == "reply":
        return instagram.reply(item["comment_id"], text)
    instagram.hide(item["comment_id"])
    return None


# ---------------------------------------------------------------- commands

def cmd_inbox(a):
    c = cfg()
    days = a.days or c.get("lookback_days", 14)
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    done = read(LEDGER, {})
    idx = project_index()
    wanted = c.get("platforms", ["youtube", "instagram"]) if a.platform == "all" else [a.platform]
    items, errors = [], {}
    for p in wanted:
        try:
            items += yt_inbox(cutoff, done, idx) if p == "youtube" else ig_inbox(cutoff, done, idx, c.get("instagram_posts", 25))
        except SystemExit as e:          # not signed in to that platform
            errors[p] = str(e)
        except Exception as e:           # one platform down should not hide the other
            errors[p] = f"{type(e).__name__}: {e}"
    items.sort(key=lambda i: i["published"], reverse=True)
    write(INBOX, {"generated": dt.datetime.now().astimezone().isoformat(), "days": days, "items": items, "errors": errors})
    counts = {p: sum(1 for i in items if i["platform"] == p) for p in wanted}
    print(json.dumps({"inbox": INBOX, "new": counts, "errors": errors}, indent=2))


def validate(text):
    text = (text or "").strip()
    if not text:
        return "empty reply"
    if len(text) > MAX_REPLY:
        return f"reply is {len(text)} characters, max {MAX_REPLY}"
    if LINK.search(text):
        return "reply contains a link - links in auto-replies read as spam and are refused"
    return None


def cmd_post(a):
    c = cfg()
    inbox = {i["key"]: i for i in read(INBOX, {}).get("items", [])}
    drafts = read(a.drafts, {}).get("items", [])
    done = read(LEDGER, {})
    only = set(a.keys.split(",")) if a.keys else None
    cap = a.max or c.get("max_replies_per_run", 25)
    lo, hi = (c.get("delay_seconds") or [8, 20])[:2]
    res = {"replied": [], "hidden": [], "skipped": 0, "refused": [], "failed": [], "left_for_next_run": 0}
    acted = 0
    for d in drafts:
        key, action = d.get("key"), d.get("action")
        if only and key not in only:
            continue
        if key in done:
            continue
        item = inbox.get(key)
        if not item:
            res["refused"].append({"key": key, "why": "not in the inbox"})
            continue
        if action == "skip":
            res["skipped"] += 1
            if not a.dry_run:
                done[key] = {"action": "skip", "at": dt.datetime.now().astimezone().isoformat(), "pile": d.get("pile")}
            continue
        if action not in ("reply", "hide"):
            res["refused"].append({"key": key, "why": f"unknown action {action!r}"})
            continue
        text = (d.get("text") or "").strip()
        if action == "reply" and (why := validate(text)):
            res["refused"].append({"key": key, "why": why})
            continue
        if acted >= cap:
            res["left_for_next_run"] += 1
            continue
        if a.dry_run:
            res["replied" if action == "reply" else "hidden"].append({"key": key, "to": item["author"], "text": text, "dry_run": True})
            acted += 1
            continue
        if acted:
            time.sleep(random.uniform(lo, hi))
        try:
            rid = (yt_act if item["platform"] == "youtube" else ig_act)(item, action, text)
        except (Exception, SystemExit) as e:
            res["failed"].append({"key": key, "why": f"{type(e).__name__}: {e}"})
            if "quota" in str(e).lower():
                break
            continue
        acted += 1
        done[key] = {"action": action, "at": dt.datetime.now().astimezone().isoformat(), "reply_id": rid,
                     "text": text, "pile": d.get("pile"), "platform": item["platform"]}
        write(LEDGER, done)
        res["replied" if action == "reply" else "hidden"].append({"key": key, "to": item["author"], "text": text})
    if not a.dry_run:
        write(LEDGER, done)
    print(json.dumps(res, indent=2, ensure_ascii=False))


def cmd_ledger(a):
    done = read(LEDGER, {})
    by = {}
    for v in done.values():
        k = f"{v.get('platform', '?')}:{v['action']}"
        by[k] = by.get(k, 0) + 1
    recent = sorted(((v["at"], k, v.get("text")) for k, v in done.items() if v["action"] == "reply"), reverse=True)[:10]
    print(json.dumps({"handled": len(done), "by": by, "recent_replies": recent}, indent=2, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("inbox")
    s.add_argument("--platform", choices=["all", "youtube", "instagram"], default="all")
    s.add_argument("--days", type=float)
    s.set_defaults(fn=cmd_inbox)
    s = sub.add_parser("post")
    s.add_argument("--drafts", default=DRAFTS)
    s.add_argument("--max", type=int)
    s.add_argument("--keys", help="only these keys, comma-separated")
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(fn=cmd_post)
    sub.add_parser("ledger").set_defaults(fn=cmd_ledger)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
