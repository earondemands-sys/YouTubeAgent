#!/usr/bin/env python3
"""yt_analytics.py - what happened to a published video: stats, retention curve, comments.

    .venv/bin/python scripts/yt_analytics.py stats <video_id>
    .venv/bin/python scripts/yt_analytics.py retention <video_id> --out work/retention.csv
    .venv/bin/python scripts/yt_analytics.py comments <video_id> --out work/comments.json [--max 300]

Uses the same sign-in as uploads (scripts/youtube_auth.py). Read-only: nothing here posts, replies
or changes anything on the channel.

retention.csv is in the shape the yt-retention skill's retention.py reads: position as a percent of
the video, percent of viewers still watching (YouTube's audienceWatchRatio x 100; it can pass 100
where people rewatch). Pass the video's length to retention.py with --duration.

YouTube Analytics lags by a day or two, and a curve from under ~100 views is noise - `stats` says
how many views there are so the analytics agent can decide whether the curve means anything.
"""
import argparse, csv, datetime as dt, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def published(yt, vid):
    items = yt.videos().list(part="snippet,contentDetails,statistics", id=vid).execute().get("items", [])
    if not items:
        sys.exit(f"video {vid} not found on this channel")
    return items[0]


def window(video):
    start = video["snippet"]["publishedAt"][:10]
    end = dt.date.today().isoformat()
    return start, end


def retention_rows(response):
    """API rows [[elapsedVideoTimeRatio, audienceWatchRatio], ...] -> [(percent, percent)]."""
    return [(round(float(x) * 100, 2), round(float(y) * 100, 2)) for x, y in response.get("rows", [])]


def write_csv(rows, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["position_percent", "audience_percent"])
        w.writerows(rows)


def flatten_comments(threads):
    out = []
    for t in threads:
        top = t["snippet"]["topLevelComment"]["snippet"]
        out.append({"id": t["id"], "author": top.get("authorDisplayName"), "text": top.get("textDisplay") or top.get("textOriginal"),
                    "likes": top.get("likeCount", 0), "replies": t["snippet"].get("totalReplyCount", 0),
                    "published": top.get("publishedAt")})
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("what", choices=["stats", "retention", "comments"])
    p.add_argument("video_id")
    p.add_argument("--out")
    p.add_argument("--max", type=int, default=300)
    a = p.parse_args()

    from youtube_auth import youtube
    yt = youtube()
    video = published(yt, a.video_id)
    start, end = window(video)

    if a.what == "stats":
        ya = youtube("youtubeAnalytics", "v2")
        r = ya.reports().query(ids="channel==MINE", startDate=start, endDate=end, filters=f"video=={a.video_id}",
                               metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,comments,subscribersGained").execute()
        head = [h["name"] for h in r.get("columnHeaders", [])]
        vals = (r.get("rows") or [[0] * len(head)])[0]
        out = dict(zip(head, vals))
        out.update(title=video["snippet"]["title"], published=video["snippet"]["publishedAt"],
                   duration=video["contentDetails"]["duration"], public_views=video.get("statistics", {}).get("viewCount"),
                   enough_for_retention=int(out.get("views", 0) or 0) >= 100)
        print(json.dumps(out, indent=2, ensure_ascii=False))
    elif a.what == "retention":
        if not a.out:
            p.error("--out is required for retention")
        ya = youtube("youtubeAnalytics", "v2")
        r = ya.reports().query(ids="channel==MINE", startDate=start, endDate=end, filters=f"video=={a.video_id}",
                               metrics="audienceWatchRatio", dimensions="elapsedVideoTimeRatio").execute()
        rows = retention_rows(r)
        if len(rows) < 8:
            sys.exit(f"only {len(rows)} retention points so far - YouTube has not processed enough views yet")
        write_csv(rows, a.out)
        print(json.dumps({"retention": a.out, "points": len(rows)}))
    else:
        if not a.out:
            p.error("--out is required for comments")
        threads, token = [], None
        while len(threads) < a.max:
            r = yt.commentThreads().list(part="snippet", videoId=a.video_id, maxResults=100, order="relevance",
                                         textFormat="plainText", pageToken=token).execute()
            threads += r.get("items", [])
            token = r.get("nextPageToken")
            if not token:
                break
        comments = flatten_comments(threads[: a.max])
        json.dump({"video": a.video_id, "count": len(comments), "comments": comments}, open(a.out, "w"),
                  indent=1, ensure_ascii=False)
        print(json.dumps({"comments": a.out, "count": len(comments)}))


if __name__ == "__main__":
    main()
