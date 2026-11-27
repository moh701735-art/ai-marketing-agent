import importlib.util, os, unittest
H = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("pe", os.path.join(H, "..", "..", "ops", "platform-enable.py")); pe = importlib.util.module_from_spec(spec); spec.loader.exec_module(pe)
def go(rows, apply_=False, slug="zainab-forever", plat="meta"):
    calls, out = [], []
    def db(sql, v=None):
        calls.append((sql, v or {}))
        if sql.lstrip().upper().startswith("SELECT C.CONNECTION_ID"): return rows
        return "1|1"
    rc = pe.run(slug, plat, apply_, db=db, out=out.append); return rc, "\n".join(out), calls
class T(unittest.TestCase):
    def test_dry_run_expired_writes_nothing(self):
        rc, o, calls = go("b91885c0-8645|expired|false"); self.assertEqual(rc, 0); self.assertIn("فحص فقط", o); self.assertEqual(len(calls), 1)
    def test_apply_expired(self):
        rc, o, calls = go("b91885c0-8645|expired|false", True); self.assertEqual(rc, 0); self.assertEqual(len(calls), 2); self.assertIn("تم", o)
        self.assertEqual(calls[1][1]["plat"], "meta"); self.assertEqual(calls[1][1]["cid"], "b91885c0-8645"); self.assertEqual(calls[1][1]["slug"], "zainab-forever")
        self.assertIn("status = 'active'", calls[1][0]); self.assertIn("jsonb_build_object", calls[1][0]); self.assertNotIn("ready", calls[1][0].lower().replace("readiness", ""))
    def test_already_fine_is_noop(self):
        rc, o, calls = go("x|active|true", True); self.assertEqual(rc, 0); self.assertIn("سليم", o); self.assertEqual(len(calls), 1)
    def test_active_but_feature_off_gets_enabled(self):
        rc, o, calls = go("x|active|false", True); self.assertEqual(len(calls), 2)
    def test_no_connection_fails(self):
        rc, o, calls = go(""); self.assertEqual(rc, 1); self.assertIn("ما فيه اتصال", o)
    def test_two_connections_refused(self):
        rc, o, calls = go("a|expired|false\nb|active|false", True); self.assertEqual(rc, 1); self.assertEqual(len(calls), 1)
    def test_bad_inputs(self):
        self.assertEqual(go("", slug="Bad Slug!")[0], 2); self.assertEqual(go("", plat="whatsapp")[0], 2)
    def test_unexpected_status(self):
        rc, o, calls = go("a|error|false", True); self.assertEqual(rc, 1); self.assertEqual(len(calls), 1)
    def test_never_touches_readiness_or_status(self):
        rc, o, calls = go("a|expired|null", True); sql = calls[1][0].lower(); self.assertNotIn("readiness", sql); self.assertNotIn("update core.tenants set status", sql)
if __name__ == "__main__": unittest.main()
