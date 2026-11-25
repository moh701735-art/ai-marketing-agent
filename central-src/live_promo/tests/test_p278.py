# -*- coding: utf-8 -*-
import importlib.util, os, subprocess, sys, tempfile, unittest, re
H = os.path.dirname(os.path.abspath(__file__)); MOD = os.path.dirname(H); P = os.path.join(os.path.dirname(MOD), "ops", "p279-live-create-probe-v3.py.txt")
def load(name, p):
    s = importlib.util.spec_from_file_location(name, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
tool = load("cprobe2", os.path.join(MOD, "ops", "tt_live_create_probe.py"))
rd = lambda p: open(p, encoding="utf-8").read()
def res(msg): return {"ok": False, "error": {"class": "bad_request", "platform_code": 40002, "message": msg}}
LST = ["TRAFFIC", "APP_PROMOTION", "WEB_CONVERSIONS", "SHOP_PURCHASES", "LEAD_GENERATION", "REACH", "VIDEO_VIEWS", "ENGAGEMENT", "RF_REACH", "RF_ENGAGEMENT", "RF_APP_INSTALL", "PRODUCT_SALES"]


class Parse(unittest.TestCase):
    def test_formats(self):
        fmts = ["[bad_request] platform_code 40002: objective_type: not a valid value; allowed: " + ", ".join(LST),
                "objective_type: Must be one of the allowed values: ['" + "', '".join(LST) + "']",
                'objective_type: invalid. allowed values: ["' + '","'.join(LST) + '"]',
                "Not a valid value. Allowed: (" + " | ".join(LST) + ")",
                "not a valid choice; allowed:\n" + "\n".join("- " + x for x in LST),
                "objective_type: PROBE_INVALID_OBJECTIVE is not allowed; allowed: " + ", ".join(LST)]
        for f in fmts:
            self.assertEqual(tool.parse(res(f))["allowed"], LST, f)

    def test_digits_in_tokens_and_dedup(self):
        r = tool.parse(res("allowed: A1_B2, A1_B2, XYZ, PROBE_INVALID_OBJECTIVE, ab_cd")); self.assertEqual(r["allowed"], ["A1_B2", "XYZ"])

    def test_no_allowed_word_falls_back_to_all_tokens(self):
        r = tool.parse(res("bad value, expected one of TRAFFIC, REACH")); self.assertEqual(r["allowed"], [])
        out = tool.report(r); self.assertIn("ALL UPPER-CASE TOKENS FOUND ANYWHERE IN THE MESSAGE (2): TRAFFIC, REACH", out); self.assertIn("T01 T R A F F I C", out)

    def test_report_one_per_line_and_spaced(self):
        out = tool.report(tool.parse(res("allowed: ENGAGEMENT, TRAFFIC")))
        self.assertIn("01 ENGAGEMENT | E N G A G E M E N T", out); self.assertIn("02 TRAFFIC | T R A F F I C", out)
        self.assertIn("LIVE/ENGAGEMENT-LIKE OBJECTIVES: ENGAGEMENT", out); self.assertIn("E N G A G E M E N T", out.split("letter-spaced: ")[-1])
        self.assertTrue(all(ord(c) < 128 for c in out)); self.assertFalse(any(l.startswith("WARNING:") for l in out.split("\n")))

    def test_long_message_not_cut_before_parse(self):
        big = "allowed: " + ", ".join("OBJ_%03d" % i for i in range(300)); r = tool.parse(res(big)); self.assertEqual(len(r["allowed"]), 300)

    def test_accepted_warns(self):
        self.assertIn("WARNING: TikTok ACCEPTED", tool.report(tool.parse({"ok": True, "data": {}})))

    def test_guard_unchanged(self):
        c = tool.build_call(); self.assertEqual(c["params"]["objective_type"], "PROBE_INVALID_OBJECTIVE"); self.assertEqual(c["op"], "tiktok.probe_campaign")
        for bad in ("TRAFFIC", "ENGAGEMENT", ""):
            with self.assertRaises(SystemExit): tool.build_call(bad)
        src = rd(os.path.join(MOD, "ops", "tt_live_create_probe.py"))
        for bad in ("access_token", "getpass", "INSERT", "ad_group", "tiktok.create_"): self.assertNotIn(bad, src)
        self.assertIn("v3 / p279", src)


class Patch(unittest.TestCase):
    def mk(self, old="OLD\n", wad=True, tool_present=True):
        d = tempfile.mkdtemp(); os.makedirs(d + "/ops")
        if wad: open(d + "/ops/wa-diagnose.py", "w").write("x=1\n")
        if tool_present: open(d + "/ops/tt-live-create-probe.py", "w").write(old)
        return d
    def run_p(self, d): return subprocess.run([sys.executable, P], env={**os.environ, "P279_BASE": d + "/"}, capture_output=True, text=True)

    def test_apply_backup_idempotent(self):
        d = self.mk(); r = self.run_p(d); self.assertIn("APPLY279_OK", r.stdout, r.stdout + r.stderr)
        self.assertEqual(rd(d + "/ops/tt-live-create-probe.py"), rd(os.path.join(MOD, "ops", "tt_live_create_probe.py"))); self.assertEqual(rd(d + "/ops/tt-live-create-probe.py.pre279"), "OLD\n")
        self.assertIn("changed=0", self.run_p(d).stdout)

    def test_fail_closed(self):
        for kw in ({"wad": False}, {"tool_present": False}):
            d = self.mk(**kw); r = self.run_p(d); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr)
            self.assertFalse(os.path.exists(d + "/ops/tt-live-create-probe.py.pre279"))

    def test_installed_tool_parses(self):
        d = self.mk(); self.run_p(d); m = load("inst", d + "/ops/tt-live-create-probe.py"); self.assertEqual(m.parse(res("allowed: A_B, CCC"))["allowed"], ["A_B", "CCC"])

    def test_oneliner_file(self):
        s = rd(os.path.join(os.path.dirname(os.path.dirname(MOD)), "out", "p279s.txt")); self.assertEqual(s.count("\n"), 1); self.assertTrue(s.startswith("echo '")); self.assertIn("| base64 -d | xz -d | python3 &&", s)
        self.assertNotIn("update.sh", s)


if __name__ == "__main__":
    unittest.main(verbosity=1)


class V3(unittest.TestCase):
    def test_cut_message_flag_and_spaced_lines(self):
        msg = ("x" * 280) + " allowed: ENGAGEMENT, PROBE_IN"; msg = msg[:300].ljust(300, "y")
        out = tool.report(tool.parse(res(msg))); self.assertIn("EXACTLY 300", out); self.assertIn("M01 x x x", out); self.assertIn("M08", out)
        self.assertNotIn("PROBE_IN,", out); self.assertTrue(all(ord(c) < 128 for c in out))
    def test_probe_prefix_tokens_dropped(self):
        r = tool.parse(res("Invalid PROBE_IN list: TRAFFIC, REACH")); self.assertEqual(r["all_tokens"], ["TRAFFIC", "REACH"])
    def test_short_message_no_cut_flag(self): self.assertNotIn("EXACTLY 300", tool.report(tool.parse(res("allowed: A_B"))))
