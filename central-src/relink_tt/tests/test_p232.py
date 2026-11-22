import importlib.util, os, sys, unittest
H = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("trl", os.path.join(H, "test_relink.py")); trl = importlib.util.module_from_spec(spec); spec.loader.exec_module(trl)
EXP = ["c-9|tt_agency_c902141e|ref-hussain-tt-aa11|expired"]; ACT = ["c-9|tt_agency_c902141e|ref-hussain-tt-aa11|active"]


class T(unittest.TestCase):
    def test_01_expired_apply_reactivates_after_vault_write(self):
        at, call, r, err, out = trl.run(at=trl.FakeAt(conns=EXP), apply=True, slug="hussain-alaa")
        self.assertIsNone(err); self.assertTrue(r["written"] and r["reactivated"]); self.assertEqual(len(at.vaults), 1)
        self.assertEqual(at.vaults[0][0]["secret_ref"], "ref-hussain-tt-aa11")
        self.assertEqual(len(at.writes), 1); sql, v = at.writes[0]
        self.assertIn("status = 'active'", sql); self.assertIn("alerted_at = NULL", sql); self.assertIn("status = 'expired'", sql); self.assertEqual(v, {"cid": "c-9", "tid": "t-1"})
        self.assertIn("رجعت «active»", out); self.assertIn("حالته: expired", out)
    def test_02_expired_dry_run_writes_nothing(self):
        at, call, r, err, out = trl.run(at=trl.FakeAt(conns=EXP), apply=False)
        self.assertIsNone(err); self.assertFalse(r["written"]); self.assertEqual((at.vaults, at.writes), ([], []))
    def test_03_expired_with_missing_coverage_changes_nothing(self):
        at, call, r, err, out = trl.run(at=trl.FakeAt(conns=EXP), call=trl.mkcall(adv_ids=trl.ACC[:2], readable=trl.ACC[:2]), apply=True)
        self.assertIn("ما يغطي", err); self.assertEqual((at.vaults, at.writes), ([], []))
    def test_04_active_connection_never_updated(self):
        at, call, r, err, out = trl.run(at=trl.FakeAt(conns=ACT), apply=True)
        self.assertTrue(r["written"]); self.assertFalse(r["reactivated"]); self.assertEqual(at.writes, [])
    def test_05_expired_new_ref_updates_ref_then_status(self):
        at, call, r, err, out = trl.run(at=trl.FakeAt(conns=EXP), apply=True, new_ref=True)
        self.assertTrue(r["reactivated"]); self.assertEqual(len(at.vaults), 1); self.assertNotEqual(at.vaults[0][0]["secret_ref"], "ref-hussain-tt-aa11")
        self.assertEqual(len(at.writes), 2); self.assertIn("secret_ref", at.writes[0][0]); self.assertIn("status = 'active'", at.writes[1][0])
    def test_06_query_only_active_or_expired(self):
        at, *_ = trl.run(at=trl.FakeAt(conns=EXP)); q = [s for s in at.sqls if "FROM core.platform_connections" in s][0]
        self.assertIn("status IN ('active', 'expired')", q); self.assertNotIn("revoked", q)
    def test_07_two_connections_refused_without_tiktok_call(self):
        at, call, r, err, out = trl.run(at=trl.FakeAt(conns=EXP + ["c-8|tt_other|ref-x|active"]), apply=True)
        self.assertIn("**واحد**", err); self.assertEqual((at.vaults, at.writes, call.calls), ([], [], []))
    def test_08_old_three_column_rows_still_work(self):
        at, call, r, err, out = trl.run(at=trl.FakeAt(conns=["c-1|tt_x|ref-1"]), apply=True)
        self.assertTrue(r["written"]); self.assertFalse(r["reactivated"]); self.assertEqual(at.writes, [])
    def test_09_secrets_not_printed_in_reactivation_path(self):
        at, call, r, err, out = trl.run(at=trl.FakeAt(conns=EXP), apply=True)
        for secret in (trl.TOKEN, trl.SECRET, trl.CODE): self.assertNotIn(secret, out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
