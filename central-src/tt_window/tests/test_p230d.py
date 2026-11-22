import importlib.util, os, shutil, subprocess, sys, unittest
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..")
def _load(n, f):
    spec = importlib.util.spec_from_file_location(n, os.path.join(H, f)); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
t230 = _load("t230", "test_p230.py"); t230c = _load("t230c", "test_p230c.py")
subprocess.run([sys.executable, os.path.join(ROOT, "build_patch_d.py")], check=True, capture_output=True)
PATCH_D = os.path.join(ROOT, "..", "ops", "p230d-tt-window-noverb.py.txt")
ING = "n8n/wf_ingress.py"
rd = lambda p: open(p, encoding="utf-8").read()
def apply_d(d): return subprocess.run([sys.executable, PATCH_D], env={**os.environ, "P230D_BASE": d + "/"}, capture_output=True, text=True)


class T(unittest.TestCase):
    def setUp(self):
        self.d = t230.mk(); assert "APPLY230_OK" in t230.apply(self.d).stdout; assert "APPLY230C_OK" in t230c.apply_c(self.d).stdout
    def tearDown(self): shutil.rmtree(self.d, ignore_errors=True)

    def test_01_upgrade_chain_markers_backup_idempotent(self):
        before = rd(os.path.join(self.d, ING)); r = apply_d(self.d); self.assertIn("APPLY230D_OK", r.stdout, r.stdout + r.stderr)
        after = rd(os.path.join(self.d, ING)); self.assertEqual(rd(os.path.join(self.d, ING + ".pre230d")), before)
        L = after.split("\n"); self.assertEqual(sum(1 for l in L if "p230d" in l), 2); self.assertEqual(sum(1 for l in L if "p230c" in l), 2); self.assertEqual(sum(1 for l in L if "p230" in l), 4)
        self.assertEqual(after.count("/*p230*/"), 1); self.assertIn("changed=0", apply_d(self.d).stdout)

    def test_02_owner_message_in_patched_node(self):
        apply_d(self.d); ns = {}; exec(rd(os.path.join(self.d, ING)), ns); js = ns["A"]
        txt = "ارفع حمله ساعه ١٠ بليل\nوقفها ساعه ٧ صبح\n\nيوم واحد\nميزانيه ٢٠ الف\nبحساب boostpro13\n\nعميل محتمل واتساب\n07829503973"
        l = t230.node(js, {"text": txt, "chatId": 1, "updateId": 2}, {"budget": 20000})[0]["json"]["launch"]
        self.assertIn("start_at", l); self.assertEqual(l["budget"], 30)                       # بقية الإعدادات ما تغيّرت (launch الاصطناعي)
        out = t230.node(js, {"text": "ارفع حمله ساعه 10 وقفها ساعه 7 صبح", "chatId": 1, "updateId": 2}, {"budget": 30}); self.assertIn("say", out)
        out = t230.node(js, {"text": "ارفع حمله عميل محتمل 07829503973 ميزانيه 20 الف", "chatId": 1, "updateId": 2}, {"budget": 20000}); self.assertNotIn("start_at", out[0]["json"]["launch"])

    def test_03_requires_v2_block(self):
        d = t230.mk()
        try:
            t230.apply(d); r = apply_d(d); self.assertNotEqual(r.returncode, 0); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertIn("differs", r.stdout + r.stderr)
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_04_build_failure_restores(self):
        open(os.path.join(self.d, "n8n/build.py"), "w").write("import sys; sys.exit(1)\n"); p = os.path.join(self.d, ING); before = rd(p); r = apply_d(self.d)
        self.assertNotEqual(r.returncode, 0); self.assertIn("restored", r.stdout + r.stderr); self.assertEqual(rd(p), before)

    def test_05_embedded_blocks_match_files(self):
        t = rd(PATCH_D); self.assertIn("OLD = r'''" + rd(os.path.join(ROOT, "block_v2.js")).rstrip("\n") + "'''", t); self.assertIn("NEW = r'''" + rd(os.path.join(ROOT, "block.js")).rstrip("\n") + "'''", t)

    def test_06_v2_equals_what_p230c_installs(self):
        self.assertIn("NEW = r'''" + rd(os.path.join(ROOT, "block_v2.js")).rstrip("\n") + "'''", rd(os.path.join(ROOT, "..", "ops", "p230c-tt-window-days.py.txt")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
