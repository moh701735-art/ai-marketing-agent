import asyncio, importlib.util, os, subprocess, sys, tempfile, unittest
H = os.path.dirname(__file__); PATCH = os.path.join(H, "..", "..", "ops", "p229-report-v2.py.txt"); LOOP = open(os.path.join(H, "..", "loop.js"), encoding="utf-8").read().rstrip("\n")
SERVICE = '''
import asyncio, datetime
def num_(v):
    try: return float(v)
    except Exception: return None
class Svc:
    async def day(self, rd, accts, op_name):
        failed = []
        day = datetime.date.today().isoformat()
        async def one_active(acct):
            d = await rd(acct, "tiktok.read_report", {"report_type": "BASIC", "data_level": "AUCTION_AD", "dimensions": ["ad_id"], "metrics": ["campaign_id", "campaign_name", "spend"], "start_date": day, "end_date": day, "page_size": 1000})
            if not d:
                failed.append(acct)
                return []
            agg = {}
            for x in d.get("list") or []:
                m = x.get("metrics") or {}
                cid = str(m.get("campaign_id") or "")
                if not cid:
                    continue
                t = agg.setdefault(cid, {"campaign_id": cid, "ad_account": acct, "name": str(m.get("campaign_name") or "")[:80], "spend": 0.0, "impressions": 0.0, "clicks": 0.0, "results": 0.0, "reach": 0.0})
                for k, mk in (("spend", "spend"), ("results", "result")):
                    v = num_(m.get(mk))
                    t[k] += v or 0.0
            rows = [t for t in agg.values() if t["spend"] > 0]
            if op_name == "tiktok.day_report":
                cl = await rd(acct, "tiktok.read_campaigns", {"page": 1, "page_size": 100})
                stm = {str(c.get("campaign_id")): str(c.get("operation_status") or c.get("secondary_status") or "") for c in ((cl or {}).get("list") or [])}
                for t in rows:
                    t["status"] = stm.get(t["campaign_id"]) or ""
            if rows:
                ad0 = await rd(acct, "tiktok.read_advertiser", {"fields": ["currency", "name"]})
                a0 = ((ad0 or {}).get("list") or [{}])[0]
                cur = str(a0.get("currency") or "USD").upper()
                fx = 1555.0 if cur == "IQD" else 1.0
                for t in rows:
                    t["currency"] = cur
                    t["spend_local"] = round(t["spend"], 2)
                    t["cost_per_result_local"] = round(t["spend"] / t["results"], 2) if t["results"] else None
                    t["spend_usd"] = round(t["spend"] / fx, 2)
                    t["cost_per_result_usd"] = round(t["spend"] / fx / t["results"], 3) if t["results"] else None
                    t.pop("spend", None)
            return rows
        rs = await asyncio.gather(*[one_active(a) for a in accts])
        rows = [r for rr in rs for r in rr]
        return rows
'''
CAT = '''
class P:
    def __init__(self, kind, *a, **k): self.kind = kind; self.k = k
class Op:
    def __init__(self, name, *a, **k): self.name = name; self.k = k
OPS = [
    Op("tiktok.read_report", "tiktok", "GET", "/report/integrated/get/", bearer=False, advertiser_param="advertiser_id",
       params={"report_type": P("enum", required=True, values=("BASIC",)), "data_level": P("enum", required=True, values=("AUCTION_CAMPAIGN",)),
               "start_date": P("date", required=True), "end_date": P("date", required=True), "page_size": P("int", lo=1, hi=1000)}),
]
'''
JOB = '''
fmt = code(w, "Format", r"""
const groups = {}; const out = []; const sd = {snap: {}};
for (const g of Object.values(groups)) {
  const old = 1;
  out.push(old);
}
return out;
""")
send = call_broker(w, "Send", mode="each")
'''
def apply(d): return subprocess.run([sys.executable, "-"], input=open(PATCH, encoding="utf-8").read(), text=True, capture_output=True, env=dict(os.environ, P229_BASE=d + "/"))
class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); os.makedirs(self.d + "/broker/app"); os.makedirs(self.d + "/n8n")
        for f, s in (("broker/app/service.py", SERVICE), ("broker/app/catalog.py", CAT), ("n8n/wf_job_report.py", JOB)): open(self.d + "/" + f, "w", encoding="utf-8").write(s)
    def load(self, name, f):
        spec = importlib.util.spec_from_file_location(name, self.d + "/" + f); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
    def rd(self, life, secs=None, lifefail=False, calls=None):
        async def rd(acct, op, params):
            if calls is not None: calls.append((op, dict(params)))
            if op == "tiktok.read_report" and params["data_level"] == "AUCTION_AD": return {"list": [{"metrics": {"campaign_id": "1", "campaign_name": "بخاخ", "spend": "7916", "result": "20"}}, {"metrics": {"campaign_id": "2", "campaign_name": "ثانية", "spend": "100", "result": "0"}}]}
            if op == "tiktok.read_report": return None if lifefail else {"list": [{"dimensions": {"campaign_id": k}, "metrics": {"spend": str(v)}} for k, v in life.items()]}
            if op == "tiktok.read_campaigns": return {"list": [{"campaign_id": "1", "operation_status": "ENABLE", "secondary_status": (secs or {}).get("1", "CAMPAIGN_STATUS_DELIVERY_OK")}, {"campaign_id": "2", "operation_status": "DISABLE", "secondary_status": "CAMPAIGN_STATUS_DISABLE"}]}
            if op == "tiktok.read_advertiser": return {"list": [{"currency": "IQD", "name": "بنين"}]}
        return rd
    def run_(self, rd, op="tiktok.day_report"): return asyncio.run(self.load("s", "broker/app/service.py").Svc().day(rd, ["A1"], op))
    def test_01_apply_all_three_idempotent_backups_markers(self):
        r = apply(self.d); self.assertIn("APPLY229_OK report v2", r.stdout, r.stderr)
        for f in ("broker/app/service.py", "broker/app/catalog.py", "n8n/wf_job_report.py"): self.assertTrue(os.path.exists(self.d + "/" + f + ".pre229"), f)
        self.assertIn("changed=0", apply(self.d).stdout)
    def test_02_day_report_adds_lifetime_and_sec_status(self):
        apply(self.d); calls = []; rows = self.run_(self.rd({"1": 20000.0}, calls=calls)); r1 = [r for r in rows if r["campaign_id"] == "1"][0]
        self.assertEqual(r1["spend_life_local"], 20000.0); self.assertEqual(r1["spend_life_usd"], round(20000 / 1555.0, 2)); self.assertEqual(r1["sec_status"], "CAMPAIGN_STATUS_DELIVERY_OK"); self.assertEqual(r1["status"], "ENABLE"); self.assertNotIn("_life", r1)
        lc = [p for o, p in calls if o == "tiktok.read_report" and p["data_level"] == "AUCTION_CAMPAIGN"]; self.assertEqual(len(lc), 1); self.assertEqual(lc[0]["query_lifetime"], "true"); self.assertEqual(lc[0]["metrics"], ["spend"]); self.assertEqual(lc[0]["start_date"], lc[0]["end_date"])
    def test_03_missing_lifetime_gives_none_not_fake_number(self):
        apply(self.d); rows = self.run_(self.rd({}, lifefail=True)); r1 = [r for r in rows if r["campaign_id"] == "1"][0]; self.assertIsNone(r1["spend_life_local"]); self.assertIsNone(r1["spend_life_usd"])
        rows = self.run_(self.rd({"9": 5})); self.assertIsNone([r for r in rows if r["campaign_id"] == "1"][0]["spend_life_local"])
    def test_04_other_ops_do_not_call_lifetime(self):
        apply(self.d); calls = []; rows = self.run_(self.rd({"1": 1}, calls=calls), op="tiktok.report_summary")
        self.assertFalse([p for o, p in calls if o == "tiktok.read_report" and p["data_level"] == "AUCTION_CAMPAIGN"]); self.assertIsNone(rows[0]["spend_life_local"]); self.assertNotIn("sec_status", rows[0])
    def test_05_catalog_allows_query_lifetime_only_on_read_report(self):
        apply(self.d); ns = self.load("c", "broker/app/catalog.py"); p = ns.OPS[0].k["params"]; self.assertIn("query_lifetime", p); self.assertEqual(p["query_lifetime"].kind, "enum"); self.assertIn("start_date", p)
    def test_06_job_report_loop_replaced_rest_kept(self):
        apply(self.d); s = open(self.d + "/n8n/wf_job_report.py", encoding="utf-8").read(); self.assertIn(LOOP, s); self.assertIn("const groups = {}; const out = []; const sd = {snap: {}};", s); self.assertTrue(s.rstrip().endswith('send = call_broker(w, "Send", mode="each")')); self.assertNotIn("const old = 1;", s)
        self.assertEqual(s.count("return out;"), 1); self.assertEqual(sum(1 for l in s.split("\n") if "p229" in l), 1)
    def test_07_any_missing_anchor_writes_nothing_to_any_file(self):
        before = {f: open(self.d + "/" + f, encoding="utf-8").read() for f in ("broker/app/service.py", "broker/app/catalog.py", "n8n/wf_job_report.py")}
        open(self.d + "/n8n/wf_job_report.py", "w", encoding="utf-8").write("nothing")
        r = apply(self.d); self.assertIn("PATCH FAIL (nothing written)", r.stderr); self.assertIn("report loop anchor count=0", r.stderr)
        for f in ("broker/app/service.py", "broker/app/catalog.py"): self.assertEqual(open(self.d + "/" + f, encoding="utf-8").read(), before[f])
    def test_08_today_variable_name_is_detected_not_assumed(self):
        open(self.d + "/broker/app/service.py", "w", encoding="utf-8").write(SERVICE.replace("day = datetime", "today = datetime").replace("start_date\": day, \"end_date\": day", "start_date\": today, \"end_date\": today"))
        r = apply(self.d); self.assertIn("APPLY229_OK", r.stdout, r.stderr); s = open(self.d + "/broker/app/service.py", encoding="utf-8").read(); self.assertIn('"start_date": today, "end_date": today, "page_size": 1000})', s)
if __name__ == "__main__": unittest.main(verbosity=1)
