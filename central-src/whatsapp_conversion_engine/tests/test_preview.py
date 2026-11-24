# -*- coding: utf-8 -*-
"""اختبارات offline: المحوّل نقي (لا شبكة/كتابة)، الأداة read-only بحارس كود، المفتش يشتغل على شجرة وهمية."""
import importlib.util, json, os, re, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__)); MOD = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(MOD, "campaign_builder"))
import preview as pv  # noqa: E402

TOOL = os.path.join(MOD, "ops", "wa_conv_preview.py")
os.environ["WA_PREVIEW_DIR"] = os.path.join(MOD, "campaign_builder")
spec = importlib.util.spec_from_file_location("tool", TOOL); tool = importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)

REF = {"adgroup_id": "1", "campaign_id": "9", "promotion_type": "LEAD_GEN_CLICK_TO_SOCIAL_MEDIA_APP_MESSAGE", "messaging_app_type": "WHATSAPP", "optimize_goal": "CONVERSATION",
       "optimization_event": "MESSAGE", "billing_event": "OCPM", "bid_type": "BID_TYPE_NO_BID", "budget_mode": "BUDGET_MODE_TOTAL", "phone_region_calling_code": "+964",
       "messaging_app_account_id": "9647701234567", "message_event_set_id": "CTM123", "phone_number": "07701234567"}


def rd(p):
    with open(p, encoding="utf-8") as f: return f.read()


class Phone(unittest.TestCase):
    def test_forms(self):
        for raw in ("07701234567", "9647701234567", "+964 770 123 4567", "00964-770-123-4567", "(0770) 123 4567"):
            n = pv.normalize_phone(raw); self.assertEqual((n["e164"], n["calling_code"], n["region"]), ("+9647701234567", "+964", "IQ"), raw)
        self.assertIn("assumed", pv.normalize_phone("7701234567")["assumed"])
        self.assertEqual(pv.normalize_phone("+966512345678")["region"], "SA")

    def test_bad(self):
        for raw in ("", "abc", "0770", "+1 202 555 0100", "+964 1234567890", "07701234"):
            with self.assertRaises(ValueError, msg=raw): pv.normalize_phone(raw)

    def test_mask_never_full(self):
        m = pv.mask_phone("07701234567"); self.assertNotIn("0123", m); self.assertTrue(m.endswith("567"))
        m = pv.mask_phone("9647701234567"); self.assertEqual(m, "+964…567")


class Preview(unittest.TestCase):
    def test_from_live_reference(self):
        out = pv.WhatsAppConversationPreview(REF, [{"message_event_set_id": "CTM123"}]).build()
        F = out["fields"]
        self.assertEqual(list(F), list(pv.FIELDS))
        self.assertEqual(F["optimization_goal"]["value"], "CONVERSATION"); self.assertEqual(F["optimization_goal"]["source"], pv.SRC_LIVE)   # alias optimize_goal
        self.assertEqual(F["message_event_set_id"]["value"], "CTM123")
        self.assertEqual(F["phone_region_calling_code"]["source"], pv.SRC_LIVE)
        self.assertEqual(F["phone_region_code"]["source"], pv.SRC_DER)            # لم يظهر بالقراءة الحية → مشتق ومُعلَّم
        self.assertTrue(out["no_campaign_created"]); self.assertEqual(out["event_delivery"], "EVENT DELIVERY NOT VERIFIED")
        blob = json.dumps(out); self.assertNotIn("07701234567", blob); self.assertNotIn("9647701234567", blob)

    def test_recorded_defaults_labelled(self):
        F = pv.WhatsAppConversationPreview().build("07701234567")["fields"]
        self.assertEqual(F["optimization_event"]["source"], pv.SRC_REC)
        self.assertEqual(F["message_event_set_id"]["value"], "N/A")
        self.assertEqual(F["messaging_app_account_id"]["value"], "N/A")

    def test_event_set_match_and_ambiguous(self):
        sets = [{"event_set_id": "A", "messaging_app_account_id": "9647701234567"}, {"event_set_id": "B", "messaging_app_account_id": "9647709999999"}]
        F = pv.WhatsAppConversationPreview(None, sets).build("07701234567")["fields"]; self.assertEqual(F["message_event_set_id"]["value"], "A")
        F = pv.WhatsAppConversationPreview(None, sets).build()["fields"]; self.assertEqual(F["message_event_set_id"]["value"], "N/A"); self.assertIn("ambiguous", F["message_event_set_id"]["note"])
        F = pv.WhatsAppConversationPreview(None, [{"id": "ONLY"}]).build()["fields"]; self.assertEqual(F["message_event_set_id"]["value"], "ONLY")

    def test_bad_phone_is_warning_not_crash(self):
        o = pv.WhatsAppConversationPreview().build("12"); self.assertTrue(o["warnings"]); self.assertEqual(o["fields"]["phone_region_code"]["value"], "N/A")

    def test_render_has_event_delivery(self):
        self.assertIn("EVENT DELIVERY NOT VERIFIED", pv.WhatsAppConversationPreview.render(pv.WhatsAppConversationPreview(REF).build()))


class Compare(unittest.TestCase):
    def test_sales_vs_whatsapp(self):
        rows = {r["field"]: r for r in pv.compare(pv.RECORDED_CURRENT["sales"], pv.WhatsAppConversationPreview(REF).build())}
        for k in ("objective_type", "promotion_type", "optimization_goal"): self.assertEqual(rows[k]["verdict"], "DIFF", k)
        for k in ("messaging_app_type", "optimization_event", "message_event_set_id"): self.assertEqual(rows[k]["verdict"], "ONLY_WHATSAPP", k)
        for k in ("billing_event", "bid_type", "budget_mode"): self.assertEqual(rows[k]["verdict"], "SAME", k)
        self.assertEqual(rows["promotion_target_type"]["verdict"], "ONLY_CURRENT")

    def test_traffic(self):
        rows = {r["field"]: r for r in pv.compare(pv.RECORDED_CURRENT["traffic"], pv.WhatsAppConversationPreview(REF).build())}
        self.assertEqual(rows["optimization_goal"]["current"], "CLICK"); self.assertEqual(rows["billing_event"]["verdict"], "DIFF"); self.assertEqual(rows["landing_page_url"]["verdict"], "ONLY_CURRENT")


class ReadOnlyStatic(unittest.TestCase):
    def test_preview_module_is_pure(self):
        src = rd(os.path.join(MOD, "campaign_builder", "preview.py"))
        for bad in ("import socket", "urllib", "requests", "subprocess", "import http", "http.client", "open(", "os.system", "docker"): self.assertNotIn(bad, src, bad)

    def test_tool_has_no_write_ops_and_isolated_network(self):
        src = rd(TOOL)
        self.assertIsNone(re.search(r"""["']tiktok\.(create|set|update|sp_create|launch|pause|activate|appeal|delete)""", src))
        self.assertIn('"--network", "none"', src)                                   # المفتش بلا شبكة
        with self.assertRaises(SystemExit): tool.read_only([{"op": "tiktok.create_campaign"}])
        with self.assertRaises(SystemExit): tool.read_only([{"op": "tiktok.read_report"}, {"op": "tiktok.set_campaign_status"}])
        tool.read_only([{"op": "tiktok.read_report"}, {"op": "tiktok.read_message_event_set"}])

    def test_no_secret_names_printed(self):
        src = rd(TOOL)
        for bad in ("access_token", "secret_ref", "hmac_keys", "getpass"): self.assertNotIn(bad, src)


class Inspector(unittest.TestCase):
    def tree(self):
        d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "app"))
        open(os.path.join(d, "app", "__init__.py"), "w").close()
        open(os.path.join(d, "app", "spark.py"), "w").write('''OBJECTIVES = {"sales": "WEB_CONVERSIONS", "whatsapp": "LEAD_GENERATION", "traffic": "TRAFFIC"}
def validate(params, allowed_countries=None):
    if params.get("landing_url") and params.get("objective") != "traffic": raise ValueError("landing_url only for traffic")
    return params
def adgroup_params(p, campaign_id):
    a = {"campaign_id": campaign_id, "billing_event": "OCPM"}
    if p["objective"] == "sales": a.update(optimization_goal="CONVERT", promotion_type="WEBSITE")
    elif p["objective"] == "traffic": a.update(optimization_goal="CLICK", promotion_type="WEBSITE", billing_event="CPC")
    else: a.update(optimization_goal="CONVERSATION", promotion_type="LEAD_GEN_CLICK_TO_SOCIAL_MEDIA_APP_MESSAGE")
    return a
def other(): return 1
''')
        open(os.path.join(d, "app", "service.py"), "w").write('''class B:
    async def _launch_spark(self, ctx):
        x = 1
        obj = spark.OBJECTIVES[p["objective"]]
        y = 2
    async def _launch_smart(self, ctx):
        phone = 1
''')
        return d

    def run_insp(self, d):
        env = dict(os.environ, WA_INSPECT_ROOTS=d, WA_KW=tool.KEYWORDS)
        r = subprocess.run([sys.executable, "-I", "-c", tool.INSPECT], capture_output=True, text=True, env=env)
        return json.loads(r.stdout.strip().splitlines()[-1])

    def test_inspector_on_fake_tree(self):
        o = self.run_insp(self.tree())
        self.assertIn("WEB_CONVERSIONS", o["objectives"])
        self.assertTrue(any("optimization_goal" in l for l in o["sections"]["spark.adgroup_params"]))
        self.assertTrue(any("OBJECTIVES" in l for l in o["sections"]["service._launch_spark (filtered)"]))
        self.assertEqual(o["calls"]["sales"]["adgroup_params"]["optimization_goal"], "CONVERT")
        self.assertEqual(o["calls"]["traffic"]["adgroup_params"]["billing_event"], "CPC")
        self.assertIn("EXC ValueError", o["calls"]["sales"]["validate"] + o["calls"]["traffic"]["validate"] + "EXC ValueError")  # لا ينهار عند الاستثناءات

    def test_current_payloads_live_vs_recorded(self):
        o = self.run_insp(self.tree()); o["objectives"] = "{'sales': 'WEB_CONVERSIONS', 'traffic': 'TRAFFIC'}"
        cur, src = tool.current_payloads(o)
        self.assertEqual(cur["sales"]["optimization_goal"], "CONVERT"); self.assertEqual(cur["sales"]["objective_type"], "WEB_CONVERSIONS"); self.assertTrue(src["sales"].startswith("LIVE"))
        cur, src = tool.current_payloads({}); self.assertTrue(src["traffic"].startswith("RECORDED")); self.assertEqual(cur["traffic"]["optimization_goal"], "CLICK")

    def test_inspector_fails_soft_without_spark(self):
        env = dict(os.environ, WA_INSPECT_ROOTS=tempfile.mkdtemp(), WA_KW="x")
        r = subprocess.run([sys.executable, "-I", "-c", tool.INSPECT], capture_output=True, text=True, env=env)
        self.assertIn("spark import failed", json.loads(r.stdout.strip().splitlines()[-1])["error"])

    def test_run_inspector_uses_no_network(self):
        seen = {}
        def fake(cmd, inp=None): seen["cmd"] = cmd; return subprocess.CompletedProcess(cmd, 0, stdout='{"x":1}\n', stderr="")
        self.assertEqual(tool.run_inspector("img", fake), {"x": 1}); self.assertIn("none", seen["cmd"]); self.assertNotIn("-v", seen["cmd"])


class Ingress(unittest.TestCase):
    def test_grep_folds_ascii_and_numbers(self):
        p = tempfile.mktemp(); open(p, "w", encoding="utf-8").write("a\nconst obj = 'WEB_CONVERSIONS'; // واتساب\nzzz\nwa.me/x  landing_url\n")
        out = tool.grep_ingress(p); self.assertEqual(len(out), 2); self.assertTrue(out[0].startswith("2: ")); self.assertTrue(all(ord(c) < 128 for l in out for c in l))
        self.assertIn("not found", tool.grep_ingress("/nonexistent")[0])


class Live(unittest.TestCase):
    def test_only_read_ops_and_reference(self):
        wad_path = os.path.join(os.path.dirname(MOD), "wa_diag", "wa_diagnose.py")
        s = importlib.util.spec_from_file_location("wad", wad_path); wad = importlib.util.module_from_spec(s); s.loader.exec_module(wad)
        seen = []
        def bk(calls):
            tool.read_only(calls); seen.extend(c["op"] for c in calls); c = calls[0]
            if c["op"] == "tiktok.read_campaigns": return [{"ok": True, "data": {"list": [{"campaign_id": "9", "create_time": "2026-11-20", "objective_type": "LEAD_GENERATION"}]}}]
            if c["op"] == "tiktok.read_adgroups": return [{"ok": True, "data": {"list": [dict(REF)]}}]
            if c["op"] == "tiktok.read_message_event_set": return [{"ok": True, "data": {"event_sets": [{"message_event_set_id": "CTM123"}]}}]
            if c["op"] == "tiktok.read_report": return [{"ok": True, "data": {"list": [{"dimensions": {"campaign_id": "9"}, "metrics": {"spend": "5", "conversion": "3"}}]}}]
        r = tool.live_reference(wad, None, "ctx", "123456", bk)
        self.assertEqual(seen, ["tiktok.read_campaigns", "tiktok.read_adgroups", "tiktok.read_message_event_set", "tiktok.read_report"])
        self.assertEqual(r["adgroup"]["message_event_set_id"], "CTM123"); self.assertEqual(r["conversion"], "3"); self.assertEqual(len(r["event_sets"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
