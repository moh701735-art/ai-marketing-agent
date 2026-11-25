# -*- coding: utf-8 -*-
import importlib.util, os, re, subprocess, sys, tempfile, unittest, json
H = os.path.dirname(os.path.abspath(__file__)); MOD = os.path.dirname(H)
def load(name, p):
    s = importlib.util.spec_from_file_location(name, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
tool = load("probe", os.path.join(MOD, "ops", "tt_live_probe.py")); wad = load("wad", os.path.join(os.path.dirname(MOD), "wa_diag", "wa_diagnose.py"))
rd = lambda p: open(p, encoding="utf-8").read()
SPECS = {"tiktok.read_tt_accounts": {"write": False, "path": "/tt/", "params": {"page_size": "int"}}, "tiktok.read_identities": {"write": False, "path": "/identity/get/", "params": {"identity_type": "enum"}}, "tiktok.create_identity": {"write": True, "path": "/x", "params": {}},
         "tiktok.read_video_info": {"write": False, "path": "/v", "params": {}}}


class T(unittest.TestCase):
    def fake(self, id_rows, fail_id=False):
        calls = []
        def bk(cs):
            tool.guard(SPECS, cs); c = cs[0]; calls.append((c["op"], dict(c["params"])))
            if c["op"] == "tiktok.read_advertiser": return [{"ok": True, "data": {"list": [{"name": "boostpro13", "status": "STATUS_ENABLE", "currency": "IQD", "country": "IQ"}]}}]
            if c["op"] == "tiktok.read_campaigns": return [{"ok": True, "data": {"list": [{"objective_type": "LEAD_GENERATION"}, {"objective_type": "LEAD_GENERATION"}, {"objective_type": "WEB_CONVERSIONS"}]}}]
            if c["op"] in ("tiktok.read_identities", "tiktok.read_tt_accounts"):
                if fail_id or (c["op"] == "tiktok.read_identities" and getattr(self, "ext", False)): return [{"ok": False, "error": {"class": "unknown_op", "message": "not in allowlist"}}]
                return [{"ok": True, "data": {"list": id_rows}}]
        return bk, calls

    def test_report_with_live_field(self):
        rows = [{"identity_id": "I1", "identity_type": "AUTH_CODE", "display_name": "golanar_fashion", "can_use_live_ads": True, "can_manage_message": True, "access_token": "SECRET"}]
        bk, calls = self.fake(rows); out = tool.report(tool.gather(wad, bk, SPECS), SPECS)
        self.assertIn("LIVE-RELATED IDENTITY FIELDS: can_use_live_ads", out); self.assertIn("LEAD_GENERATION", out); self.assertNotIn("SECRET", out); self.assertNotIn("access_token", out)
        self.assertIn("IRAQ AVAILABILITY OF LIVE ADS: UNKNOWN", out); self.assertIn("NO CAMPAIGN CREATED", out); self.assertTrue(all(o in ("tiktok.read_advertiser", "tiktok.read_campaigns", "tiktok.read_identities", "tiktok.read_tt_accounts") for o, _ in calls))

    def test_identity_summary_uses_yn_letters_and_dedupes(self):
        rows = [{"identity_id": "aaaa1111bbbb2222", "identity_type": "TT_USER", "can_use_live_ads": True, "can_manage_message": False, "can_push_video": True},
                {"identity_id": "cccc3333dddd4444", "identity_type": "BC_AUTH_TT", "can_use_live_ads": False, "can_manage_message": True, "can_push_video": True}]
        bk, _ = self.fake(rows); out = tool.report(tool.gather(wad, bk, SPECS), SPECS)
        self.assertIn("unique ids: 2, live=Y: 1", out); self.assertIn("id=...bbbb2222 live=Y msg=N push=Y type=TT_USER", out); self.assertIn("id=...dddd4444 live=N msg=Y push=Y type=BC_AUTH_TT", out)

    def test_no_live_fields_is_not_a_verdict(self):
        bk, _ = self.fake([{"identity_id": "I1", "identity_type": "AUTH_CODE"}]); out = tool.report(tool.gather(wad, bk, SPECS), SPECS)
        self.assertIn("NONE FOUND", out); self.assertIn("does not prove", out); self.assertIn("a LIVE promotion op does not exist yet", out)

    def test_identity_read_failure_and_missing_op(self):
        bk, _ = self.fake([], fail_id=True); R = tool.gather(wad, bk, SPECS); self.assertTrue(R["id_errors"]); self.assertIn("identity read error", tool.report(R, SPECS))
        specs = {k: v for k, v in SPECS.items() if "identit" not in k and "tt_account" not in k}; bk, calls = self.fake([{"identity_id": "I9", "identity_type": "AUTH_CODE", "can_use_live_ads": False}])
        R = tool.gather(wad, bk, specs); self.assertEqual(R["id_op"], "tiktok.read_identities"); self.assertIn("known internal op", R["id_src"]); self.assertEqual(len(R["identities"]), 5)       # {} + page_size + 3 identity types
        ids = [p for o, p in calls if o == "tiktok.read_identities"]; self.assertIn({"identity_type": "AUTH_CODE", "page_size": 100}, ids); self.assertTrue(all(set(p) <= {"identity_type", "page_size"} for p in ids))
        out = tool.report(R, specs); self.assertIn("can_use_live_ads", out); self.assertIn("known internal op", out)

    def test_external_catalog_without_identity_op_uses_tt_accounts_and_survives_unknown_op(self):
        specs = {k: v for k, v in SPECS.items() if "identit" not in k}
        bk, calls = self.fake([{"identity_id": "T1", "can_use_live_ads": True}]); R = tool.gather(wad, bk, specs)
        self.assertEqual(R["id_op"], "tiktok.read_tt_accounts"); self.assertTrue(R["identities"]); self.assertTrue(all(o != "tiktok.read_identities" for o, _ in calls))
        self.assertIn("can_use_live_ads", tool.report(R, specs))
        self.ext = True; specs2 = {k: v for k, v in specs.items() if "tt_account" not in k}; bk2, _ = self.fake([]); R2 = tool.gather(wad, bk2, specs2)
        self.assertTrue(any("unknown_op" in e for e in R2["id_errors"])); self.assertIn("identity read error", tool.report(R2, specs2))

    def test_catalog_enums_reported_and_live_like_values_detected(self):
        specs = dict(SPECS); specs["tiktok.create_campaign"] = {"write": True, "path": "/c", "params": {"objective_type": "enum*"}, "enums": {"objective_type": ["TRAFFIC", "LEAD_GENERATION", "LIVE_SHOPPING"], "budget_mode": ["BUDGET_MODE_TOTAL"]}}
        out = tool.report(tool.gather(wad, self.fake([])[0], specs), specs)
        self.assertIn("create_campaign.objective_type = TRAFFIC, LEAD_GENERATION, LIVE_SHOPPING", out); self.assertIn("create_campaign.objective_type=LIVE_SHOPPING", out)
        specs["tiktok.create_campaign"]["enums"]["objective_type"] = ["TRAFFIC"]; out2 = tool.report(tool.gather(wad, self.fake([])[0], specs), specs)
        self.assertIn("NONE (the catalog enums do not list any LIVE value", out2)

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
