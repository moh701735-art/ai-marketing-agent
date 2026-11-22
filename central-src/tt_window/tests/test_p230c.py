import importlib.util, json, os, shutil, subprocess, sys, unittest
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..")
spec = importlib.util.spec_from_file_location("t230", os.path.join(H, "test_p230.py")); t230 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t230)
subprocess.run([sys.executable, os.path.join(ROOT, "build_patch_c.py")], check=True, capture_output=True)
PATCH_C = os.path.join(ROOT, "..", "ops", "p230c-tt-window-days.py.txt")
ING = "n8n/wf_ingress.py"
rd = lambda p: open(p, encoding="utf-8").read()


def apply_c(d):
    return subprocess.run([sys.executable, PATCH_C], env={**os.environ, "P230C_BASE": d + "/"}, capture_output=True, text=True)


class T(unittest.TestCase):
    def setUp(self):
        self.d = t230.mk(); r = t230.apply(self.d); assert "APPLY230_OK" in r.stdout, r.stdout + r.stderr
    def tearDown(self): shutil.rmtree(self.d, ignore_errors=True)

    def test_01_upgrade_replaces_block_exactly(self):
        before = rd(os.path.join(self.d, ING)); r = apply_c(self.d); self.assertIn("APPLY230C_OK", r.stdout, r.stdout + r.stderr)
        after = rd(os.path.join(self.d, ING)); self.assertEqual(rd(os.path.join(self.d, ING + ".pre230c")), before)
        blk = rd(os.path.join(ROOT, "block_v2.js")).rstrip("\n"); self.assertIn("\n" + blk.split("\n")[0], "\n" + after)
        self.assertEqual(sum(1 for l in after.split("\n") if "p230c" in l), 2); self.assertEqual(sum(1 for l in after.split("\n") if "p230" in l), 3)
        self.assertEqual(after.count("/*p230*/"), 1)                                  # بطاقة النتيجة لم تتغيّر
        self.assertNotIn("const dOff = /", after)                                      # فحص اليوم العام انحذف
        self.assertIn("APPLY230C_OK", r.stdout); self.assertIn("changed=0", apply_c(self.d).stdout)

    def test_02_patched_node_behaviour(self):
        apply_c(self.d); ns = {}; exec(rd(os.path.join(self.d, ING)), ns); js = ns["A"]
        out = t230.node(js, {"text": "روجها 22:00 وقفها بكرة 7 صباحا ميزانية 30 دولار", "chatId": 1, "updateId": 2}, {"budget": 30})
        l = out[0]["json"]["launch"]; self.assertIn("start_at", l); self.assertEqual(l["budget"], 30)
        out = t230.node(js, {"text": "ارفع حمله 30 دولار يوم واحد", "chatId": 1, "updateId": 2}, {"budget": 30})
        self.assertNotIn("start_at", out[0]["json"]["launch"])
        out = t230.node(js, {"text": "روجها 22:00 وقفها 10:00", "chatId": 1, "updateId": 2}, {"budget": 30}); self.assertIn("say", out)

    def test_03_requires_p230(self):
        d = t230.mk()
        try: r = apply_c(d); self.assertNotEqual(r.returncode, 0); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr)
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_04_modified_installed_block_refused_and_untouched(self):
        p = os.path.join(self.d, ING); txt = rd(p).replace("const BG = 3 * 3600000", "const BG = 3 * 3600001"); open(p, "w", encoding="utf-8").write(txt)
        r = apply_c(self.d); self.assertNotEqual(r.returncode, 0); self.assertIn("differs", r.stdout + r.stderr)
        self.assertEqual(rd(p), txt); self.assertFalse(os.path.exists(p + ".pre230c"))

    def test_05_build_failure_restores(self):
        open(os.path.join(self.d, "n8n/build.py"), "w").write("import sys; sys.exit(1)\n")
        p = os.path.join(self.d, ING); before = rd(p); r = apply_c(self.d)
        self.assertNotEqual(r.returncode, 0); self.assertIn("restored", r.stdout + r.stderr); self.assertEqual(rd(p), before)

    def test_06_embedded_blocks_match_files(self):
        t = rd(PATCH_C); self.assertIn("OLD = r'''" + rd(os.path.join(ROOT, "block_v1.js")).rstrip("\n") + "'''", t); self.assertIn("NEW = r'''" + rd(os.path.join(ROOT, "block_v2.js")).rstrip("\n") + "'''", t)

    def test_07_v1_block_equals_what_p230_installs(self):
        # الكتلة القديمة بالرقعة = حرفياً اللي ركّبتها p230 (المطبّقة بالسيرفر)
        blk = rd(os.path.join(ROOT, "block_v1.js")).rstrip("\n"); self.assertIn("BLOCK = r'''" + blk + "'''", rd(os.path.join(ROOT, "..", "ops", "p230-tt-window.py.txt")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
