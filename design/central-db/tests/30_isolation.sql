-- 30_isolation.sql : اختبارات عزل العملاء (T-ISO) عبر الحسابات الحقيقية للتطبيق (app_runtime/app_jobs)،
-- لا بـ superuser. الهدف: إثبات أن عميلاً لا يقرأ ولا يعدّل ولا ينفّذ على بيانات عميل آخر.
\set A '\'a0000000-0000-0000-0000-000000000001\''
\set B '\'b0000000-0000-0000-0000-000000000001\''
SELECT encode(ext.digest('secret-a','sha256'),'hex') AS ha, encode(ext.digest('secret-b','sha256'),'hex') AS hb,
       encode(ext.digest('secret-c','sha256'),'hex') AS hc, encode(ext.digest('secret-d','sha256'),'hex') AS hd \gset
-- ctx منتهي الصلاحية (يصدره superuser فقط لغرض الاختبار)
SELECT private.sign_ctx(jsonb_build_object('t','a0000000-0000-0000-0000-000000000001','u',1001,'r','owner',
   'b',(SELECT bot_id FROM core.bots WHERE telegram_bot_id=111),'e',1,'k','user')) AS a_expired \gset

SET ROLE app_runtime;
SELECT ctx AS a_owner  FROM api.resolve_context('botAAAAAAAAAAAAAAAAAAAAAAAA', decode(:'ha','hex'), 1001) \gset
SELECT ctx AS a_viewer FROM api.resolve_context('botAAAAAAAAAAAAAAAAAAAAAAAA', decode(:'ha','hex'), 1002) \gset
SELECT ctx AS a_mgr    FROM api.resolve_context('botAAAAAAAAAAAAAAAAAAAAAAAA', decode(:'ha','hex'), 1003) \gset
SELECT ctx AS b_owner  FROM api.resolve_context('botBBBBBBBBBBBBBBBBBBBBBBBB', decode(:'hb','hex'), 2001) \gset
SELECT ctx AS b_mgr    FROM api.resolve_context('botBBBBBBBBBBBBBBBBBBBBBBBB', decode(:'hb','hex'), 2002) \gset

-- ═══ T-ISO-A: لا وصول مباشر لأي جدول أو دالة داخلية ═══
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname='core' AND c.relkind IN ('r','p') ORDER BY 1 LOOP
    PERFORM t.raises('ISO-A1 app_runtime cannot SELECT core.'||r.relname,
                     format('SELECT 1 FROM core.%I LIMIT 1', r.relname), '42501');
    PERFORM t.raises('ISO-A2 app_runtime cannot INSERT core.'||r.relname,
                     format('INSERT INTO core.%I DEFAULT VALUES', r.relname), '42501');
  END LOOP;
END $$;
SELECT t.raises('ISO-A3 cannot read private.ctx_key (signing key)', 'SELECT * FROM private.ctx_key', '42501');
SELECT t.raises('ISO-A4 cannot mint ctx (private.sign_ctx)', $q$SELECT private.sign_ctx('{"t":"x"}'::jsonb)$q$, '42501');
SELECT t.raises('ISO-A5 cannot call private.enter_ctx directly', format('SELECT private.enter_ctx(%L)', :'a_owner'), '42501');
SELECT t.raises('ISO-A6 cannot use extension schema (digest/hmac)', $q$SELECT ext.hmac('a','b','sha256')$q$, '42501');
SET app.tenant_id = 'b0000000-0000-0000-0000-000000000001';       -- محاولة "انتحال" tenant بالجلسة
SELECT t.raises('ISO-A7 setting app.tenant_id by hand does not grant table access', 'SELECT 1 FROM core.campaigns', '42501');
RESET app.tenant_id;

-- ═══ T-ISO-B: حل الهوية (resolve_context) ═══
SELECT t.ok('ISO-B1 valid secret + registered user -> ctx', :'a_owner' <> '' AND :'a_viewer' <> '' AND :'a_mgr' <> '');
SELECT t.ok('ISO-B2 wrong webhook secret -> no context',
  (SELECT count(*) FROM api.resolve_context('botAAAAAAAAAAAAAAAAAAAAAAAA', decode(:'hb','hex'), 1001)) = 0);
SELECT t.ok('ISO-B3 secret of B on bot of A -> no context',
  (SELECT count(*) FROM api.resolve_context('botAAAAAAAAAAAAAAAAAAAAAAAA', decode(:'hb','hex'), 2001)) = 0);
SELECT t.ok('ISO-B4 user of B on bot of A (right secret) -> no context',
  (SELECT count(*) FROM api.resolve_context('botAAAAAAAAAAAAAAAAAAAAAAAA', decode(:'ha','hex'), 2001)) = 0);
SELECT t.ok('ISO-B5 unknown bot id -> no context',
  (SELECT count(*) FROM api.resolve_context('botNOPENOPENOPENOPENOPENO', decode(:'ha','hex'), 1001)) = 0);
SELECT t.ok('ISO-B6 tenant not READY (C) -> no context',
  (SELECT count(*) FROM api.resolve_context('botCCCCCCCCCCCCCCCCCCCCCCCC', decode(:'hc','hex'), 3001)) = 0);
SELECT t.ok('ISO-B7 user not registered -> no context',
  (SELECT count(*) FROM api.resolve_context('botAAAAAAAAAAAAAAAAAAAAAAAA', decode(:'ha','hex'), 999999)) = 0);

-- ═══ T-ISO-C: تزوير/إعادة استخدام ctx ═══
SELECT encode(convert_to(replace(convert_from(decode(split_part(:'a_owner','.',1),'hex'),'UTF8'),
         'a0000000-0000-0000-0000-000000000001','b0000000-0000-0000-0000-000000000001'),'UTF8'),'hex')
       || '.' || split_part(:'a_owner','.',2) AS forged_tenant \gset
SELECT t.raises('ISO-C1 ctx with tenant swapped to B (payload edited) is rejected',
  format('SELECT * FROM api.list_campaigns(%L)', :'forged_tenant'), '28000', 'invalid_ctx');
SELECT t.raises('ISO-C2 garbage ctx rejected', $q$SELECT * FROM api.list_campaigns('abc.def')$q$, '28000', 'invalid_ctx');
SELECT t.raises('ISO-C3 NULL ctx rejected', $q$SELECT * FROM api.list_campaigns(NULL)$q$, '28000', 'invalid_ctx');
SELECT t.raises('ISO-C4 truncated signature rejected',
  format('SELECT * FROM api.list_campaigns(%L)', left(:'a_owner', length(:'a_owner')-4)), '28000', 'invalid_ctx');
SELECT t.raises('ISO-C5 expired ctx rejected',
  format('SELECT * FROM api.list_campaigns(%L)', :'a_expired'), '28000', 'expired_ctx');
SELECT t.raises('ISO-C6 role escalation by editing payload (viewer -> owner) rejected',
  format('SELECT api.record_campaign(%L,%L,%L,%L,%L,%L,%s)',
    encode(convert_to(replace(convert_from(decode(split_part(:'a_viewer','.',1),'hex'),'UTF8'),'"viewer"','"owner"'),'UTF8'),'hex')
      || '.' || split_part(:'a_viewer','.',2), 'meta','act_A1','x1','x','o',1), '28000', 'invalid_ctx');
SELECT t.ok('ISO-C7 no api function accepts a tenant_id/p_tenant input argument',
  (SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
   WHERE n.nspname = 'api'
     AND EXISTS (SELECT 1 FROM unnest(coalesce(p.proargnames, '{}')) WITH ORDINALITY a(nm, i)
                 WHERE (p.proargmodes IS NULL OR p.proargmodes[a.i] IN ('i','b','v')) AND a.nm ~* 'tenant')) = 0);

-- ═══ T-ISO-D: فصل البيانات والأدوار ═══
SELECT t.raises('ISO-D1 viewer cannot record a campaign',
  format('SELECT api.record_campaign(%L,%L,%L,%L,%L,%L,%s)', :'a_viewer','meta','act_A1','xv1','x','o',1), '42501', 'forbidden');
SELECT t.raises('ISO-D2 manager of A cannot create a campaign on B''s ad account',
  format('SELECT api.record_campaign(%L,%L,%L,%L,%L,%L,%s)', :'a_mgr','meta','act_B1','xb1','x','o',1), '42501', 'ad_account_not_owned_or_disabled');
SELECT t.raises('ISO-D3 manager over personal budget limit (50) rejected',
  format('SELECT api.record_campaign(%L,%L,%L,%L,%L,%L,%s)', :'a_mgr','meta','act_A1','xl1','x','o',60), '42501', 'budget_over_user_limit');
SELECT api.record_campaign(:'a_mgr','meta','act_A1','camp_A_1','Campaign A','OUTCOME_ENGAGEMENT',40) AS a_camp_id \gset
SELECT api.record_campaign(:'b_mgr','meta','act_B1','camp_B_1','Campaign B','OUTCOME_ENGAGEMENT',40) AS b_camp_id \gset
SELECT t.ok('ISO-D4 A sees only its own campaigns (seed + new)',
  (SELECT count(*) FROM api.list_campaigns(:'a_viewer')) = 2
  AND (SELECT bool_and(external_id LIKE 'camp_A_%') FROM api.list_campaigns(:'a_viewer')));
SELECT t.ok('ISO-D5 B sees only its own campaign',
  (SELECT count(*) FROM api.list_campaigns(:'b_owner')) = 1
  AND (SELECT bool_and(external_id = 'camp_B_1') FROM api.list_campaigns(:'b_owner')));
SELECT t.ok('ISO-D6 B cannot see A campaign by status filter either',
  (SELECT count(*) FROM api.list_campaigns(:'b_owner', 'PAUSED')) = 1);

-- تحديث الدور/التعطيل يسري فوراً على ctx القديم
RESET ROLE;
UPDATE core.tenant_users SET active = false WHERE tenant_id = :A AND telegram_user_id = 1003;
SET ROLE app_runtime;
SELECT t.raises('ISO-D7 deactivated user: old ctx stops working immediately',
  format('SELECT * FROM api.list_campaigns(%L)', :'a_mgr'), '42501', 'user_inactive');
RESET ROLE;
UPDATE core.tenant_users SET active = true, role = 'viewer' WHERE tenant_id = :A AND telegram_user_id = 1003;
SET ROLE app_runtime;
SELECT t.raises('ISO-D8 demoted user: old manager ctx can no longer write',
  format('SELECT api.record_campaign(%L,%L,%L,%L,%L,%L,%s)', :'a_mgr','meta','act_A1','xd8','x','o',1), '42501', 'forbidden');
RESET ROLE;
UPDATE core.tenant_users SET role = 'manager' WHERE tenant_id = :A AND telegram_user_id = 1003;
SET ROLE app_runtime;

-- ═══ T-ISO-E: updates / تقارير / أخطاء / معرفة ═══
SELECT t.ok('ISO-E1 claim_update first time true', api.claim_update(:'a_viewer', 5001));
SELECT t.ok('ISO-E2 claim_update duplicate false', NOT api.claim_update(:'a_viewer', 5001));
SELECT t.ok('ISO-E3 same update_id on another tenant''s bot is independent', api.claim_update(:'b_owner', 5001));

SELECT api.log_error(:'a_owner','AUTH_EXPIRED','tiktok','job/report','TikTok Report',NULL,'40105',
  'token 1234567890:AAAbbbCCCdddEEEfffGGGhhhIIIjjjKKK123 and EAABsbCS1iHgBAAAAAAAAAAAAAAAAAAAAAAAAA leaked') ;
SELECT api.log_error(NULL,'BUG','telegram','system','x',NULL,NULL,'system-level error');
SELECT t.ok('ISO-E4 A sees its own error, with secret-like text redacted',
  (SELECT count(*) FROM api.list_errors(:'a_viewer')) = 1
  AND (SELECT message FROM api.list_errors(:'a_viewer')) LIKE '%[REDACTED]%'
  AND (SELECT message NOT LIKE '%AAAbbbCCC%' AND message NOT LIKE '%EAABsbCS%' FROM api.list_errors(:'a_viewer')));
SELECT t.ok('ISO-E5 B sees no errors of A and no system errors',
  (SELECT count(*) FROM api.list_errors(:'b_owner')) = 0);

RESET ROLE;
SET ROLE app_ops;
SELECT api_admin.publish_global_doc('Meta error 190','Token expired. Ask the client to reconnect from the connect link.','kb','owner') AS g_doc \gset
SELECT t.raises('ISO-E6 sanitizer blocks global doc with long ids',
  $q$SELECT api_admin.publish_global_doc('x','Account 7689583413044510741 failed','kb','owner')$q$, 'P0001', 'sanitize_failed');
SELECT t.raises('ISO-E7 sanitizer blocks global doc with email',
  $q$SELECT api_admin.publish_global_doc('x','contact client@example.com for token','kb','owner')$q$, 'P0001', 'sanitize_failed');
SELECT t.raises('ISO-E8 sanitizer blocks global doc with token-like strings',
  $q$SELECT api_admin.publish_global_doc('x','use abcdefghijklmnopqrstuvwxyz0123456789ABC as the key','kb','owner')$q$, 'P0001', 'sanitize_failed');
RESET ROLE;
SET ROLE app_runtime;
SELECT api.add_tenant_knowledge(:'a_mgr','A private note','Client A prefers Iraqi dialect and 20 USD minimum') AS a_doc \gset
SELECT t.ok('ISO-E9 A search finds global + its private note',
  (SELECT count(*) FROM api.search_knowledge(:'a_viewer','e')) >= 2
  AND EXISTS (SELECT 1 FROM api.search_knowledge(:'a_viewer','Client A prefers')));
SELECT t.ok('ISO-E10 B search never returns A private note but still sees global',
  NOT EXISTS (SELECT 1 FROM api.search_knowledge(:'b_owner','Client A prefers'))
  AND EXISTS (SELECT 1 FROM api.search_knowledge(:'b_owner','Token expired')));
SELECT t.raises('ISO-E11 viewer cannot add private knowledge',
  format('SELECT api.add_tenant_knowledge(%L,%L,%L)', :'a_viewer','x','y'), '42501', 'forbidden');

-- ═══ T-ISO-F: فصل صلاحيات الحسابات (interactive مقابل jobs) ═══
SELECT t.raises('ISO-F1 interactive account cannot request system ctx (job_contexts)',
  $q$SELECT * FROM api.job_contexts('schedule', 10)$q$, '42501');
SELECT t.raises('ISO-F2 interactive account cannot write report snapshots',
  $q$SELECT api.add_report_snapshot('x','meta','c',now(),1,1,1,1,'USD')$q$, '42501');
SELECT t.raises('ISO-F3 interactive account cannot set readiness / promote',
  $q$SELECT api.promote_ready('x')$q$, '42501');
RESET ROLE;
SET ROLE app_jobs;
SELECT t.raises('ISO-F4 jobs account cannot resolve user contexts',
  format('SELECT * FROM api.resolve_context(%L, decode(%L,''hex''), 1001)', 'botAAAAAAAAAAAAAAAAAAAAAAAA', :'ha'), '42501');
SELECT ctx AS a_sys FROM api.job_contexts('schedule', 10) WHERE tenant_id = :A \gset
SELECT ctx AS b_sys FROM api.job_contexts('schedule', 10) WHERE tenant_id = :B \gset
SELECT t.ok('ISO-F5 job_contexts returns only READY tenants with the feature (A,B,D; not C)',
  (SELECT count(*) FROM api.job_contexts('schedule', 10)) = 3
  AND NOT EXISTS (SELECT 1 FROM api.job_contexts('schedule', 10) WHERE tenant_id = 'c0000000-0000-0000-0000-000000000001'));
SELECT t.ok('ISO-F6 job_contexts respects feature flag (tiktok: A,B only; D has no tiktok)',
  (SELECT count(*) FROM api.job_contexts('tiktok', 10)) = 2);
SELECT api.add_report_snapshot(:'a_sys','meta','camp_A_1', date_trunc('hour', now()), 12.5, 1000, 20, 3, 'USD');
SELECT api.add_report_snapshot(:'b_sys','meta','camp_B_1', date_trunc('hour', now()), 99, 5000, 90, 7, 'USD');
SELECT t.ok('ISO-F7 report snapshots are written to the right tenant',
  (SELECT count(*) FROM api.get_report(:'a_sys','meta', now() - interval '1 day')) = 1
  AND (SELECT spend FROM api.get_report(:'a_sys','meta', now() - interval '1 day')) = 12.5
  AND (SELECT spend FROM api.get_report(:'b_sys','meta', now() - interval '1 day')) = 99);
SELECT t.ok('ISO-F8 A system ctx cannot read B snapshots (campaign ids never mix)',
  NOT EXISTS (SELECT 1 FROM api.get_report(:'a_sys','meta', now() - interval '1 day') WHERE campaign_external_id = 'camp_B_1'));
RESET ROLE;

-- ═══ T-RLS: دفاع بالعمق. لو حصل خطأ بالتطبيق وفُتح الجدول مباشرة، الـ RLS وحدها تمنع ═══
SET ROLE app_owner;     -- مالك الجداول (غير superuser، وبـ FORCE RLS)
SELECT t.ok('RLS-01 with no tenant set, owner sees zero campaigns', (SELECT count(*) FROM core.campaigns) = 0);
SET app.tenant_id = 'a0000000-0000-0000-0000-000000000001';
SELECT t.ok('RLS-02 with tenant A set, only A rows are visible',
  (SELECT count(*) FROM core.campaigns) = 2 AND (SELECT count(DISTINCT tenant_id) FROM core.campaigns) = 1);
SELECT t.raises('RLS-03 INSERT of a row for tenant B while tenant A is set is rejected (WITH CHECK)',
  $q$INSERT INTO core.campaigns (tenant_id, platform, ad_account_external_id, external_id, name, status) VALUES ('b0000000-0000-0000-0000-000000000001','meta','act_B1','hack','h','PAUSED')$q$, '42501');
UPDATE core.campaigns SET name = 'HACKED' WHERE tenant_id = 'b0000000-0000-0000-0000-000000000001';
SELECT t.ok('RLS-04 UPDATE of B rows affects nothing', (SELECT count(*) FROM core.campaigns WHERE name = 'HACKED') = 0);
DELETE FROM core.campaigns WHERE tenant_id = 'b0000000-0000-0000-0000-000000000001';
RESET app.tenant_id;
SET app.tenant_id = 'b0000000-0000-0000-0000-000000000001';
SELECT t.ok('RLS-05 DELETE of B rows by A-scope did nothing (B row still there)',
  (SELECT count(*) FROM core.campaigns WHERE external_id = 'camp_B_1') = 1);
SELECT t.ok('RLS-06 tenants/readiness/connections also scoped (B sees only B)',
  (SELECT count(*) FROM core.tenants) = 1 AND (SELECT count(*) FROM core.platform_connections) = 2
  AND (SELECT count(*) FROM core.readiness_checks WHERE tenant_id <> 'b0000000-0000-0000-0000-000000000001') = 0);
RESET app.tenant_id;
RESET ROLE;
SET ROLE app_resolver;
SELECT t.raises('RLS-07 resolver role cannot read campaigns', 'SELECT 1 FROM core.campaigns', '42501');
SELECT t.raises('RLS-08 resolver role cannot read platform_connections', 'SELECT 1 FROM core.platform_connections', '42501');
SELECT t.raises('RLS-09 resolver can only update tenants.status (not features)', $q$UPDATE core.tenants SET features = '{}'$q$, '42501');
RESET ROLE;
