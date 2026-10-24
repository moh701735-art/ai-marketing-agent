-- 10_setup.sql : بيانات اختبار (تُنفَّذ بـ superuser). tenants: A,B جاهزان. C غير جاهز. D بلا tiktok.
\set A '\'a0000000-0000-0000-0000-000000000001\''
\set B '\'b0000000-0000-0000-0000-000000000001\''
\set C '\'c0000000-0000-0000-0000-000000000001\''
\set D '\'d0000000-0000-0000-0000-000000000001\''

INSERT INTO core.tenants (tenant_id, slug, display_name, status, features) VALUES
 (:A,'tenant-a','A','CONFIGURATION_REQUIRED','{"meta":true,"tiktok":true,"schedule":true}'),
 (:B,'tenant-b','B','CONFIGURATION_REQUIRED','{"meta":true,"tiktok":true,"schedule":true}'),
 (:C,'tenant-c','C','CONFIGURATION_REQUIRED','{"meta":true,"tiktok":true,"schedule":true}'),
 (:D,'tenant-d','D','CONFIGURATION_REQUIRED','{"meta":true,"schedule":true}');
INSERT INTO core.config_versions (tenant_id, version, config, author)
  SELECT tenant_id, 1, '{"lang":"ar"}', 'test' FROM core.tenants;
UPDATE core.tenants SET active_config_version = 1;

INSERT INTO core.bots (tenant_id, bot_public_id, telegram_bot_id, secret_ref, webhook_secret_hash, status) VALUES
 (:A,'botAAAAAAAAAAAAAAAAAAAAAAAA', 111, 'ref-bot-a', ext.digest('secret-a','sha256'), 'active'),
 (:B,'botBBBBBBBBBBBBBBBBBBBBBBBB', 222, 'ref-bot-b', ext.digest('secret-b','sha256'), 'active'),
 (:C,'botCCCCCCCCCCCCCCCCCCCCCCCC', 333, 'ref-bot-c', ext.digest('secret-c','sha256'), 'active'),
 (:D,'botDDDDDDDDDDDDDDDDDDDDDDDD', 444, 'ref-bot-d', ext.digest('secret-d','sha256'), 'active');

INSERT INTO core.tenant_users (tenant_id, telegram_user_id, role, max_daily_budget_usd) VALUES
 (:A,1001,'owner',NULL),(:A,1002,'viewer',NULL),(:A,1003,'manager',50),
 (:B,2001,'owner',NULL),(:B,2002,'manager',NULL),
 (:C,3001,'owner',NULL),(:D,4001,'owner',NULL);

INSERT INTO core.platform_connections (connection_id, tenant_id, platform, auth_mode, external_user_id, secret_ref) VALUES
 ('a1000000-0000-0000-0000-000000000001',:A,'meta','oauth_user','fbA','ref-a-meta'),
 ('a1000000-0000-0000-0000-000000000002',:A,'tiktok','tiktok_oauth','ttA','ref-a-tt'),
 ('b1000000-0000-0000-0000-000000000001',:B,'meta','oauth_user','fbB','ref-b-meta'),
 ('b1000000-0000-0000-0000-000000000002',:B,'tiktok','tiktok_oauth','ttB','ref-b-tt'),
 ('d1000000-0000-0000-0000-000000000001',:D,'meta','oauth_user','fbD','ref-d-meta');

INSERT INTO core.ad_accounts (tenant_id, platform, external_id, connection_id, name) VALUES
 (:A,'meta','act_A1','a1000000-0000-0000-0000-000000000001','A meta'),
 (:A,'tiktok','tt_A1','a1000000-0000-0000-0000-000000000002','A tiktok'),
 (:B,'meta','act_B1','b1000000-0000-0000-0000-000000000001','B meta'),
 (:B,'tiktok','tt_B1','b1000000-0000-0000-0000-000000000002','B tiktok'),
 (:D,'meta','act_D1','d1000000-0000-0000-0000-000000000001','D meta');
INSERT INTO core.pages (tenant_id, page_id, connection_id) VALUES
 (:A,'page_A1','a1000000-0000-0000-0000-000000000001'),
 (:B,'page_B1','b1000000-0000-0000-0000-000000000001');

-- فحوصات الجاهزية الإلزامية لـ A,B (الكل) و D (بدون tiktok: R05)
INSERT INTO core.readiness_checks (tenant_id, check_code, status, evidence, checked_at, expires_at)
SELECT t.tenant_id, d.check_code, 'pass', '{}', now(), now() + d.max_age
FROM core.tenants t, core.readiness_check_defs d
WHERE t.tenant_id IN (:A,:B,:D) AND NOT (t.tenant_id = :D AND d.check_code = 'R05');
UPDATE core.tenants SET status = 'READY' WHERE tenant_id IN (:A,:B,:D);

SELECT t.ok('SETUP: A,B,D are READY; C is not',
  (SELECT count(*) FROM core.tenants WHERE status='READY') = 3
  AND (SELECT status FROM core.tenants WHERE tenant_id = 'c0000000-0000-0000-0000-000000000001') = 'CONFIGURATION_REQUIRED');
