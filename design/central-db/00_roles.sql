-- 00_roles.sql : الأدوار. تُنفَّذ مرة واحدة على الخادم (superuser).
-- app_owner    : يملك الجداول والدوال. NOLOGIN. غير superuser ولا BYPASSRLS، فتسري عليه RLS (FORCE).
-- app_resolver : يملك الدوال العابرة للـ tenants فقط (resolve_context و job_contexts). NOLOGIN.
-- app_runtime  : حساب اتصال Workflows التفاعلية (Ingress). لا صلاحية على أي جدول. EXECUTE على api.* التفاعلية فقط.
-- app_jobs     : حساب Workflows المجدولة (job/*). يستطيع طلب system ctx. لا يستطيع resolve_context. حساب مستقل بـ credential مستقل.
-- app_ops_fn   : يملك دوال نشر المعرفة العامة فقط.
-- app_ops      : حساب إدارة (صيانة الأقسام، ترقية READY، إدخال معرفة عامة). NOLOGIN هنا، يُمنح لحساب بشري/خدمة.
DO $$
DECLARE r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['app_owner','app_resolver','app_runtime','app_jobs','app_ops','app_ops_fn'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('CREATE ROLE %I NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE', r);
    END IF;
  END LOOP;
END $$;
