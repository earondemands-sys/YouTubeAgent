#!/usr/bin/env python3
"""broll.py - a visual for every beat: Pexels footage, an AI image, or nothing (a text card).

    python3 scripts/broll.py --script work/script.json --out work/broll
    ... --only 3 --query "server room blinking lights"     # redo one beat with a better search
    ... --offline                                         # no network: every beat becomes a text card

Per beat, by its `visual`:
  broll   Pexels video search on broll_query (PEXELS_API_KEY). Landscape, prefers a file at least
          1920 wide and a clip at least as long as the beat; never the same clip twice in a video.
          No match -> an AI image if an image key is set, else a text card.
  image   an AI image of on_screen (scripts/imagegen.py).
  text / screen   no asset; the renderer draws a card.

Writes <out>/beat-NN.mp4|png and <out>/../broll.json:
  {"beats": [{"id", "kind": "video|image|none", "file", "source", "source_url", "credit", "query"}]}
Credits are exact, because the seo agent copies them into the description.
"""
import argparse, json, os, sys, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from imagegen import KEYS, env, generate  # noqa: E402

CONFIG = os.environ.get("YTA_CONFIG") or os.path.join(ROOT, "config", "channel.json")
UA = {"User-Agent": "YouTubeAgent/1.0 (+local)"}


def pexels(query, key, min_seconds, used):
    url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
        {"query": query, "orientation": "landscape", "per_page": 15, "size": "medium"})
    req = urllib.request.Request(url, headers={"Authorization": key, **UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            vids = json.load(r).get("videos", [])
    except urllib.error.HTTPError as e:
        sys.exit(f"Pexels error {e.code}: {e.read().decode(errors='replace')[:300]}")
    vids = [v for v in vids if v["id"] not in used]
    vids.sort(key=lambda v: (v["duration"] < min_seconds, -v["width"]))
    for v in vids:
        files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("width")]
        if not files:
            continue
        big = sorted((f for f in files if f["width"] >= 1920), key=lambda f: f["width"])
        pick = big[0] if big else max(files, key=lambda f: f["width"])
        return v, pick
    return None, None


def download(url, path):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r, open(path, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--script", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--only", type=int)
    p.add_argument("--query")
    p.add_argument("--offline", action="store_true")
    a = p.parse_args()
    cfg = json.load(open(CONFIG)) if os.path.exists(CONFIG) else {}
    script = json.load(open(a.script))
    os.makedirs(a.out, exist_ok=True)
    index = os.path.join(os.path.dirname(os.path.abspath(a.out)), "broll.json")
    prev = {b["id"]: b for b in json.load(open(index))["beats"]} if os.path.exists(index) else {}
    pdir = os.path.dirname(os.path.dirname(os.path.abspath(a.out)))
    rel = lambda f: os.path.relpath(f, pdir)

    pkey = env("PEXELS_API_KEY")
    provider = cfg.get("images", {}).get("provider")
    ikey = provider in KEYS and env(KEYS[provider])
    needs = {b.get("visual") for b in script["beats"]}
    if not a.offline and "broll" in needs and not pkey:
        sys.exit("PEXELS_API_KEY is not set in .env (free at pexels.com/api), or run with --offline")
    if not a.offline and "image" in needs and not ikey:
        print("note: no image key - image beats become text cards", file=sys.stderr)

    used = {b.get("pexels_id") for b in prev.values() if b.get("pexels_id")}
    out = []
    for b in script["beats"]:
        if a.only is not None and b["id"] != a.only and b["id"] in prev:
            out.append(prev[b["id"]])
            continue
        if a.only is not None and b["id"] == a.only and prev.get(b["id"], {}).get("pexels_id"):
            used.discard(prev[b["id"]]["pexels_id"])
        visual = b.get("visual", "broll")
        entry = {"id": b["id"], "kind": "none", "file": None, "source": None, "source_url": None, "credit": None}
        if a.offline or visual in ("text", "screen"):
            out.append(entry)
            continue
        if visual == "broll":
            q = (a.query if a.only == b["id"] and a.query else None) or b.get("broll_query") or b.get("on_screen", "")
            v, f = pexels(q, pkey, b.get("est_seconds", 5), used)
            if v:
                path = os.path.join(a.out, f"beat-{b['id']:02d}.mp4")
                download(f["link"], path)
                used.add(v["id"])
                entry.update(kind="video", file=rel(path), source="pexels", source_url=v["url"], pexels_id=v["id"],
                             credit=f"{v['user']['name']} / Pexels", query=q, width=f["width"], seconds=v["duration"])
                out.append(entry)
                continue
            entry["query"] = q
        if ikey:
            path = os.path.join(a.out, f"beat-{b['id']:02d}.png")
            img, model = generate(f"{b.get('on_screen') or b.get('say')}. Cinematic, photographic, 16:9. "
                                  "No text, no letters, no logos, no watermarks.", size="landscape")
            open(path, "wb").write(img)
            entry.update(kind="image", file=rel(path), source=provider, model=model)
        out.append(entry)

    json.dump({"beats": out}, open(index, "w"), indent=1, ensure_ascii=False)
    kinds = {}
    for e in out:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    print(json.dumps({"broll": rel(index), "beats": len(out), "kinds": kinds}))


if __name__ == "__main__":
    main()
