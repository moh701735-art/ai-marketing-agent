# -*- coding: utf-8 -*-
import asyncio, importlib.util, json, os, re, shutil, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); MOD = os.path.dirname(H); ROOT = os.path.dirname(os.path.dirname(MOD)); P = os.path.join(os.path.dirname(MOD), "ops", "p286-meta-objectives.py.txt")
rd = lambda p: open(p, encoding="utf-8").read()
FLOW, BUILD, CATB = rd(os.path.join(MOD, "flow.py.txt")), rd(os.path.join(MOD, "build_block.py.txt")), rd(os.path.join(MOD, "catalog.py.txt"))
MF = '''import re
ACCT_RE = re.compile(r"^act_[0-9]{5,25}$")
def _bad(msg): return 400, {"ok": False, "error": {"class": "invalid_params", "message": msg}}
def _fail(stage, msg, cls="upstream"): return 200, {"ok": False, "error": {"class": cls, "message": msg}, "data": {"stage": stage}}
async def _call(svc, ctx, op, ad_account, params, *rest):
    idem = rest[0] if rest else None
    if op in ("meta.read_account", "meta.get_object") and rest: raise AssertionError("reads must not pass idem (live _call has no 6th arg for reads)")
    svc.calls.append((op, dict(params), idem))
    r = svc.script(op, params)
    if isinstance(r, tuple): return None, r
    return r, None
async def resolve_post(svc, ctx, url):
    svc.calls.append(("resolve", {"url": url}, None))
    if "bad" in url: return None, _fail("post", "post_not_found")
    return {"page_id": "111", "video_id": "222", "picture": "https://img/x.jpg", "message": "hello\\nworld"}, None
async def launch_whatsapp(svc, ctx, ad_account, params, idem=None): return 200, {"ok": True, "data": {"wa": True}}
async def suggest_interests(svc, ctx, params): return 200, {"ok": True}
async def run(svc, op_name, ctx, ad_account, params, idem):
@@IF@@    if op_name == "meta.suggest_interests":
        return await suggest_interests(svc, ctx, params)
    @@KW@@ op_name == "meta.launch_whatsapp":
        return await launch_whatsapp(svc, ctx, ad_account, params, idem)
'''
SV = '''class Svc:
    def _build(self, op, p, ad_account):
        if op.name == "meta.create_adset":
            pid = p.pop("page_id"); p["targeting"] = {"old": 1}; p["promoted_object"] = {"page_id": str(pid), "whatsapp_phone_number": "1"}
        if op.name == "meta.search_related":
            p["interest_list"] = "x"
        if op.name == "meta.create_ad":
            p["creative"] = {"creative_id": str(p.pop("creative_id"))}
        return p
'''
CAT = '''
import dataclasses
class P:
    def __init__(self, kind, **k): self.kind = kind; self.k = k; self.required = k.get("required", False)
@dataclasses.dataclass(frozen=@@F@@)
class Op:
    name: str
    platform: str = "meta"
    write: bool = False
    params: dict = dataclasses.field(default_factory=dict)
    forced: dict = dataclasses.field(default_factory=dict)
OPS = {}
OPS["meta.create_adset"] = Op("meta.create_adset", write=True, params={"name": P("text"), "campaign_id": P("id"), "page_id": P("id"), "whatsapp_phone_number": P("text"), "daily_budget": P("int")}, forced={"status": "PAUSED", "optimization_goal": "CONVERSATIONS", "destination_type": "WHATSAPP", "billing_event": "IMPRESSIONS", "bid_strategy": "LOWEST_COST_WITHOUT_CAP"})
OPS["meta.create_adcreative"] = Op("meta.create_adcreative", write=True, params={"name": P("text"), "page_id": P("id"), "video_id": P("id"), "message": P("text"), "image_url": P("text")})
'''
def tree(frozen=False, kw="if", variant4=False, mf_extra=""):
    d = tempfile.mkdtemp(); os.makedirs(d + "/broker/app"); os.makedirs(d + "/ops")
    mf = MF.replace("@@IF@@", "").replace("@@KW@@", kw) if kw == "if" else MF.replace("@@IF@@", '    if op_name == "meta.inspect_campaign":\n        return 200, {}\n').replace("@@KW@@", kw)
    open(d + "/broker/app/metaflow.py", "w", encoding="utf-8").write(mf + mf_extra)
    open(d + "/broker/app/service.py", "w", encoding="utf-8").write(SV if not variant4 else SV.replace("        ", "    ").replace("    def _build", "def _build").replace("class Svc:\n", ""))
    open(d + "/broker/app/catalog.py", "w", encoding="utf-8").write(CAT.replace("@@F@@", str(frozen)))
    return d
def apply(d): return subprocess.run([sys.executable, P], env={**os.environ, "P286_BASE": d + "/"}, capture_output=True, text=True)
def load(name, path):
    s = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


class Svc:
    def __init__(self, cur="USD", status="1", fail_at=None, ids=None):
        self.calls = []; self.cur = cur; self.status = status; self.fail_at = fail_at; self.ids = ids or {}
    def script(self, op, params):
        if op == self.fail_at: return 200, {"ok": False, "error": {"class": "bad_request", "message": "Meta says no: " + op}, "data": {"stage": op}}
        if op == "meta.read_account": return {"currency": self.cur, "account_status": self.status, "name": "n"}
        if op == "meta.create_campaign": return {"id": "900"}
        if op == "meta.create_adset_obj": return {"id": "901"}
        if op == "meta.create_adcreative_obj": return {"id": "902"}
        if op == "meta.create_ad": return {"id": "903"}
        if op == "meta.get_object": return {"id": "900", "objective": "OUTCOME_TRAFFIC", "effective_status": "PAUSED", "configured_status": "PAUSED"}
        if op == "meta.set_status": return {"success": True}
        raise AssertionError(op)


def run_mf(d, params, svc, ad="act_123456", idem="a" * 20):
    mf = load("mf%d" % id(d), d + "/broker/app/metaflow.py")
    return asyncio.run(mf.run(svc, "meta.launch_whatsapp", "ctx", ad, params, idem))


def GOOD(**k):
    p = {"objective_key": "traffic", "post_url": "https://www.facebook.com/x/videos/1", "link_url": "https://example.com/p", "budget_usd": 5, "days": 2, "name": "Test", "countries": ["IQ"]}
    p.update(k); return p


class Patch(unittest.TestCase):
    def test_apply_all_dispatcher_variants(self):
        for kw in ("if", "elif"):
            d = tree(kw=kw); r = apply(d); self.assertIn("APPLY286_OK", r.stdout, r.stdout + r.stderr)
            for f in ("metaflow", "service", "catalog"): self.assertTrue(os.path.exists(d + "/broker/app/%s.py.pre286" % f)); self.assertIn("p286", rd(d + "/broker/app/%s.py" % f))
            self.assertIn("changed=0", apply(d).stdout)
            # واتساب القديم ما تغيّر
            svc = Svc(); res = run_mf(d, {"anything": 1}, svc); self.assertEqual(res[1]["data"], {"wa": True})

    def test_fail_closed(self):
        d = tree(); s = rd(d + "/broker/app/service.py").replace('"meta.search_related"', '"meta.other"'); open(d + "/broker/app/service.py", "w").write(s)
        before = rd(d + "/broker/app/metaflow.py"); r = apply(d); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertEqual(rd(d + "/broker/app/metaflow.py"), before); self.assertFalse(os.path.exists(d + "/broker/app/metaflow.py.pre286"))
        d = tree(); s = rd(d + "/broker/app/metaflow.py").replace("def resolve_post", "def resolve_post2"); open(d + "/broker/app/metaflow.py", "w").write(s); self.assertIn("PATCH FAIL", apply(d).stdout + apply(d).stderr)
        d = tree(mf_extra='\nasync def zz(svc, ctx, ad_account, params, idem):\n    if op_name == "meta.launch_whatsapp":\n        return await launch_whatsapp(svc, ctx, ad_account, params, idem)\n'); self.assertIn("count=2", apply(d).stdout + apply(d).stderr)

    def test_partial_marker_refused(self):
        d = tree(); apply(d); open(d + "/broker/app/catalog.py", "w").write(rd(d + "/broker/app/catalog.py.pre286")); self.assertIn("partially applied", apply(d).stdout + apply(d).stderr)

    def test_oneliner(self):
        s = rd(os.path.join(ROOT, "out", "p286s.txt")); self.assertEqual(s.count("\n"), 1); self.assertIn("bash deploy/update.sh", s)


class Catalog(unittest.TestCase):
    def check(self, frozen):
        d = tree(frozen=frozen); apply(d); cat = load("c%d" % id(d), d + "/broker/app/catalog.py"); a = cat.OPS["meta.create_adset_obj"]; c = cat.OPS["meta.create_adcreative_obj"]
        self.assertNotIn("whatsapp_phone_number", a.params); self.assertEqual(a.params["objective_key"].kind, "enum"); self.assertEqual(a.forced["status"], "PAUSED"); self.assertNotIn("optimization_goal", a.forced); self.assertNotIn("destination_type", a.forced)
        self.assertIn("link_url", c.params); self.assertEqual(cat.OPS["meta.create_adset"].forced["destination_type"], "WHATSAPP")   # الأصل ما تغيّر
        self.assertIn("whatsapp_phone_number", cat.OPS["meta.create_adset"].params)
    def test_mutable_frozen(self): self.check(False); self.check(True)


class Build(unittest.TestCase):
    def build(self, variant4=False):
        d = tree(variant4=variant4); apply(d); src = rd(d + "/broker/app/service.py"); ns = {}
        exec(compile(src, "svc", "exec"), ns); return ns
    def test_adset_obj_payloads(self):
        ns = self.build() if False else None
        d = tree(); apply(d); ns = {}; exec(compile(rd(d + "/broker/app/service.py"), "svc", "exec"), ns); svc = ns["Svc"]()
        class Op:
            def __init__(s, n): s.name = n
        for key, goal, dest, prom in (("awareness", "REACH", None, False), ("traffic", "LINK_CLICKS", "WEBSITE", False), ("engagement", "POST_ENGAGEMENT", "ON_POST", True)):
            p = svc._build(Op("meta.create_adset_obj"), {"objective_key": key, "page_id": "111", "name": "n", "campaign_id": "9", "countries": ["iq"], "regions": ["777"], "age_min": 20, "age_max": 40, "genders": ["2"], "interests": ["1", "2"], "placements": ["facebook_feed", "instagram_reels", "messenger_inbox"], "daily_budget": 500}, "act_1")
            self.assertEqual(p["optimization_goal"], goal); self.assertEqual(p.get("destination_type"), dest); self.assertEqual("promoted_object" in p, prom); self.assertNotIn("page_id", p); self.assertNotIn("objective_key", p)
            tg = p["targeting"]; self.assertEqual(tg["geo_locations"], {"countries": ["IQ"], "regions": [{"key": "777"}]}); self.assertEqual((tg["age_min"], tg["age_max"], tg["genders"]), (20, 40, [2]))
            self.assertEqual(tg["flexible_spec"], [{"interests": [{"id": "1"}, {"id": "2"}]}]); self.assertEqual(tg["publisher_platforms"], ["facebook", "instagram", "messenger"]); self.assertEqual(tg["facebook_positions"], ["feed"]); self.assertEqual(tg["instagram_positions"], ["reels"])
            self.assertEqual(tg["targeting_automation"], {"advantage_audience": 0}); json.dumps(p)
        p = svc._build(Op("meta.create_adset_obj"), {"objective_key": "awareness", "page_id": "1", "name": "n", "campaign_id": "9"}, "act_1"); self.assertEqual(p["targeting"]["geo_locations"], {"countries": ["IQ"]})   # افتراضي العراق
    def test_creative_obj_payloads(self):
        d = tree(); apply(d); ns = {}; exec(compile(rd(d + "/broker/app/service.py"), "svc", "exec"), ns); svc = ns["Svc"]()
        class Op:
            def __init__(s, n): s.name = n
        p = svc._build(Op("meta.create_adcreative_obj"), {"objective_key": "traffic", "page_id": "111", "video_id": 222, "name": "n", "message": "hi", "image_url": "https://i/x.jpg", "link_url": "https://example.com", "cta": "SHOP_NOW"}, "act_1")
        vd = p["object_story_spec"]["video_data"]; self.assertEqual(p["object_story_spec"]["page_id"], "111"); self.assertEqual(vd["video_id"], "222"); self.assertEqual(vd["call_to_action"], {"type": "SHOP_NOW", "value": {"link": "https://example.com"}}); self.assertEqual(vd["image_url"], "https://i/x.jpg")
        p = svc._build(Op("meta.create_adcreative_obj"), {"objective_key": "awareness", "page_id": "111", "video_id": "2", "name": "n"}, "act_1"); self.assertNotIn("call_to_action", p["object_story_spec"]["video_data"])
        p = svc._build(Op("meta.create_adcreative_obj"), {"objective_key": "traffic", "page_id": "111", "video_id": "2", "name": "n", "link_url": "https://e.com"}, "act_1"); self.assertEqual(p["object_story_spec"]["video_data"]["call_to_action"]["type"], "LEARN_MORE")
    def test_other_ops_untouched(self):
        d = tree(); apply(d); ns = {}; exec(compile(rd(d + "/broker/app/service.py"), "svc", "exec"), ns); svc = ns["Svc"]()
        class Op:
            def __init__(s, n): s.name = n
        self.assertEqual(svc._build(Op("meta.create_ad"), {"creative_id": 5}, "a"), {"creative": {"creative_id": "5"}})
        self.assertEqual(svc._build(Op("meta.create_adset"), {"page_id": 9}, "a")["promoted_object"]["whatsapp_phone_number"], "1")


class Flow(unittest.TestCase):
    def setUp(self): self.d = tree(); apply(self.d)
    def ops(self, svc): return [c[0] for c in svc.calls]
    def test_traffic_success_sequence_and_values(self):
        svc = Svc(); st, r = run_mf(self.d, GOOD(), svc); self.assertTrue(r["ok"], r); d = r["data"]
        self.assertEqual(self.ops(svc), ["meta.read_account", "resolve", "meta.create_campaign", "meta.create_adset_obj", "meta.create_adcreative_obj", "meta.create_ad", "meta.get_object"])
        self.assertEqual(d["campaign_objective"], "OUTCOME_TRAFFIC"); self.assertEqual(d["optimization_goal"], "LINK_CLICKS"); self.assertEqual(d["status"], "PAUSED"); self.assertEqual(d["budget_minor"], 500); self.assertEqual(d["result_metric"], "link_clicks")
        self.assertEqual((d["campaign_id"], d["adset_id"], d["creative_id"], d["ad_id"]), ("900", "901", "902", "903")); self.assertEqual(d["readback"]["effective_status"], "PAUSED")
        camp = svc.calls[2][1]; self.assertEqual(camp, {"name": "Test", "objective": "OUTCOME_TRAFFIC", "special_ad_categories": ["NONE"]})
        ads = svc.calls[3][1]; self.assertEqual(ads["objective_key"], "traffic"); self.assertEqual(ads["lifetime_budget"], 500); self.assertNotIn("daily_budget", ads); self.assertEqual(ads["page_id"], "111"); self.assertLess(ads["start_time"], ads["end_time"])
        cre = svc.calls[4][1]; self.assertEqual(cre["link_url"], "https://example.com/p"); self.assertEqual(cre["cta"], "LEARN_MORE"); self.assertEqual(cre["message"], "hello world"); self.assertEqual(cre["image_url"], "https://img/x.jpg")
        self.assertEqual([c[2] for c in svc.calls[2:6]], ["a" * 20 + s for s in ("-c", "-a", "-r", "-d")]); self.assertNotIn("meta.set_status", self.ops(svc))
    def test_awareness_and_engagement(self):
        for key, goal in (("awareness", "OUTCOME_AWARENESS"), ("engagement", "OUTCOME_ENGAGEMENT")):
            svc = Svc(); st, r = run_mf(self.d, GOOD(objective_key=key, link_url=""), svc); self.assertTrue(r["ok"]); self.assertEqual(r["data"]["campaign_objective"], goal)
            self.assertNotIn("link_url", svc.calls[4][1])
    def test_iqd_and_daily_budget(self):
        svc = Svc(cur="IQD"); st, r = run_mf(self.d, GOOD(budget_usd=5, budget_mode="daily"), svc); self.assertEqual(r["data"]["budget_minor"], 7775); self.assertIn("daily_budget", svc.calls[3][1]); self.assertNotIn("lifetime_budget", svc.calls[3][1])
    def test_account_guards_before_any_create(self):
        for svc, msg in ((Svc(status="2"), "account_not_active"), (Svc(cur="EUR"), "currency_not_supported:EUR")):
            st, r = run_mf(self.d, GOOD(), svc); self.assertFalse(r["ok"]); self.assertIn(msg, r["error"]["message"]); self.assertEqual(self.ops(svc), ["meta.read_account"])
    def test_validation(self):
        for bad in (GOOD(objective_key="sales"), GOOD(budget_usd=0.1), GOOD(budget_usd=5000), GOOD(days=0), GOOD(days=31), GOOD(post_url="http://x"), GOOD(link_url=""), GOOD(name=" "), GOOD(age_min=10), GOOD(countries="IQ"), GOOD(budget_usd="x")):
            svc = Svc(); st, r = run_mf(self.d, bad, svc); self.assertFalse(r["ok"], bad); self.assertEqual(svc.calls, [])
        svc = Svc(); st, r = run_mf(self.d, GOOD(), svc, ad="123"); self.assertFalse(r["ok"]); svc = Svc(); st, r = run_mf(self.d, GOOD(), svc, idem="short"); self.assertFalse(r["ok"])
    def test_post_failure_creates_nothing(self):
        svc = Svc(); st, r = run_mf(self.d, GOOD(post_url="https://bad/post"), svc); self.assertFalse(r["ok"]); self.assertNotIn("meta.create_campaign", self.ops(svc))
    def test_partial_failure_reports_created_ids(self):
        svc = Svc(fail_at="meta.create_adcreative_obj"); st, r = run_mf(self.d, GOOD(), svc); self.assertFalse(r["ok"]); self.assertEqual(r["data"]["created_before_failure"]["campaign_id"], "900"); self.assertEqual(r["data"]["created_before_failure"]["adset_id"], "901")
        self.assertNotIn("meta.create_ad", self.ops(svc)); self.assertIn("Meta says no", r["error"]["message"])
        svc = Svc(fail_at="meta.create_campaign"); st, r = run_mf(self.d, GOOD(), svc); self.assertFalse(r["ok"]); self.assertNotIn("meta.create_adset_obj", self.ops(svc))
    def test_activation_only_on_request_and_order(self):
        svc = Svc(); st, r = run_mf(self.d, GOOD(activate_now=True), svc); self.assertEqual(r["data"]["status"], "ACTIVE")
        self.assertEqual([c[1]["oid"] for c in svc.calls if c[0] == "meta.set_status"], ["903", "901", "900"])
        svc = Svc(); st, r = run_mf(self.d, GOOD(activate_now="yes"), svc); self.assertEqual(r["data"]["status"], "PAUSED")
    def test_default_start_is_in_future(self):
        import datetime
        svc = Svc(); run_mf(self.d, GOOD(), svc); st = svc.calls[3][1]["start_time"]; t = datetime.datetime.strptime(st[:19], "%Y-%m-%dT%H:%M:%S"); self.assertGreater(t, datetime.datetime.utcnow())


class Tool(unittest.TestCase):
    def setUp(self): self.t = load("mot", os.path.join(MOD, "ops", "meta_obj_test.py"))
    def test_params_and_guards(self):
        p = self.t.build_params("traffic", "https://fb/x", "https://e.com", "1", "1", "PROBE"); self.assertEqual(p["budget_usd"], 1.0); self.assertEqual(p["link_url"], "https://e.com")
        for bad in (("sales", "https://x", "", 1, 1), ("traffic", "http://x", "https://e", 1, 1), ("traffic", "https://x", "", 1, 1), ("awareness", "https://x", "", 50, 1)):
            with self.assertRaises(SystemExit): self.t.build_params(bad[0], bad[1], bad[2], bad[3], bad[4], "n")
    def test_report_ascii(self):
        o = self.t.report({"ok": True, "data": {"campaign_id": "9", "status": "PAUSED", "result_metric": "reach", "readback": {"effective_status": "PAUSED"}}}); self.assertIn("PAUSED", o); self.assertIn("NOT messages", o); self.assertTrue(all(ord(c) < 128 for c in o))
        o = self.t.report({"ok": False, "error": {"class": "bad_request", "message": "خطأ"}, "data": {"created_before_failure": {"campaign_id": "1"}}}); self.assertIn("FAILED", o); self.assertTrue(all(ord(c) < 128 for c in o))
    def test_source_has_no_activation(self):
        s = rd(os.path.join(MOD, "ops", "meta_obj_test.py")); self.assertNotIn("activate_now", s); self.assertNotIn("ACTIVE", s)


if __name__ == "__main__":
    unittest.main(verbosity=1)
