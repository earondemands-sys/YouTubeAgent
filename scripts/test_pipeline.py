#!/usr/bin/env python3
"""test_pipeline.py - drive both pipelines end to end the way the Director does, with fake agents.

    python3 scripts/test_pipeline.py
"""
import json, os, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.join(HERE, "pipeline.py")


class Engine:
    def __init__(self, gates=None, delay=48):
        self.tmp = tempfile.mkdtemp(prefix="yta-test-")
        self.projects = os.path.join(self.tmp, "projects")
        self.config = os.path.join(self.tmp, "channel.json")
        with open(self.config, "w") as f:
            json.dump({"gates": gates or {}, "analytics_delay_hours": delay,
                       "defaults": {"recorded_style": "clean-talking-head", "faceless_style": "storytime"}}, f)
        self.source = os.path.join(self.tmp, "raw.mp4")
        open(self.source, "w").close()

    def run(self, *args, ok=True):
        env = dict(os.environ, YTA_PROJECTS=self.projects, YTA_CONFIG=self.config)
        r = subprocess.run([sys.executable, PIPELINE, *args], capture_output=True, text=True, env=env)
        if ok and r.returncode != 0:
            raise AssertionError(f"{' '.join(args)} failed: {r.stderr}")
        if not ok:
            assert r.returncode != 0, f"{' '.join(args)} should have failed"
            return r.stderr
        return json.loads(r.stdout) if r.stdout.strip().startswith(("{", "[")) else r.stdout

    def fake_agent(self, slug, step):
        """What an agent does: write a file into the project, report done."""
        self.run("start", slug, step)
        brief = self.run("brief", slug, step)
        path = f"work/{step}.txt"
        with open(os.path.join(brief["project_dir"], path), "w") as f:
            f.write(json.dumps(brief))
        self.run("done", slug, step, "--out", f"{step}={path}")
        return brief

    def drive(self, slug, decide=lambda gate: ("approve", "ok")):
        """The Director's loop. Returns the order steps ran in, as rounds."""
        rounds = []
        for _ in range(50):
            nx = self.run("next", slug)
            if nx["complete"] or (not nx["run"] and not nx["gates"] and nx["waiting"]):
                return rounds, nx
            if nx["run"]:
                rounds.append(sorted(nx["run"]))
                for step in nx["run"]:
                    self.fake_agent(slug, step)
            for g in nx["gates"]:
                decision, note = decide(g["gate"])
                self.run("gate", slug, g["gate"], decision, "--note", note)
        raise AssertionError("pipeline did not settle in 50 rounds")


class TestPipeline(unittest.TestCase):

    def test_recorded_end_to_end_with_parallel_rounds(self):
        e = Engine(delay=0)
        e.run("new", "my-vid", "--mode", "recorded", "--source", e.source)
        rounds, nx = e.drive("my-vid")
        self.assertTrue(nx["complete"])
        self.assertEqual(rounds[0], ["editor"])
        self.assertEqual(rounds[1], ["packaging", "remotion"])      # parallel after the cuts gate
        self.assertEqual(rounds[2], ["shorts"])                      # runs while the user decides the package
        self.assertEqual(rounds[3], ["seo", "thumbnail"])            # parallel after the package gate
        self.assertEqual(rounds[-1], ["analytics"])

    def test_faceless_end_to_end(self):
        e = Engine(delay=0)
        e.run("new", "faceless-vid", "--mode", "faceless", "--topic", "iPhone 18 leaks", "--length", "8")
        rounds, nx = e.drive("faceless-vid")
        self.assertTrue(nx["complete"])
        self.assertEqual(rounds[0], ["research"])
        self.assertEqual(rounds[2], ["broll", "packaging", "voiceover"])
        st = e.run("status", "faceless-vid", "--json")
        self.assertEqual(st["inputs"]["style"], "storytime")          # default from config

    def test_blocked_question_reaches_agent_on_rerun(self):
        e = Engine()
        e.run("new", "q", "--mode", "recorded", "--source", e.source)
        e.run("start", "q", "editor")
        e.run("ask", "q", "editor", "--question", "Which language?", "--options", "Telugu|English")
        nx = e.run("next", "q")
        self.assertEqual(nx["blocked"][0]["options"], ["Telugu", "English"])
        self.assertEqual(nx["run"], [])
        e.run("answer", "q", "editor", "--answer", "Telugu")
        self.assertEqual(e.run("next", "q")["run"], ["editor"])
        brief = e.fake_agent("q", "editor")
        self.assertEqual(brief["answers"][0]["a"], "Telugu")
        self.assertEqual(brief["attempt"], 2)

    def test_gate_reject_sends_feedback_back_and_resets_downstream(self):
        e = Engine()
        e.run("new", "r", "--mode", "recorded", "--source", e.source)
        e.fake_agent("r", "editor")
        e.run("gate", "r", "gate:cuts", "reject", "--note", "keep the intro joke")
        self.assertEqual(e.run("next", "r")["run"], ["editor"])
        brief = e.fake_agent("r", "editor")
        self.assertEqual(brief["feedback"][0]["note"], "keep the intro joke")
        self.assertEqual(e.run("next", "r")["gates"][0]["gate"], "gate:cuts")

    def test_publish_reject_with_redo_targets_owner(self):
        e = Engine(gates={"cuts": "auto", "package": "auto"})
        e.run("new", "p", "--mode", "recorded", "--source", e.source)
        for _ in range(10):
            nx = e.run("next", "p")
            if nx["gates"]:
                break
            for s in nx["run"]:
                e.fake_agent("p", s)
        self.assertEqual(nx["gates"][0]["gate"], "gate:publish")
        out = e.run("gate", "p", "gate:publish", "reject", "--note", "thumbnail text unreadable", "--redo", "thumbnail")
        self.assertEqual(out["reset"], ["thumbnail", "qa", "gate:publish", "publish", "analytics"])
        st = e.run("status", "p", "--json")
        self.assertEqual(st["steps"]["seo"]["status"], "done")         # untouched
        self.assertEqual(st["gates"]["gate:package"]["status"], "approved")

    def test_auto_gates_never_ask(self):
        e = Engine(gates={"cuts": "auto", "package": "auto", "publish": "auto"}, delay=0)
        e.run("new", "a", "--mode", "recorded", "--source", e.source)
        asked = []
        rounds, nx = e.drive("a", decide=lambda g: asked.append(g) or ("approve", "x"))
        self.assertTrue(nx["complete"])
        self.assertEqual(asked, [])

    def test_analytics_waits_for_delay(self):
        e = Engine(gates={"cuts": "auto", "package": "auto", "publish": "auto"}, delay=48)
        e.run("new", "w", "--mode", "recorded", "--source", e.source)
        rounds, nx = e.drive("w")
        self.assertFalse(nx["complete"])
        self.assertEqual(nx["waiting"][0]["step"], "analytics")

    def test_skip_removes_step_and_its_gate(self):
        e = Engine(delay=0)
        e.run("new", "s", "--mode", "faceless", "--topic", "x", "--skip", "research,shorts")
        rounds, nx = e.drive("s")
        flat = [s for r in rounds for s in r]
        self.assertNotIn("research", flat)
        self.assertNotIn("shorts", flat)
        self.assertEqual(rounds[0], ["script"])

    def test_guards(self):
        e = Engine()
        e.run("new", "Bad Slug", "--mode", "recorded", "--source", e.source, ok=False)
        e.run("new", "g", "--mode", "recorded", ok=False)                       # no source
        e.run("new", "g", "--mode", "faceless", ok=False)                       # no topic
        e.run("new", "g", "--mode", "recorded", "--source", e.source, "--skip", "gate:cuts", ok=False)
        e.run("new", "g", "--mode", "recorded", "--source", e.source, "--style", "nope", ok=False)
        e.run("new", "g", "--mode", "recorded", "--source", e.source)
        e.run("new", "g", "--mode", "recorded", "--source", e.source, ok=False)  # exists
        e.run("start", "g", "remotion", ok=False)                               # deps not done
        e.run("gate", "g", "gate:cuts", "approve", ok=False)                    # not ready
        e.fake_agent("g", "editor")
        e.run("gate", "g", "gate:cuts", "reject", ok=False)                     # needs a note
        e.run("brief", "g", "gate:cuts", ok=False)

    def test_both_platforms_runs_reels_and_ig_publish(self):
        e = Engine(delay=0)
        out = e.run("new", "b", "--mode", "recorded", "--source", e.source, "--platforms", "both")
        self.assertEqual(out["platforms"], ["youtube", "instagram"])
        rounds, nx = e.drive("b")
        self.assertTrue(nx["complete"])
        self.assertEqual(rounds[3], ["reels", "seo", "thumbnail"])    # captions while SEO and thumbnail run
        self.assertEqual(rounds[4], ["qa"])                            # QA sees the Reels
        self.assertEqual(rounds[5], ["ig-publish", "publish"])        # both platforms post in parallel

    def test_instagram_only_skips_youtube_publish_and_analytics(self):
        e = Engine(delay=0)
        e.run("new", "i", "--mode", "faceless", "--topic", "x", "--platforms", "instagram")
        rounds, nx = e.drive("i")
        self.assertTrue(nx["complete"])
        flat = [s for r in rounds for s in r]
        self.assertNotIn("publish", flat)
        self.assertNotIn("analytics", flat)
        self.assertIn("ig-publish", flat)

    def test_youtube_default_keeps_instagram_out(self):
        e = Engine(delay=0)
        e.run("new", "y", "--mode", "recorded", "--source", e.source)
        rounds, _ = e.drive("y")
        flat = [s for r in rounds for s in r]
        self.assertNotIn("reels", flat)
        self.assertNotIn("ig-publish", flat)

    def test_platforms_ask_and_guards(self):
        e = Engine()
        with open(e.config) as f:
            cfg = json.load(f)
        cfg["platforms"] = {"default": "ask"}
        with open(e.config, "w") as f:
            json.dump(cfg, f)
        self.assertIn("--platforms", e.run("new", "a", "--mode", "recorded", "--source", e.source, ok=False))
        e.run("new", "a", "--mode", "recorded", "--source", e.source, "--platforms", "tiktok", ok=False)
        e.run("new", "a", "--mode", "recorded", "--source", e.source, "--platforms", "instagram",
              "--skip", "shorts", ok=False)                             # Reels are the Shorts

    def test_platforms_command_adds_instagram_later(self):
        e = Engine(gates={"cuts": "auto", "package": "auto"}, delay=0)
        e.run("new", "l", "--mode", "recorded", "--source", e.source, "--platforms", "youtube")
        for _ in range(10):
            nx = e.run("next", "l")
            if nx["gates"]:
                break
            for s in nx["run"]:
                e.fake_agent("l", s)
        out = e.run("platforms", "l", "both")                          # changed their mind at the gate
        self.assertIn("reels: pending", out["changed"])
        e.run("gate", "l", "gate:publish", "approve", "--note", "privacy=private ig=now")
        rounds, nx = e.drive("l")
        self.assertTrue(nx["complete"])
        flat = [s for r in rounds for s in r]
        self.assertLess(flat.index("reels"), flat.index("ig-publish"))
        out = e.run("platforms", "l", "instagram")
        self.assertTrue(any("publish is already done" in k for k in out["already_ran"]))

    def test_old_project_loads_with_new_steps_skipped(self):
        e = Engine()
        e.run("new", "o", "--mode", "recorded", "--source", e.source)
        path = os.path.join(e.projects, "o", "state.json")
        with open(path) as f:
            st = json.load(f)
        for k in ("reels", "ig-publish"):
            del st["steps"][k]
        del st["inputs"]["platforms"]
        with open(path, "w") as f:
            json.dump(st, f)
        st = e.run("status", "o", "--json")
        self.assertEqual(st["steps"]["reels"]["status"], "skipped")
        self.assertEqual(st["inputs"]["platforms"], ["youtube"])
        self.assertEqual(e.run("next", "o")["run"], ["editor"])

    def test_done_reports_missing_files(self):
        e = Engine()
        e.run("new", "m", "--mode", "recorded", "--source", e.source)
        e.run("start", "m", "editor")
        out = e.run("done", "m", "editor", "--out", "edl=work/nope.json")
        self.assertEqual(out["missing_files"], ["work/nope.json"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
