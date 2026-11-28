import importlib.util, os, shutil, subprocess, sys, unittest
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..")
def _load(n, f):
    spec = importlib.util.spec_from_file_location(n, os.path.join(H, f)); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
t230 = _load("t230", "test_p230.py"); t230c = _load("t230c", "test_p230c.py"); t230d = _load("t230d", "test_p230d.py")
subprocess.run([sys.executable, os.path.join(ROOT, "build_patch_e.py")], check=True, capture_output=True)
PATCH_E = os.path.join(ROOT, "..", "ops", "p230e-tt-window-night.py.txt")
ING = "n8n/wf_ingress.py"
rd = lambda p: open(p, encoding="utf-8").read()
def apply_e(d): return subprocess.run([sys.executable, PATCH_E], env={**os.environ, "P230E_BASE": d + "/"}, capture_output=True, text=True)
class T(unittest.TestCase):
    def setUp(self):
        self.d = t230.mk(); assert "APPLY230_OK" in t230.apply(self.d).stdout; assert "APPLY230C_OK" in t230c.apply_c(self.d).stdout; assert "APPLY230D_OK" in t230d.apply_d(self.d).stdout
    def tearDown(self): shutil.rmtree(self.d, ignore_errors=True)
    def test_01_apply_backup_idempotent(self):
        before = rd(os.path.join(self.d, ING)); r = apply_e(self.d); self.assertIn("APPLY230E_OK", r.stdout, r.stdout + r.stderr)
        self.assertEqual(rd(os.path.join(self.d, ING + ".pre230e")), before); after = rd(os.path.join(self.d, ING)); self.assertEqual(after.count("p230e"), 1); self.assertIn("changed=0", apply_e(self.d).stdout)
    def test_02_owner_example_in_patched_node(self):
        apply_e(self.d); ns = {}; exec(rd(os.path.join(self.d, ING)), ns); js = ns["A"]
        l = t230.node(js, {"text": "ارفع حمله بكرة ساعه 7 صبح وقفها ساعه 1 بالليل ميزانيه 20 دولار", "chatId": 1, "updateId": 2}, {"budget": 20})[0]["json"]["launch"]
        self.assertTrue(l["end_at"].endswith("22:00:00"), l)   # 01:00 بغداد = 22:00Z (اليوم السابق للتاريخ المحلي)
    def test_03_refuses_when_line_modified(self):
        p = os.path.join(self.d, ING); t = rd(p); self.assertEqual(t.count("const to24"), 1); open(p, "w", encoding="utf-8").write(t.replace("const to24", "const to24x")); b = rd(p)
        r = apply_e(self.d); self.assertNotEqual(r.returncode, 0); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertEqual(rd(p), b); self.assertFalse(os.path.exists(p + ".pre230e"))
    def test_04_build_failure_restores(self):
        open(os.path.join(self.d, "n8n/build.py"), "w").write("import sys; sys.exit(1)\n"); p = os.path.join(self.d, ING); b = rd(p); r = apply_e(self.d)
        self.assertNotEqual(r.returncode, 0); self.assertIn("restored", r.stdout + r.stderr); self.assertEqual(rd(p), b)
if __name__ == "__main__": unittest.main()
