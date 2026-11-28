import importlib.util, os, shutil, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..")
spec = importlib.util.spec_from_file_location("ctl2", os.path.join(ROOT, "deploy", "web_portal_ctl.py")); ctl = importlib.util.module_from_spec(spec); spec.loader.exec_module(ctl)


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); ctl.ROOT = self.d; os.makedirs(self.d + "/db")
        for f in ("82_web_only_tenants.sql", "82_web_only_tenants_down.sql"): open(self.d + "/db/" + f, "w").write("-- " + f)
        self.log = []; self.map_calls = 0; self.maps = ["a:R01,R02\nb:R01"] * 2; self.defs = "telegram,telegram,telegram"; self.count = "0"; self.fail = None; self.out = []
        def psql(sql, v=None, check=True):
            self.log.append((sql, dict(v or {})))
            if "string_agg(d.check_code" in sql and "web_only" in sql: self.map_calls += 1; return 0, self.maps[min(self.map_calls - 1, len(self.maps) - 1)] + "\n", ""
            if "string_agg(applies_when" in sql: return 0, self.defs + "\n", ""
            if "count(*) FROM core.tenants WHERE slug" in sql: return 0, self.count + "\n", ""
            if self.fail and self.fail in sql: return 1, "", "ERROR: boom\nCONTEXT: x"
            return 0, "", ""
        ctl.psql = psql; self.p = lambda *a: self.out.append(" ".join(map(str, a)))
    def tearDown(self): shutil.rmtree(self.d, ignore_errors=True)
    A = type("A", (), {})

    def args(self, **k):
        a = self.A(); a.slug, a.name, a.currency, a.days, a.tz, a.plan = "web-acme", "شركة أكمي", "IQD", 30, "Asia/Baghdad", "standard"
        for kk, vv in k.items(): setattr(a, kk, vv)
        return a

    def test_01_enable_requires_yes(self):
        a = self.A(); a.yes = False
        with self.assertRaises(SystemExit): ctl.cmd_enable(a, self.p)
        self.assertFalse(any("82_web_only_tenants.sql" in s and s.startswith("--") for s, _ in self.log))

    def test_02_enable_success_compares_before_after(self):
        a = self.A(); a.yes = True; ctl.cmd_enable(a, self.p); self.assertTrue(any(s == "-- 82_web_only_tenants.sql" for s, _ in self.log)); self.assertTrue(any("مطابقة تماماً" in o for o in self.out)); self.assertEqual(self.map_calls, 2)

    def test_03_enable_mismatch_rolls_back_with_down(self):
        self.maps = ["a:R01,R02", "a:R01"]; a = self.A(); a.yes = True
        with self.assertRaises(SystemExit): ctl.cmd_enable(a, self.p)
        sqls = [s for s, _ in self.log]; self.assertIn("-- 82_web_only_tenants.sql", sqls); self.assertIn("-- 82_web_only_tenants_down.sql", sqls); self.assertLess(sqls.index("-- 82_web_only_tenants.sql"), sqls.index("-- 82_web_only_tenants_down.sql"))

    def test_04_enable_migration_failure_stops(self):
        self.fail = "-- 82_web_only_tenants.sql"; a = self.A(); a.yes = True
        with self.assertRaises(SystemExit): ctl.cmd_enable(a, self.p)
        self.assertEqual(self.map_calls, 1); self.assertFalse(any(s == "-- 82_web_only_tenants_down.sql" for s, _ in self.log))

    def test_05_create_tenant_sql_and_vars(self):
        ctl.cmd_create_tenant(self.args(), self.p); sql, v = [x for x in self.log if "INSERT INTO core.tenants" in x[0]][0]
        self.assertIn('"web_only": true', sql); self.assertIn('"telegram": false', sql); self.assertIn("'TESTING'", sql); self.assertIn("api_admin.set_subscription", sql); self.assertIn("core.config_versions", sql); self.assertNotIn("core.bots", sql); self.assertNotIn("tenant_users", sql)
        self.assertEqual(v, {"slug": "web-acme", "name": "شركة أكمي", "tz": "Asia/Baghdad", "cur": "IQD", "plan": "standard", "days": "30"}); self.assertTrue(sql.index("BEGIN;") < sql.index("COMMIT;")); self.assertTrue(any("invite --slug web-acme" in o for o in self.out))

    def test_06_create_tenant_guards(self):
        for bad in ({"slug": "Bad Slug"}, {"name": "x"}, {"name": "a" * 70}, {"currency": "EUR"}, {"days": 0}, {"days": 999}, {"tz": "x; drop"}, {"plan": "Std Plan"}):
            with self.assertRaises(SystemExit, msg=str(bad)): ctl.cmd_create_tenant(self.args(**bad), self.p)
        self.defs = "always,always,always"
        with self.assertRaises(SystemExit): ctl.cmd_create_tenant(self.args(), self.p)
        self.defs = "telegram,telegram,telegram"; self.count = "1"
        with self.assertRaises(SystemExit): ctl.cmd_create_tenant(self.args(), self.p)
        self.assertFalse(any("INSERT INTO core.tenants" in s for s, _ in self.log))

    def test_07_create_tenant_db_failure_reports(self):
        self.fail = "INSERT INTO core.tenants"
        with self.assertRaises(SystemExit) as c: ctl.cmd_create_tenant(self.args(), self.p)
        self.assertIn("ما انكتب شي", str(c.exception))

    def test_08_parser_has_new_commands(self):
        ctl.cmd_enable = lambda a, out=print: self.out.append("E%s" % a.yes); ctl.cmd_create_tenant = lambda a, out=print: self.out.append("C%s%s" % (a.slug, a.currency))
        ctl.main(["enable-web-tenants", "--yes"]); ctl.main(["create-tenant", "--slug", "x-y", "--name", "اسم"]); self.assertEqual(self.out, ["ETrue", "Cx-yIQD"])
if __name__ == "__main__": unittest.main()
