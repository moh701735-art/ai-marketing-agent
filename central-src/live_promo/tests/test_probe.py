# -*- coding: utf-8 -*-
import importlib.util, os, re, subprocess, sys, tempfile, unittest, json
H = os.path.dirname(os.path.abspath(__file__)); MOD = os.path.dirname(H)
def load(name, p):
    s = importlib.util.spec_from_file_location(name, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
tool = load("probe", os.path.join(MOD, "ops", "tt_live_probe.py")); wad = load("wad", os.path.join(os.path.dirname(MOD), "wa_diag", "wa_diagnose.py"))
rd = lambda p: open(p, encoding="utf-8").read()
SPECS = {"tiktok.read_identities": {"write": False, "path": "/identity/get/", "params": {"identity_type": "enum"}}, "tiktok.create_identity": {"write": True, "path": "/x", "params": {}},
         "tiktok.read_video_info": {"write": False, "path": "/v", "params": {}}}


class T(unittest.TestCase):
    def fake(self, id_rows, fail_id=False):
        calls = []
        def bk(cs):
            tool.guard(SPECS, cs); c = cs[0]; calls.append((c["op"], dict(c["params"])))
            if c["op"] == "tiktok.read_advertiser": return [{"ok": True, "data": {"list": [{"name": "boostpro13", "status": "STATUS_ENABLE", "currency": "IQD", "country": "IQ"}]}}]
            if c["op"] == "tiktok.read_campaigns": return [{"ok": True, "data": {"list": [{"objective_type": "LEAD_GENERATION"}, {"objective_type": "LEAD_GENERATION"}, {"objective_type": "WEB_CONVERSIONS"}]}}]
            if c["op"] == "tiktok.read_identities":
                if fail_id: return [{"ok": False, "error": {"message": "bad"}}]
                return [{"ok": True, "data": {"list": id_rows}}]
        return bk, calls

    def test_report_with_live_field(self):
        rows = [{"identity_id": "I1", "identity_type": "AUTH_CODE", "display_name": "golanar_fashion", "can_use_live_ads": True, "can_manage_message": True, "access_token": "SECRET"}]
        bk, calls = self.fake(rows); out = tool.report(tool.gather(wad, bk, SPECS), SPECS)
        self.assertIn("LIVE-RELATED IDENTITY FIELDS: can_use_live_ads", out); self.assertIn("LEAD_GENERATION", out); self.assertNotIn("SECRET", out); self.assertNotIn("access_token", out)
        self.assertIn("IRAQ AVAILABILITY OF LIVE ADS: UNKNOWN", out); self.assertIn("NO CAMPAIGN CREATED", out); self.assertTrue(all(o in ("tiktok.read_advertiser", "tiktok.read_campaigns", "tiktok.read_identities") for o, _ in calls))

    def test_no_live_fields_is_not_a_verdict(self):
        bk, _ = self.fake([{"identity_id": "I1", "identity_type": "AUTH_CODE"}]); out = tool.report(tool.gather(wad, bk, SPECS), SPECS)
        self.assertIn("NONE FOUND", out); self.assertIn("does not prove", out); self.assertIn("a LIVE promotion op does not exist yet", out)

    def test_identity_read_failure_and_missing_op(self):
        bk, _ = self.fake([], fail_id=True); R = tool.gather(wad, bk, SPECS); self.assertTrue(R["id_errors"]); self.assertIn("identity read error", tool.report(R, SPECS))
        specs = {k: v for k, v in SPECS.items() if "identit" not in k}; bk, calls = self.fake([{"identity_id": "I9", "identity_type": "AUTH_CODE", "can_use_live_ads": False}])
        R = tool.gather(wad, bk, specs); self.assertEqual(R["id_op"], "tiktok.read_identities"); self.assertIn("known live op", R["id_src"]); self.assertEqual(len(R["identities"]), 4)       # {} + 3 types
        ids = [p for o, p in calls if o == "tiktok.read_identities"]; self.assertIn({"identity_type": "AUTH_CODE", "page_size": 100}, ids); self.assertTrue(all(set(p) <= {"identity_type", "page_size"} for p in ids))
        out = tool.report(R, specs); self.assertIn("can_use_live_ads", out); self.assertIn("known live op", out)

    def test_catalog_dump_option(self):
        def fake(cmd, inp=None): return subprocess.CompletedProcess(cmd, 0, stdout='{"tiktok.read_x": {"write": false, "path": "/", "params": {}}, "tiktok.create_y": {"write": true, "path": "/", "params": {}}}\n', stderr="")
        self.assertIn("tiktok.read_x", tool.catalog_dump("img", fake)[0])

    def test_guard_blocks_writes_and_unknown(self):
        for op in ("tiktok.create_identity", "tiktok.create_campaign", "tiktok.set_campaign_status", "tiktok.launch_spark"):
            with self.assertRaises(SystemExit): tool.guard(SPECS, [{"op": op}])
        tool.guard(SPECS, [{"op": "tiktok.read_identities"}, {"op": "tiktok.read_report"}])

    def test_static_and_ascii(self):
        src = rd(os.path.join(MOD, "ops", "tt_live_probe.py"))
        self.assertIsNone(re.search(r"""["']tiktok\.(create|set_|update|sp_create|launch|pause|activate|appeal|delete)""", src))
        for bad in ("access_token", "getpass", "INSERT", "DELETE "): self.assertNotIn(bad, src)
        bk, _ = self.fake([{"identity_id": "I1", "display_name": "محمد"}]); out = tool.report(tool.gather(wad, bk, SPECS), SPECS)
        self.assertTrue(all(ord(c) < 128 for c in out))

    def test_introspect_uses_no_network_and_fails_soft(self):
        seen = {}
        def fake(cmd, inp=None): seen["c"] = cmd; return subprocess.CompletedProcess(cmd, 0, stdout='{"tiktok.read_identities": {"write": false, "path": "/i", "params": {}}}\n', stderr="")
        self.assertIn("tiktok.read_identities", tool.introspect("img", fake)); self.assertIn("none", seen["c"]); self.assertNotIn("-v", seen["c"])
        def boom(cmd, inp=None): raise FileNotFoundError("docker")
        self.assertIn("error", tool.introspect("img", boom))


if __name__ == "__main__":
    unittest.main(verbosity=1)
