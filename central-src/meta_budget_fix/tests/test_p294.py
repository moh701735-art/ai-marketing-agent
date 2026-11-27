import asyncio, importlib.util, os, re, subprocess, sys, unittest
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..", "..")
spec = importlib.util.spec_from_file_location("t286", os.path.join(ROOT, "meta_objectives", "tests", "test_p286.py")); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
P294 = os.path.join(ROOT, "ops", "p294-meta-daily-1day.py.txt")
LEGACY = '''

def legacy_adset(p, minor, end, cid, post):
    return {"name": p["name"] + " - adset", "campaign_id": cid, "page_id": post["page_id"], "whatsapp_phone_number": p["whatsapp"], "end_time": end, "countries": p["countries"],
            "age_min": p["age_min"], "age_max": p["age_max"], ("daily_budget" if p["budget_mode"] == "daily" else "lifetime_budget"): minor}
'''
def prep(legacy=True):
    d = t.tree(); r = t.apply(d); assert "APPLY286_OK" in r.stdout, r.stdout + r.stderr
    if legacy:
        m = d + "/broker/app/metaflow.py"; open(m, "a", encoding="utf-8").write(LEGACY)
    return d
def ap(d): return subprocess.run([sys.executable, P294], env={**os.environ, "P294_BASE": d + "/"}, capture_output=True, text=True)
class T(unittest.TestCase):
    def test_apply_and_behaviour(self):
        d = prep(); r = ap(d); self.assertIn("APPLY294_OK daily budget", r.stdout, r.stdout + r.stderr)
        src = t.rd(d + "/broker/app/metaflow.py"); self.assertEqual(src.count('int(p.get("days") or 0) > 1'), 2); self.assertNotIn('p["budget_mode"] == "daily" else', src)
        self.assertTrue(os.path.exists(d + "/broker/app/metaflow.py.pre294")); self.assertIn("changed=0", ap(d).stdout)
        # launch_objective: يومية + يوم واحد => lifetime
        for mode, days, key in (("daily", 1, "lifetime_budget"), ("daily", 2, "daily_budget"), ("daily", 7, "daily_budget"), ("total", 1, "lifetime_budget"), ("total", 3, "lifetime_budget")):
            svc = t.Svc(); res = t.run_mf(d, t.GOOD(budget_mode=mode, days=days), svc); self.assertTrue(res[1]["ok"], res)
            ap_ = [c for c in svc.calls if c[0] == "meta.create_adset_obj"][0][1]
            self.assertIn(key, ap_, (mode, days, ap_)); self.assertNotIn("daily_budget" if key == "lifetime_budget" else "lifetime_budget", ap_)
            self.assertEqual(ap_[key], 500 if True else 0)   # نفس المبلغ بالسنت (5 دولار) بالحالتين
        # المسار القديم (الشكل الحي): نفس التحويل
        mf = t.load("mf%d" % id(d), d + "/broker/app/metaflow.py"); post = {"page_id": "9"}
        base = {"name": "n", "whatsapp": "1", "countries": ["IQ"], "age_min": 18, "age_max": 65}
        for mode, days, key in (("daily", 1, "lifetime_budget"), ("daily", 2, "daily_budget"), ("total", 1, "lifetime_budget")):
            out = mf.legacy_adset({**base, "budget_mode": mode, "days": days}, 777, "E", "1", post); self.assertIn(key, out); self.assertEqual(out[key], 777); self.assertEqual(len([k for k in out if k.endswith("_budget")]), 1)
        out = mf.legacy_adset({**base, "budget_mode": "daily"}, 5, "E", "1", post); self.assertIn("lifetime_budget", out)   # days مفقود => إجمالية (الأكثر أماناً)
    def test_fail_closed_wrong_count(self):
        d = prep(legacy=False); before = t.rd(d + "/broker/app/metaflow.py"); r = ap(d); self.assertIn("PATCH FAIL (nothing written)", r.stderr + r.stdout); self.assertIn("count=1", r.stderr + r.stdout)
        self.assertEqual(t.rd(d + "/broker/app/metaflow.py"), before); self.assertFalse(os.path.exists(d + "/broker/app/metaflow.py.pre294"))
        d = prep(); open(d + "/broker/app/metaflow.py", "a").write(LEGACY.replace("legacy_adset", "legacy2")); self.assertIn("count=3", ap(d).stderr + ap(d).stdout)
    def test_missing_file(self):
        import tempfile; d = tempfile.mkdtemp(); os.makedirs(d + "/broker/app"); self.assertIn("PATCH FAIL", ap(d).stderr + ap(d).stdout)
    def test_oneliner(self):
        s = t.rd(os.path.join(ROOT, "..", "out", "p294s.txt")); self.assertEqual(s.count("\n"), 1); self.assertIn("bash deploy/update.sh", s)
        import base64, lzma
        self.assertEqual(lzma.decompress(base64.b64decode(re.search(r"echo '([^']+)'", s).group(1))).decode(), t.rd(P294))
if __name__ == "__main__": unittest.main()
