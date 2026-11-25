# -*- coding: utf-8 -*-
import importlib.util, os, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); MOD = os.path.dirname(H); ROOT = os.path.dirname(os.path.dirname(MOD)); P = os.path.join(os.path.dirname(MOD), "ops", "p282-live-b2-v3.py.txt")
def load(name, p):
    s = importlib.util.spec_from_file_location(name, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
tool = load("b2v2", os.path.join(MOD, "ops", "tt_live_b2.py")); t80 = load("t80", os.path.join(H, "test_p280.py"))
rd = lambda p: open(p, encoding="utf-8").read()
SP = {**t80.SPECS, "tiktok.probe_adgroup": {"write": True, "params": {k: "safe" for k in ("campaign_id", "adgroup_name", "promotion_type", "optimization_goal", "billing_event", "location_ids", "budget", "schedule_start_time", "schedule_end_time", "schedule_type", "gender")}}}


class Needs(t80.FakeWad):
    """Broker-side validation: يرفض بـ«missing param» لين تكتمل المعاملات الإلزامية، بعدها تيك توك يرفض القيمة الغلط بقائمة allowed"""
    REQ = ("location_ids", "budget", "schedule_start_time", "schedule_end_time")
    def broker(self, env, ctx, acct, calls):
        c = calls[0]
        if c["op"] == "tiktok.probe_adgroup":
            self.calls.append((c["op"], c["params"]))
            for k in self.REQ:
                if k not in c["params"]: return [t80.err("missing param: " + k, "invalid_params", None)]
            return [t80.err("promotion_type: not valid; allowed: LIVE, VIDEO_VIEWS, FOLLOWERS, PRB_BA")]
        return super().broker(env, ctx, acct, calls)


class V2(unittest.TestCase):
    def test_autofill_then_lists(self):
        w = Needs(specs=SP); o = t80.go(w)
        self.assertIn("autofilled required params: location_ids, budget, schedule_start_time, schedule_end_time", o)
        fb = o.split("FINAL BLOCK")[1]; self.assertIn("adgroup_all (3 values", fb); self.assertIn("F|all|01|x_LIVE_x", fb); self.assertIn("F|all|03|x_FOLLOWERS_x", fb)
        for op, p in w.calls:
            if op == "tiktok.probe_adgroup": self.assertIn("PRB_BAD", p.values())
        self.assertFalse(any(l.startswith("WARNING") for l in o.split("\n"))); self.assertTrue(all(ord(c) < 128 for c in o))

    def test_dummy_values_are_valid_shapes(self):
        d = tool.dummies(); self.assertEqual(d["location_ids"], ["99237"]); self.assertRegex(d["schedule_start_time"], r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$"); self.assertLess(d["schedule_start_time"], d["schedule_end_time"])

    def test_unknown_missing_param_stops_and_reports(self):
        class W2(Needs):
            REQ = ("totally_unknown_param",)
        w = W2(specs=SP); o = t80.go(w); self.assertIn("missing param: totally_unknown_param", o); self.assertNotIn("autofilled", o)
        self.assertLessEqual(sum(1 for c in w.calls if c[0] == "tiktok.probe_adgroup"), 5)                 # لا حلقة لانهائية

    def test_param_not_in_catalog_not_forced(self):
        sp = {**SP}; sp["tiktok.probe_adgroup"] = {"write": True, "params": {k: "safe" for k in ("campaign_id", "adgroup_name", "promotion_type", "optimization_goal", "billing_event", "budget")}}
        w = Needs(specs=sp); o = t80.go(w); self.assertNotIn("autofilled", o); self.assertIn("missing param: location_ids", o)

    def test_sentinel_never_dropped_and_no_forbidden_ops(self):
        src = rd(os.path.join(MOD, "ops", "tt_live_b2.py")); self.assertRegex(src, r"v\d / p28\d"); self.assertIn("probe lost its invalid value", src)
        for bad in ("create_ad", "getpass", "access_token"): self.assertNotIn(bad, src)

    def test_short_messages_no_spaced_flood(self):
        o = t80.go(Needs(specs=SP)); self.assertLess(o.count("   M0"), 8)


class Patch(unittest.TestCase):
    def mk(self, old="OLD\n", wad=True, cat="# p277\n"):
        d = tempfile.mkdtemp(); os.makedirs(d + "/ops"); os.makedirs(d + "/broker/app")
        if wad: open(d + "/ops/wa-diagnose.py", "w").write("x=1\n")
        open(d + "/broker/app/catalog.py", "w").write(cat); open(d + "/ops/tt-live-b2.py", "w").write(old); return d
    def run_p(self, d): return subprocess.run([sys.executable, P], env={**os.environ, "P282_BASE": d + "/"}, capture_output=True, text=True)
    def test_apply(self):
        d = self.mk(); r = self.run_p(d); self.assertIn("APPLY282_OK", r.stdout, r.stdout + r.stderr); self.assertIn("PROBE-LIVE-DELETE-ME", rd(d + "/ops/tt-live-b2.py")); self.assertEqual(rd(d + "/ops/tt-live-b2.py.pre282"), "OLD\n"); self.assertIn("changed=0", self.run_p(d).stdout)
        d = self.mk(wad=False); self.assertIn("PATCH FAIL (nothing written)", self.run_p(d).stdout + self.run_p(d).stderr)
    def test_oneliner(self):
        s = rd(os.path.join(ROOT, "out", "p282s.txt")); self.assertEqual(s.count("\n"), 1); self.assertIn("python3 ops/tt-live-b2.py", s); self.assertNotIn("update.sh", s)


if __name__ == "__main__":
    unittest.main(verbosity=1)


class V3(unittest.TestCase):
    def test_no_utcnow_warning_and_wrapped_tokens(self):
        src = rd(os.path.join(MOD, "ops", "tt_live_b2.py")); self.assertNotIn("utcnow", src); self.assertEqual(tool.wrap("LIVE"), "x_LIVE_x")
    def test_cut_list_flag_kept(self):
        msg = ("allowed: " + ", ".join("OBJ_%02d" % i for i in range(60)))[:300]; w = Needs(specs=SP); w.REQ = ()
        o = []; ww = t80.FakeWad(specs=SP, adg={"adgroup_promotion_type": t80.err(msg)}); tool.run(ww, None, "c", "7593807340588253185", out=o.append); self.assertIn("CUT-AT-300", "\n".join(o))
