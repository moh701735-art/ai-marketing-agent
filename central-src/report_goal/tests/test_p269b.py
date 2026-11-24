# -*- coding: utf-8 -*-
import asyncio, importlib.util, os, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); OPS = os.path.join(H, "..", "..", "ops"); P229 = os.path.join(OPS, "p229-report-v2.py.txt"); P269 = os.path.join(OPS, "p269b-report-goal.py.txt")
sys.path.insert(0, os.path.join(H, "..", "..", "report_v2", "tests")); import test_p229 as t229                      # نفس fixtures الحقيقية (مبنية من نص الخادم)
rd_ = lambda p: open(p, encoding="utf-8").read()
def sh(path, d, var): return subprocess.run([sys.executable, path], env={**os.environ, var: d + "/"}, capture_output=True, text=True)


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); os.makedirs(self.d + "/broker/app"); os.makedirs(self.d + "/n8n")
        for f, s in (("broker/app/service.py", t229.SERVICE), ("broker/app/catalog.py", t229.CAT), ("n8n/wf_job_report.py", t229.JOB)): open(self.d + "/" + f, "w", encoding="utf-8").write(s)
        r = sh(P229, self.d, "P229_BASE") if False else subprocess.run([sys.executable, "-"], input=rd_(P229), text=True, capture_output=True, env={**os.environ, "P229_BASE": self.d + "/"})
        assert "APPLY229_OK" in r.stdout, r.stdout + r.stderr
    def load(self):
        s = importlib.util.spec_from_file_location("s%d" % id(self), self.d + "/broker/app/service.py"); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
    def rd(self, calls, goals, adg_fail=False, n=1):
        async def rd(acct, op, params):                                                                    # توقيع strict مثل الحي: (acct, op, params)
            calls.append((op, dict(params)))
            if op == "tiktok.read_report" and params["data_level"] == "AUCTION_AD":
                return {"list": [{"metrics": {"campaign_id": str(i), "campaign_name": "c%d" % i, "spend": "100", "result": "5"}} for i in range(1, n + 1)]}
            if op == "tiktok.read_report": return {"list": [{"dimensions": {"campaign_id": str(i)}, "metrics": {"spend": "200"}} for i in range(1, n + 1)]}
            if op == "tiktok.read_campaigns": return {"list": [{"campaign_id": str(i), "operation_status": "ENABLE", "secondary_status": "CAMPAIGN_STATUS_DELIVERY_OK"} for i in range(1, n + 1)]}
            if op == "tiktok.read_advertiser": return {"list": [{"currency": "IQD", "name": "x"}]}
            if op == "tiktok.read_adgroups":
                if adg_fail: raise RuntimeError("boom")
                return {"list": [{"campaign_id": c, "optimization_goal": goals.get(c, "")} for c in params["campaign_ids"]]}
        return rd
    def day(self, rd): return asyncio.run(self.load().Svc().day(rd, ["A1"], "tiktok.day_report"))

    def test_01_apply_backup_idempotent_markers(self):
        r = sh(P269, self.d, "P269B_BASE"); self.assertIn("APPLY269B_OK report labels", r.stdout, r.stderr)
        for f in ("broker/app/service.py", "n8n/wf_job_report.py"): self.assertTrue(os.path.exists(self.d + "/" + f + ".pre269b"))
        self.assertIn("changed=0", sh(P269, self.d, "P269B_BASE").stdout)
        self.assertIn("p269b", rd_(self.d + "/n8n/wf_job_report.py")); self.assertNotIn("📩 رسائل اليوم", rd_(self.d + "/n8n/wf_job_report.py"))

    def test_02_rows_get_goal_batched_by_10(self):
        sh(P269, self.d, "P269B_BASE"); calls = []; goals = {str(i): ("CONVERSATION" if i % 2 else "CLICK") for i in range(1, 13)}
        rows = self.day(self.rd(calls, goals, n=12)); g = {r["campaign_id"]: r["goal"] for r in rows}
        self.assertEqual(g["1"], "CONVERSATION"); self.assertEqual(g["2"], "CLICK")
        ag = [p for o, p in calls if o == "tiktok.read_adgroups"]; self.assertEqual([len(p["campaign_ids"]) for p in ag], [10, 2]); self.assertTrue(all(p["page_size"] == 100 and set(p) == {"campaign_ids", "page_size"} for p in ag))

    def test_03_failure_is_soft_goal_empty(self):
        sh(P269B := P269, self.d, "P269B_BASE"); rows = self.day(self.rd([], {}, adg_fail=True, n=2)); self.assertTrue(rows and all(r["goal"] == "" for r in rows)); self.assertIn("spend_life_local", rows[0])

    def test_04_other_ops_unchanged_no_adgroup_read(self):
        sh(P269, self.d, "P269B_BASE"); calls = []
        asyncio.run(self.load().Svc().day(self.rd(calls, {}), ["A1"], "tiktok.other_op")); self.assertFalse(any(o == "tiktok.read_adgroups" for o, _ in calls))

    def test_05_fail_closed_nothing_written(self):
        for f, mut in (("broker/app/service.py", lambda s: s.replace("# p229", "# p2x9")), ("n8n/wf_job_report.py", lambda s: s.replace("رسائل اليوم", "رسائل اليوم!"))):
            before = {x: rd_(self.d + "/" + x) for x in ("broker/app/service.py", "n8n/wf_job_report.py")}
            open(self.d + "/" + f, "w", encoding="utf-8").write(mut(before[f])); mid = rd_(self.d + "/" + f); r = sh(P269, self.d, "P269B_BASE")
            self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertEqual(rd_(self.d + "/" + f), mid); self.assertFalse(os.path.exists(self.d + "/" + f + ".pre269b"))
            open(self.d + "/" + f, "w", encoding="utf-8").write(before[f])

    def test_06_requires_p229(self):
        d = tempfile.mkdtemp(); os.makedirs(d + "/broker/app"); os.makedirs(d + "/n8n"); open(d + "/broker/app/service.py", "w").write("x=1\n"); open(d + "/n8n/wf_job_report.py", "w").write("y=1\n")
        self.assertIn("p229", sh(P269, d, "P269B_BASE").stdout + sh(P269, d, "P269B_BASE").stderr)

    def test_07_build_failure_restores_both(self):
        open(self.d + "/n8n/build.py", "w").write("import sys; sys.exit(1)\n"); b = {x: rd_(self.d + "/" + x) for x in ("broker/app/service.py", "n8n/wf_job_report.py")}
        r = sh(P269, self.d, "P269B_BASE"); self.assertIn("restored", r.stdout + r.stderr)
        for x, v in b.items(): self.assertEqual(rd_(self.d + "/" + x), v)


if __name__ == "__main__":
    unittest.main(verbosity=1)
