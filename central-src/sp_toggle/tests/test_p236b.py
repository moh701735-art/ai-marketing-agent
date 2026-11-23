import importlib.util, os, shutil, subprocess, sys, unittest
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..", "..")
spec = importlib.util.spec_from_file_location("t236", os.path.join(H, "test_p236.py")); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
PB = os.path.join(ROOT, "ops", "p236b-sp-budget-mode.py.txt")
def apply_b(d): return subprocess.run([sys.executable, PB], env={**os.environ, "P236B_BASE": d + "/"}, capture_output=True, text=True)
rd = lambda p: open(p, encoding="utf-8").read()


class T(unittest.TestCase):
    def setUp(self): self.d = t.mk(); assert "APPLY236_OK" in t.apply(self.d).stdout
    def tearDown(self): shutil.rmtree(self.d, ignore_errors=True)

    def test_01_enum_extended_nothing_else_changes(self):
        cat = os.path.join(self.d, "broker/app/catalog.py"); before = t.load_ops(cat); r = apply_b(self.d); self.assertIn("APPLY236B_OK", r.stdout, r.stdout + r.stderr); after = t.load_ops(cat)
        self.assertEqual(after["tiktok.sp_create_campaign"]["params"]["budget_mode"]["values"], ("BUDGET_MODE_TOTAL", "BUDGET_MODE_DYNAMIC_DAILY", "BUDGET_MODE_DYNAMIC_DAILY_BUDGET"))
        for name in before:
            b = dict(before[name]); a = dict(after[name])
            if name == "tiktok.sp_create_campaign":
                b["params"] = {k: v for k, v in b["params"].items() if k != "budget_mode"}; a["params"] = {k: v for k, v in a["params"].items() if k != "budget_mode"}
            self.assertEqual(a, b, name)
        self.assertEqual(sum(1 for l in rd(cat).split("\n") if "p236b" in l), 1); self.assertTrue(os.path.exists(cat + ".pre236b"))
    def test_02_idempotent_and_requires_p236(self):
        apply_b(self.d); self.assertIn("changed=0", apply_b(self.d).stdout)
        d2 = t.mk()
        try: r = apply_b(d2); self.assertNotEqual(r.returncode, 0); self.assertIn("p236 must be applied first", r.stdout + r.stderr)
        finally: shutil.rmtree(d2, ignore_errors=True)
    def test_03_anchor_failure_writes_nothing(self):
        cat = os.path.join(self.d, "broker/app/catalog.py"); txt = rd(cat).replace('"BUDGET_MODE_DYNAMIC_DAILY")', '"X")'); open(cat, "w", encoding="utf-8").write(txt)
        r = apply_b(self.d); self.assertNotEqual(r.returncode, 0); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertEqual(rd(cat), txt); self.assertFalse(os.path.exists(cat + ".pre236b"))
    def test_04_script_v2_modes_and_scope(self):
        apply_b(self.d); path = os.path.join(self.d, "ops/tt-smart-toggle-test.py"); self.assertEqual(rd(path), rd(os.path.join(H, "script_v2.py")))
        spec2 = importlib.util.spec_from_file_location("tst2", path); m = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(m); compile(m.PY, "PY", "exec")
        self.assertEqual(m.build_params(10000)["budget_mode"], "BUDGET_MODE_DYNAMIC_DAILY_BUDGET"); self.assertEqual(m.build_params(10000, "TOTAL")["budget_mode"], "BUDGET_MODE_TOTAL")
        self.assertEqual(set(m.MODES.values()), {"BUDGET_MODE_DYNAMIC_DAILY_BUDGET", "BUDGET_MODE_TOTAL"}); self.assertEqual(m.build_params(5)["budget_auto_adjust_strategy"], "AUTO_BUDGET_INCREASE")
        src = rd(path)
        for bad in ("set_campaign_status", "sp_create_adgroup", "sp_create_ad", "BUDGET_MODE_DYNAMIC_DAILY\""): self.assertNotIn(bad, src)
    def test_05_embedded_script_matches_repo_file(self):
        self.assertIn(repr(rd(os.path.join(H, "script_v2.py"))), rd(PB))


if __name__ == "__main__":
    unittest.main(verbosity=2)
