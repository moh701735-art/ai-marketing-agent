import importlib.util, os, shutil, subprocess, sys, unittest
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..", "..")
spec = importlib.util.spec_from_file_location("t236", os.path.join(H, "test_p236.py")); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
specb = importlib.util.spec_from_file_location("t236b", os.path.join(H, "test_p236b.py")); tb = importlib.util.module_from_spec(specb); specb.loader.exec_module(tb)
PC = os.path.join(ROOT, "ops", "p236c-sp-request-id.py.txt")
def apply_c(d): return subprocess.run([sys.executable, PC], env={**os.environ, "P236C_BASE": d + "/"}, capture_output=True, text=True)
rd = lambda p: open(p, encoding="utf-8").read()


class T(unittest.TestCase):
    def setUp(self):
        self.d = t.mk(); assert "APPLY236_OK" in t.apply(self.d).stdout; assert "APPLY236B_OK" in tb.apply_b(self.d).stdout
    def tearDown(self): shutil.rmtree(self.d, ignore_errors=True)

    def test_01_request_id_added_only_to_campaign_op(self):
        cat = os.path.join(self.d, "broker/app/catalog.py"); before = t.load_ops(cat); r = apply_c(self.d); self.assertIn("APPLY236C_OK", r.stdout, r.stdout + r.stderr); after = t.load_ops(cat)
        self.assertEqual(set(after["tiktok.sp_create_campaign"]["params"]) - set(before["tiktok.sp_create_campaign"]["params"]), {"request_id"})
        self.assertEqual(after["tiktok.sp_create_campaign"]["params"]["request_id"]["kind"], "id"); self.assertFalse(after["tiktok.sp_create_campaign"]["params"]["request_id"].get("required", False))
        self.assertEqual(after["tiktok.sp_create_adgroup"], before["tiktok.sp_create_adgroup"]); self.assertEqual(after["tiktok.read_adgroups"], before["tiktok.read_adgroups"])
        self.assertEqual(after["tiktok.sp_create_campaign"]["forced"], before["tiktok.sp_create_campaign"]["forced"])
        self.assertEqual(sum(1 for l in rd(cat).split("\n") if "p236c" in l), 1); self.assertTrue(os.path.exists(cat + ".pre236c"))
    def test_02_idempotent_requires_p236b_and_anchor_failure(self):
        apply_c(self.d); self.assertIn("changed=0", apply_c(self.d).stdout)
        d2 = t.mk(); assert "APPLY236_OK" in t.apply(d2).stdout
        try: r = apply_c(d2); self.assertNotEqual(r.returncode, 0); self.assertIn("p236b must be applied first", r.stdout + r.stderr)
        finally: shutil.rmtree(d2, ignore_errors=True)
        d3 = t.mk(); t.apply(d3); tb.apply_b(d3); cat = os.path.join(d3, "broker/app/catalog.py"); txt = rd(cat).replace("AUTO_BUDGET_INCREASE", "X"); open(cat, "w", encoding="utf-8").write(txt)
        try: r = apply_c(d3); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertEqual(rd(cat), txt)
        finally: shutil.rmtree(d3, ignore_errors=True)
    def test_03_script_v3_request_id_and_hex_errors(self):
        apply_c(self.d); path = os.path.join(self.d, "ops/tt-smart-toggle-test.py"); self.assertEqual(rd(path), rd(os.path.join(ROOT, "ops", "tt-smart-toggle-test.py")))
        sp = importlib.util.spec_from_file_location("tst3", path); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); compile(m.PY, "PY", "exec")
        rid = m.new_request_id(); self.assertTrue(rid.isdigit() and 18 <= len(rid) <= 24); self.assertEqual(m.build_params(5, request_id="123")["request_id"], "123"); self.assertTrue(m.build_params(5)["request_id"].isdigit())
        out = m.err_lines({"class": "bad_request", "platform_code": "40002", "message": "request_id: Missing data for required field. تجربة"}); txt = "\n".join(out)
        self.assertIn("platform_code=40002", txt); self.assertIn("MSG(ascii)=request_id: Missing data for required field.", txt)
        hx = [l for l in out if l.startswith("  MSGHEX=")][0][9:]; self.assertTrue(bytes.fromhex(hx).decode("utf-8", "ignore").startswith("request_id: Missing data"))
        self.assertEqual(m.err_lines(None)[0], "  class=None platform_code=None")
        src = rd(path)
        for bad in ("set_campaign_status", "sp_create_adgroup", "sp_create_ad"): self.assertNotIn(bad, src)
    def test_04_embedded_script_matches_repo_file(self): self.assertIn(repr(rd(os.path.join(ROOT, "ops", "tt-smart-toggle-test.py"))), rd(PC))


if __name__ == "__main__":
    unittest.main(verbosity=2)
