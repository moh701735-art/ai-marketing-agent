"""اختبار الهجرة 77 (p293) على Postgres حقيقي مؤقت مع مخطط بديل مطابق لنص الدالة الحية. لا يلمس أي قاعدة حقيقية. يتخطى نفسه إن ما توفّر initdb/runuser."""
import os, shutil, subprocess, tempfile, unittest
PGBIN = next((p for p in ("/usr/lib/postgresql/16/bin", "/usr/lib/postgresql/15/bin", "/usr/lib/postgresql/14/bin") if os.path.exists(p + "/initdb")), None)
HERE = os.path.dirname(os.path.abspath(__file__)); MIG = os.path.join(HERE, "..", "..", "db", "77_degrade_platform.sql")
T1, T2 = "a0000000-0000-0000-0000-000000000001", "b0000000-0000-0000-0000-000000000002"
FUNC = """CREATE OR REPLACE FUNCTION api.broker_report_connection(p_ctx text, p_platform text, p_secret_ref text, p_status text) RETURNS integer
 LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core AS $function$
DECLARE %(v)s int;
BEGIN
  IF p_status NOT IN ('expired','revoked','error') THEN RAISE EXCEPTION 'bad_status' USING ERRCODE = '22023'; END IF;
  PERFORM private.enter_ctx(p_ctx, 'broker');
  UPDATE core.platform_connections SET status = p_status WHERE platform = p_platform::core.platform AND secret_ref = p_secret_ref AND status = 'active';
  %(gd)s
  RETURN %(v)s;
END $function$;"""
STUB = """
DO $r$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_owner') THEN CREATE ROLE app_owner NOLOGIN SUPERUSER; END IF; IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_runtime') THEN CREATE ROLE app_runtime NOLOGIN; END IF; END $r$;
CREATE SCHEMA core; CREATE SCHEMA private; CREATE SCHEMA api;
CREATE TYPE core.platform AS ENUM ('telegram','tiktok','meta','snapchat');
CREATE TABLE core.tenants (tenant_id uuid PRIMARY KEY, status text NOT NULL DEFAULT 'ready', features jsonb NOT NULL DEFAULT '{}');
CREATE TABLE core.platform_connections (connection_id serial PRIMARY KEY, tenant_id uuid NOT NULL, platform core.platform NOT NULL, secret_ref text NOT NULL, status text NOT NULL DEFAULT 'active');
CREATE FUNCTION private.enter_ctx(p text, r text) RETURNS void LANGUAGE plpgsql AS $f$ BEGIN PERFORM set_config('app.tenant_id', substr(p, 5), true); END $f$;
INSERT INTO core.tenants VALUES ('%s','ready','{"meta": true, "tiktok": true}'), ('%s','ready','{"meta": true}');
""" % (T1, T2)


@unittest.skipUnless(PGBIN and shutil.which("runuser"), "postgres + runuser required")
class DB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(); os.chmod(cls.dir, 0o755); shutil.chown(cls.dir, "postgres"); cls.data = cls.dir + "/data"; cls.sock = cls.dir + "/sock"; os.makedirs(cls.sock); shutil.chown(cls.sock, "postgres")
        cls.run_pg([PGBIN + "/initdb", "-D", cls.data, "-A", "trust", "--no-sync", "-U", "postgres"])
        cls.run_pg([PGBIN + "/pg_ctl", "-D", cls.data, "-o", "-p 54331 -k %s -c listen_addresses=''" % cls.sock, "-w", "-l", cls.dir + "/log", "start"])
    @classmethod
    def tearDownClass(cls):
        cls.run_pg([PGBIN + "/pg_ctl", "-D", cls.data, "-m", "immediate", "stop"], check=False); shutil.rmtree(cls.dir, ignore_errors=True)
    @classmethod
    def run_pg(cls, cmd, check=True):
        r = subprocess.run(["runuser", "-u", "postgres", "--"] + cmd, capture_output=True, text=True)
        if check and r.returncode: raise RuntimeError(r.stderr)
        return r
    @classmethod
    def psql(cls, args, db="postgres"): return cls.run_pg([PGBIN + "/psql", "-h", cls.sock, "-p", "54331", "-U", "postgres", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-d", db] + args, check=False)
    def fresh(self, v="n", gd=None, extra=""):
        name = "t%d" % (id(self) % 10**8) + v
        self.run_pg([PGBIN + "/createdb", "-h", self.sock, "-p", "54331", "-U", "postgres", name], check=False)
        gd = gd if gd is not None else "GET DIAGNOSTICS %s = ROW_COUNT;" % v
        sql = STUB + (FUNC % {"v": v, "gd": gd}) + "\nGRANT EXECUTE ON FUNCTION api.broker_report_connection(text,text,text,text) TO app_runtime;\nALTER FUNCTION api.broker_report_connection(text,text,text,text) OWNER TO app_owner;\n" + extra
        r = self.psql(["-c", sql], db=name); assert r.returncode == 0, r.stderr
        return name
    def q(self, db, sql):
        r = self.psql(["-c", sql], db=db)
        if r.returncode: raise RuntimeError(r.stderr)
        return r.stdout.strip()
    def apply(self, db): return self.psql(["-f", MIG], db=db)
    def feats(self, db, t): return self.q(db, "SELECT features::text FROM core.tenants WHERE tenant_id='%s'" % t)
    def conn(self, db, t, plat, ref, st="active"): self.q(db, "INSERT INTO core.platform_connections (tenant_id, platform, secret_ref, status) VALUES ('%s','%s','%s','%s')" % (t, plat, ref, st))
    def report(self, db, t, plat, ref, st): return self.q(db, "SELECT api.broker_report_connection('ctx:%s','%s','%s','%s')" % (t, plat, ref, st))

    def test_expired_disables_platform_only(self):
        db = self.fresh(); r = self.apply(db); self.assertEqual(r.returncode, 0, r.stderr)
        self.conn(db, T1, "meta", "m1"); self.conn(db, T1, "tiktok", "t1"); self.conn(db, T2, "meta", "m2")
        self.assertEqual(self.report(db, T1, "meta", "m1", "expired"), "1")
        self.assertIn('"meta": false', self.feats(db, T1)); self.assertIn('"tiktok": true', self.feats(db, T1))
        self.assertIn('"meta": true', self.feats(db, T2))
        self.assertEqual(self.q(db, "SELECT status FROM core.tenants WHERE tenant_id='%s'" % T1), "ready")   # ما لمس status
        self.assertEqual(self.q(db, "SELECT status FROM core.platform_connections WHERE secret_ref='m1'"), "expired")
    def test_tiktok_expired(self):
        db = self.fresh(); self.apply(db); self.conn(db, T1, "tiktok", "t1"); self.conn(db, T1, "meta", "m1")
        self.report(db, T1, "tiktok", "t1", "expired"); f = self.feats(db, T1); self.assertIn('"tiktok": false', f); self.assertIn('"meta": true', f)
    def test_second_active_connection_keeps_platform(self):
        db = self.fresh(); self.apply(db); self.conn(db, T1, "meta", "m1"); self.conn(db, T1, "meta", "m1b")
        self.report(db, T1, "meta", "m1", "expired"); self.assertIn('"meta": true', self.feats(db, T1))
        self.report(db, T1, "meta", "m1b", "expired"); self.assertIn('"meta": false', self.feats(db, T1))
    def test_revoked_error_and_noop_do_not_disable(self):
        db = self.fresh(); self.apply(db); self.conn(db, T1, "meta", "m1"); self.conn(db, T1, "meta", "m3", "expired")
        self.assertEqual(self.report(db, T1, "meta", "m1", "revoked"), "1"); self.assertIn('"meta": true', self.feats(db, T1))
        self.assertEqual(self.report(db, T1, "meta", "m3", "expired"), "0"); self.assertIn('"meta": true', self.feats(db, T1))   # لا تغيير: الاتصال أصلاً غير نشط
        self.conn(db, T1, "meta", "m4"); self.report(db, T1, "meta", "m4", "error"); self.assertIn('"meta": true', self.feats(db, T1))
    def test_bad_status_still_rejected(self):
        db = self.fresh(); self.apply(db); self.conn(db, T1, "meta", "m1")
        with self.assertRaises(RuntimeError): self.report(db, T1, "meta", "m1", "active")
    def test_idempotent_owner_and_grants_preserved(self):
        db = self.fresh(); self.apply(db); f1 = self.q(db, "SELECT md5(prosrc) FROM pg_proc WHERE proname='broker_report_connection'")
        r = self.apply(db); self.assertEqual(r.returncode, 0, r.stderr); self.assertIn("already applied", r.stderr)
        self.assertEqual(self.q(db, "SELECT md5(prosrc) FROM pg_proc WHERE proname='broker_report_connection'"), f1)
        self.assertEqual(self.q(db, "SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE proname='broker_report_connection'"), "app_owner")
        self.assertEqual(self.q(db, "SELECT has_function_privilege('app_runtime','api.broker_report_connection(text,text,text,text)','execute')"), "t")
        self.assertEqual(self.q(db, "SELECT count(*) FROM pg_proc WHERE proname='broker_report_connection'"), "1")
        self.assertIn("SECURITY DEFINER", self.q(db, "SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname='broker_report_connection'"))
    def test_other_variable_name(self):
        db = self.fresh(v="v_rows"); r = self.apply(db); self.assertEqual(r.returncode, 0, r.stderr)
        self.conn(db, T1, "meta", "m1"); self.report(db, T1, "meta", "m1", "expired"); self.assertIn('"meta": false', self.feats(db, T1))
    def test_missing_anchor_fails_closed(self):
        db = self.fresh(gd="NULL;"); before = self.q(db, "SELECT md5(prosrc) FROM pg_proc WHERE proname='broker_report_connection'")
        r = self.apply(db); self.assertNotEqual(r.returncode, 0); self.assertIn("anchor", r.stderr)
        self.assertEqual(self.q(db, "SELECT md5(prosrc) FROM pg_proc WHERE proname='broker_report_connection'"), before)
    def test_two_anchors_fail_closed(self):
        db = self.fresh(gd="GET DIAGNOSTICS n = ROW_COUNT; GET DIAGNOSTICS n = ROW_COUNT;"); r = self.apply(db); self.assertNotEqual(r.returncode, 0); self.assertIn("count=2", r.stderr)
    def test_missing_function_fails(self):
        name = "tmissing%d" % (id(self) % 10**6); self.run_pg([PGBIN + "/createdb", "-h", self.sock, "-p", "54331", "-U", "postgres", name], check=False)
        self.psql(["-c", "CREATE SCHEMA api"], db=name); r = self.apply(name); self.assertNotEqual(r.returncode, 0); self.assertIn("not found", r.stderr)
if __name__ == "__main__": unittest.main()
