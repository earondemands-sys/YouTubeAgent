#!/usr/bin/env python3
"""test_e2e.py - both pipelines, start to finish, through the real scripts and the state engine.

    python3 scripts/test_e2e.py              # ~10 minutes: renders two videos, a Short each, thumbnails
    python3 scripts/test_e2e.py --whisper    # also transcribe the recording (slower; otherwise a saved transcript)

Every step does what its agent would do with the scripts, using fixed inputs where an agent would
write (titles, metadata, shorts picks) - so this tests the machinery, not the writing. Uploads are
--dry-run: nothing reaches YouTube. Runs in tests/sandbox/ with its own config and projects.
"""
import json, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SANDBOX = os.path.join(ROOT, "tests", "sandbox")
FIX = os.path.join(ROOT, "tests", "fixtures")
PY, VPY = sys.executable, os.path.join(ROOT, ".venv", "bin", "python")
ENV = dict(os.environ, YTA_CONFIG=os.path.join(SANDBOX, "channel.json"), YTA_PROJECTS=os.path.join(SANDBOX, "projects"))


def sh(*cmd, cwd=ROOT, out=None):
    r = subprocess.run(list(cmd), capture_output=True, text=True, env=ENV, cwd=cwd)
    if r.returncode != 0:
        sys.exit(f"\nFAILED: {' '.join(map(str, cmd))}\n{(r.stderr or r.stdout)[-1500:]}")
    if out:
        open(out, "w").write(r.stdout)
    return r.stdout


def pl(*args):
    o = sh(PY, "scripts/pipeline.py", *args)
    return json.loads(o) if o.strip().startswith(("{", "[")) else o


def step(slug, name, outputs, fn):
    print(f"  ▶ {name}", flush=True)
    pl("start", slug, name)
    fn()
    pl("done", slug, name, *sum((["--out", f"{k}={v}"] for k, v in outputs.items()), []))
    missing = pl("status", slug, "--json")["steps"][name]
    return missing


def gate(slug, name, note):
    print(f"  ✋ {name} approve ({note})", flush=True)
    pl("gate", slug, name, "approve", "--note", note)


def expect_next(slug, run=(), gates=()):
    nx = pl("next", slug)
    assert sorted(nx["run"]) == sorted(run) and [g["gate"] for g in nx["gates"]] == list(gates), \
        f"{slug}: expected run={list(run)} gates={list(gates)}, got run={nx['run']} gates={[g['gate'] for g in nx['gates']]}"
    return nx


def setup():
    if not os.path.exists(os.path.join(FIX, "raw-recorded.mp4")):
        sh(PY, "scripts/make_test_media.py")
    os.makedirs(SANDBOX, exist_ok=True)
    cfg = json.load(open(os.path.join(ROOT, "config", "channel.json")))
    cfg["music"]["dir"] = FIX
    cfg["brand"]["faces_dir"] = FIX
    cfg["gates"] = {k: "ask" for k in cfg["gates"]}
    cfg["analytics_delay_hours"] = 0
    cfg["images"] = {"provider": "", "model": ""}   # never call a paid API from a test
    cfg["platforms"] = {"default": "youtube"}         # this test drives the YouTube path
    json.dump(cfg, open(ENV["YTA_CONFIG"], "w"), indent=2)


def metadata(pdir, title, credits=()):
    ch = json.loads(sh(PY, os.path.expanduser("~/.claude/skills/yt-chapters/chapters.py"),
                       os.path.join(pdir, "work", "final-transcript.srt"), "--target", "4", "--json"))
    chapters = [{"t": c["label"], "title": c["draft_title"]} for c in ch["chapters"]]
    if not ch["valid"]:
        chapters = []
    desc = f"{title} - explained simply, for freshers.\n\n" + "".join(f"{c['t']} {c['title']}\n" for c in chapters)
    if credits:
        desc += "\nFootage: " + "; ".join(sorted(set(credits))) + "\n"
    json.dump({"title": title, "description": desc, "tags": ["servicenow", "servicenow telugu", "ITSM"],
               "chapters": chapters, "category_id": "27", "default_language": "te", "made_for_kids": False},
              open(os.path.join(pdir, "work", "metadata.json"), "w"), indent=1)


def package(pdir, t1, w1):
    json.dump({"options": [
        {"n": 1, "title": t1, "thumb_text": w1, "score": 80, "issues": [], "brief": {"image_prompt": "dark IT office"}},
        {"n": 2, "title": t1 + " (Telugu)", "thumb_text": "WATCH THIS", "score": 70, "issues": [], "brief": {}}],
        "choice": None}, open(os.path.join(pdir, "work", "package.json"), "w"))


def thumbnails(pdir, face):
    for v in (1, 2):
        sh(PY, "scripts/thumbnail.py", pdir, "--option", "1", "--variant", str(v), "--face", face)
    shutil.copy(os.path.join(pdir, "work/thumb/thumb-1-1.jpg"), os.path.join(pdir, "out/thumbnail.jpg"))
    shutil.copy(os.path.join(pdir, "work/thumb/thumb-1-2.jpg"), os.path.join(pdir, "out/thumbnail-alt.jpg"))


def shorts(pdir, start, end, hook):
    json.dump({"shorts": [{"n": 1, "file": "out/shorts/short-1.mp4", "start": start, "end": end,
                           "title": "Where every ServiceNow ticket lives #shorts", "first_line": hook,
                           "on_screen": hook, "crop_x": 0.5}]}, open(os.path.join(pdir, "work", "shorts.json"), "w"))
    sh(PY, "scripts/short_props.py", pdir)
    sh(PY, "scripts/render.py", pdir, "--short", "1")


def tail(slug, pdir, synthetic):
    step(slug, "qa", {"qa": "work/qa-report.json"},
         lambda: sh(PY, "scripts/qa_check.py", pdir, "--json", out=os.path.join(pdir, "work", "qa-report.json")))
    qa = json.load(open(os.path.join(pdir, "work", "qa-report.json")))
    bad = [c for c in qa["checks"] if c["status"] == "FAIL"]
    assert not bad, f"QA failed: {bad}"
    assert qa["synthetic_media"] == synthetic, f"synthetic_media should be {synthetic}"
    print(f"    QA {qa['verdict']}: " + ", ".join(f"{c['name']} {c['status']}" for c in qa["checks"] if c["status"] != "PASS"))
    expect_next(slug, gates=["gate:publish"])
    gate(slug, "gate:publish", "privacy=private")

    def upload():
        args = ["--synthetic-media"] if synthetic else []
        sh(VPY, os.path.join(ROOT, "scripts/youtube_upload.py"), "--video", "out/video.mp4", "--meta", "work/metadata.json",
           "--thumbnail", "out/thumbnail.jpg", "--privacy", "private", "--out", "work/publish.json", "--dry-run", *args, cwd=pdir)
        sh(VPY, os.path.join(ROOT, "scripts/youtube_upload.py"), "--short", "1", "--video", "out/shorts/short-1.mp4",
           "--meta", "work/metadata.json", "--title", "Where every ServiceNow ticket lives #shorts", "--privacy", "private",
           "--publish-at", "2030-01-06T18:00:00+05:30", "--out", "work/publish.json", "--dry-run", cwd=pdir)
    step(slug, "publish", {"publish": "work/publish.json"}, upload)
    pub = json.load(open(os.path.join(pdir, "work", "publish.json")))
    assert pub["long"]["request"]["status"]["containsSyntheticMedia"] == synthetic
    assert pub["shorts"][0]["publish_at"] == "2030-01-06T12:30:00.000Z"

    def analytics():
        rows = "position_percent,audience_percent\n" + "".join(
            f"{i},{round(100 - 30 * min(i / 10, 1) - (12 if i > 40 else 0) - 0.2 * i, 2)}\n" for i in range(1, 101))
        open(os.path.join(pdir, "work", "retention.csv"), "w").write(rows)
        r = json.loads(sh(PY, os.path.expanduser("~/.claude/skills/yt-retention/retention.py"),
                          os.path.join(pdir, "work", "retention.csv"), "--duration", "60",
                          "--transcript", os.path.join(pdir, "work", "final-transcript.srt"), "--json"))
        open(os.path.join(pdir, "work", "analytics-report.md"), "w").write(f"hook leak {r['hook_leak']}%\n")
        json.dump({"comments": []}, open(os.path.join(pdir, "work", "comments.json"), "w"))
    expect_next(slug, run=["analytics"])
    step(slug, "analytics", {"report": "work/analytics-report.md", "comments": "work/comments.json"}, analytics)
    assert pl("next", slug)["complete"], f"{slug} not complete"
    print(f"  ✓ {slug} complete\n", flush=True)


def recorded(whisper):
    slug = "e2e-recorded"
    pdir = os.path.join(ENV["YTA_PROJECTS"], slug)
    shutil.rmtree(pdir, ignore_errors=True)
    print(f"\nRECORDED ({slug}, style hormozi)")
    pl("new", slug, "--mode", "recorded", "--source", os.path.join(FIX, "raw-recorded.mp4"), "--style", "hormozi")
    expect_next(slug, run=["editor"])

    def editor():
        if whisper:
            sh(PY, "scripts/transcribe.py", os.path.join(FIX, "raw-recorded.mp4"), "--out",
               os.path.join(pdir, "work", "transcript"), "--model", "base", "--language", "en", "--caption-script", "native")
        else:
            for ext in ("json", "srt"):
                shutil.copy(os.path.join(FIX, f"transcript.{ext}"), os.path.join(pdir, "work", f"transcript.{ext}"))
        sh(PY, "scripts/make_edl.py", pdir)
    step(slug, "editor", {"edl": "work/edl.json", "report": "work/edit-report.md", "transcript": "work/transcript.json",
                          "srt": "work/transcript.srt"}, editor)
    edl = json.load(open(os.path.join(pdir, "work", "edl.json")))
    assert any("REPEAT" in c["kind"] for c in edl["cuts"]), "the retake was not cut"
    expect_next(slug, gates=["gate:cuts"])
    gate(slug, "gate:cuts", "ok")
    expect_next(slug, run=["packaging", "remotion"])

    step(slug, "packaging", {"package": "work/package.json"},
         lambda: package(pdir, "ServiceNow Incidents in 60 Seconds", "TICKET STUCK?"))

    def remotion():
        json.dump({"title": "How incidents work", "items": [
            {"at": 20.4, "type": "chapter", "title": "The incident table"},
            {"at": 28.0, "type": "slam", "text": "ASSIGNMENT"},
            {"at": 42.1, "type": "callout", "text": "priority = impact x urgency", "variant": "code-highlight", "dur": 4}]},
            open(os.path.join(pdir, "work", "sections.json"), "w"))
        sh(PY, "scripts/render_props.py", pdir)
        sh(PY, "scripts/render.py", pdir)
    step(slug, "remotion", {"video": "out/video.mp4", "props": "work/render-props.json",
                            "final_srt": "work/final-transcript.srt", "final_transcript": "work/final-transcript.json"}, remotion)
    expect_next(slug, run=["shorts"], gates=["gate:package"])
    gate(slug, "gate:package", "choice=1")
    expect_next(slug, run=["shorts", "seo", "thumbnail"])
    step(slug, "thumbnail", {"thumbnail": "out/thumbnail.jpg", "alt": "out/thumbnail-alt.jpg"}, lambda: thumbnails(pdir, "auto"))
    step(slug, "shorts", {"shorts": "work/shorts.json", "dir": "out/shorts"},
         lambda: shorts(pdir, 7.7, 30.5, "WHERE TICKETS LIVE"))
    step(slug, "seo", {"metadata": "work/metadata.json"}, lambda: metadata(pdir, "ServiceNow Incidents in 60 Seconds"))
    expect_next(slug, run=["qa"])
    tail(slug, pdir, synthetic=False)


def faceless():
    slug = "e2e-faceless"
    pdir = os.path.join(ENV["YTA_PROJECTS"], slug)
    shutil.rmtree(pdir, ignore_errors=True)
    print(f"\nFACELESS ({slug}, style listicle)")
    pl("new", slug, "--mode", "faceless", "--topic", "3 ServiceNow tables every fresher must know", "--style", "listicle", "--length", "0.5")
    expect_next(slug, run=["research"])
    step(slug, "research", {"research": "work/research.md"},
         lambda: open(os.path.join(pdir, "work", "research.md"), "w").write("# angle\nThree tables, countdown.\n"))
    step(slug, "script", {"script": "work/script.json"},
         lambda: shutil.copy(os.path.join(FIX, "script.json"), os.path.join(pdir, "work", "script.json")))
    expect_next(slug, gates=["gate:script"])
    gate(slug, "gate:script", "hook 1")
    expect_next(slug, run=["broll", "packaging", "voiceover"])
    step(slug, "voiceover", {"voice": "work/voice.mp3", "timestamps": "work/voice-timestamps.json"},
         lambda: sh(PY, os.path.join(ROOT, "scripts/tts.py"), "--script", "work/script.json", "--out", "work/voice.mp3",
                    "--timestamps", "work/voice-timestamps.json", "--engine", "say", cwd=pdir))

    def broll():
        sh(PY, os.path.join(ROOT, "scripts/broll.py"), "--script", "work/script.json", "--out", "work/broll", "--offline", cwd=pdir)
        # stand-in footage, since a test must not call Pexels
        d = os.path.join(pdir, "work", "broll")
        for i, src in ((1, "mandelbrot=size=1920x1080:rate=30"), (4, "life=size=1920x1080:rate=30:mold=10:life_color=#00ccff"),
                       (5, "cellauto=size=1920x1080:rate=30:rule=110")):
            sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", src, "-t", "3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
               os.path.join(d, f"beat-0{i}.mp4"))
        sh("ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "gradients=size=1920x1080:c0=0x1e3c72:c1=0xffb400",
           "-frames:v", "1", os.path.join(d, "beat-02.png"))
        idx = json.load(open(os.path.join(pdir, "work", "broll.json")))
        for b in idx["beats"]:
            if b["id"] in (1, 4, 5):
                b.update(kind="video", file=f"work/broll/beat-0{b['id']}.mp4", source="pexels",
                         source_url=f"https://www.pexels.com/video/{b['id']}/", credit=f"Fixture {b['id'] % 2} / Pexels")
            if b["id"] == 2:
                b.update(kind="image", file="work/broll/beat-02.png", source="openai")
        json.dump(idx, open(os.path.join(pdir, "work", "broll.json"), "w"))
    step(slug, "broll", {"broll": "work/broll.json", "dir": "work/broll"}, broll)
    step(slug, "packaging", {"package": "work/package.json"},
         lambda: package(pdir, "3 ServiceNow Tables Every Fresher Needs", "3 TABLES"))
    expect_next(slug, run=["remotion"], gates=["gate:package"])
    step(slug, "remotion", {"video": "out/video.mp4", "props": "work/render-props.json",
                            "final_srt": "work/final-transcript.srt", "final_transcript": "work/final-transcript.json"},
         lambda: (sh(PY, "scripts/render_props.py", pdir), sh(PY, "scripts/render.py", pdir)))
    props = json.load(open(os.path.join(pdir, "work", "render-props.json")))
    assert {s["kind"] for s in props["segments"]} == {"video", "image", "card"}, "faceless should mix footage, image and cards"
    assert sum(o["type"] == "list" for o in props["overlays"]) == 3, "listicle should show three number cards"
    gate(slug, "gate:package", "choice=1")
    step(slug, "thumbnail", {"thumbnail": "out/thumbnail.jpg", "alt": "out/thumbnail-alt.jpg"}, lambda: thumbnails(pdir, "none"))
    step(slug, "shorts", {"shorts": "work/shorts.json", "dir": "out/shorts"}, lambda: shorts(pdir, 8.8, 25.0, "TOP 3 TABLES"))
    credits = [b["credit"] for b in json.load(open(os.path.join(pdir, "work", "broll.json")))["beats"] if b.get("credit")]
    step(slug, "seo", {"metadata": "work/metadata.json"},
         lambda: metadata(pdir, "3 ServiceNow Tables Every Fresher Needs", credits))
    tail(slug, pdir, synthetic=True)


def main():
    setup()
    recorded("--whisper" in sys.argv)
    faceless()
    print("END TO END: both pipelines complete")


if __name__ == "__main__":
    main()
