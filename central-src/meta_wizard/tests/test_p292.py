import asyncio, importlib.util, os, subprocess, sys, unittest
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..", "..")
spec = importlib.util.spec_from_file_location("t286", os.path.join(ROOT, "meta_objectives", "tests", "test_p286.py"))
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
P292 = os.path.join(ROOT, "ops", "p292-meta-wizard-pages.py.txt")
WIZ_OLD = "# old wizard p287\nSEQ = 1\n"
def prep(wiz=WIZ_OLD):
    d = t.tree(); r = t.apply(d); assert "APPLY286_OK" in r.stdout, r.stdout + r.stderr
    m = d + "/broker/app/metaflow.py"; x = t.rd(m); assert x.count('"page_id": "111"') == 1; open(m, "w", encoding="utf-8").write(x.replace('"page_id": "111"', '"page_id": "1110011"'))
    os.makedirs(d + "/meta_wizard"); open(d + "/meta_wizard/wizard.py", "w", encoding="utf-8").write(wiz); return d
def ap(d): return subprocess.run([sys.executable, P292], env={**os.environ, "P292_BASE": d + "/"}, capture_output=True, text=True)
class T(unittest.TestCase):
    def test_apply_and_behaviour(self):
        d = prep(); r = ap(d); self.assertIn("APPLY292_OK page step", r.stdout, r.stdout + r.stderr)
        self.assertEqual(t.rd(d + "/meta_wizard/wizard.py.pre292"), WIZ_OLD); self.assertIn("p292", t.rd(d + "/broker/app/metaflow.py")); self.assertTrue(os.path.exists(d + "/broker/app/metaflow.py.pre292"))
        self.assertIn("changed=0", ap(d).stdout)
        # page_id مطابق لصفحة المنشور (الوهمي يرجع 111) → ينجح
        svc = t.Svc(); res = t.run_mf(d, t.GOOD(page_id="1110011"), svc); self.assertTrue(res[1]["ok"], res)
        ap_ = [c for c in svc.calls if c[0] == "meta.create_adset_obj"][0][1]; self.assertEqual(ap_["page_id"], "1110011")
        # صفحة غير مطابقة → رفض قبل أي إنشاء
        svc = t.Svc(); res = t.run_mf(d, t.GOOD(page_id="2220022"), svc)
        self.assertFalse(res[1]["ok"]); self.assertIn("post_not_from_selected_page", res[1]["error"]["message"]); self.assertEqual(res[1]["data"]["stage"], "post")
        self.assertFalse([c for c in svc.calls if c[0].startswith("meta.create")], svc.calls)
        # page_id غير رقمي → رفض
        svc = t.Svc(); res = t.run_mf(d, t.GOOD(page_id="abc"), svc); self.assertFalse(res[1]["ok"]); self.assertFalse(svc.calls)
        # بدون page_id → السلوك القديم
        svc = t.Svc(); res = t.run_mf(d, t.GOOD(), svc); self.assertTrue(res[1]["ok"])
        svc = t.Svc(); res = t.run_mf(d, t.GOOD(page_id=""), svc); self.assertTrue(res[1]["ok"])
        # واتساب القديم ما تغيّر
        res = t.run_mf(d, {"anything": 1}, t.Svc()); self.assertEqual(res[1]["data"], {"wa": True})
    def test_fail_closed(self):
        d = prep(); s = t.rd(d + "/broker/app/metaflow.py").replace('    # 1) حملة (PAUSED بالكتالوج)\n', '    # 1) camp\n'); open(d + "/broker/app/metaflow.py", "w", encoding="utf-8").write(s)
        w0 = t.rd(d + "/meta_wizard/wizard.py"); r = ap(d); self.assertIn("PATCH FAIL (nothing written)", r.stderr + r.stdout); self.assertEqual(t.rd(d + "/meta_wizard/wizard.py"), w0); self.assertFalse(os.path.exists(d + "/meta_wizard/wizard.py.pre292"))
    def test_requires_p286_and_wizard(self):
        d = t.tree(); os.makedirs(d + "/meta_wizard"); open(d + "/meta_wizard/wizard.py", "w").write(WIZ_OLD); self.assertIn("PATCH FAIL", ap(d).stderr + ap(d).stdout)
        d = prep(); os.remove(d + "/meta_wizard/wizard.py"); self.assertIn("PATCH FAIL", ap(d).stderr + ap(d).stdout)
    def test_build_failure_restores(self):
        d = prep(); os.makedirs(d + "/n8n"); open(d + "/n8n/build.py", "w").write("import sys; sys.exit(3)\n"); mf0 = t.rd(d + "/broker/app/metaflow.py")
        r = ap(d); self.assertIn("build failed, restored", r.stderr + r.stdout); self.assertEqual(t.rd(d + "/broker/app/metaflow.py"), mf0); self.assertEqual(t.rd(d + "/meta_wizard/wizard.py"), WIZ_OLD)
    def test_oneliner_and_wizard_embedded(self):
        s = t.rd(os.path.join(ROOT, "..", "out", "p292s.txt")); self.assertEqual(s.count("\n"), 1); self.assertIn("bash deploy/update.sh", s)
        import re, base64, lzma
        body = lzma.decompress(base64.b64decode(re.search(r"echo '([^']+)'", s).group(1))).decode(); self.assertEqual(body, t.rd(P292))
if __name__ == "__main__": unittest.main()
