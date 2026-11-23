import importlib.util, json, os, unittest
P = os.path.join(os.path.dirname(__file__), "..", "..", "ops", "tt-adgroup-probe.py")
spec = importlib.util.spec_from_file_location("probe", P); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
A = {"adgroup_id": "1", "adgroup_name": "a", "campaign_id": "10", "budget_mode": "BUDGET_MODE_TOTAL", "budget": 30000.0, "pacing": "PACING_MODE_SMOOTH", "bid_type": "BID_TYPE_NO_BID",
     "safe_budget_increase": {"enabled": True, "extra": 5}, "interest_keyword_ids": [str(i) for i in range(300)], "create_time": "t1", "schedule_start_time": "s1"}
B = {**A, "adgroup_id": "2", "adgroup_name": "b", "campaign_id": "11", "create_time": "t2", "schedule_start_time": "s2"}; del B["safe_budget_increase"]; B["pacing"] = "PACING_MODE_FAST"


class T(unittest.TestCase):
    def test_01_find_list_nested(self): self.assertEqual(m.find_list({"data": {"list": [{"x": 1}], "page_info": {}}}), [{"x": 1}]); self.assertIsNone(m.find_list({"data": {}}))
    def test_02_render_puts_candidates_first_and_truncates_long_values(self):
        out = m.render(A); self.assertEqual(out[0], "-- حقول مرشّحة للزر (%d) --" % 5); self.assertTrue(any(l.startswith("  safe_budget_increase = ") for l in out))
        long_line = [l for l in out if l.startswith("  interest_keyword_ids")][0]; self.assertLess(len(long_line), 160); self.assertIn("…(", long_line)
    def test_03_diff_ignores_ids_names_times_and_reports_real_differences(self):
        vals, only_a, only_b = m.diff(A, B); self.assertEqual([v[0] for v in vals], ["pacing"]); self.assertEqual(only_a, ["safe_budget_increase"]); self.assertEqual(only_b, [])
    def test_04_report_single_and_pair(self):
        one = "\n".join(m.report(A)); self.assertIn("=== مجموعة A", one); self.assertNotIn("الفروقات", one)
        two = "\n".join(m.report(A, B)); self.assertIn("الفروقات (A = بالزر", two); self.assertIn("pacing: A=", two); self.assertIn("حقول عند A فقط: safe_budget_increase", two)
    def test_05_identical_groups_report_no_difference(self):
        self.assertIn("(لا فروقات بالقيم)", "\n".join(m.report(A, {**A, "adgroup_id": "9"})))
    def test_06_script_is_read_only(self):
        src = open(P, encoding="utf-8").read(); self.assertNotIn('"POST"', src.split("PY = r'''")[0]); self.assertIn("tiktok.read_adgroups", src); self.assertNotIn("tiktok.create", src); self.assertNotIn("update", src.replace("# update", ""))
    def test_07_env_validation_exits(self):
        os.environ.pop("SA_SLUG", None)
        with self.assertRaises(SystemExit): m.main()


if __name__ == "__main__":
    unittest.main(verbosity=2)
