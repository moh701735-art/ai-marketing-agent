import importlib.util, io, os, re, sys, unittest, contextlib, json
H = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("wad", os.path.join(H, "..", "wa_diagnose.py")); W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)

NATIVE = {"adgroup_id": "11", "campaign_id": "1", "promotion_type": "LEAD_GEN_CLICK_TO_SOCIAL_MEDIA_APP_MESSAGE", "messaging_app_type": "WHATSAPP", "optimization_goal": "CONVERSATION", "optimization_event": "MESSAGE",
          "message_event_set_id": "CTM123", "billing_event": "OCPM", "phone_number": "9647701234567", "messaging_app_account_id": "9647701234567", "access_token": "SHOULD-NEVER-PRINT", "billing_event_x": 1}
SALES = {"adgroup_id": "22", "campaign_id": "2", "promotion_type": "WEBSITE", "optimization_goal": "CONVERT", "billing_event": "OCPM", "landing_page_url": "https://wa.me/9647701234567?text=hello", "pixel_id": "999"}
TRAF = {"adgroup_id": "33", "campaign_id": "3", "promotion_type": "WEBSITE", "optimization_goal": "CLICK", "billing_event": "CPC", "landing_page_url": "https://wa.me/9647701234567"}


class Pure(unittest.TestCase):
    def test_mask(self):
        self.assertNotIn("7701234567", W.mask_phone("9647701234567")); self.assertTrue(W.mask_phone("9647701234567").endswith("567"))
        u = W.mask_url("https://wa.me/9647701234567?text=secret+words"); self.assertIn("WHATSAPP_LINK", u); self.assertNotIn("7701234567", u); self.assertNotIn("secret", u)
        self.assertEqual(W.mask_url(""), "N/A"); self.assertIn("OTHER", W.mask_url("https://example.com/p?x=1")); self.assertNotIn("x=1", W.mask_url("https://example.com/p?x=1"))

    def test_pick_hides_secrets_and_unlisted_keys(self):
        p = W.pick(NATIVE, W.ADG_KEYS); self.assertNotIn("access_token", p); self.assertNotIn("billing_event_x", p); self.assertEqual(p["phone_number"][-3:], "567"); self.assertNotIn("7701234567", json.dumps(p))
        self.assertIn("WHATSAPP_LINK", W.pick(SALES, W.ADG_KEYS)["landing_page_url"])

    def test_classify(self):
        self.assertEqual(W.classify_adgroup(NATIVE)[0], "NATIVE_WHATSAPP")
        self.assertEqual(W.classify_adgroup(SALES, {"objective_type": "WEB_CONVERSIONS"})[0], "SALES_WEB_CONVERSIONS_WA_LINK")
        self.assertEqual(W.classify_adgroup(TRAF, {"objective_type": "TRAFFIC"})[0], "TRAFFIC_CLICK_WA_LINK")
        self.assertEqual(W.classify_adgroup({"promotion_type": "WEBSITE", "optimization_goal": "CONVERT"}, {"objective_type": "WEB_CONVERSIONS"})[0], "SALES_WEB_CONVERSIONS")
        self.assertEqual(W.classify_adgroup({"promotion_type": "LEAD_GEN_CLICK_TO_TT_DIRECT_MESSAGE"})[0], "TIKTOK_DM"); self.assertEqual(W.classify_adgroup({})[0], "UNKNOWN")
        p, n = W.classify_adgroup({**NATIVE, "optimization_goal": "CLICK", "message_event_set_id": None}); self.assertEqual(p, "NATIVE_WHATSAPP"); self.assertTrue(any("ليس CONVERSATION" in x for x in n) and any("message_event_set_id" in x for x in n))

    def test_eligibility_only_from_evidence(self):
        self.assertEqual(W.eligibility(True, [{"x": 1}], 2, [])[0], "WHATSAPP_CONVERSATION_READY"); self.assertEqual(W.eligibility(True, [{"x": 1}], 0, [])[0], "UNKNOWN_READY_TO_TEST")
        self.assertEqual(W.eligibility(True, [], 0, [])[0], "NOT_READY_NO_EVENT_SET"); self.assertEqual(W.eligibility(False, [], 0, ["bad_request"])[0], "UNKNOWN")

    def test_build_params_only_known(self):
        self.assertEqual(W.build_params({"params": {"page": "int"}}, {"page": 1, "bogus": 2}), {"page": 1}); self.assertEqual(W.build_params(None, {"a": 1}), {"a": 1})


class Main(unittest.TestCase):
    def run_main(self, ops_seen, adgroups=None, **over):
        calls = []
        specs = {"tiktok.read_advertiser": {"write": False, "params": {}}, "tiktok.read_message_event_set": {"write": False, "params": {"messaging_app_account_id": "id*", "messaging_app_type": "enum*"}}, "tiktok.read_campaigns": {"write": False, "params": {"page": "int", "page_size": "int"}},
                 "tiktok.read_adgroups": {"write": False, "params": {"campaign_ids": "x", "page_size": "int"}}, "tiktok.read_report": {"write": False, "params": {"metrics": "x"}}, "tiktok.launch_spark": {"write": True, "params": {}}}
        camps = [{"campaign_id": "1", "campaign_name": "wa", "objective_type": "LEAD_GENERATION", "create_time": "2026-11-20"}, {"campaign_id": "2", "campaign_name": "sales", "objective_type": "WEB_CONVERSIONS", "create_time": "2026-11-21"}]
        ags = adgroups if adgroups is not None else [NATIVE, SALES]
        def fake_broker(env, ctx, acct, cs):
            out = []
            for c in cs:
                calls.append((c["op"], acct)); ops_seen.append(c["op"]); d = {"data": None}
                if c["op"] == "tiktok.read_advertiser": d = {"data": {"list": [{"name": "adv", "status": "STATUS_ENABLE", "currency": "IQD", "country": "IQ", "access_token": "LEAK"}]}}
                elif c["op"] == "tiktok.read_message_event_set":
                    assert c["params"].get("messaging_app_type") == "WHATSAPP" and c["params"].get("messaging_app_account_id") == "9647701234567", c["params"]
                    d = {"data": {"list": [{"event_set_id": "CTM123", "messaging_app_type": "WHATSAPP", "phone_number": "9647701234567", "status": "ACTIVE", "api_secret": "LEAK"}]}}
                elif c["op"] == "tiktok.read_campaigns": d = {"data": {"list": camps}}
                elif c["op"] == "tiktok.read_adgroups": d = {"data": {"list": ags}}
                elif c["op"] == "tiktok.read_report": d = {"data": {"list": [{"dimensions": {"campaign_id": "1"}, "metrics": {"spend": "5", "clicks": "10", "conversion": "0"}}]}} if c["label"] == "rep_base" else {"error": {"message": "invalid metric"}}
                out.append({"label": c["label"], "op": c["op"], "ok": ("error" not in d), **d})
            return out
        W.broker, W.introspect = fake_broker, lambda env: specs
        W.psql = lambda env, sql: (["t-1"] if "core.tenants" in sql else ["CTX-SECRET-xyz"] if "job_contexts" in sql else ["tiktok/adgroup/create|ok|3", "tiktok/adgroup/create|bad_request|1"] if "api_call_log" in sql else [])
        out = io.StringIO()
        with contextlib.redirect_stdout(out): W.main()
        return out.getvalue(), calls

    def test_read_only_single_account_no_leaks(self):
        seen = []; o, calls = self.run_main(seen)
        self.assertTrue(set(seen) <= {"tiktok.read_advertiser", "tiktok.read_message_event_set", "tiktok.read_campaigns", "tiktok.read_adgroups", "tiktok.read_ads", "tiktok.read_ad", "tiktok.read_report"}, seen)
        self.assertEqual({a for _, a in calls}, {"7593807340588253185"}); self.assertIn("tiktok.read_message_event_set", seen)
        for leak in ("LEAK", "CTX-SECRET", "SHOULD-NEVER-PRINT", "7701234567"): self.assertNotIn(leak, o, leak)
        self.assertIn("REDACTED", o); self.assertIn("WHATSAPP_LINK", o)

    def test_sections_paths_and_eligibility(self):
        o, _ = self.run_main([])
        for frag in ("PATH=NATIVE_WHATSAPP", "PATH=SALES_WEB_CONVERSIONS_WA_LINK", "WHATSAPP_CONVERSATION_READY", "[5b]", "FAIL", "رابط واتساب كوجهة موقع", "التوصيف الرسمي المطلوب", "N/A", "OK n=1"):
            self.assertIn(frag, o)
        self.assertIn('"NATIVE_WHATSAPP": 1', o)

    def test_write_ops_listed_but_never_called(self):
        seen = []; os.environ["SA_CATALOG"] = "1"
        try: o, _ = self.run_main(seen)
        finally: os.environ.pop("SA_CATALOG")
        self.assertIn("W tiktok.launch_spark", o); self.assertNotIn("tiktok.launch_spark", seen)

    def test_no_adgroups_is_na_not_invented(self):
        o, _ = self.run_main([], adgroups=[]); self.assertIn("N/A", o); self.assertNotIn("PATH=NATIVE", o); self.assertNotIn("WHATSAPP_CONVERSATION_READY", o)

    def test_tool_contains_no_write_op_calls(self):
        src = open(os.path.join(H, "..", "wa_diagnose.py"), encoding="utf-8").read()
        for w in ("create_campaign", "create_adgroup", "create_ad", "set_campaign_status", "launch_spark", "update_", "activate"): self.assertNotRegex(src.replace('"create_adgroup" in ep', ""), r'"op": "tiktok\.[a-z_]*%s' % w)


if __name__ == "__main__":
    unittest.main(verbosity=1)
