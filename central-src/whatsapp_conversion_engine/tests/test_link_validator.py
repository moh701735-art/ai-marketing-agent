# -*- coding: utf-8 -*-
import importlib.util, os, re, sys, unittest
H = os.path.dirname(os.path.abspath(__file__)); MOD = os.path.dirname(H)
os.environ["WA_PREVIEW_DIR"] = os.path.join(MOD, "campaign_builder"); os.environ["WA_VALIDATOR_DIR"] = os.path.join(MOD, "validator")
sys.path.insert(0, os.environ["WA_PREVIEW_DIR"]); sys.path.insert(0, os.environ["WA_VALIDATOR_DIR"])
import link_validator as lv  # noqa: E402
spec = importlib.util.spec_from_file_location("tool2", os.path.join(MOD, "ops", "wa_link_validator.py")); tool = importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)
wspec = importlib.util.spec_from_file_location("wad", os.path.join(os.path.dirname(MOD), "wa_diag", "wa_diagnose.py")); wad = importlib.util.module_from_spec(wspec); wspec.loader.exec_module(wad)

def rd(p):
    with open(p, encoding="utf-8") as f: return f.read()

def ag(num, es="S1", goal="CONVERSATION", cid="c1", st="ENABLE"):
    return {"adgroup_id": "a" + cid, "campaign_id": cid, "promotion_type": "LEAD_GEN_CLICK_TO_SOCIAL_MEDIA_APP_MESSAGE", "messaging_app_type": "WHATSAPP", "optimization_goal": goal, "messaging_app_account_id": num, "message_event_set_id": es, "operation_status": st}


class Logic(unittest.TestCase):
    def test_linked_ready(self):
        n = lv.collect_numbers([ag("+9647701234319"), ag("+9647701234319", cid="c2")], lambda g: True); self.assertEqual(n["9647701234319"]["groups"], 2)
        a = lv.assess("+9647701234319", n, [{"event_set_id": "S1", "status": "ACTIVE"}], True)
        self.assertEqual((a["link_status"], a["message_event_set"], a["conversation_eligibility"], a["whatsapp_api_status"], a["event_set_status"]), ("LINKED", "FOUND", "READY", "READY", "ACTIVE"))

    def test_not_linked(self):
        n = lv.collect_numbers([ag("+9647701234319")], lambda g: True); a = lv.assess("+9647811317191", n, [], True)
        self.assertEqual((a["link_status"], a["message_event_set"], a["conversation_eligibility"], a["whatsapp_api_status"]), ("NOT_LINKED", "NOT_FOUND", "NOT_READY", "UNKNOWN"))
        self.assertIn("NOT among", lv.root_cause(a, ["+964...319"])); self.assertIn("Messaging Partner", lv.min_action(a)); self.assertIn("forbidden", lv.min_action(a))

    def test_unknown_when_partial(self):
        a = lv.assess("+9647811317191", {}, [{"event_set_id": "S9"}], True)            # event set بدون تاريخ adgroup
        self.assertEqual((a["link_status"], a["conversation_eligibility"], a["whatsapp_api_status"]), ("LINKED", "UNKNOWN", "UNKNOWN"))
        a = lv.assess("+9647701234319", lv.collect_numbers([ag("+9647701234319")], lambda g: True), [{"event_set_id": "S1", "status": "DISABLED"}], True)
        self.assertEqual(a["conversation_eligibility"], "UNKNOWN")                      # حالة غير سليمة ≠ READY

    def test_format_independent_match(self):
        n = lv.collect_numbers([ag("9647701234319")], lambda g: True); self.assertEqual(lv.assess("+9647701234319", n, [], True)["link_status"], "LINKED")

    def test_masking(self):
        self.assertEqual(lv.mask("+9647701234319"), "+964...319"); s = lv.safe_set({"event_set_id": "S1", "messaging_app_account_id": "+9647701234319", "token": "x"})
        self.assertEqual(s["messaging_app_account_id"], "+964...319"); self.assertNotIn("token", s)


class Tool(unittest.TestCase):
    def fake(self, linked, target_sets=None):
        calls = []
        def bk(cs):
            tool.read_only(cs); c = cs[0]; calls.append((c["op"], c["params"].get("messaging_app_account_id")))
            if c["op"] == "tiktok.read_advertiser": return [{"ok": True, "data": {"list": [{"name": "boostpro13", "status": "STATUS_ENABLE", "currency": "IQD"}]}}]
            if c["op"] == "tiktok.read_campaigns": return [{"ok": True, "data": {"list": [{"campaign_id": "c1", "create_time": "2026-11-20"}]}}]
            if c["op"] == "tiktok.read_adgroups": return [{"ok": True, "data": {"list": [ag(linked)]}}]
            if c["op"] == "tiktok.read_message_event_set":
                a = lv.digits(c["params"]["messaging_app_account_id"]); return [{"ok": True, "data": {"event_sets": [{"event_set_id": "S1", "status": "ACTIVE"}] if a == lv.digits(linked) else (target_sets or [])}}]
        return bk, calls

    def test_not_linked_report_is_masked_and_read_only(self):
        bk, calls = self.fake("+9647701234319"); R = tool.gather(wad, bk, "+9647811317191"); out = tool.report(R, "07811317191")
        self.assertIn("LINK_STATUS: NOT_LINKED", out); self.assertIn("CONVERSATION_ELIGIBILITY: NOT_READY", out); self.assertIn("+964...191", out); self.assertIn("+964...319", out)
        self.assertNotIn("07811317191", out); self.assertNotIn("9647811317191", out); self.assertNotIn("9647701234319", out); self.assertIn("EVENT DELIVERY: NOT VERIFIED", out); self.assertIn("NO CAMPAIGN CREATED", out)
        self.assertTrue(all(o.startswith("tiktok.read_") for o, _ in calls)); self.assertTrue(any(a and a.endswith("7811317191") for _, a in calls))

    def test_linked_report(self):
        bk, _ = self.fake("+9647701234319"); out = tool.report(tool.gather(wad, bk, "+9647701234319"), "07701234319")
        self.assertIn("LINK_STATUS: LINKED", out); self.assertIn("CONVERSATION_ELIGIBILITY: READY", out); self.assertIn("MESSAGE_EVENT_SET: FOUND S1", out)

    def test_bad_number_and_no_target(self):
        bk, _ = self.fake("+9647701234319"); R = tool.gather(wad, bk, None)
        self.assertIn("INVALID", tool.report(R, "12")); self.assertIn("none given", tool.report(R, ""))

    def test_static_read_only(self):
        src = rd(os.path.join(MOD, "ops", "wa_link_validator.py"))
        self.assertIsNone(re.search(r"""["']tiktok\.(create|set|update|sp_create|launch|pause|activate|appeal|delete)""", src))
        for bad in ("access_token", "hmac_keys", "getpass", "INSERT", "UPDATE ", "DELETE"): self.assertNotIn(bad, src)
        with self.assertRaises(SystemExit): tool.read_only([{"op": "tiktok.create_campaign"}])
        self.assertNotIn("07811317191", src)                                              # لا رقم كامل بالمستودع
        self.assertTrue(all(ord(c) < 128 for c in tool.report(tool.gather(wad, self.fake("+9647701234319")[0], "+9647811317191"), "07811317191").split("FINAL BLOCK")[1]))


if __name__ == "__main__":
    unittest.main(verbosity=1)
