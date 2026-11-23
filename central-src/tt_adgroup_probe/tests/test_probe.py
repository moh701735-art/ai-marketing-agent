import importlib.util, json, os, unittest
P = os.path.join(os.path.dirname(__file__), "..", "..", "ops", "tt-adgroup-probe.py")
spec = importlib.util.spec_from_file_location("probe", P); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
A = {"adgroup_id": "1", "adgroup_name": "a", "campaign_id": "10", "budget_mode": "BUDGET_MODE_TOTAL", "budget": 30000.0, "pacing": "PACING_MODE_SMOOTH", "bid_type": "BID_TYPE_NO_BID",
     "safe_budget_increase": {"enabled": True, "extra": 5}, "interest_keyword_ids": [str(i) for i in range(300)], "create_time": "t1", "schedule_start_time": "s1"}
B = {**A, "adgroup_id": "2", "adgroup_name": "b", "campaign_id": "11", "create_time": "t2", "schedule_start_time": "s2"}; del B["safe_budget_increase"]; B["pacing"] = "PACING_MODE_FAST"


class T(unittest.TestCase):
    def test_01_find_list_nested(self): self.assertEqual(m.find_list({"data": {"list": [{"x": 1}], "page_info": {}}}), [{"x": 1}]); self.assertIsNone(m.find_list({"data": {}}))
    def test_02_render_puts_candidates_first_and_truncates_long_values(self):
        out = m.render(A); self.assertTrue(out[0].startswith("-- حقول مرشّحة للزر (")); self.assertTrue(any(l.startswith("  safe_budget_increase = ") for l in out))
        long_line = [l for l in out if l.startswith("  interest_keyword_ids")][0]; self.assertLess(len(long_line), 160); self.assertIn("…(", long_line)
    def test_03_diff_ignores_ids_names_times_and_reports_real_differences(self):
        vals, only_a, only_b = m.diff(A, B); self.assertEqual([v[0] for v in vals], ["pacing"]); self.assertEqual(only_a, ["safe_budget_increase"]); self.assertEqual(only_b, [])
    def test_04_report_single_and_pair(self):
        one = "\n".join(m.report(A)); self.assertIn("=== مجموعة A", one); self.assertNotIn("الفروقات", one)
        two = "\n".join(m.report(A, B)); self.assertIn("الفروقات (A = بالزر", two); self.assertIn("pacing: A=", two); self.assertIn("حقول عند A فقط: safe_budget_increase", two)
    def test_05_identical_groups_report_no_difference(self):
        self.assertIn("(لا فروقات بالقيم)", "\n".join(m.report(A, {**A, "adgroup_id": "9"})))
    def test_06_script_is_read_only(self):
        src = open(P, encoding="utf-8").read(); self.assertNotIn('"POST"', src.split("PY = r'''")[0]); self.assertIn("tiktok.read_adgroups", src); self.assertNotIn("tiktok.create", src)
    def test_08_pick_finds_the_owning_account_and_explains_misses(self):
        ok_empty = {"acct": "111", "ok": True, "data": {"list": []}}; ok_hit = {"acct": "222", "ok": True, "data": {"list": [{"adgroup_id": "5"}]}}; bad = {"acct": "333", "ok": False, "error": {"message": "no permission"}}
        self.assertEqual(m.pick([ok_empty, ok_hit, bad]), ("222", {"adgroup_id": "5"}))
        a, why = m.pick([ok_empty, bad]); self.assertIsNone(a); self.assertIn("333", why); self.assertIn("no permission", why)
        a, why = m.pick([ok_empty]); self.assertIsNone(a); self.assertIn("111", why); self.assertEqual(m.pick([])[0], None)
    def test_09_account_is_optional_but_validated(self):
        os.environ.update({"SA_SLUG": "mohm", "SA_CAMP": "1882666808770625", "SA_ACCT": "abc"})
        try:
            with self.assertRaises(SystemExit): m.main()
        finally:
            for k in ("SA_SLUG", "SA_CAMP", "SA_ACCT"): os.environ.pop(k, None)
    def test_10_spaced_names_defeat_translation_and_stay_readable(self):
        self.assertEqual(m.spaced("budget_mode"), "b u d g e t _ m o d e"); self.assertIn("  " + m.spaced("safe_budget_increase"), m.render(A))
    def test_11_first_picks_matching_op_only(self):
        res = [{"op": "a", "ok": True, "data": {"list": [{"x": 1}]}}, {"op": "b", "ok": False}, {"op": "b", "ok": True, "data": {"list": [{"y": 2}]}}]
        self.assertEqual(m.first(res, "a"), {"x": 1}); self.assertEqual(m.first(res, "b"), {"y": 2}); self.assertIsNone(m.first(res, "c"))
    def test_12_embedded_script_compiles_and_only_reads(self):
        compile(m.PY, "PY", "exec"); src = open(P, encoding="utf-8").read()
        for op in ("tiktok.read_adgroups", "tiktok.sp_read_campaigns", "tiktok.sp_read_adgroups"): self.assertIn(op, src)
        for bad in ("tiktok.create", "tiktok.set_", "tiktok.update", "tiktok.appeal"): self.assertNotIn(bad, src)
    def test_13_brief_hides_the_rest(self):
        out = "\n".join(m.render(A, brief=True)); self.assertIn("SA_BRIEF", out); self.assertNotIn("create_time", out); self.assertNotIn("interest_keyword_ids", out)
        self.assertIn("interest_keyword_ids", "\n".join(m.render(A))); self.assertNotIn("-- باقي الحقول (", "\n".join(m.report(A, B, brief=True)))
    def test_07_env_validation_exits(self):
        os.environ.pop("SA_SLUG", None)
        with self.assertRaises(SystemExit): m.main()


if __name__ == "__main__":
    unittest.main(verbosity=2)
