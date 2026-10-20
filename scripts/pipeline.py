#!/usr/bin/env python3
"""pipeline.py - the state engine for the YouTube agent team.

    python3 scripts/pipeline.py new my-video --mode recorded --source ~/Movies/raw.mp4 --style hormozi
    python3 scripts/pipeline.py new my-video --mode faceless --topic "iPhone 18 leaks" --length 10
    python3 scripts/pipeline.py new my-video ... --platforms youtube,instagram   # where it goes
    python3 scripts/pipeline.py platforms my-video instagram   # change where it goes, before publish
    python3 scripts/pipeline.py next my-video            # what can run now, what needs the user
    python3 scripts/pipeline.py brief my-video editor    # the JSON brief handed to an agent
    python3 scripts/pipeline.py start my-video editor
    python3 scripts/pipeline.py done my-video editor --out edl=work/edl.json --out report=work/edit-report.md
    python3 scripts/pipeline.py ask my-video editor --question "..." --options "a|b|c"
    python3 scripts/pipeline.py answer my-video editor --answer "a"
    python3 scripts/pipeline.py gate my-video gate:cuts approve --note "..."
    python3 scripts/pipeline.py gate my-video gate:cuts reject --note "keep the intro" [--redo editor]
    python3 scripts/pipeline.py fail my-video editor --reason "..."
    python3 scripts/pipeline.py retry my-video editor    # failed/blocked/done -> pending, answers kept
    python3 scripts/pipeline.py reset my-video remotion  # the step and everything downstream of it
    python3 scripts/pipeline.py status my-video
    python3 scripts/pipeline.py list

One video is one folder, projects/<slug>/, with one state file, projects/<slug>/state.json. The
Director is the only thing that writes it. Agents write their own files into the project folder and
report back; they never touch the state, so agents running in parallel cannot race on it.

Steps are run by agents. Gates (gate:*) are decided by the user, unless config/channel.json marks
that gate "auto". A step that needs the user is "blocked" with a question; answering it puts the
step back to pending with the answer recorded, so the next run of the agent sees it.

Platforms: a video goes to YouTube, Instagram or both. Each platform owns some steps
(PLATFORM_STEPS); the steps of a platform the video is not going to are "skipped". Instagram posts
the Shorts as Reels, so it needs the shorts step.
"""
import argparse, datetime as dt, json, os, re, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS = os.environ.get("YTA_PROJECTS") or os.path.join(ROOT, "projects")
CONFIG = os.environ.get("YTA_CONFIG") or os.path.join(ROOT, "config", "channel.json")
STYLES = os.path.join(ROOT, "config", "styles.json")
VOICE = os.path.expanduser("~/.claude/youtube/voice.md")

# Pipeline order matters only for display; the dependencies decide what runs.
PIPELINES = {
    "recorded": [
        ("editor", []),
        ("gate:cuts", ["editor"]),
        ("packaging", ["gate:cuts"]),
        ("remotion", ["gate:cuts"]),
        ("gate:package", ["packaging"]),
        ("thumbnail", ["gate:package"]),
        ("shorts", ["remotion"]),
        ("seo", ["remotion", "gate:package"]),
        ("reels", ["shorts"]),
        ("qa", ["thumbnail", "shorts", "seo", "reels"]),
        ("gate:publish", ["qa"]),
        ("publish", ["gate:publish"]),
        ("ig-publish", ["gate:publish", "reels"]),
        ("analytics", ["publish"]),
    ],
    "faceless": [
        ("research", []),
        ("script", ["research"]),
        ("gate:script", ["script"]),
        ("voiceover", ["gate:script"]),
        ("broll", ["gate:script"]),
        ("packaging", ["gate:script"]),
        ("remotion", ["voiceover", "broll"]),
        ("gate:package", ["packaging"]),
        ("thumbnail", ["gate:package"]),
        ("shorts", ["remotion"]),
        ("seo", ["remotion", "gate:package"]),
        ("reels", ["shorts"]),
        ("qa", ["thumbnail", "shorts", "seo", "reels"]),
        ("gate:publish", ["qa"]),
        ("publish", ["gate:publish"]),
        ("ig-publish", ["gate:publish", "reels"]),
        ("analytics", ["publish"]),
    ],
}
GATE_FEEDS = {"gate:cuts": "editor", "gate:script": "script", "gate:package": "packaging", "gate:publish": "qa"}
GATE_KEYS = {"gate:cuts": "cuts", "gate:script": "script", "gate:package": "package", "gate:publish": "publish"}
DELAYED = {"analytics": "analytics_delay_hours"}  # step -> config key holding its delay
PLATFORM_STEPS = {"youtube": ["publish", "analytics"], "instagram": ["reels", "ig-publish"]}
PLATFORMS = list(PLATFORM_STEPS)
SUBDIRS = ["raw", "work", "out", "out/shorts"]
SATISFIED = ("done", "skipped", "approved")


def now():
    return dt.datetime.now().astimezone().replace(microsecond=0)


def iso(t):
    return t.isoformat()


def die(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def emit(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def load_config():
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        die(f"{CONFIG} is not valid JSON: {e}")


def pdir(slug):
    return os.path.join(PROJECTS, slug)


def load(slug):
    try:
        with open(os.path.join(pdir(slug), "state.json")) as f:
            return migrate(json.load(f))
    except FileNotFoundError:
        die(f"no project '{slug}' in {PROJECTS}")


def migrate(st):
    """Projects made before a step existed get it as skipped, and go to YouTube only."""
    st["inputs"].setdefault("platforms", ["youtube"])
    for n, _ in PIPELINES[st["mode"]]:
        if is_gate(n):
            st["gates"].setdefault(n, {"status": "pending", "note": None})
        elif n not in st["steps"]:
            st["steps"][n] = {"status": "skipped", "outputs": {}, "attempts": 0, "answers": [], "feedback": []}
    return st


def parse_platforms(raw):
    raw = (raw or "").strip().lower().replace(" ", "")
    if raw in ("both", "all"):
        return list(PLATFORMS)
    got = [p for p in raw.split(",") if p]
    bad = [p for p in got if p not in PLATFORMS]
    if bad or not got:
        die(f"platforms must be youtube, instagram, or both (got '{raw}')")
    return [p for p in PLATFORMS if p in got]


def platform_skips(platforms):
    return [s for p, steps in PLATFORM_STEPS.items() if p not in platforms for s in steps]


def save(st):
    st["updated"] = iso(now())
    path = os.path.join(pdir(st["slug"]), "state.json")
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".state-")
    with os.fdopen(fd, "w") as f:
        json.dump(st, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def log(st, event, **kw):
    st["log"].append({"at": iso(now()), "event": event, **kw})


def graph(st):
    return dict(PIPELINES[st["mode"]])


def is_gate(name):
    return name.startswith("gate:")


def node(st, name):
    if name in st["steps"]:
        return st["steps"][name]
    if name in st["gates"]:
        return st["gates"][name]
    die(f"'{name}' is not in the {st['mode']} pipeline: {', '.join(graph(st))}")


def satisfied(st, name):
    return node(st, name)["status"] in SATISFIED


def deps_ok(st, name):
    return all(satisfied(st, d) for d in graph(st)[name])


def downstream(st, name):
    g, seen, frontier = graph(st), set(), [name]
    while frontier:
        cur = frontier.pop()
        for n, deps in g.items():
            if cur in deps and n not in seen:
                seen.add(n)
                frontier.append(n)
    return [n for n in g if n in seen]


def reset_nodes(st, names):
    """Back to pending, except skipped steps. Returns the names actually reset."""
    hit = []
    for n in names:
        x = node(st, n)
        if x["status"] == "skipped":
            continue
        hit.append(n)
        if is_gate(n):
            x.update(status="pending", note=None)
        else:
            x.update(status="pending", outputs={}, question=None, options=[], reason=None)
            x.pop("not_before", None)
    return hit


def schedule_delayed(st, cfg):
    for step, key in DELAYED.items():
        n = st["steps"].get(step)
        if n and n["status"] == "pending" and "not_before" not in n and deps_ok(st, step):
            n["not_before"] = iso(now() + dt.timedelta(hours=float(cfg.get(key, 48))))


def advance(st, cfg):
    """Approve the gates config marks "auto". Loops, since one approval can open the next gate."""
    rules = cfg.get("gates", {})
    changed = True
    while changed:
        changed = False
        for name in graph(st):
            g = st["gates"].get(name)
            if g and g["status"] == "pending" and deps_ok(st, name) and rules.get(GATE_KEYS[name]) == "auto":
                g.update(status="approved", note="auto (config/channel.json)", at=iso(now()))
                log(st, "gate-auto", gate=name)
                changed = True


# ---------------------------------------------------------------- commands

def cmd_new(a):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,60}", a.slug):
        die("slug must be lowercase letters, digits and dashes, e.g. iphone-18-leaks")
    if os.path.exists(pdir(a.slug)):
        die(f"project '{a.slug}' already exists")
    if a.mode == "recorded" and not a.source:
        die("--mode recorded needs --source <raw video file>")
    if a.mode == "faceless" and not a.topic:
        die("--mode faceless needs --topic \"...\"")
    source = os.path.abspath(os.path.expanduser(a.source)) if a.source else None
    if source and not os.path.exists(source):
        die(f"source not found: {source}")
    if a.style and os.path.exists(STYLES):
        with open(STYLES) as f:
            ids = [s["id"] for s in json.load(f)["styles"]]
        if a.style not in ids:
            die(f"unknown style '{a.style}'. Styles: {', '.join(ids)}")
    names = [n for n, _ in PIPELINES[a.mode]]
    skip = [s for s in (a.skip or "").split(",") if s]
    for s in skip:
        if s not in names or is_gate(s):
            die(f"cannot skip '{s}'. Skippable steps: {', '.join(n for n in names if not is_gate(n))}")

    cfg = load_config()
    defaults = cfg.get("defaults", {})
    default_platforms = cfg.get("platforms", {}).get("default", "youtube")
    if not a.platforms and default_platforms == "ask":
        die("config says ask where this video goes: pass --platforms youtube, instagram or both")
    platforms = parse_platforms(a.platforms or default_platforms)
    if "instagram" in platforms and "shorts" in skip:
        die("Instagram posts the Shorts as Reels: do not skip shorts, or leave Instagram out")
    style = a.style or defaults.get(f"{a.mode}_style")
    st = {
        "slug": a.slug, "mode": a.mode, "created": iso(now()), "updated": None,
        "inputs": {"source": source, "topic": a.topic, "style": style, "length_min": a.length,
                   "notes": a.notes, "platforms": platforms, "skip": skip},
        "steps": {}, "gates": {}, "log": [],
    }
    off = skip + platform_skips(platforms)
    for n in names:
        if is_gate(n):
            st["gates"][n] = {"status": "skipped" if GATE_FEEDS[n] in skip else "pending", "note": None}
        else:
            st["steps"][n] = {"status": "skipped" if n in off else "pending", "outputs": {},
                              "attempts": 0, "answers": [], "feedback": []}
    for d in SUBDIRS:
        os.makedirs(os.path.join(pdir(a.slug), d), exist_ok=True)
    log(st, "created", mode=a.mode, skip=skip, platforms=platforms)
    save(st)
    emit({"created": a.slug, "dir": pdir(a.slug), "mode": a.mode, "style": style, "skipped": skip,
          "platforms": platforms})


def cmd_next(a):
    st, cfg = load(a.slug), load_config()
    advance(st, cfg)
    schedule_delayed(st, cfg)
    t = now()
    res = {"slug": st["slug"], "mode": st["mode"], "run": [], "running": [], "gates": [],
           "blocked": [], "failed": [], "waiting": []}
    for name in graph(st):
        n = node(st, name)
        if is_gate(name):
            if n["status"] == "pending" and deps_ok(st, name):
                feeder = GATE_FEEDS[name]
                res["gates"].append({"gate": name, "evidence": st["steps"][feeder]["outputs"]})
            continue
        s = n["status"]
        if s == "running":
            res["running"].append(name)
        elif s == "blocked":
            res["blocked"].append({"step": name, "question": n.get("question"), "options": n.get("options", [])})
        elif s == "failed":
            res["failed"].append({"step": name, "reason": n.get("reason")})
        elif s == "pending" and deps_ok(st, name):
            nb = n.get("not_before")
            if nb and dt.datetime.fromisoformat(nb) > t:
                res["waiting"].append({"step": name, "not_before": nb})
            else:
                res["run"].append(name)
    res["complete"] = all(satisfied(st, n) for n in graph(st))
    save(st)
    emit(res)


def cmd_brief(a):
    st = load(a.slug)
    if is_gate(a.step):
        die("gates are decided by the user, not briefed to an agent")
    n = node(st, a.step)
    g = graph(st)
    emit({
        "project": st["slug"], "mode": st["mode"], "step": a.step, "agent": f"{a.step}-agent",
        "attempt": n["attempts"] + (0 if n["status"] == "running" else 1),
        "project_dir": pdir(st["slug"]), "root": ROOT,
        "config": CONFIG, "styles": STYLES, "voice_profile": VOICE,
        "inputs": st["inputs"],
        "upstream": {s: st["steps"][s]["outputs"] for s in g
                     if not is_gate(s) and st["steps"][s]["status"] == "done" and s != a.step},
        "decisions": {k: v.get("note") for k, v in st["gates"].items() if v["status"] == "approved"},
        "answers": n["answers"],
        "feedback": n["feedback"],
    })


def cmd_start(a):
    st = load(a.slug)
    n = node(st, a.step)
    if is_gate(a.step):
        die("use 'gate' for gates")
    if n["status"] not in ("pending",):
        die(f"{a.step} is {n['status']}, not pending")
    if not deps_ok(st, a.step):
        die(f"{a.step} is waiting on: {', '.join(d for d in graph(st)[a.step] if not satisfied(st, d))}")
    n["status"] = "running"
    n["attempts"] += 1
    n["started"] = iso(now())
    log(st, "start", step=a.step, attempt=n["attempts"])
    save(st)
    emit({"running": a.step, "attempt": n["attempts"]})


def cmd_done(a):
    st, cfg = load(a.slug), load_config()
    n = node(st, a.step)
    if is_gate(a.step):
        die("use 'gate' for gates")
    if n["status"] not in ("running", "pending"):
        die(f"{a.step} is {n['status']}; only a running or pending step can be marked done")
    outputs, missing = {}, []
    for kv in a.out or []:
        if "=" not in kv:
            die(f"--out wants key=path, got '{kv}'")
        k, v = kv.split("=", 1)
        outputs[k] = v
        full = v if os.path.isabs(v) else os.path.join(pdir(a.slug), v)
        if not re.match(r"^[a-z]+://", v) and not os.path.exists(full):
            missing.append(v)
    n.update(status="done", outputs=outputs, finished=iso(now()), question=None, options=[], reason=None)
    if a.note:
        n["note"] = a.note
    log(st, "done", step=a.step, outputs=outputs)
    schedule_delayed(st, cfg)
    save(st)
    emit({"done": a.step, "outputs": outputs, "missing_files": missing})


def cmd_ask(a):
    st = load(a.slug)
    n = node(st, a.step)
    opts = [o.strip() for o in (a.options or "").split("|") if o.strip()]
    n.update(status="blocked", question=a.question, options=opts)
    log(st, "blocked", step=a.step, question=a.question)
    save(st)
    emit({"blocked": a.step, "question": a.question, "options": opts})


def cmd_answer(a):
    st = load(a.slug)
    n = node(st, a.step)
    if n["status"] != "blocked":
        die(f"{a.step} is {n['status']}, not blocked")
    n["answers"].append({"q": n["question"], "a": a.answer, "at": iso(now())})
    n.update(status="pending", question=None, options=[])
    log(st, "answered", step=a.step, answer=a.answer)
    save(st)
    emit({"answered": a.step, "answers": n["answers"]})


def cmd_fail(a):
    st = load(a.slug)
    n = node(st, a.step)
    n.update(status="failed", reason=a.reason)
    log(st, "failed", step=a.step, reason=a.reason)
    save(st)
    emit({"failed": a.step, "reason": a.reason})


def cmd_retry(a):
    st = load(a.slug)
    n = node(st, a.step)
    if is_gate(a.step) or n["status"] not in ("failed", "blocked", "done", "running"):
        die(f"{a.step} is {n['status']}; nothing to retry")
    n.update(status="pending", question=None, options=[], reason=None)
    log(st, "retry", step=a.step)
    save(st)
    emit({"retry": a.step})


def cmd_reset(a):
    st = load(a.slug)
    node(st, a.step)
    names = reset_nodes(st, [a.step] + downstream(st, a.step))
    log(st, "reset", step=a.step, affected=names)
    save(st)
    emit({"reset": names})


def cmd_gate(a):
    st = load(a.slug)
    if not is_gate(a.gate):
        die(f"'{a.gate}' is not a gate. Gates: {', '.join(n for n in graph(st) if is_gate(n))}")
    g = node(st, a.gate)
    if g["status"] != "pending" or not deps_ok(st, a.gate):
        die(f"{a.gate} is not waiting for a decision (status {g['status']})")
    if a.decision == "approve":
        g.update(status="approved", note=a.note, at=iso(now()))
        log(st, "approved", gate=a.gate, note=a.note)
        save(st)
        emit({"approved": a.gate, "note": a.note})
        return
    if not a.note:
        die("a rejection needs --note saying what to change; the agent reads it")
    redo = a.redo or GATE_FEEDS[a.gate]
    if a.gate not in downstream(st, redo):
        die(f"'{redo}' does not feed {a.gate}")
    st["steps"][redo]["feedback"].append({"from": a.gate, "note": a.note, "at": iso(now())})
    names = reset_nodes(st, [redo] + downstream(st, redo))
    log(st, "rejected", gate=a.gate, redo=redo, note=a.note, affected=names)
    save(st)
    emit({"rejected": a.gate, "redo": redo, "reset": names})


def cmd_platforms(a):
    st = load(a.slug)
    platforms = parse_platforms(a.platforms)
    if "instagram" in platforms and st["steps"]["shorts"]["status"] == "skipped":
        die("Instagram posts the Shorts as Reels, and this project skipped shorts")
    user_skip = st["inputs"].get("skip") or []
    changed, kept = [], []
    for p, steps in PLATFORM_STEPS.items():
        for name in steps:
            n = st["steps"][name]
            if p in platforms and n["status"] == "skipped" and name not in user_skip:
                n.update(status="pending", outputs={}, question=None, options=[], reason=None)
                changed.append(f"{name}: pending")
            elif p not in platforms and n["status"] in ("pending", "blocked", "failed"):
                n["status"] = "skipped"
                changed.append(f"{name}: skipped")
            elif p not in platforms and n["status"] in ("running", "done"):
                kept.append(f"{name} is already {n['status']}")
    st["inputs"]["platforms"] = platforms
    log(st, "platforms", platforms=platforms, changed=changed)
    save(st)
    emit({"platforms": platforms, "changed": changed, "already_ran": kept})


ICON = {"pending": "·", "running": "▶", "done": "✓", "blocked": "?", "failed": "✗",
        "skipped": "-", "approved": "✓", "rejected": "✗"}


def cmd_status(a):
    st = load(a.slug)
    if a.json:
        emit(st)
        return
    print(f"{st['slug']}  ({st['mode']}, style: {st['inputs'].get('style')}, "
          f"to: {' + '.join(st['inputs'].get('platforms', ['youtube']))})")
    for name in graph(st):
        n = node(st, name)
        extra = ""
        if n["status"] == "blocked":
            extra = f"  Q: {n.get('question')}"
        elif n["status"] == "failed":
            extra = f"  {n.get('reason')}"
        elif n.get("not_before") and n["status"] == "pending":
            extra = f"  after {n['not_before']}"
        elif n["status"] == "approved" and n.get("note"):
            extra = f"  {n['note']}"
        print(f"  {ICON.get(n['status'], ' ')} {name:<14} {n['status']}{extra}")


def cmd_list(a):
    if not os.path.isdir(PROJECTS):
        emit([])
        return
    rows = []
    for slug in sorted(os.listdir(PROJECTS)):
        p = os.path.join(PROJECTS, slug, "state.json")
        if not os.path.exists(p):
            continue
        with open(p) as f:
            st = migrate(json.load(f))
        names = list(graph(st))
        done = sum(1 for n in names if satisfied(st, n))
        attention = [n for n in names if node(st, n)["status"] in ("blocked", "failed")]
        rows.append({"slug": slug, "mode": st["mode"], "platforms": st["inputs"]["platforms"],
                     "progress": f"{done}/{len(names)}",
                     "needs_attention": attention, "updated": st.get("updated")})
    emit(rows)


def main():
    p = argparse.ArgumentParser(description="State engine for the YouTube agent team.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new")
    s.add_argument("slug")
    s.add_argument("--mode", choices=list(PIPELINES), required=True)
    s.add_argument("--source")
    s.add_argument("--topic")
    s.add_argument("--style")
    s.add_argument("--length", type=float, help="target minutes (faceless)")
    s.add_argument("--notes")
    s.add_argument("--skip", help="comma-separated steps to skip, e.g. shorts,research")
    s.add_argument("--platforms", help="youtube, instagram, or both (default: config platforms.default)")
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("platforms")
    s.add_argument("slug")
    s.add_argument("platforms", help="youtube, instagram, or both")
    s.set_defaults(fn=cmd_platforms)

    for name, fn in (("next", cmd_next), ("list", cmd_list)):
        s = sub.add_parser(name)
        if name != "list":
            s.add_argument("slug")
        s.set_defaults(fn=fn)

    s = sub.add_parser("status")
    s.add_argument("slug")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    for name, fn in (("brief", cmd_brief), ("start", cmd_start), ("retry", cmd_retry), ("reset", cmd_reset)):
        s = sub.add_parser(name)
        s.add_argument("slug")
        s.add_argument("step")
        s.set_defaults(fn=fn)

    s = sub.add_parser("done")
    s.add_argument("slug")
    s.add_argument("step")
    s.add_argument("--out", action="append", help="key=path, relative to the project folder")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_done)

    s = sub.add_parser("ask")
    s.add_argument("slug")
    s.add_argument("step")
    s.add_argument("--question", required=True)
    s.add_argument("--options", help="'a|b|c'")
    s.set_defaults(fn=cmd_ask)

    s = sub.add_parser("answer")
    s.add_argument("slug")
    s.add_argument("step")
    s.add_argument("--answer", required=True)
    s.set_defaults(fn=cmd_answer)

    s = sub.add_parser("fail")
    s.add_argument("slug")
    s.add_argument("step")
    s.add_argument("--reason", required=True)
    s.set_defaults(fn=cmd_fail)

    s = sub.add_parser("gate")
    s.add_argument("slug")
    s.add_argument("gate")
    s.add_argument("decision", choices=["approve", "reject"])
    s.add_argument("--note")
    s.add_argument("--redo", help="step to send back to (default: the step that feeds the gate)")
    s.set_defaults(fn=cmd_gate)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
