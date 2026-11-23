"""اختبار الهجرة 80 على Postgres حقيقي مؤقت (مجلد مؤقت، منفذ محلي) مع مخطط أساس بديل (core.tenants + private.enter_ctx/cur_tenant).
يتخطى نفسه إن ما توفّر initdb/runuser. لا يلمس أي قاعدة حقيقية."""
import json, os, shutil, subprocess, tempfile, unittest

PGBIN = next((p for p in ("/usr/lib/postgresql/16/bin", "/usr/lib/postgresql/15/bin", "/usr/lib/postgresql/14/bin") if os.path.exists(p + "/initdb")), None)
HERE = os.path.dirname(os.path.abspath(__file__)); DBDIR = os.path.join(HERE, "..", "db")
TA, TB = "a0000000-0000-0000-0000-000000000001", "b0000000-0000-0000-0000-000000000002"
CA, CB = "ctx:" + TA, "ctx:" + TB
STUB = """
CREATE ROLE app_owner NOLOGIN; CREATE ROLE app_runtime NOLOGIN; CREATE ROLE app_jobs NOLOGIN;
CREATE SCHEMA core; CREATE TABLE core.tenants (tenant_id uuid PRIMARY KEY, features jsonb NOT NULL DEFAULT '{}');
INSERT INTO core.tenants VALUES ('%s'), ('%s');
CREATE SCHEMA private;
CREATE FUNCTION private.enter_ctx(p text, r text) RETURNS void LANGUAGE plpgsql AS $f$ BEGIN
  IF p !~ '^ctx:[0-9a-f-]{36}$' THEN RAISE EXCEPTION 'invalid_ctx' USING ERRCODE = '28000'; END IF; PERFORM set_config('radar.tenant', substr(p, 5), true); END $f$;
CREATE FUNCTION private.cur_tenant() RETURNS uuid LANGUAGE sql AS $f$ SELECT current_setting('radar.tenant')::uuid $f$;
GRANT USAGE ON SCHEMA core, private TO app_owner; GRANT SELECT ON core.tenants TO app_owner; GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA private TO app_owner;
CREATE TABLE core.old_data (x int); INSERT INTO core.old_data VALUES (1);
""" % (TA, TB)
SNAP = """SELECT md5(coalesce(string_agg(n.nspname || '.' || c.relname || ':' || c.relkind::text, ',' ORDER BY n.nspname, c.relname), '')) || '/' ||
  (SELECT md5(coalesce(string_agg(n2.nspname || '.' || p.proname || '(' || pg_get_function_identity_arguments(p.oid) || ')' || md5(p.prosrc), ',' ORDER BY n2.nspname, p.proname), ''))
   FROM pg_proc p JOIN pg_namespace n2 ON n2.oid = p.pronamespace WHERE n2.nspname NOT IN ('pg_catalog','information_schema','competitor_radar'))
  || '/' || (SELECT md5(coalesce(string_agg(rolname, ',' ORDER BY rolname), '')) FROM pg_roles WHERE rolname NOT LIKE 'pg\\_%' AND rolname <> 'radar_rt')
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema','pg_toast','competitor_radar')"""
FUNCS = ("config(text)", "competitor_add(text,text,text,text)", "competitor_list(text)", "competitor_get(text,uuid)", "competitor_delete(text,uuid)", "samples_add(text,uuid,jsonb)", "samples_list(text,uuid)",
         "report_save(text,uuid,jsonb,text,text)", "report_get(text,uuid)", "plan_save(text,uuid,jsonb)", "plan_get(text,uuid)", "cache_get(text,text)", "cache_set(text,text,jsonb,int)")


@unittest.skipUnless(PGBIN and shutil.which("runuser"), "postgres + runuser required")
class RadarDB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(); os.chmod(cls.dir, 0o755); shutil.chown(cls.dir, "postgres"); cls.data = cls.dir + "/data"; cls.sock = cls.dir + "/sock"; os.makedirs(cls.sock); shutil.chown(cls.sock, "postgres")
        cls.run_pg([PGBIN + "/initdb", "-D", cls.data, "-A", "trust", "--no-sync", "-U", "postgres"])
        cls.run_pg([PGBIN + "/pg_ctl", "-D", cls.data, "-o", "-p 54329 -k %s -c listen_addresses=''" % cls.sock, "-w", "-l", cls.dir + "/log", "start"])
        cls.sql(STUB)

    @classmethod
    def tearDownClass(cls):
        cls.run_pg([PGBIN + "/pg_ctl", "-D", cls.data, "-m", "immediate", "stop"], check=False); shutil.rmtree(cls.dir, ignore_errors=True)

    @classmethod
    def run_pg(cls, cmd, check=True):
        r = subprocess.run(["runuser", "-u", "postgres", "--"] + cmd, capture_output=True, text=True)
        if check and r.returncode: raise RuntimeError(r.stderr)
        return r

    @classmethod
    def psql(cls, sql, role=None):
        s = ("SET ROLE %s;\n" % role if role else "") + sql
        return cls.run_pg([PGBIN + "/psql", "-h", cls.sock, "-p", "54329", "-U", "postgres", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-d", "postgres", "-c", s], check=False)

    @classmethod
    def sql(cls, sql, role=None):
        r = cls.psql(sql, role)
        if r.returncode: raise RuntimeError(r.stderr)
        return r.stdout.strip()

    @classmethod
    def file(cls, name):
        shutil.copy(os.path.join(DBDIR, name), cls.dir + "/" + name); os.chmod(cls.dir + "/" + name, 0o644)
        r = cls.run_pg([PGBIN + "/psql", "-h", cls.sock, "-p", "54329", "-U", "postgres", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", "postgres", "-f", cls.dir + "/" + name], check=False)
        if r.returncode: raise RuntimeError(r.stderr)

    def raises(self, sql, frag, role="radar_rt"):
        r = self.psql(sql, role); self.assertNotEqual(r.returncode, 0, sql); self.assertIn(frag, r.stderr, sql)

    def q(self, sql, role="radar_rt"): return self.sql(sql, role)

    def test_00_baseline_up_and_old_objects_untouched(self):
        base = self.sql(SNAP); self.file("80_competitor_radar.sql"); self.__class__.snap_before = base
        self.assertEqual(self.sql(SNAP), base)   # الهجرة ما غيّرت أي كائن خارج مخططها (جداول/دوال/أدوار؛ radar_rt مستثنى)
        self.assertEqual(self.sql("SELECT x FROM core.old_data"), "1")

    def test_01_default_off(self):
        self.assertEqual(self.q("SELECT competitor_radar.config('%s')->>'enabled'" % CA), "false")
        self.raises("SELECT competitor_radar.competitor_add('%s','tiktok','x',null)" % CA, "radar_disabled")
        self.raises("SELECT competitor_radar.competitor_list('%s')" % CA, "radar_disabled")

    def test_02_enable_flag_and_tenant_optout(self):
        self.sql("UPDATE competitor_radar.settings SET value='true'::jsonb WHERE key='enabled'")
        self.assertEqual(self.q("SELECT (competitor_radar.config('%s')->>'enabled')||(competitor_radar.config('%s')->>'enabled')" % (CA, CB)), "truetrue")
        self.sql("UPDATE core.tenants SET features = features || '{\"competitor_radar\": false}' WHERE tenant_id='%s'" % TB)
        self.assertEqual(self.q("SELECT (competitor_radar.config('%s')->>'enabled')||(competitor_radar.config('%s')->>'enabled')" % (CA, CB)), "truefalse")
        self.raises("SELECT competitor_radar.competitor_list('%s')" % CB, "radar_disabled")
        self.sql("UPDATE core.tenants SET features = features - 'competitor_radar' WHERE tenant_id='%s'" % TB)

    def test_03_isolation_and_flow(self):
        a = json.loads(self.q("SELECT competitor_radar.competitor_add('%s','instagram','منافس A','https://example.com/a')" % CA))["id"]
        b = json.loads(self.q("SELECT competitor_radar.competitor_add('%s','tiktok','منافس B',null)" % CB))["id"]
        self.assertEqual(self.q("SELECT jsonb_array_length(competitor_radar.competitor_list('%s'))" % CA), "1"); self.assertEqual(self.q("SELECT competitor_radar.competitor_list('%s')->0->>'id'" % CB), b)
        self.assertEqual(self.q("SELECT coalesce(competitor_radar.competitor_get('%s','%s')::text,'null')" % (CB, a)), "null")
        self.assertEqual(self.q("SELECT competitor_radar.competitor_delete('%s','%s')" % (CB, a)), "false")
        for fn in ("samples_add('%s','%s','[]'::jsonb)", "samples_list('%s','%s')", "report_get('%s','%s')", "plan_get('%s','%s')", "report_save('%s','%s','{}'::jsonb,'done','low')", "plan_save('%s','%s','{}'::jsonb)"):
            self.raises("SELECT competitor_radar." + fn % (CB, a), "radar_not_found")
        s = '[{"id":"aaaaaaaaaaaa","src":"pasted","text":"عينة للاختبار الأولى"},{"id":"bbbbbbbbbbbb","src":"html_meta","text":"عينة ثانية للاختبار"}]'
        self.assertEqual(self.q("SELECT competitor_radar.samples_add('%s','%s','%s'::jsonb)" % (CA, a, s)), "2"); self.assertEqual(self.q("SELECT competitor_radar.samples_add('%s','%s','%s'::jsonb)" % (CA, a, s)), "2")   # idempotent
        self.assertEqual(self.q("SELECT jsonb_array_length(competitor_radar.samples_list('%s','%s'))" % (CA, a)), "2")
        self.assertEqual(self.q("SELECT competitor_radar.report_save('%s','%s','{\"status\":\"ok\"}'::jsonb,'done','medium')" % (CA, a)), "true")
        self.assertEqual(self.q("SELECT competitor_radar.report_get('%s','%s')->>'confidence'" % (CA, a)), "medium"); self.assertEqual(self.q("SELECT competitor_radar.competitor_list('%s')->0->>'status'" % CA), "done")
        self.assertEqual(self.q("SELECT competitor_radar.plan_save('%s','%s','{\"p\":1}'::jsonb)" % (CA, a)), "true"); self.assertEqual(self.q("SELECT competitor_radar.plan_get('%s','%s')->'plan'->>'p'" % (CA, a)), "1")
        self.assertEqual(self.q("SELECT competitor_radar.cache_set('%s','mk:abc','{\"v\":1}'::jsonb,3600)" % CA), "true"); self.assertEqual(self.q("SELECT competitor_radar.cache_get('%s','mk:abc')->>'v'" % CA), "1")
        self.assertEqual(self.q("SELECT coalesce(competitor_radar.cache_get('%s','mk:abc')::text,'null')" % CB), "null")   # الكاش معزول
        self.assertEqual(self.q("SELECT competitor_radar.cache_set('%s','BAD KEY','{}'::jsonb,3600)" % CA), "false"); self.assertEqual(self.q("SELECT competitor_radar.cache_set('%s','ok','{}'::jsonb,5)" % CA), "false")
        self.assertEqual(self.q("SELECT competitor_radar.competitor_delete('%s','%s')" % (CA, a)), "true")   # حذف متسلسل
        self.assertEqual(self.sql("SELECT (SELECT count(*) FROM competitor_radar.samples)+(SELECT count(*) FROM competitor_radar.reports)+(SELECT count(*) FROM competitor_radar.plans)"), "0")
        self.q("SELECT competitor_radar.competitor_delete('%s','%s')" % (CB, b))

    def test_04_validation_and_limits(self):
        self.raises("SELECT competitor_radar.competitor_add('%s','myspace','x',null)" % CA, "radar_invalid")
        self.raises("SELECT competitor_radar.competitor_add('%s','tiktok','','')" % CA, "radar_invalid")
        self.raises("SELECT competitor_radar.competitor_add('%s','tiktok','%s',null)" % (CA, "x" * 81), "radar_invalid")
        c = json.loads(self.q("SELECT competitor_radar.competitor_add('%s','tiktok','v',null)" % CA))["id"]
        self.raises("SELECT competitor_radar.samples_add('%s','%s','[{\"id\":\"zz\",\"src\":\"pasted\",\"text\":\"نص طويل كفاية\"}]'::jsonb)" % (CA, c), "radar_invalid")
        self.raises("SELECT competitor_radar.samples_add('%s','%s','[{\"id\":\"aaaaaaaaaaaa\",\"src\":\"evil\",\"text\":\"نص طويل كفاية\"}]'::jsonb)" % (CA, c), "radar_invalid")
        self.raises("SELECT competitor_radar.report_save('%s','%s','{}'::jsonb,'weird','low')" % (CA, c), "radar_invalid")
        self.raises("SELECT competitor_radar.report_save('%s','%s',jsonb_build_object('x', repeat('a', 61000)),'done','low')" % (CA, c), "radar_too_large")
        for rep in range(3):
            b = ",".join('{"id":"%012x","src":"pasted","text":"عينة رقم %d-%d للاختبار"}' % (rep * 100 + i + 1, rep, i) for i in range(30)); n = self.q("SELECT competitor_radar.samples_add('%s','%s','[%s]'::jsonb)" % (CA, c, b))
        self.assertEqual(n, "60")   # أحدث 60 فقط
        self.q("SELECT competitor_radar.competitor_delete('%s','%s')" % (CA, c))
        ids = [json.loads(self.q("SELECT competitor_radar.competitor_add('%s','tiktok','m%d',null)" % (CA, i)))["id"] for i in range(20)]
        self.raises("SELECT competitor_radar.competitor_add('%s','tiktok','extra',null)" % CA, "radar_limit")
        self.assertEqual(self.q("SELECT jsonb_array_length(competitor_radar.competitor_list('%s'))" % CB), "0")   # حد A ما يأثر على B
        for i in ids: self.q("SELECT competitor_radar.competitor_delete('%s','%s')" % (CA, i))

    def test_05_invalid_ctx(self):
        for ctx in ("bad", "ctx:nothex", ""): self.raises("SELECT competitor_radar.config('%s')" % ctx, "invalid_ctx")

    def test_06_privileges(self):
        for f in FUNCS: self.assertEqual(self.sql("SELECT has_function_privilege('radar_rt','competitor_radar.%s','EXECUTE')" % f), "t", f)
        self.assertEqual(self.sql("SELECT has_function_privilege('app_runtime','competitor_radar.config(text)','EXECUTE')"), "t")
        self.assertEqual(self.sql("SELECT has_function_privilege('app_runtime','competitor_radar.service_key()','EXECUTE')"), "t")
        for f in ("radar_rt", "app_jobs"): self.assertEqual(self.sql("SELECT has_function_privilege('%s','competitor_radar.service_key()','EXECUTE')" % f), "f", f)
        self.assertEqual(self.sql("SELECT coalesce(competitor_radar.service_key(),'null')"), "null")   # بدون تهيئة = null (الواجهة تقول غير مهيأ)
        self.sql("UPDATE competitor_radar.settings SET value=to_jsonb('k'||repeat('x',63)) WHERE false; INSERT INTO competitor_radar.settings VALUES ('service_key', to_jsonb(repeat('a',64)), now()) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value")
        self.assertEqual(self.sql("SELECT length(competitor_radar.service_key())", role="app_runtime"), "64"); self.raises("SELECT 1 FROM competitor_radar.settings", "permission denied", role="app_runtime")
        self.sql("DELETE FROM competitor_radar.settings WHERE key='service_key'")
        for f in FUNCS[1:]: self.assertEqual(self.sql("SELECT has_function_privilege('app_runtime','competitor_radar.%s','EXECUTE')" % f), "f", f)
        for f in FUNCS: self.assertEqual(self.sql("SELECT has_function_privilege('app_jobs','competitor_radar.%s','EXECUTE')" % f), "f", f)
        self.assertEqual(self.sql("SELECT has_function_privilege('radar_rt','competitor_radar._enabled()','EXECUTE')"), "f")
        for r in ("radar_rt", "app_runtime", "app_jobs"):
            for t in ("settings", "competitors", "samples", "reports", "plans", "cache"):
                for pr in ("SELECT", "INSERT", "UPDATE", "DELETE"): self.assertEqual(self.sql("SELECT has_table_privilege('%s','competitor_radar.%s','%s')" % (r, t, pr)), "f", (r, t, pr))
        self.assertEqual(self.sql("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='competitor_radar' AND (NOT p.prosecdef OR NOT EXISTS (SELECT 1 FROM unnest(coalesce(p.proconfig,'{}')) c WHERE c LIKE 'search_path=%'))"), "0")
        self.assertEqual(self.sql("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='competitor_radar' AND EXISTS (SELECT 1 FROM aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a WHERE a.grantee=0 AND a.privilege_type='EXECUTE')"), "0")
        self.raises("SELECT competitor_radar.competitor_list('%s')" % CA, "permission denied", role="app_jobs")
        self.raises("SELECT * FROM competitor_radar.competitors", "permission denied", role="app_runtime")

    def test_07_reapply_idempotent_keeps_state_and_flag(self):
        self.q("SELECT competitor_radar.competitor_add('%s','tiktok','keep',null)" % CA); self.file("80_competitor_radar.sql")
        self.assertEqual(self.sql("SELECT value::text FROM competitor_radar.settings WHERE key='enabled'"), "true"); self.assertEqual(self.q("SELECT jsonb_array_length(competitor_radar.competitor_list('%s'))" % CA), "1")
        self.assertEqual(self.sql(SNAP), self.__class__.snap_before)

    def test_99_down_restores_everything(self):
        self.file("80_competitor_radar_down.sql")
        self.assertEqual(self.sql("SELECT count(*) FROM pg_namespace WHERE nspname='competitor_radar'"), "0"); self.assertEqual(self.sql("SELECT count(*) FROM pg_roles WHERE rolname='radar_rt'"), "0")
        self.assertEqual(self.sql(SNAP), self.__class__.snap_before); self.assertEqual(self.sql("SELECT x FROM core.old_data"), "1")
        self.file("80_competitor_radar_down.sql")   # idempotent
        self.file("80_competitor_radar.sql"); self.assertEqual(self.sql("SELECT value::text FROM competitor_radar.settings WHERE key='enabled'"), "false")   # إعادة التركيب نظيفة ومطفأة


if __name__ == "__main__":
    unittest.main(verbosity=1)
