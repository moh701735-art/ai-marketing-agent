"""اختبار الهجرة 82 (زبائن الويب) على Postgres حقيقي مؤقت مع بدائل أمينة لحارس الجاهزية (نفس شروط guard_ready/sweep_readiness الحية) ولدالة api.readiness_local (نص R01/R15 الحي)."""
import json, os, shutil, subprocess, tempfile, unittest

PGBIN = next((p for p in ("/usr/lib/postgresql/16/bin", "/usr/lib/postgresql/15/bin", "/usr/lib/postgresql/14/bin") if os.path.exists(p + "/initdb")), None)
HERE = os.path.dirname(os.path.abspath(__file__)); DBDIR = os.path.join(HERE, "..", "db")
T = {k: "%s0000000-0000-0000-0000-00000000000%d" % (c, i) for i, (k, c) in enumerate((("tg_ready", "a"), ("tg_test", "b"), ("tg_old", "c"), ("web", "d"), ("web2", "e")), 1)}
DEFS = [("R01", "always"), ("R02", "always"), ("R03", "always"), ("R04", "always"), ("R05", "tiktok"), ("R06", "meta"), ("R07", "meta"), ("R08", "always"), ("R09", "meta"), ("R10", "always"),
        ("R11", "always"), ("R12", "always"), ("R13", "always"), ("R14", "always"), ("R15", "always")]
STUB = """
CREATE SCHEMA core; CREATE SCHEMA private; CREATE SCHEMA api;
CREATE TABLE core.tenants (tenant_id uuid PRIMARY KEY, slug text UNIQUE, display_name text, status text NOT NULL DEFAULT 'CONFIGURATION_REQUIRED', timezone text, currency text, features jsonb NOT NULL DEFAULT '{}', active_config_version int);
CREATE TABLE core.readiness_check_defs (check_code text PRIMARY KEY, title text, mandatory boolean NOT NULL DEFAULT true, applies_when text NOT NULL DEFAULT 'always', max_age interval);
CREATE TABLE core.readiness_checks (tenant_id uuid, check_code text, status text, evidence jsonb, expires_at timestamptz, PRIMARY KEY (tenant_id, check_code));
CREATE TABLE core.tenant_users (tenant_id uuid, telegram_user_id bigint, role text, active boolean);
CREATE TABLE core.bots (tenant_id uuid, status text);
CREATE TABLE core.config_versions (tenant_id uuid, version int);
INSERT INTO core.readiness_check_defs (check_code, applies_when) VALUES %(defs)s;
CREATE FUNCTION private.guard_ready() RETURNS trigger LANGUAGE plpgsql AS $f$ BEGIN
  IF NEW.status = 'READY' AND OLD.status IS DISTINCT FROM 'READY' THEN
    IF EXISTS (SELECT 1 FROM core.readiness_check_defs d LEFT JOIN core.readiness_checks c ON c.tenant_id = NEW.tenant_id AND c.check_code = d.check_code
               WHERE d.mandatory AND (d.applies_when = 'always' OR coalesce((NEW.features->>d.applies_when)::boolean, false)) AND (c.status IS DISTINCT FROM 'pass' OR c.expires_at <= now()))
    THEN RAISE EXCEPTION 'readiness_not_passed' USING ERRCODE = '42501'; END IF;
  END IF; RETURN NEW; END $f$;
CREATE TRIGGER tenants_guard_ready BEFORE UPDATE ON core.tenants FOR EACH ROW EXECUTE FUNCTION private.guard_ready();
CREATE FUNCTION api_sweep() RETURNS SETOF uuid LANGUAGE sql AS $f$
  SELECT t.tenant_id FROM core.tenants t WHERE t.status = 'READY' AND EXISTS (SELECT 1 FROM core.readiness_check_defs d LEFT JOIN core.readiness_checks c ON c.tenant_id = t.tenant_id AND c.check_code = d.check_code
    WHERE d.mandatory AND (d.applies_when = 'always' OR coalesce((t.features->>d.applies_when)::boolean, false)) AND (c.status IS DISTINCT FROM 'pass' OR c.expires_at <= now())) $f$;
CREATE OR REPLACE FUNCTION api.readiness_local(p_ctx text)
 RETURNS TABLE(check_code text, status text, evidence jsonb)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'core', 'private', 'ext'
AS $function$
DECLARE t core.tenants; v_owners int; v_bots int; v_cfg int;
BEGIN
  SELECT * INTO t FROM core.tenants WHERE tenant_id = current_setting('t.tenant')::uuid;
  SELECT count(*) INTO v_owners FROM core.tenant_users u WHERE u.tenant_id = t.tenant_id AND u.role = 'owner' AND u.active;
  SELECT count(*) INTO v_bots FROM core.bots b WHERE b.tenant_id = t.tenant_id AND b.status = 'active';
  -- R01
  check_code := 'R01'; status := CASE WHEN t.features <> '{}'::jsonb AND t.timezone IS NOT NULL AND v_owners >= 1 AND v_bots >= 1 THEN 'pass' ELSE 'fail' END;
  evidence := jsonb_build_object('owners', v_owners, 'active_bots', v_bots, 'features', t.features, 'timezone', t.timezone); RETURN NEXT;
  -- R15
  SELECT count(*) INTO v_cfg FROM core.config_versions c WHERE c.tenant_id = t.tenant_id;
  check_code := 'R15'; status := CASE WHEN t.active_config_version IS NOT NULL THEN 'pass' ELSE 'fail' END;
  evidence := jsonb_build_object('active_version', t.active_config_version, 'versions', v_cfg, 'rollback_possible', v_cfg >= 2); RETURN NEXT;
END $function$;
INSERT INTO core.tenants (tenant_id, slug, display_name, status, timezone, currency, features, active_config_version) VALUES
 ('%(tg_ready)s','tg-ready','R','TESTING','Asia/Baghdad','USD','{"tiktok": true, "schedule": true}',1),
 ('%(tg_test)s','tg-test','T','TESTING','Asia/Baghdad','IQD','{"meta": true, "tiktok": true}',1),
 ('%(tg_old)s','tg-old','O','TESTING','Asia/Baghdad','USD','{"tiktok": true}',1);
INSERT INTO core.tenant_users VALUES ('%(tg_ready)s', 1, 'owner', true); INSERT INTO core.bots VALUES ('%(tg_ready)s', 'active');
""" % {"defs": ", ".join("('%s','%s')" % d for d in DEFS), **T}
APPLICABLE = """SELECT t.slug || ':' || coalesce((SELECT string_agg(d.check_code, ',' ORDER BY d.check_code) FROM core.readiness_check_defs d WHERE d.mandatory AND (d.applies_when = 'always' OR coalesce((t.features->>d.applies_when)::boolean, false))), '')
  FROM core.tenants t WHERE t.slug IN ('tg-ready','tg-test','tg-old') ORDER BY t.slug"""


@unittest.skipUnless(PGBIN and shutil.which("runuser"), "postgres + runuser required")
class DB82(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(); os.chmod(cls.dir, 0o755); shutil.chown(cls.dir, "postgres"); cls.data = cls.dir + "/data"; cls.sock = cls.dir + "/sock"; os.makedirs(cls.sock); shutil.chown(cls.sock, "postgres")
        cls.run_pg([PGBIN + "/initdb", "-D", cls.data, "-A", "trust", "--no-sync", "-U", "postgres"])
        cls.run_pg([PGBIN + "/pg_ctl", "-D", cls.data, "-o", "-p 54332 -k %s -c listen_addresses=''" % cls.sock, "-w", "-l", cls.dir + "/log", "start"])
        cls.sql(STUB); cls.before = cls.sql(APPLICABLE); cls.rl_before = cls.sql("SELECT pg_get_functiondef('api.readiness_local(text)'::regprocedure)")

    @classmethod
    def tearDownClass(cls):
        cls.run_pg([PGBIN + "/pg_ctl", "-D", cls.data, "-m", "immediate", "stop"], check=False); shutil.rmtree(cls.dir, ignore_errors=True)

    @classmethod
    def run_pg(cls, cmd, check=True):
        r = subprocess.run(["runuser", "-u", "postgres", "--"] + cmd, capture_output=True, text=True)
        if check and r.returncode: raise RuntimeError(r.stderr)
        return r

    @classmethod
    def psql(cls, sql):
        return cls.run_pg([PGBIN + "/psql", "-h", cls.sock, "-p", "54332", "-U", "postgres", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-d", "postgres", "-c", sql], check=False)

    @classmethod
    def sql(cls, sql):
        r = cls.psql(sql)
        if r.returncode: raise RuntimeError(r.stderr)
        return r.stdout.strip()

    @classmethod
    def file(cls, name, check=True):
        shutil.copy(os.path.join(DBDIR, name), cls.dir + "/" + name); os.chmod(cls.dir + "/" + name, 0o644)
        r = cls.run_pg([PGBIN + "/psql", "-h", cls.sock, "-p", "54332", "-U", "postgres", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", "postgres", "-f", cls.dir + "/" + name], check=False)
        if check and r.returncode: raise RuntimeError(r.stderr)
        return r

    def rl(self, tid): return {r.split("|")[0]: r.split("|")[1] for r in self.sql("SELECT set_config('t.tenant','%s',false); SELECT check_code || '|' || status FROM api.readiness_local('x')" % tid).split("\n")[1:]}

    def test_01_existing_tenants_unchanged_by_migration(self):
        self.file("81_dummy_skip.sql") if False else None
        self.file("82_web_only_tenants.sql")
        self.assertEqual(self.sql(APPLICABLE), self.before)                                    # نفس الفحوصات الإلزامية لكل زبون حالي بالضبط
        self.assertEqual(self.sql("SELECT count(*) FROM core.tenants WHERE slug LIKE 'tg-%' AND (features->>'telegram')::boolean"), "3")
        self.assertEqual(self.sql("SELECT string_agg(check_code || '=' || applies_when, ',' ORDER BY check_code) FROM core.readiness_check_defs WHERE check_code IN ('R02','R03','R04')"), "R02=telegram,R03=telegram,R04=telegram")
        self.assertEqual(self.rl(T["tg_ready"])["R01"], "pass"); self.assertEqual(self.rl(T["tg_old"])["R01"], "fail")   # بدون مالك/بوت يفشل كما كان

    def test_02_idempotent(self):
        self.file("82_web_only_tenants.sql"); self.assertEqual(self.sql(APPLICABLE), self.before); self.assertEqual(self.sql("SELECT count(*) FROM pg_trigger WHERE tgname = 'tenants_default_telegram'"), "1")

    def test_03_default_trigger_fail_safe(self):
        self.sql("INSERT INTO core.tenants (tenant_id, slug, features) VALUES ('f0000000-0000-0000-0000-000000000001','new-default','{\"tiktok\": true}'), ('f0000000-0000-0000-0000-000000000002','new-null','{}')")
        self.assertEqual(self.sql("SELECT (features->>'telegram') FROM core.tenants WHERE slug = 'new-default'"), "true"); self.assertEqual(self.sql("SELECT (features->>'telegram') FROM core.tenants WHERE slug = 'new-null'"), "true")
        self.sql("INSERT INTO core.tenants (tenant_id, slug, features) VALUES ('f0000000-0000-0000-0000-000000000003','new-web','{\"web_only\": true, \"telegram\": false}')"); self.assertEqual(self.sql("SELECT (features->>'telegram') FROM core.tenants WHERE slug = 'new-web'"), "false")
        self.sql("INSERT INTO core.tenants (tenant_id, slug, features) VALUES ('f0000000-0000-0000-0000-000000000004','new-explicit-true','{\"telegram\": true}')")

    def test_04_web_tenant_ready_only_with_non_telegram_checks(self):
        w = T["web"]; self.sql("INSERT INTO core.tenants (tenant_id, slug, display_name, status, timezone, currency, features, active_config_version) VALUES ('%s','web-a','W','TESTING','Asia/Baghdad','IQD','{\"web_only\": true, \"telegram\": false, \"tiktok\": true}',1)" % w)
        self.assertEqual(self.rl(w), {"R01": "pass", "R15": "pass"})
        self.assertTrue("readiness_not_passed" in self.psql("UPDATE core.tenants SET status='READY' WHERE tenant_id='%s'" % w).stderr)          # بدون فحوصات: يُرفض
        for code in [c for c, a in DEFS if a == "always" and c not in ("R02", "R03", "R04")] + ["R05"]:
            self.sql("INSERT INTO core.readiness_checks VALUES ('%s','%s','pass','{}', now() + interval '1 day')" % (w, code))
        self.sql("UPDATE core.tenants SET status='READY' WHERE tenant_id='%s'" % w)                                                              # بدون R02/R03/R04 ينجح
        self.assertEqual(self.sql("SELECT status FROM core.tenants WHERE tenant_id='%s'" % w), "READY"); self.assertNotIn(w, self.sql("SELECT api_sweep()"))
        self.sql("UPDATE core.readiness_checks SET status='fail' WHERE tenant_id='%s' AND check_code='R08'" % w); self.assertIn(w, self.sql("SELECT api_sweep()"))   # وغيرها يبقى إلزامياً

    def test_05_telegram_tenant_still_needs_telegram_checks(self):
        t = T["tg_test"]
        for code in [c for c, a in DEFS if a in ("always", "tiktok", "meta")]:
            if code not in ("R02", "R03", "R04"): self.sql("INSERT INTO core.readiness_checks VALUES ('%s','%s','pass','{}', now() + interval '1 day') ON CONFLICT DO NOTHING" % (t, code))
        self.assertIn("readiness_not_passed", self.psql("UPDATE core.tenants SET status='READY' WHERE tenant_id='%s'" % t).stderr)
        for code in ("R02", "R03", "R04"): self.sql("INSERT INTO core.readiness_checks VALUES ('%s','%s','pass','{}', now() + interval '1 day')" % (t, code))
        self.sql("UPDATE core.tenants SET status='READY' WHERE tenant_id='%s'" % t)

    def test_06_r01_only_relaxed_for_web_only(self):
        self.sql("INSERT INTO core.tenants (tenant_id, slug, status, timezone, features, active_config_version) VALUES ('%s','web-b','TESTING','Asia/Baghdad','{\"web_only\": false, \"telegram\": true}',1)" % T["web2"])
        self.assertEqual(self.rl(T["web2"])["R01"], "fail"); self.sql("UPDATE core.tenants SET features = '{\"web_only\": true, \"telegram\": false}' WHERE tenant_id='%s'" % T["web2"]); self.assertEqual(self.rl(T["web2"])["R01"], "pass")
        self.sql("UPDATE core.tenants SET features = '{}' WHERE tenant_id='%s'" % T["web2"]); self.assertEqual(self.rl(T["web2"])["R01"], "fail")      # features فاضية تبقى فشل

    def test_90_fail_closed_when_r01_text_differs(self):
        r0 = self.file("82_web_only_tenants_down.sql", check=False)   # يرفض لو فيه web_only؛ نحذفهم أولاً
        self.assertNotEqual(r0.returncode, 0); self.assertIn("web_only tenants exist", r0.stderr)
        self.sql("DELETE FROM core.tenants WHERE (features->>'web_only')::boolean OR slug LIKE 'new-%'"); self.file("82_web_only_tenants_down.sql")
        self.assertEqual(self.sql("SELECT string_agg(check_code || '=' || applies_when, ',' ORDER BY check_code) FROM core.readiness_check_defs WHERE check_code IN ('R02','R03','R04')"), "R02=always,R03=always,R04=always")
        self.assertEqual(self.sql("SELECT pg_get_functiondef('api.readiness_local(text)'::regprocedure)"), self.rl_before)                                 # النص رجع حرفياً
        self.sql("UPDATE core.tenants SET features = features - 'telegram'")
        d = self.sql("SELECT pg_get_functiondef('api.readiness_local(text)'::regprocedure)").replace("v_owners >= 1 AND v_bots >= 1", "v_owners >= 2 AND v_bots >= 1")
        self.sql("DO $z$ BEGIN EXECUTE $q$" + d + "$q$; END $z$")
        r = self.file("82_web_only_tenants.sql", check=False); self.assertNotEqual(r.returncode, 0); self.assertIn("found 0 times", r.stderr)
        self.assertEqual(self.sql("SELECT string_agg(check_code || '=' || applies_when, ',' ORDER BY check_code) FROM core.readiness_check_defs WHERE check_code IN ('R02','R03','R04')"), "R02=always,R03=always,R04=always")   # لا شي تغيّر
        self.assertEqual(self.sql("SELECT count(*) FROM core.tenants WHERE features ? 'telegram'"), "0"); self.assertEqual(self.sql("SELECT count(*) FROM pg_trigger WHERE tgname = 'tenants_default_telegram'"), "0")


if __name__ == "__main__":
    unittest.main(verbosity=1)
