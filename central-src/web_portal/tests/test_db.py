"""اختبار الهجرة 81 على Postgres حقيقي مؤقت مع مخطط أساس بديل (core.tenants/ad_accounts + private.sign_ctx/enter_ctx + api.list_*). يتخطى نفسه إن ما توفّر initdb/runuser."""
import json, os, shutil, subprocess, tempfile, unittest

PGBIN = next((p for p in ("/usr/lib/postgresql/16/bin", "/usr/lib/postgresql/15/bin", "/usr/lib/postgresql/14/bin") if os.path.exists(p + "/initdb")), None)
HERE = os.path.dirname(os.path.abspath(__file__)); DBDIR = os.path.join(HERE, "..", "db")
TA, TB, TC = "a0000000-0000-0000-0000-000000000001", "b0000000-0000-0000-0000-000000000002", "c0000000-0000-0000-0000-000000000003"
PWD = "scrypt$15$8$1$" + "A" * 22 + "$" + "B" * 43
H1, H2, H3 = "1" * 64, "2" * 64, "3" * 64
STUB = """
CREATE ROLE app_owner NOLOGIN; CREATE ROLE app_runtime NOLOGIN; CREATE ROLE app_jobs NOLOGIN;
CREATE SCHEMA core; CREATE TABLE core.tenants (tenant_id uuid PRIMARY KEY, slug text UNIQUE, display_name text, status text NOT NULL DEFAULT 'READY');
CREATE TABLE core.ad_accounts (tenant_id uuid, platform text, external_id text, name text, currency text, status text, enabled boolean, unlinked_at timestamptz);
CREATE TABLE core.campaigns (tenant_id uuid, name text, external_id text, status text, created_at timestamptz DEFAULT now());
ALTER TABLE core.tenants ENABLE ROW LEVEL SECURITY; CREATE POLICY only_cur ON core.tenants USING (tenant_id = nullif(current_setting('t.tenant', true), '')::uuid);   -- مثل الحي: app_owner ما يشوف core.tenants بدون سياق
INSERT INTO core.tenants VALUES ('%(a)s','acme','Acme','READY'), ('%(b)s','beta','Beta','NEEDS_REVIEW'), ('%(c)s','gone','Gone','CANCELLED');
INSERT INTO core.campaigns (tenant_id, name, external_id, status) VALUES ('%(a)s','Camp A','9001','ACTIVE'), ('%(b)s','Camp B','9002','PAUSED');
INSERT INTO core.ad_accounts VALUES ('%(a)s','tiktok','111','A1','USD','ENABLE',true,NULL), ('%(b)s','tiktok','222','B1','IQD','ENABLE',true,NULL);
CREATE SCHEMA private;
CREATE FUNCTION private.sign_ctx(p jsonb) RETURNS text LANGUAGE sql AS $f$ SELECT 'ctx:' || (p->>'t') || ':' || (p->>'r') || ':' || (p->>'e') $f$;
CREATE FUNCTION private.enter_ctx(p text, r text) RETURNS void LANGUAGE plpgsql AS $f$ BEGIN
  IF p !~ '^ctx:[0-9a-f-]{36}:[a-z]+:[0-9]+$' THEN RAISE EXCEPTION 'invalid_ctx' USING ERRCODE = '28000'; END IF;
  IF split_part(p, ':', 3) <> 'system' THEN RAISE EXCEPTION 'user_inactive' USING ERRCODE = '42501'; END IF;   -- مثل enter_ctx الحي: غير system يحتاج سجل tenant_users
  IF split_part(p, ':', 4)::bigint < extract(epoch FROM now()) THEN RAISE EXCEPTION 'expired_ctx' USING ERRCODE = '28000'; END IF;
  PERFORM set_config('t.tenant', split_part(p, ':', 2), true); END $f$;
CREATE SCHEMA api;
CREATE FUNCTION api.list_ad_accounts(p_ctx text) RETURNS TABLE (platform text, external_id text, name text, currency text, status text, enabled boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $f$
BEGIN PERFORM private.enter_ctx(p_ctx, 'viewer'); RETURN QUERY SELECT a.platform, a.external_id, a.name, a.currency, a.status, a.enabled FROM core.ad_accounts a WHERE a.tenant_id = current_setting('t.tenant')::uuid; END $f$;
CREATE FUNCTION api.list_campaigns(p_ctx text, p_status text DEFAULT NULL) RETURNS SETOF core.campaigns LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $f$
BEGIN PERFORM private.enter_ctx(p_ctx, 'viewer'); RETURN QUERY SELECT * FROM core.campaigns c WHERE c.tenant_id = current_setting('t.tenant')::uuid ORDER BY c.created_at DESC; END $f$;
CREATE FUNCTION api.list_pages(p_ctx text) RETURNS TABLE (x text) LANGUAGE plpgsql SECURITY DEFINER AS $f$ BEGIN RETURN; END $f$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA api, private FROM PUBLIC; REVOKE ALL ON SCHEMA api, private FROM PUBLIC;
GRANT USAGE ON SCHEMA core, private, api TO app_owner; GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA api TO app_owner; GRANT SELECT ON core.campaigns TO app_owner; GRANT SELECT ON core.tenants TO app_owner; GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA private TO app_owner;
CREATE TABLE core.old_data (x int); INSERT INTO core.old_data VALUES (1);
""" % {"a": TA, "b": TB, "c": TC}
SNAP = """SELECT md5(coalesce(string_agg(n.nspname || '.' || c.relname || ':' || c.relkind::text, ',' ORDER BY n.nspname, c.relname), '')) || '/' ||
  (SELECT md5(coalesce(string_agg(n2.nspname || '.' || p.proname || '(' || pg_get_function_identity_arguments(p.oid) || ')' || md5(p.prosrc), ',' ORDER BY n2.nspname, p.proname), ''))
   FROM pg_proc p JOIN pg_namespace n2 ON n2.oid = p.pronamespace WHERE n2.nspname NOT IN ('pg_catalog','information_schema','web'))
  || '/' || (SELECT md5(coalesce(string_agg(rolname, ',' ORDER BY rolname), '')) FROM pg_roles WHERE rolname NOT LIKE 'pg\\_%' AND rolname <> 'web_rt')
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema','pg_toast','web')"""


@unittest.skipUnless(PGBIN and shutil.which("runuser"), "postgres + runuser required")
class WebDB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(); os.chmod(cls.dir, 0o755); shutil.chown(cls.dir, "postgres"); cls.data = cls.dir + "/data"; cls.sock = cls.dir + "/sock"; os.makedirs(cls.sock); shutil.chown(cls.sock, "postgres")
        cls.run_pg([PGBIN + "/initdb", "-D", cls.data, "-A", "trust", "--no-sync", "-U", "postgres"])
        cls.run_pg([PGBIN + "/pg_ctl", "-D", cls.data, "-o", "-p 54331 -k %s -c listen_addresses=''" % cls.sock, "-w", "-l", cls.dir + "/log", "start"])
        cls.sql(STUB); cls.base = cls.sql(SNAP); cls.file("81_web_portal.sql")

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
        return cls.run_pg([PGBIN + "/psql", "-h", cls.sock, "-p", "54331", "-U", "postgres", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-d", "postgres", "-c", s], check=False)

    @classmethod
    def sql(cls, sql, role=None):
        r = cls.psql(sql, role)
        if r.returncode: raise RuntimeError(r.stderr)
        return r.stdout.strip()

    @classmethod
    def file(cls, name):
        shutil.copy(os.path.join(DBDIR, name), cls.dir + "/" + name); os.chmod(cls.dir + "/" + name, 0o644)
        r = cls.run_pg([PGBIN + "/psql", "-h", cls.sock, "-p", "54331", "-U", "postgres", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", "postgres", "-f", cls.dir + "/" + name], check=False)
        if r.returncode: raise RuntimeError(r.stderr)

    def raises(self, sql, frag, role="web_rt"):
        r = self.psql(sql, role); self.assertNotEqual(r.returncode, 0, sql); self.assertIn(frag, r.stderr, sql)

    def invite(self, slug="acme", email="Client@Acme.com", h=H1, ttl=24):
        return json.loads(self.sql("SELECT web.invite_create('%s','%s','%s',%d)" % (slug, email, h, ttl)))

    def test_01_nothing_outside_web_changed_and_idempotent(self):
        self.assertEqual(self.sql(SNAP), self.base); self.file("81_web_portal.sql"); self.assertEqual(self.sql(SNAP), self.base)

    def test_01b_harness_really_hides_tenants_from_app_owner(self):
        self.assertEqual(self.sql("SELECT count(*) FROM core.tenants", "app_owner"), "0"); self.assertEqual(self.sql("SELECT count(*) FROM core.tenants"), "3")

    def test_02_admin_only_invite_create(self):
        self.raises("SELECT web.invite_create('acme','a@b.co','%s',24)" % H1, "permission denied")
        self.raises("SELECT * FROM web.users", "permission denied"); self.raises("SELECT * FROM core.tenants", "permission denied"); self.raises("SELECT * FROM web.sessions", "permission denied")

    def test_03_invite_accept_login_flow(self):
        u = self.invite(email="Flow@Acme.com", h="a" * 64)
        self.assertEqual(u["email"], "flow@acme.com")
        self.assertEqual(json.loads(self.sql("SELECT web.invite_peek('%s')" % ("a" * 64), "web_rt"))["email"], "flow@acme.com")
        self.assertEqual(self.sql("SELECT web.invite_peek('%s')" % ("9" * 64), "web_rt"), "")
        self.raises("SELECT web.invite_accept('%s','plain-password')" % ("a" * 64), "violates check constraint")
        r = json.loads(self.sql("SELECT web.invite_accept('%s','%s')" % ("a" * 64, PWD), "web_rt")); self.assertEqual(r["user_id"], u["user_id"])
        self.raises("SELECT web.invite_accept('%s','%s')" % ("a" * 64, PWD), "invite_invalid")
        l = json.loads(self.sql("SELECT web.login_lookup('FLOW@acme.com')", "web_rt")); self.assertTrue(l["active"]); self.assertFalse(l["locked"]); self.assertEqual(l["pwd"], PWD)
        self.assertEqual(self.sql("SELECT web.login_lookup('nobody@x.co')", "web_rt"), "")

    def test_04_expired_invite_and_disabled_user(self):
        u = self.invite(email="exp@acme.com", h="b" * 64); self.sql("UPDATE web.invites SET expires_at = now() - interval '1 minute' WHERE token_hash = '%s'" % ("b" * 64))
        self.raises("SELECT web.invite_accept('%s','%s')" % ("b" * 64, PWD), "invite_invalid")
        self.invite(email="dis@acme.com", h="c" * 64); self.sql("UPDATE web.users SET status = 'disabled' WHERE lower(email) = 'dis@acme.com'")
        self.raises("SELECT web.invite_accept('%s','%s')" % ("c" * 64, PWD), "user_disabled")
        self.raises("SELECT web.invite_create('acme','x@y.co','%s',0)" % ("d" * 64), "bad_ttl", None); self.raises("SELECT web.invite_create('nope','x@y.co','%s',5)" % ("d" * 64), "tenant_not_found", None)

    def test_05_email_unique_per_tenant_case_insensitive(self):
        self.invite(email="same@acme.com", h="e" * 64); u2 = self.invite(email="SAME@acme.com", h="f" * 64); self.assertEqual(self.sql("SELECT count(*) FROM web.users WHERE lower(email)='same@acme.com'"), "1"); self.assertTrue(u2["user_id"])
        self.raises("SELECT web.invite_create('beta','same@acme.com','%s',24)" % ("0" * 64), "email_belongs_to_other_tenant", None)

    def test_06_lockout_after_five_failures(self):
        u = self.invite(email="lock@acme.com", h="1a" * 32); self.sql("SELECT web.invite_accept('%s','%s')" % ("1a" * 32, PWD), "web_rt")
        for _ in range(4): self.sql("SELECT web.login_fail('%s')" % u["user_id"], "web_rt")
        self.assertFalse(json.loads(self.sql("SELECT web.login_lookup('lock@acme.com')", "web_rt"))["locked"])
        self.sql("SELECT web.login_fail('%s')" % u["user_id"], "web_rt"); self.assertTrue(json.loads(self.sql("SELECT web.login_lookup('lock@acme.com')", "web_rt"))["locked"])
        self.sql("SELECT web.login_ok('%s')" % u["user_id"], "web_rt"); self.assertFalse(json.loads(self.sql("SELECT web.login_lookup('lock@acme.com')", "web_rt"))["locked"])

    def test_07_sessions(self):
        u = self.invite(email="sess@acme.com", h="2b" * 32); self.sql("SELECT web.invite_accept('%s','%s')" % ("2b" * 32, PWD), "web_rt")
        self.sql("SELECT web.session_create('%s','%s',24)" % (u["user_id"], H2), "web_rt")
        s = json.loads(self.sql("SELECT web.session_get('%s')" % H2, "web_rt")); self.assertEqual((s["slug"], s["email"], s["tenant_id"], s["name"]), ("acme", "sess@acme.com", TA, "Acme"))
        self.assertEqual(self.sql("SELECT web.session_get('%s')" % H3, "web_rt"), "")
        self.sql("UPDATE web.sessions SET expires_at = now() - interval '1 second' WHERE session_hash = '%s'" % H2); self.assertEqual(self.sql("SELECT web.session_get('%s')" % H2, "web_rt"), "")
        for i in range(7): self.sql("SELECT web.session_create('%s','%s',24)" % (u["user_id"], ("%02d" % (10 + i)) * 32), "web_rt")
        self.assertEqual(self.sql("SELECT count(*) FROM web.sessions WHERE user_id='%s'" % u["user_id"]), "5")
        self.sql("SELECT web.session_delete('%s')" % ("16" * 32), "web_rt"); self.assertEqual(self.sql("SELECT web.session_get('%s')" % ("16" * 32), "web_rt"), "")
        self.raises("SELECT web.session_create('%s','%s',0)" % (u["user_id"], H3), "bad_ttl")

    def test_08_accounts_and_campaigns_scoped_to_user_tenant(self):
        ua = self.invite("acme", "ctxa@acme.com", "3c" * 32); ub = self.invite("beta", "ctxb@beta.com", "4d" * 32)
        for h in ("3c" * 32, "4d" * 32): self.sql("SELECT web.invite_accept('%s','%s')" % (h, PWD), "web_rt")
        ra = self.sql("SELECT external_id FROM web.accounts('%s')" % ua["user_id"], "web_rt"); rb = self.sql("SELECT external_id FROM web.accounts('%s')" % ub["user_id"], "web_rt"); self.assertEqual((ra, rb), ("111", "222"))
        ca = json.loads(self.sql("SELECT web.campaigns('%s')" % ua["user_id"], "web_rt")); cb = json.loads(self.sql("SELECT web.campaigns('%s')" % ub["user_id"], "web_rt"))
        self.assertEqual([c["external_id"] for c in ca], ["9001"]); self.assertEqual([c["external_id"] for c in cb], ["9002"]); self.assertEqual(set(ca[0]), {"name", "external_id", "status", "created_at"})
        self.assertEqual(self.sql("SELECT count(*) FROM web.accounts('00000000-0000-0000-0000-000000000000')", "web_rt"), "0"); self.assertEqual(json.loads(self.sql("SELECT web.campaigns('00000000-0000-0000-0000-000000000000')", "web_rt")), [])
        self.sql("UPDATE web.users SET status='disabled' WHERE user_id='%s'" % ua["user_id"]); self.assertEqual(self.sql("SELECT count(*) FROM web.accounts('%s')" % ua["user_id"], "web_rt"), "0")

    def test_09_tenant_without_data_gets_empty_lists(self):
        u = self.invite("gone", "g@gone.com", "5e" * 32); self.sql("SELECT web.invite_accept('%s','%s')" % ("5e" * 32, PWD), "web_rt"); self.assertEqual(self.sql("SELECT count(*) FROM web.accounts('%s')" % u["user_id"], "web_rt"), "0"); self.assertEqual(json.loads(self.sql("SELECT web.campaigns('%s')" % u["user_id"], "web_rt")), [])

    def test_10b_connect_privilege_granted_even_if_public_revoked(self):
        self.assertEqual(self.sql("SELECT has_database_privilege('web_rt', current_database(), 'CONNECT')"), "t")
        self.sql("REVOKE CONNECT ON DATABASE postgres FROM PUBLIC"); self.file("81_web_portal.sql"); self.assertEqual(self.sql("SELECT has_database_privilege('web_rt', current_database(), 'CONNECT')"), "t")
        self.assertEqual(self.sql("SELECT has_database_privilege('app_jobs', current_database(), 'CONNECT')"), "f")   # الدور الثاني ما يحصل على شي إضافي

    def test_10_web_rt_has_no_other_privileges(self):
        self.raises("SELECT * FROM core.ad_accounts", "permission denied"); self.raises("INSERT INTO web.users (tenant_id,email) VALUES ('%s','x@y.co')" % TA, "permission denied")
        self.raises("SELECT private.sign_ctx('{}'::jsonb)", "permission denied")
        self.raises("SELECT * FROM api.list_ad_accounts('x')", "permission denied"); self.raises("SELECT api.list_campaigns('x', NULL)", "permission denied")
        self.assertEqual(self.sql("SELECT has_function_privilege('web_rt','web.invite_create(text,text,text,integer)','EXECUTE')"), "f")
        for f in ("web.accounts(uuid)", "web.campaigns(uuid)", "web.session_get(text)"): self.assertEqual(self.sql("SELECT has_function_privilege('web_rt','%s','EXECUTE')" % f), "t", f)
        self.assertEqual(self.sql("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'web' AND p.proname = 'ctx'"), "0")   # الـctx ما يطلع من القاعدة

    def test_98_upgrade_from_previous_live_version(self):
        # حالة السيرفر الحالية: النسخة الأولى كانت منشأة web.ctx ومانحة web_rt صلاحيات مباشرة على api.list_*
        self.sql("CREATE FUNCTION web.ctx(p uuid) RETURNS text LANGUAGE sql SECURITY DEFINER AS $f$ SELECT 'x'::text $f$; GRANT EXECUTE ON FUNCTION web.ctx(uuid) TO web_rt; GRANT USAGE ON SCHEMA api TO web_rt; "
                 "GRANT EXECUTE ON FUNCTION api.list_ad_accounts(text), api.list_campaigns(text, text), api.list_pages(text) TO web_rt")
        self.assertEqual(self.sql("SELECT has_function_privilege('web_rt','api.list_ad_accounts(text)','EXECUTE')"), "t")
        self.file("81_web_portal.sql")
        self.assertEqual(self.sql("SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'web' AND p.proname = 'ctx'"), "0")
        self.assertEqual(self.sql("SELECT has_function_privilege('web_rt','api.list_ad_accounts(text)','EXECUTE')"), "f"); self.assertEqual(self.sql("SELECT has_schema_privilege('web_rt','api','USAGE')"), "f")

    def test_99_down_restores_everything(self):
        self.file("81_web_portal_down.sql"); self.assertEqual(self.sql("SELECT count(*) FROM pg_namespace WHERE nspname='web'"), "0")
        self.assertEqual(self.sql("SELECT count(*) FROM pg_proc p, aclexplode(p.proacl) a WHERE a.grantee = 'web_rt'::regrole"), "0"); self.assertEqual(self.sql(SNAP), self.base); self.assertEqual(self.sql("SELECT has_database_privilege('web_rt', current_database(), 'CONNECT')"), "f")
        self.file("81_web_portal.sql"); self.assertEqual(self.sql("SELECT count(*) FROM pg_namespace WHERE nspname='web'"), "1")


if __name__ == "__main__":
    unittest.main(verbosity=1)
