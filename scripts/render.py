#!/usr/bin/env python3
"""render.py - render a project with Remotion, then make the file YouTube-ready.

    python3 scripts/render.py projects/<slug>                     # long video -> out/video.mp4
    python3 scripts/render.py projects/<slug> --short 2           # work/shorts/short-2.props.json -> out/shorts/short-2.mp4
    python3 scripts/render.py projects/<slug> --thumbnail work/thumb/thumb-1.props.json --out out/thumbnail.jpg
    ... --thumbnail ... --scale 3                                 # 1280x720 composition rendered at 3840x2160
    ... --frames 0-299                                            # render only part (a quick check)

Assets are served to Remotion from the project folder by a local HTTP server for the length of the
render (Remotion copies a --public-dir into every bundle, which for a project holding raw footage
would mean copying gigabytes per render, and drops symlinks). The props get `assetBase` set to it.

Video: Remotion renders h264/aac, then audio is
normalised to -14 LUFS / -1.5 dBTP in two passes (video stream copied, not re-encoded).
Thumbnail: Remotion renders a PNG still, then it is encoded to JPEG at the best quality that fits
under YouTube's 2MB limit.

Long renders take a while; run them in the background. The first render ever downloads a headless
Chrome for Remotion.
"""
import argparse, functools, http.server, json, os, re, subprocess, sys, tempfile, threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTION = os.path.join(ROOT, "remotion")
MAX_THUMB = 2 * 1024 * 1024


def remotion(args):
    cmd = ["npx", "remotion", *args, "--log=error"]
    r = subprocess.run(cmd, cwd=REMOTION, capture_output=True, text=True)
    if r.returncode != 0:
        tail = (r.stderr or r.stdout)[-2500:]
        sys.exit(f"remotion failed ({' '.join(args[:2])}):\n{tail}")


class Quiet(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # the waveform overlay reads audio with fetch(), which the bundle's origin needs CORS for
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, *args):
        pass


class Server(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass  # Chrome drops connections mid-file all the time; that is not an error worth printing


def serve(directory):
    srv = Server(("127.0.0.1", 0), functools.partial(Quiet, directory=directory))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def with_base(props_path, base):
    props = json.load(open(props_path))
    props["assetBase"] = base
    fd, tmp = tempfile.mkstemp(suffix=".json", prefix="yta-props-")
    with os.fdopen(fd, "w") as f:
        json.dump(props, f, ensure_ascii=False)
    return tmp


def loudnorm(path, target=-14.0, tp=-1.5):
    probe = ["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn",
             "-af", f"loudnorm=I={target}:TP={tp}:LRA=11:print_format=json", "-f", "null", "-"]
    err = subprocess.run(probe, capture_output=True, text=True).stderr
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S)
    if not m:
        return None
    j = json.loads(m.group(0))
    if j["input_i"] in ("-inf", "inf"):
        return None
    af = (f"loudnorm=I={target}:TP={tp}:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
          f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    tmp = path + ".norm.mp4"
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-c:v", "copy", "-af", af,
                        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", tmp],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"loudness pass failed: {r.stderr[-600:]}")
    os.replace(tmp, path)
    return float(j["input_i"])


def to_jpeg(png, out, scale=1):
    w, h = round(1280 * scale), round(720 * scale)
    for q in range(2, 32):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", png, "-vf", f"scale={w}:{h}", "-q:v", str(q), out],
                       check=True)
        if os.path.getsize(out) < MAX_THUMB:
            return q, os.path.getsize(out)
    sys.exit("could not get the thumbnail under 2MB")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("project")
    p.add_argument("--short", type=int)
    p.add_argument("--thumbnail", help="props JSON for the Thumbnail still")
    p.add_argument("--out")
    p.add_argument("--frames")
    p.add_argument("--scale", type=float, default=1, help="thumbnail only: render the 1280x720 still at this multiple")
    a = p.parse_args()
    pdir = os.path.abspath(a.project)
    if not os.path.isdir(os.path.join(REMOTION, "node_modules")):
        sys.exit("remotion/ is not installed: cd remotion && npm install")
    empty = tempfile.mkdtemp(prefix="yta-public-")
    public = f"--public-dir={empty}"
    srv, base = serve(pdir)

    if a.thumbnail:
        props = os.path.abspath(a.thumbnail if os.path.isabs(a.thumbnail) else os.path.join(pdir, a.thumbnail))
        out = os.path.join(pdir, a.out or "out/thumbnail.jpg")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        png = os.path.splitext(out)[0] + ".png"
        remotion(["still", "src/index.ts", "Thumbnail", png, f"--props={with_base(props, base)}", public,
                  f"--scale={a.scale:g}"])
        q, size = to_jpeg(png, out, a.scale)
        os.remove(png)
        print(json.dumps({"thumbnail": os.path.relpath(out, pdir), "bytes": size, "jpeg_q": q,
                          "size": f"{round(1280 * a.scale)}x{round(720 * a.scale)}"}))
        return

    if a.short is not None:
        props = os.path.join(pdir, "work", "shorts", f"short-{a.short}.props.json")
        out = os.path.join(pdir, a.out or f"out/shorts/short-{a.short}.mp4")
        comp = "Short"
        fr = json.load(open(props)).get("frameRange")
        frames = a.frames or (f"{fr[0]}-{fr[1]}" if fr else None)
    else:
        props = os.path.join(pdir, "work", "render-props.json")
        out = os.path.join(pdir, a.out or "out/video.mp4")
        comp = "Main"
        frames = a.frames
    if not os.path.exists(props):
        sys.exit(f"missing {props} - run render_props.py / short_props.py first")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    args = ["render", "src/index.ts", comp, out, f"--props={with_base(props, base)}", public,
            "--codec=h264", "--audio-codec=aac", "--crf=18", "--pixel-format=yuv420p"]
    if frames:
        args.append(f"--frames={frames}")
    remotion(args)
    before = loudnorm(out)
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out],
                       capture_output=True, text=True).stdout.strip()
    print(json.dumps({"video": os.path.relpath(out, pdir), "duration": float(d or 0),
                      "loudness_before": before, "loudness_after": -14.0 if before is not None else None}))


if __name__ == "__main__":
    main()
