# -*- coding: utf-8 -*-
import importlib.util, os, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); MOD = os.path.dirname(H); ROOT = os.path.dirname(os.path.dirname(MOD)); P = os.path.join(os.path.dirname(MOD), "ops", "p280-live-b2.py.txt")
def load(name, p):
    s = importlib.util.spec_from_file_location(name, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
tool = load("b2", os.path.join(MOD, "ops", "tt_live_b2.py"))
rd = lambda p: open(p, encoding="utf-8").read()
SPECS = {"tiktok.probe_campaign": {"write": True, "params": {"campaign_name": "text*", "objective_type": "safe*", "budget_mode": "safe", "budget": "num"}},
         "tiktok.probe_adgroup": {"write": True, "params": {"campaign_id": "safe*", "adgroup_name": "text*", "promotion_type": "safe*", "optimization_goal": "safe*", "billing_event": "safe", "budget": "num"}},
         "tiktok.read_campaigns": {"write": False, "params": {"page": "num", "page_size": "num", "campaign_ids": "list"}}}
def err(msg, cls="bad_request", code=40002): return {"ok": False, "error": {"class": cls, "platform_code": code, "message": msg}}


class FakeWad:
    def __init__(self, existing=None, status_seq=("DISABLE",), create=None, adg=None, specs=SPECS):
        self.calls = []; self.existing = existing; self.status_seq = list(status_seq); self.create = create; self.adg = adg or {}; self.specs = specs
    def introspect(self, env): return self.specs
    def broker(self, env, ctx, acct, calls):
        c = calls[0]; self.calls.append((c["op"], c["params"]))
        if c["op"] == "tiktok.read_campaigns":
            ids = c["params"].get("campaign_ids")
            if ids:
                s = self.status_seq.pop(0) if len(self.status_seq) > 1 else self.status_seq[0]
                return [{"ok": True, "data": {"list": [{"campaign_id": ids[0], "operation_status": s, "objective_type": "ENGAGEMENT", "budget_mode": "BUDGET_MODE_INFINITE"}]}}]
            return [{"ok": True, "data": {"list": ([{"campaign_id": self.existing, "campaign_name": tool.NAME}] if self.existing else [])}}]
        if c["op"] == "tiktok.probe_campaign": return [self.create or {"ok": True, "data": {"campaign_id": "1888000000000001"}}]
        if c["op"] == "tiktok.set_campaign_status": return [{"ok": True, "data": {}}]
        if c["op"] == "tiktok.probe_adgroup": return [self.adg.get(c["label"]) or err("promotion_type: not valid; allowed: LIVE, VIDEO_VIEWS, PRB_BA")]
        raise AssertionError("unexpected op " + c["op"])


def go(w, **kw):
    out = []; tool.run(w, None, "ctx", "7593807340588253185", out=out.append, **kw); return "\n".join(out)


class Guards(unittest.TestCase):
    def test_objective_whitelist(self):
        self.assertEqual(tool.campaign_call("ENGAGEMENT", SPECS["tiktok.probe_campaign"])["params"]["objective_type"], "ENGAGEMENT")
        for bad in ("TRAFFIC", "LEAD_GENERATION", "PRB_BAD", "", "LIVE"):
            with self.assertRaises(SystemExit): tool.campaign_call(bad)
        p = tool.campaign_call("RF_ENGAGEMENT", SPECS["tiktok.probe_campaign"])["params"]; self.assertEqual(p["budget_mode"], "BUDGET_MODE_INFINITE"); self.assertNotIn("budget", p)

    def test_adgroup_always_has_invalid(self):
        c = tool.adgroup_call("1888000000000001", ["promotion_type", "optimization_goal"], SPECS["tiktok.probe_adgroup"]); self.assertEqual(c["params"]["promotion_type"], "PRB_BAD"); self.assertEqual(c["op"], "tiktok.probe_adgroup")
        with self.assertRaises(SystemExit): tool.adgroup_call("1888000000000001", ["budget", "name"], SPECS["tiktok.probe_adgroup"])                    # لا حقول معروفة
        with self.assertRaises(SystemExit): tool.adgroup_call("1888000000000001", ["schedule_type"], SPECS["tiktok.probe_adgroup"])                       # الحقل غير موجود بالكتالوج => لا قيمة غلط => رفض
        with self.assertRaises(SystemExit): tool.adgroup_call("abc", ["promotion_type"], SPECS)

    def test_status_only_disable(self):
        c = tool.status_call("1888000000000001"); self.assertEqual(c["params"], {"campaign_ids": ["1888000000000001"], "operation_status": "DISABLE"})
        with self.assertRaises(SystemExit): tool.status_call("1; drop")

    def test_source_has_no_forbidden_ops(self):
        s = rd(os.path.join(MOD, "ops", "tt_live_b2.py"))
        for bad in ("create_ad", "tiktok.create_", "access_token", "getpass", "INSERT", "ENABLE\""): self.assertNotIn(bad, s.replace("tiktok.probe_", "").replace("create_campaign\"", ""))
        self.assertEqual(s.count('"tiktok.set_campaign_status"'), 1)


class Flow(unittest.TestCase):
    def test_happy_path_created_paused_and_lists(self):
        w = FakeWad(); o = go(w)
        ops = [c[0] for c in w.calls]; self.assertEqual(ops.count("tiktok.probe_campaign"), 1); self.assertNotIn("tiktok.set_campaign_status", ops)
        self.assertIn("CREATED just now", o); self.assertIn("operation_status=DISABLE", o)
        self.assertIn("LIVE", o.split("FINAL BLOCK")[1]); self.assertIn("L I V E", o); self.assertNotIn("PRB_BA)", o.split("FINAL BLOCK")[1].split("LIVE/VIEWER")[0].replace("PRB_BA", ""))
        self.assertTrue(all(ord(c) < 128 for c in o)); self.assertFalse(any(l.startswith("WARNING") for l in o.split("\n")))
        for op, p in w.calls:
            if op == "tiktok.probe_adgroup": self.assertIn("PRB_BAD", p.values())

    def test_enabled_by_default_gets_paused_and_verified(self):
        w = FakeWad(status_seq=("ENABLE", "DISABLE")); o = go(w)
        self.assertIn("tiktok.set_campaign_status", [c[0] for c in w.calls]); self.assertIn("operation_status now DISABLE", o); self.assertNotIn("WARNING: campaign not confirmed", o)

    def test_cannot_confirm_pause_warns(self):
        o = go(FakeWad(status_seq=("ENABLE",))); self.assertIn("WARNING: campaign not confirmed PAUSED", o)

    def test_existing_campaign_reused_no_second_create(self):
        w = FakeWad(existing="1888000000000009"); o = go(w); self.assertNotIn("tiktok.probe_campaign", [c[0] for c in w.calls]); self.assertIn("reused existing", o); self.assertIn("1888000000000009", o)

    def test_lb_cid_skips_creation_and_listing(self):
        w = FakeWad(); go(w, cid="1888000000000002"); self.assertEqual([c[0] for c in w.calls if c[0] in ("tiktok.probe_campaign",)], [])

    def test_create_refused_stops(self):
        w = FakeWad(create=err("objective_type: not valid; allowed: PRB_BA, TRAFFIC")); o = go(w)
        self.assertIn("CAMPAIGN NOT CREATED", o); self.assertNotIn("tiktok.probe_adgroup", [c[0] for c in w.calls]); self.assertIn("NO CAMPAIGN CREATED", o)

    def test_missing_probe_ops_stops(self):
        w = FakeWad(specs={}); o = go(w); self.assertIn("NOT IN CATALOG", o); self.assertEqual(w.calls, [])

    def test_adgroup_accepted_warns(self):
        w = FakeWad(adg={"adgroup_promotion_type": {"ok": True, "data": {"adgroup_id": "5"}}}); self.assertIn("WARNING: TikTok ACCEPTED", go(w))

    def test_cut_message_flagged(self):
        msg = ("x" * 250) + " allowed: LIVE, VIDEO_VIEWS, FOLL"; w = FakeWad(adg={"adgroup_all": err(msg[:300].ljust(300, "y"))}); o = go(w); self.assertIn("CUT-AT-300", o); self.assertIn("M01", o)

    def test_tokens_drop_sentinel(self): self.assertEqual(tool.tokens("allowed: LIVE, VIDEO_VIEWS got PRB_BAD PRB_B"), ["LIVE", "VIDEO_VIEWS"])


class Patch(unittest.TestCase):
    def mk(self, wad=True, cat="# p277 ok\n"):
        d = tempfile.mkdtemp(); os.makedirs(d + "/ops"); os.makedirs(d + "/broker/app")
        if wad: open(d + "/ops/wa-diagnose.py", "w").write("x=1\n")
        open(d + "/broker/app/catalog.py", "w").write(cat); return d
    def run_p(self, d): return subprocess.run([sys.executable, P], env={**os.environ, "P280_BASE": d + "/"}, capture_output=True, text=True)
    def test_apply_idempotent_and_fail_closed(self):
        d = self.mk(); r = self.run_p(d); self.assertIn("APPLY280_OK", r.stdout, r.stdout + r.stderr); self.assertEqual(rd(d + "/ops/tt-live-b2.py"), rd(os.path.join(MOD, "ops", "tt_live_b2.py"))); self.assertIn("changed=0", self.run_p(d).stdout)
        for kw in ({"wad": False}, {"cat": "# nothing\n"}):
            d = self.mk(**kw); r = self.run_p(d); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertFalse(os.path.exists(d + "/ops/tt-live-b2.py"))
    def test_oneliner(self):
        s = rd(os.path.join(ROOT, "out", "p280s.txt")); self.assertEqual(s.count("\n"), 1); self.assertIn("| base64 -d | xz -d | python3 && cd /opt/central && python3 ops/tt-live-b2.py", s); self.assertNotIn("update.sh", s)


if __name__ == "__main__":
    unittest.main(verbosity=1)
