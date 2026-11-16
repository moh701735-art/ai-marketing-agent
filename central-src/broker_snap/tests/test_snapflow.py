import asyncio, importlib.util, json, os, sys, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("snapflow", os.path.join(ROOT, "snapflow.py")); sf = importlib.util.module_from_spec(spec); spec.loader.exec_module(sf)
IDEM = "idem-0123456789abcdef"
GOOD = {"name": "Snap · زيارات · 16/11", "objective": "trf", "budget": 20, "days": 3, "regions": ["25600", "25601"], "ages": ["18-20", "25-34"], "gender": "f", "lang": "ar", "interests": ["SLC_5", "SLC_9"], "landing_url": "https://t.me/+abc123"}
class Svc:
    def __init__(self, script): self.script = script; self.calls = []
    async def call(self, ctx, platform, op, acct, prm, key, internal=False):
        self.calls.append((platform, op, acct, prm, key, internal)); r = self.script.get(op)
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
        sq = s.calls[2][3]; self.assertEqual(sq["budget_micro"], 20_000_000); self.assertEqual(sq["status"], "PAUSED"); self.assertEqual(sq["goal"], "SWIPES")
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
if __name__ == "__main__": unittest.main(verbosity=1)
