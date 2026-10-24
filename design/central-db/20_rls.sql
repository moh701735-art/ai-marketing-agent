-- 20_rls.sql : عزل الصفوف (RLS) + صلاحيات الأدوار.
\set ON_ERROR_STOP on
-- لا EXECUTE تلقائي لـ PUBLIC على أي دالة جديدة (الافتراضي بـ PostgreSQL يمنحه!)
-- ملاحظة: الصيغة العامة (بدون IN SCHEMA) هي الوحيدة التي تلغي الافتراضي المدمج. اكتشفه اختبار ISO-F2/F3.
ALTER DEFAULT PRIVILEGES FOR ROLE app_owner REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE app_resolver REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE app_ops_fn REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
SET ROLE app_owner;
SET search_path = core, private, ext, public;

-- مفتاح توقيع سياق الطلب (ctx): صف واحد، يقرؤه التوقيع/التحقق فقط (private).
CREATE TABLE private.ctx_key (id int PRIMARY KEY CHECK (id = 1), k bytea NOT NULL CHECK (octet_length(k) >= 32));
INSERT INTO private.ctx_key VALUES (1, ext.gen_random_bytes(32));
REVOKE ALL ON private.ctx_key FROM PUBLIC;

CREATE FUNCTION private.cur_tenant() RETURNS uuid LANGUAGE sql STABLE AS
$$ SELECT nullif(current_setting('app.tenant_id', true), '')::uuid $$;

-- سياسة عزل موحّدة لكل جدول فيه tenant_id (آلياً، فلا يُنسى جدول)
DO $$
DECLARE t record;
BEGIN
  FOR t IN
    SELECT c.relname
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped
    WHERE n.nspname = 'core' AND c.relkind IN ('r','p') AND NOT c.relispartition
      AND c.relname NOT IN ('knowledge_docs','error_log','audit_log')
  LOOP
    EXECUTE format('ALTER TABLE core.%I ENABLE ROW LEVEL SECURITY', t.relname);
    EXECUTE format('ALTER TABLE core.%I FORCE ROW LEVEL SECURITY', t.relname);
    EXECUTE format($f$CREATE POLICY tenant_isolation ON core.%I
      USING (tenant_id = private.cur_tenant()) WITH CHECK (tenant_id = private.cur_tenant())$f$, t.relname);
  END LOOP;
END $$;

-- error_log وaudit_log: صفوف النظام (tenant_id NULL) تُكتب ولا يراها أي tenant
ALTER TABLE core.error_log ENABLE ROW LEVEL SECURITY;  ALTER TABLE core.error_log FORCE ROW LEVEL SECURITY;
CREATE POLICY el_select ON core.error_log FOR SELECT USING (tenant_id = private.cur_tenant());
CREATE POLICY el_insert ON core.error_log FOR INSERT WITH CHECK (tenant_id IS NULL OR tenant_id = private.cur_tenant());
CREATE POLICY el_update ON core.error_log FOR UPDATE USING (tenant_id = private.cur_tenant()) WITH CHECK (tenant_id = private.cur_tenant());
ALTER TABLE core.audit_log ENABLE ROW LEVEL SECURITY;  ALTER TABLE core.audit_log FORCE ROW LEVEL SECURITY;
CREATE POLICY al_select ON core.audit_log FOR SELECT USING (tenant_id = private.cur_tenant());
CREATE POLICY al_insert ON core.audit_log FOR INSERT WITH CHECK (tenant_id IS NULL OR tenant_id = private.cur_tenant());

-- المعرفة: العام مقروء للجميع، وكتابته عبر دالة إدارة فقط. معرفة الـ tenant لصاحبها فقط.
ALTER TABLE core.knowledge_docs ENABLE ROW LEVEL SECURITY;  ALTER TABLE core.knowledge_docs FORCE ROW LEVEL SECURITY;
CREATE POLICY kd_select ON core.knowledge_docs FOR SELECT USING (scope = 'global' OR tenant_id = private.cur_tenant());
CREATE POLICY kd_write  ON core.knowledge_docs FOR ALL
  USING (scope = 'tenant' AND tenant_id = private.cur_tenant())
  WITH CHECK (scope = 'tenant' AND tenant_id = private.cur_tenant());
-- الإدارة تنشر العام عبر دالة api_admin (مالكها app_ops_fn) بسياسة خاصة:
CREATE POLICY kd_global_admin ON core.knowledge_docs FOR ALL TO app_ops_fn
  USING (scope = 'global') WITH CHECK (scope = 'global');
GRANT USAGE ON SCHEMA core, private TO app_ops_fn;
GRANT EXECUTE ON FUNCTION private.cur_tenant() TO app_resolver, app_ops_fn;   -- تُقيَّم داخل سياسات RLS بصلاحية الدور المنفّذ
GRANT SELECT, INSERT, UPDATE, DELETE ON core.knowledge_docs TO app_ops_fn;

-- app_resolver: قراءة عابرة للـ tenants محصورة بجداول محددة + تحديث status فقط (sweep)
GRANT USAGE ON SCHEMA core, private TO app_resolver;
GRANT SELECT ON core.tenants, core.bots, core.tenant_users, core.config_versions, core.readiness_checks, core.readiness_check_defs TO app_resolver;
GRANT UPDATE (status, updated_at) ON core.tenants TO app_resolver;
CREATE POLICY resolver_tenants  ON core.tenants          FOR SELECT TO app_resolver USING (true);
CREATE POLICY resolver_tenants_u ON core.tenants         FOR UPDATE TO app_resolver USING (true) WITH CHECK (true);
CREATE POLICY resolver_bots     ON core.bots             FOR SELECT TO app_resolver USING (true);
CREATE POLICY resolver_users    ON core.tenant_users     FOR SELECT TO app_resolver USING (true);
CREATE POLICY resolver_configs  ON core.config_versions  FOR SELECT TO app_resolver USING (true);
CREATE POLICY resolver_ready    ON core.readiness_checks FOR SELECT TO app_resolver USING (true);
-- readiness_check_defs و solutions جداول عامة (لا tenant_id): لا RLS، تُقرأ عبر دوال فقط.

-- app_runtime: لا صلاحية مباشرة على أي جدول أو schema بياناتي. دوال api.* فقط (تُمنح بعد إنشائها بـ 30_functions.sql)
REVOKE ALL ON ALL TABLES IN SCHEMA core FROM PUBLIC;
REVOKE ALL ON SCHEMA core, private FROM PUBLIC;
GRANT USAGE ON SCHEMA api TO app_runtime, app_jobs;
GRANT USAGE ON SCHEMA api_admin TO app_ops;

RESET ROLE;
