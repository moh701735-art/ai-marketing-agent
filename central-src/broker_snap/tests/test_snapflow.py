import asyncio, importlib.util, json, os, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("snapflow", os.path.join(ROOT, "snapflow.py")); sf = importlib.util.module_from_spec(spec); spec.loader.exec_module(sf)
IDEM = "idem-0123456789abcdef"
GOOD = {"name": "Snap · زيارات · 16/11", "objective": "trf", "budget": 20, "days": 3, "regions": ["25600", "25601"], "ages": ["18-20", "25-34"], "gender": "f", "lang": "ar", "interests": ["SLC_5", "SLC_9"], "landing_url": "https://t.me/+abc123"}
class Svc:
    def __init__(self, script): self.script = script; self.calls = []
    async def call(self, ctx, platform, op, acct, prm, key, internal=False):
        self.calls.append((platform, op, acct, prm, key, internal)); r = self.script.get(op)
        if r is None: return (404, {"ok": False, "error": {"class": "unknown_op", "message": "unscripted " + op}})
        return r() if callable(r) else r
def ok(data): return (200, {"ok": True, "data": data})
ADOK = ok({"adaccounts": [{"adaccount": {"id": "acc-1111-aaaa", "status": "ACTIVE", "currency": "USD", "timezone": "America/Los_Angeles"}}]})
CAMP = ok({"campaigns": [{"sub_request_status": "SUCCESS", "campaign": {"id": "camp-1"}}]})
SQ = ok({"adsquads": [{"sub_request_status": "SUCCESS", "adsquad": {"id": "sq-1"}}]})
run = lambda svc, p=GOOD, acct="acc-1111-aaaa", idem=IDEM: asyncio.run(sf.launch_draft(svc, "CTX", acct, p, idem))
class T(unittest.TestCase):
    def test_happy_path(self):
        s = Svc({"snapchat.adaccount": ADOK, "snapchat.create_campaign": CAMP, "snapchat.create_adsquad": SQ}); st, env = run(s)
        self.assertEqual(st, 200); d = env["data"]; self.assertTrue(env["ok"])
        self.assertEqual((d["campaign_id"], d["adsquad_id"], d["status"], d["creative"], d["currency"]), ("camp-1", "sq-1", "PAUSED", "missing", "USD"))
        self.assertEqual([c[1] for c in s.calls], ["snapchat.adaccount", "snapchat.create_campaign", "snapchat.create_adsquad"]); self.assertTrue(all(c[5] for c in s.calls))
        self.assertEqual([c[4] for c in s.calls], [IDEM + "-a", IDEM + "-c", IDEM + "-s"])
        camp = s.calls[1][3]; self.assertEqual(camp["status"], "PAUSED"); self.assertRegex(camp["start_time"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.000-0[78]:00$")
        self.assertNotIn("pixel_id", s.calls[2][3]); sq = s.calls[2][3]; self.assertEqual(sq["budget_micro"], 20_000_000); self.assertEqual(sq["status"], "PAUSED"); self.assertEqual(sq["goal"], "SWIPES")
        t = json.loads(sq["targeting_json"]); self.assertEqual(t["geos"], [{"country_code": "iq", "region_id": ["25600", "25601"]}])
        self.assertEqual(t["demographics"], [{"age_groups": ["18-20", "25-34"], "gender": "FEMALE", "languages": ["ar"]}]); self.assertEqual(t["interests"], [{"category_id": ["SLC_5", "SLC_9"]}])
    def test_no_regions_means_all_iraq_and_minimal_targeting(self):
        p = dict(GOOD, regions=[], ages=[], gender="a", lang="", interests=[]); self.assertEqual(sf.targeting(p), {"geos": [{"country_code": "iq"}]})
    def test_account_not_active(self):
        s = Svc({"snapchat.adaccount": ok({"adaccounts": [{"adaccount": {"status": "PAUSED"}}]})}); st, env = run(s)
        self.assertFalse(env["ok"]); self.assertEqual(env["data"]["stage"], "account"); self.assertEqual(len(s.calls), 1)
    def test_campaign_failure_stops(self):
        s = Svc({"snapchat.adaccount": ADOK, "snapchat.create_campaign": (200, {"ok": False, "error": {"class": "bad_request", "message": "Invalid field"}})}); st, env = run(s)
        self.assertFalse(env["ok"]); self.assertEqual(env["data"]["stage"], "campaign"); self.assertIn("Invalid field", env["error"]["message"]); self.assertEqual(len(s.calls), 2)
    def test_adsquad_failure_reports_campaign_id(self):
        s = Svc({"snapchat.adaccount": ADOK, "snapchat.create_campaign": CAMP, "snapchat.create_adsquad": (200, {"ok": False, "error": {"class": "bad_request", "message": "targeting invalid"}})}); st, env = run(s)
        self.assertFalse(env["ok"]); self.assertEqual(env["data"]["stage"], "adsquad"); self.assertEqual(env["data"]["campaign_id"], "camp-1"); self.assertIn("targeting invalid", env["error"]["message"])
    def test_snap_sub_request_error(self):
        s = Svc({"snapchat.adaccount": ADOK, "snapchat.create_campaign": ok({"campaigns": [{"sub_request_status": "ERROR", "display_message": "Bad name"}]})}); st, env = run(s)
        self.assertEqual(env["data"]["stage"], "campaign"); self.assertIn("Bad name", env["error"]["message"])
    def test_sub_request_error_reason_is_surfaced(self):   # p197e
        s = Svc({"snapchat.adaccount": ADOK, "snapchat.create_campaign": CAMP, "snapchat.create_adsquad": ok({"adsquads": [{"sub_request_status": "ERROR", "sub_request_error_reason": "daily budget too low"}]})}); st, env = run(s)
        self.assertEqual(env["data"]["stage"], "adsquad"); self.assertIn("daily budget too low", env["error"]["message"]); self.assertEqual(env["data"]["campaign_id"], "camp-1")
    def test_pixel_goal_sends_conversion_window_p197f(self):
        b = sf.body("snapchat.create_adsquad", {"name": "n", "campaign_id": "c", "start_time": "2026-11-19T10:00:00.000+03:00", "targeting_json": "{}", "budget_micro": 20000000, "goal": "PIXEL_PURCHASE", "pixel_id": "px-1"})["adsquads"][0]
        self.assertEqual(b["optimization_goal"], "PIXEL_PURCHASE"); self.assertEqual(b["pixel_id"], "px-1"); self.assertEqual(b["conversion_window"], "SWIPE_28DAY_VIEW_1DAY")
        b2 = sf.body("snapchat.create_adsquad", {"name": "n", "campaign_id": "c", "start_time": "2026-11-19T10:00:00.000+03:00", "targeting_json": "{}", "budget_micro": 20000000, "goal": "SWIPES"})["adsquads"][0]
        self.assertNotIn("conversion_window", b2)
    def test_validation(self):
        s = Svc({})
        for bad in (dict(GOOD, name=""), dict(GOOD, objective="sal"), dict(GOOD, budget=0), dict(GOOD, budget=10**9), dict(GOOD, days=0), dict(GOOD, regions=["abc"]), dict(GOOD, ages=["10-12"]), dict(GOOD, gender="x"),
                    dict(GOOD, lang="zz"), dict(GOOD, interests=["slc_5"]), dict(GOOD, interests=["SLC_%d" % i for i in range(11)]), dict(GOOD, landing_url="http://x.com"), dict(GOOD, landing_url="https://a b"), dict(GOOD, extra=1), dict(GOOD, start_at="soon")):
            st, env = run(s, bad); self.assertEqual(st, 400, bad); self.assertEqual(env["error"]["class"], "invalid_params")
        self.assertEqual(s.calls, [])
        self.assertEqual(run(s, GOOD, idem="short")[0], 400); self.assertEqual(run(s, GOOD, acct="bad acct!")[0], 400)
    def test_status_forced_paused_in_body(self):
        b = sf.body("snapchat.create_campaign", {"name": "x", "status": "ACTIVE", "start_time": "t", "account_id": "a1"}); self.assertEqual(b["campaigns"][0]["status"], "PAUSED"); self.assertEqual(b["campaigns"][0]["ad_account_id"], "a1")
        b = sf.body("snapchat.create_adsquad", {"name": "x", "status": "ACTIVE", "start_time": "t", "campaign_id": "c1", "targeting_json": "{}", "budget_micro": 5_000_000})
        self.assertEqual(b["adsquads"][0]["status"], "PAUSED"); self.assertEqual(b["adsquads"][0]["lifetime_budget_micro"], 5_000_000); self.assertEqual(b["adsquads"][0]["campaign_id"], "c1")
    def test_iso_times(self):
        import datetime
        now = datetime.datetime(2026, 11, 16, 10, 0, 0, tzinfo=datetime.timezone.utc); s, e = sf.iso_times("+03:00", 2, None, now)
        self.assertEqual(s, "2026-11-16T13:15:00.000+03:00"); self.assertEqual(e, "2026-11-18T13:15:00.000+03:00")
        s, e = sf.iso_times("-08:00", 1, "2026-11-20T00:00:00"); self.assertEqual((s, e), ("2026-11-20T00:00:00.000-08:00", "2026-11-21T00:00:00.000-08:00"))
MEDIA = ok({"media": [{"sub_request_status": "SUCCESS", "media": {"id": "media-9"}}]})
READY = ok({"media": [{"sub_request_status": "SUCCESS", "media": {"id": "media-9", "media_status": "READY"}}]})
PROF = ok({"profiles": [{"sub_request_status": "SUCCESS", "profile": {"id": "prof-1"}}]})
CRE = ok({"creatives": [{"sub_request_status": "SUCCESS", "creative": {"id": "cre-1"}}]})
ADS = ok({"ads": [{"sub_request_status": "SUCCESS", "ad": {"id": "ad-1"}}]})
ADOK2 = ok({"adaccounts": [{"adaccount": {"id": "acc-1111-aaaa", "status": "ACTIVE", "currency": "USD", "timezone": "Asia/Baghdad", "organization_id": "org-1"}}]})
FULL = {"snapchat.adaccount": ADOK2, "snapchat.create_campaign": CAMP, "snapchat.create_adsquad": SQ, "snapchat.profiles_org": PROF, "snapchat.create_creative": CRE, "snapchat.create_ad": ADS}
class Resp:
    def __init__(self, code=200, text="{}"): self.status_code = code; self.text = text
class Cli:
    def __init__(self, resp=None, boom=False): self.resp = resp or Resp(); self.boom = boom; self.posts = []
    async def post(self, url, **kw):
        self.posts.append((url, kw))
        if self.boom: raise RuntimeError("net")
        return self.resp
class Central:
    async def authorize(self, ctx, platform, acct, mode): return {"tenant_id": "t1", "secret_ref": "ref1"}
class Store:
    async def open_latest(self, tenant, ref): return (1, "snap_oauth", "RAW")
class S2:
    base_urls = {"snapchat": "https://adsapi.snapchat.com/v1/"}
class Svc2(Svc):
    def __init__(self, script, tg=(b"VIDEO", "v.mp4"), cli=None):
        super().__init__(script); self.tg = tg; self.client = cli or Cli(); self.central = Central(); self.store = Store(); self.s = S2(); self.tg_calls = []
    async def _tg_download(self, ctx, fid): self.tg_calls.append(fid); return self.tg
    async def _snap_token(self, tenant, ref, raw): return "TOK-" + raw
VID = dict(GOOD, objective="vid", landing_url=None, file_id="BAACAgQAAxkBAAIB")
class V(unittest.TestCase):
    def test_media_id_path_full_chain(self):
        s = Svc2(dict(FULL)); p = dict(GOOD, media_id="11111111-aaaa-bbbb-cccc-222222222222", headline="خصم كبير", brand_name="متجري", cta="SHOP_NOW"); st, env = run(s, p)
        self.assertEqual(st, 200); d = env["data"]; self.assertTrue(env["ok"])
        self.assertEqual((d["ad_id"], d["creative_id"], d["profile_id"], d["media_id"], d["stage"], d["creative"], d["status"]), ("ad-1", "cre-1", "prof-1", "11111111-aaaa-bbbb-cccc-222222222222", "ad", "created", "PAUSED"))
        ops = [c[1] for c in s.calls]; self.assertEqual(ops, ["snapchat.adaccount", "snapchat.create_campaign", "snapchat.create_adsquad", "snapchat.creatives_list", "snapchat.profiles_org", "snapchat.create_creative", "snapchat.create_ad"]); self.assertEqual(s.tg_calls, [])
        self.assertEqual(s.calls[4][3], {"oid": "org-1"})
        cr = json.loads(s.calls[5][3]["payload_json"]); self.assertEqual((cr["type"], cr["top_snap_media_id"], cr["headline"], cr["brand_name"], cr["call_to_action"], cr["web_view_properties"]["url"]), ("WEB_VIEW", p["media_id"], "خصم كبير", "متجري", "SHOP_NOW", "https://t.me/+abc123"))
        self.assertEqual(cr["profile_properties"], {"profile_id": "prof-1"})
        ad = json.loads(s.calls[6][3]["payload_json"]); self.assertEqual((ad["type"], ad["status"], ad["ad_squad_id"], ad["creative_id"]), ("REMOTE_WEBPAGE", "PAUSED", "sq-1", "cre-1")); self.assertEqual(s.calls[6][3]["oid"], "sq-1")
    def test_given_profile_skips_discovery(self):
        s = Svc2(dict(FULL)); st, env = run(s, dict(GOOD, media_id="11111111-aaaa-bbbb-cccc-222222222222", profile_id="aaaaaaaa-1111")); self.assertTrue(env["ok"]); self.assertNotIn("snapchat.profiles_org", [c[1] for c in s.calls])
    def test_profile_missing_reports_stage(self):
        sc = dict(FULL, **{"snapchat.profiles_org": ok({"profiles": []}), "snapchat.profiles_acct": (200, {"ok": False, "error": {"class": "forbidden", "message": "403 nope"}})}); s = Svc2(sc); st, env = run(s, dict(GOOD, media_id="11111111-aaaa-bbbb-cccc-222222222222"))
        self.assertFalse(env["ok"]); d = env["data"]; self.assertEqual(d["stage"], "profile"); self.assertEqual((d["campaign_id"], d["adsquad_id"]), ("camp-1", "sq-1")); self.assertIn("Public Profile", env["error"]["message"]); self.assertIn("403 nope", env["error"]["message"]); self.assertEqual([c[1] for c in s.calls][-2:], ["snapchat.profiles_org", "snapchat.profiles_acct"])
    def test_profile_falls_back_to_account(self):
        sc = dict(FULL, **{"snapchat.profiles_org": (200, {"ok": False, "error": {"class": "forbidden", "message": "x"}}), "snapchat.profiles_acct": PROF}); s = Svc2(sc); st, env = run(s, dict(GOOD, media_id="11111111-aaaa-bbbb-cccc-222222222222"))
        self.assertTrue(env["ok"], env); self.assertEqual(env["data"]["profile_id"], "prof-1")
    def test_profile_from_existing_creatives(self):
        CL = ok({"creatives": [{"sub_request_status": "SUCCESS", "creative": {"id": "c0", "profile_properties": {"profile_id": "e9f1bdd3-5327-45d6-a668-d8b785f30076"}}}]})
        s = Svc2(dict(FULL, **{"snapchat.creatives_list": CL})); st, env = run(s, dict(GOOD, media_id="11111111-aaaa-bbbb-cccc-222222222222"))
        self.assertTrue(env["ok"], env); self.assertEqual(env["data"]["profile_id"], "e9f1bdd3-5327-45d6-a668-d8b785f30076"); self.assertNotIn("snapchat.profiles_org", [c[1] for c in s.calls])
    def test_age_range_targeting(self):
        p, e = sf.clean({k: v for k, v in dict(GOOD, ages=[], min_age=21, max_age=34).items()}); self.assertIsNone(e)
        self.assertEqual(sf.targeting(p)["demographics"][0]["min_age"], "21"); self.assertEqual(sf.targeting(p)["demographics"][0]["max_age"], "34"); self.assertNotIn("age_groups", sf.targeting(p)["demographics"][0])
        p, e = sf.clean(dict(GOOD, ages=[], min_age=25)); self.assertNotIn("max_age", sf.targeting(p)["demographics"][0])
        for bad in (dict(GOOD, ages=[], min_age=12), dict(GOOD, ages=[], min_age=30, max_age=20), dict(GOOD, min_age=20), dict(GOOD, ages=[], min_age="20"), dict(GOOD, ages=[], max_age=51)):
            self.assertIsNotNone(sf.clean(bad)[1], bad)
    def test_creative_and_ad_failures_keep_ids(self):
        bad = (200, {"ok": False, "error": {"class": "bad_request", "message": "creative rejected: headline"}})
        s = Svc2(dict(FULL, **{"snapchat.create_creative": bad})); st, env = run(s, dict(GOOD, media_id="11111111-aaaa-bbbb-cccc-222222222222"))
        self.assertEqual(env["data"]["stage"], "creative"); self.assertEqual(env["data"]["adsquad_id"], "sq-1"); self.assertIn("headline", env["error"]["message"])
        s = Svc2(dict(FULL, **{"snapchat.create_ad": (200, {"ok": False, "error": {"class": "bad_request", "message": "ad rejected"}})})); st, env = run(s, dict(GOOD, media_id="11111111-aaaa-bbbb-cccc-222222222222"))
        self.assertEqual(env["data"]["stage"], "ad"); self.assertEqual(env["data"]["creative_id"], "cre-1"); self.assertFalse(env["ok"])
        s = Svc2(dict(FULL, **{"snapchat.create_ad": ok({"ads": [{"sub_request_status": "ERROR", "display_message": "no profile"}]})})); st, env = run(s, dict(GOOD, media_id="11111111-aaaa-bbbb-cccc-222222222222"))
        self.assertEqual(env["data"]["stage"], "ad"); self.assertIn("no profile", env["error"]["message"])
    def test_file_id_uploads_then_waits_ready(self):
        cli = Cli(); s = Svc2(dict(FULL, **{"snapchat.create_media": MEDIA, "snapchat.media_get": READY}), cli=cli); st, env = run(s, dict(VID, landing_url="https://t.me/x"))
        self.assertTrue(env["ok"], env); d = env["data"]; self.assertEqual((d["media_id"], d["ad_id"]), ("media-9", "ad-1")); self.assertEqual(s.tg_calls, ["BAACAgQAAxkBAAIB"])
        url, kw = cli.posts[0]; self.assertEqual(url, "https://adsapi.snapchat.com/v1/media/media-9/upload"); self.assertEqual(kw["headers"], {"Authorization": "Bearer TOK-RAW"}); self.assertEqual(kw["files"]["file"][0], "v.mp4")
        ops = [c[1] for c in s.calls]; self.assertLess(ops.index("snapchat.create_media"), ops.index("snapchat.media_get")); self.assertLess(ops.index("snapchat.media_get"), ops.index("snapchat.create_creative"))
        self.assertEqual(s.calls[ops.index("snapchat.create_media")][3]["account_id"], "acc-1111-aaaa")
    def test_views_objective_no_url_makes_snap_ad(self):
        s = Svc2(dict(FULL, **{"snapchat.create_media": MEDIA, "snapchat.media_get": READY})); st, env = run(s, VID); self.assertTrue(env["ok"], env)
        cr = json.loads([c for c in s.calls if c[1] == "snapchat.create_creative"][0][3]["payload_json"]); self.assertEqual(cr["type"], "SNAP_AD"); self.assertNotIn("web_view_properties", cr)
        ad = json.loads([c for c in s.calls if c[1] == "snapchat.create_ad"][0][3]["payload_json"]); self.assertEqual(ad["type"], "SNAP_AD")
        sq = [c for c in s.calls if c[1] == "snapchat.create_adsquad"][0][3]; self.assertEqual(sq["goal"], "VIDEO_VIEWS")
    def test_sales_needs_pixel_and_passes_it(self):
        st, env = run(Svc2({}), dict(GOOD, objective="sal")); self.assertEqual(st, 400)
        s = Svc2(dict(FULL, **{"snapchat.create_media": MEDIA, "snapchat.media_get": READY})); st, env = run(s, dict(GOOD, objective="sal", pixel_id="bee15341-7ae6-477f-ae0f-b0f0db91347c", file_id="BAACAgQAAxkBAAIB")); self.assertTrue(env["ok"], env)
        sq = [c for c in s.calls if c[1] == "snapchat.create_adsquad"][0][3]; self.assertEqual((sq["goal"], sq["pixel_id"]), ("PIXEL_PURCHASE", "bee15341-7ae6-477f-ae0f-b0f0db91347c"))
    def test_upload_failures(self):
        base = dict(FULL, **{"snapchat.create_media": MEDIA, "snapchat.media_get": READY})
        s = Svc2(base, tg=(None, {"class": "invalid_params", "message": "telegram_file_too_big"})); st, env = run(s, VID); self.assertEqual(env["data"]["stage"], "upload"); self.assertIn("too_big", env["error"]["message"]); self.assertEqual(env["data"]["adsquad_id"], "sq-1")
        s = Svc2(base, cli=Cli(Resp(400, '{"msg":"bad file"}'))); st, env = run(s, VID); self.assertEqual(env["data"]["stage"], "upload"); self.assertIn("http_400", env["error"]["message"]); self.assertNotIn("snapchat.create_creative", [c[1] for c in s.calls])
        s = Svc2(base, cli=Cli(boom=True)); st, env = run(s, VID); self.assertEqual(env["data"]["stage"], "upload"); self.assertIn("RuntimeError", env["error"]["message"])
        s = Svc2(dict(base, **{"snapchat.media_get": ok({"media": [{"media": {"media_status": "ERROR"}}]})})); st, env = run(s, VID); self.assertEqual(env["data"]["stage"], "upload")
        s = Svc2(dict(base, **{"snapchat.create_media": ok({"media": [{"sub_request_status": "ERROR", "display_message": "bad media"}]})})); st, env = run(s, VID); self.assertEqual(env["data"]["stage"], "media"); self.assertEqual(s.client.posts, [])
    def test_new_field_validation(self):
        s = Svc2({}); M = "11111111-aaaa-bbbb-cccc-222222222222"
        for bad in (dict(GOOD, headline="x" * 35), dict(GOOD, brand_name="y" * 26), dict(GOOD, cta="HACK"), dict(GOOD, media_id="bad id"), dict(GOOD, file_id="a b"), dict(GOOD, media_id=M, file_id="BAACAgQAAxkBAAIB"), dict(GOOD, profile_id="x y"), dict(GOOD, pixel_id="not a uuid!"), dict(VID, landing_url="http://x.com"), dict(GOOD, headline="<b>")):
            st, env = run(s, bad); self.assertEqual(st, 400, bad)
        self.assertEqual(s.calls, [])
    def test_bodies(self):
        b = sf.body("snapchat.create_media", {"name": "v", "account_id": "a1"}); self.assertEqual(b, {"media": [{"name": "v", "type": "VIDEO", "ad_account_id": "a1"}]})
        b = sf.body("snapchat.create_creative", {"account_id": "a1", "payload_json": json.dumps({"name": "c"})}); self.assertEqual(b["creatives"][0]["ad_account_id"], "a1")
        b = sf.body("snapchat.create_ad", {"payload_json": json.dumps({"name": "a", "status": "ACTIVE"})}); self.assertEqual(b["ads"][0]["status"], "PAUSED")
        b = sf.body("snapchat.create_adsquad", {"name": "x", "start_time": "t", "campaign_id": "c1", "targeting_json": "{}", "budget_micro": 5_000_000, "pixel_id": "px"}); self.assertEqual(b["adsquads"][0]["pixel_id"], "px")
if __name__ == "__main__": unittest.main(verbosity=1)
