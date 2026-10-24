-- 50_readiness.sql : بوابة READY (T-READY). لا يصير tenant READY إلا بعد كل الفحوصات الإلزامية الصالحة.
\set C '\'c0000000-0000-0000-0000-000000000001\''
\set A '\'a0000000-0000-0000-0000-000000000001\''
SELECT encode(ext.digest('secret-c','sha256'),'hex') AS hc \gset
SET ROLE app_jobs;
SELECT ctx AS c_sys FROM api.job_contexts_for_status(ARRAY['CONFIGURATION_REQUIRED','TESTING','NEEDS_REVIEW'], 10)
  WHERE tenant_id = :C \gset
SELECT t.ok('READY-00 jobs account can obtain a system ctx for a NOT-ready tenant (onboarding), but only by status filter',
  :'c_sys' <> '');
SELECT t.raises('READY-01 promote with zero checks is rejected and lists the missing ones',
  format('SELECT api.promote_ready(%L)', :'c_sys'), 'P0001', 'R01');
SELECT t.raises('READY-02 system ctx for a NOT-ready tenant cannot create campaigns (needs READY)',
  format('SELECT api.record_campaign(%L,%L,%L,%L,%L,%L,%s)', :'c_sys','meta','act_C','c','c','o',1), '42501', 'tenant_not_ready');
-- أكمل كل الفحوصات الإلزامية إلا R10 (العزل) = fail
SELECT api.set_readiness(:'c_sys', d.check_code, CASE WHEN d.check_code='R10' THEN 'fail' ELSE 'pass' END, '{"by":"test"}')
FROM (SELECT format('R%s', lpad(g::text,2,'0')) AS check_code FROM generate_series(1,15) g) d;
RESET ROLE;
SELECT count(*) AS n FROM core.readiness_checks WHERE tenant_id = :C \gset
SET ROLE app_jobs;
SELECT t.raises('READY-03 one failing mandatory check (R10) blocks READY',
  format('SELECT api.promote_ready(%L)', :'c_sys'), 'P0001', 'R10');
SELECT api.set_readiness(:'c_sys','R10','warn','{}');
SELECT t.raises('READY-04 "warn" is not "pass" for a mandatory check',
  format('SELECT api.promote_ready(%L)', :'c_sys'), 'P0001', 'R10');
SELECT t.raises('READY-05 unknown check code rejected',
  format('SELECT api.set_readiness(%L,%L,%L,%L)', :'c_sys','R99','pass','{}'), 'P0002');
SELECT api.set_readiness(:'c_sys','R10','pass','{}');
SELECT api.promote_ready(:'c_sys');
RESET ROLE;
SELECT t.ok('READY-06 all mandatory checks pass -> tenant becomes READY', (SELECT status FROM core.tenants WHERE tenant_id = :C) = 'READY');
-- فحص انتهت صلاحيته => sweep يخفضه NEEDS_REVIEW تلقائياً
UPDATE core.readiness_checks SET checked_at = now() - interval '2 days', expires_at = now() - interval '1 day'
 WHERE tenant_id = :C AND check_code = 'R02';
SET ROLE app_ops;
SELECT api_admin.sweep_readiness() AS swept \gset
RESET ROLE;
SELECT t.ok('READY-07 expired check -> sweep demotes the tenant to NEEDS_REVIEW', :swept >= 1
  AND (SELECT status FROM core.tenants WHERE tenant_id = :C) = 'NEEDS_REVIEW');
SELECT t.ok('READY-08 healthy tenants are untouched by the sweep',
  (SELECT count(*) FROM core.tenants WHERE status = 'READY') = 3);
SET ROLE app_runtime;
SELECT t.ok('READY-09 NEEDS_REVIEW tenant: bot gets no context (interactive operations stop)',
  (SELECT count(*) FROM api.resolve_context('botCCCCCCCCCCCCCCCCCCCCCCCC', decode(:'hc','hex'), 3001)
   ) = 0);
RESET ROLE;
-- لا يمكن القفز لـ READY يدوياً حتى بـ superuser (trigger)
SELECT t.raises('READY-10 manual UPDATE to READY is blocked while a mandatory check is expired',
  $q$UPDATE core.tenants SET status = 'READY' WHERE tenant_id = 'c0000000-0000-0000-0000-000000000001'$q$, 'P0001', 'R02');
-- تجديد الفحص يسمح بالعودة
UPDATE core.readiness_checks SET checked_at = now(), expires_at = now() + interval '1 day' WHERE tenant_id = :C AND check_code = 'R02';
UPDATE core.tenants SET status = 'READY' WHERE tenant_id = :C;
SELECT t.ok('READY-11 renewed check allows READY again', (SELECT status FROM core.tenants WHERE tenant_id = :C) = 'READY');
-- الميزات: tenant بلا tiktok لا يحتاج R05 (D جاهز أصلاً بدون R05)؛ tenant بـ tiktok يحتاجه
DELETE FROM core.readiness_checks WHERE tenant_id = :A AND check_code = 'R05';
SET ROLE app_ops; SELECT api_admin.sweep_readiness(); RESET ROLE;
SELECT t.ok('READY-12 tenant WITH tiktok feature missing R05 is demoted; tenant D (no tiktok) stays READY',
  (SELECT status FROM core.tenants WHERE tenant_id = :A) = 'NEEDS_REVIEW'
  AND (SELECT status FROM core.tenants WHERE tenant_id = 'd0000000-0000-0000-0000-000000000001') = 'READY');
-- أعد A كما كان
INSERT INTO core.readiness_checks (tenant_id, check_code, status, expires_at) VALUES (:A,'R05','pass', now() + interval '1 day');
UPDATE core.tenants SET status = 'READY' WHERE tenant_id = :A;
SELECT t.ok('READY-13 A restored', (SELECT status FROM core.tenants WHERE tenant_id = :A) = 'READY');
