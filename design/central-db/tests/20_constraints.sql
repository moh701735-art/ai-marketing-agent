-- 20_constraints.sql : علاقات ومفاتيح وقيود تمنع الربط بين عملاء مختلفين (تُنفَّذ بـ superuser، فالـ RLS لا تتدخل: هذه قيود البنية نفسها).
\set A '\'a0000000-0000-0000-0000-000000000001\''
\set B '\'b0000000-0000-0000-0000-000000000001\''

-- C-01: حساب إعلاني لـ A يشير لاتصال يخص B
SELECT t.raises('CON-01 ad_account(A) -> connection of B rejected',
  $q$INSERT INTO core.ad_accounts (tenant_id, platform, external_id, connection_id) VALUES ('a0000000-0000-0000-0000-000000000001','meta','act_X1','b1000000-0000-0000-0000-000000000001')$q$, '23503');
-- C-02: منصة الحساب لا تطابق منصة الاتصال (حساب tiktok على اتصال meta)
SELECT t.raises('CON-02 ad_account platform must match connection platform',
  $q$INSERT INTO core.ad_accounts (tenant_id, platform, external_id, connection_id) VALUES ('a0000000-0000-0000-0000-000000000001','tiktok','tt_X1','a1000000-0000-0000-0000-000000000001')$q$, '23503');
-- C-03: نفس الحساب الإعلاني عند عميلين بنفس الوقت
SELECT t.raises('CON-03 same ad account cannot be linked to two tenants',
  $q$INSERT INTO core.ad_accounts (tenant_id, platform, external_id, connection_id) VALUES ('b0000000-0000-0000-0000-000000000001','meta','act_A1','b1000000-0000-0000-0000-000000000001')$q$, '23505');
-- C-04: بعد فك الربط يجوز نقله لعميل آخر (ولا يبقى مربوطاً بالاثنين)
UPDATE core.ad_accounts SET unlinked_at = now() WHERE tenant_id = :A AND external_id = 'act_A1';
INSERT INTO core.ad_accounts (tenant_id, platform, external_id, connection_id) VALUES (:B,'meta','act_A1','b1000000-0000-0000-0000-000000000001');
SELECT t.ok('CON-04 unlinked account can move to another tenant; exactly one active link',
  (SELECT count(*) FROM core.ad_accounts WHERE external_id = 'act_A1' AND unlinked_at IS NULL) = 1);
-- أعد الوضع الأصلي
DELETE FROM core.ad_accounts WHERE tenant_id = :B AND external_id = 'act_A1';
UPDATE core.ad_accounts SET unlinked_at = NULL WHERE tenant_id = :A AND external_id = 'act_A1';
-- C-05: صفحة: اتصال tenant آخر، ومنصة tiktok، وتكرار الربط
SELECT t.raises('CON-05a page(A) -> connection of B rejected',
  $q$INSERT INTO core.pages (tenant_id, page_id, connection_id) VALUES ('a0000000-0000-0000-0000-000000000001','page_X','b1000000-0000-0000-0000-000000000001')$q$, '23503');
SELECT t.raises('CON-05b page cannot use a tiktok connection',
  $q$INSERT INTO core.pages (tenant_id, page_id, connection_id) VALUES ('a0000000-0000-0000-0000-000000000001','page_Y','a1000000-0000-0000-0000-000000000002')$q$, '23503');
SELECT t.raises('CON-05c same page cannot be linked to two tenants',
  $q$INSERT INTO core.pages (tenant_id, page_id, connection_id) VALUES ('b0000000-0000-0000-0000-000000000001','page_A1','b1000000-0000-0000-0000-000000000001')$q$, '23505');
-- C-06: حملة لـ A على حساب إعلاني يخص B
SELECT t.raises('CON-06 campaign(A) on ad account of B rejected',
  $q$INSERT INTO core.campaigns (tenant_id, platform, ad_account_external_id, external_id, name, status) VALUES ('a0000000-0000-0000-0000-000000000001','meta','act_B1','c1','x','PAUSED')$q$, '23503');
-- C-07: حدث حملة يشير لحملة عميل آخر
INSERT INTO core.campaigns (campaign_pk, tenant_id, platform, ad_account_external_id, external_id, name, status)
  VALUES ('ca000000-0000-0000-0000-000000000001', :A, 'meta', 'act_A1', 'camp_A_seed', 'seed', 'PAUSED');
SELECT t.raises('CON-07 campaign_event(B) -> campaign of A rejected',
  $q$INSERT INTO core.campaign_events (tenant_id, campaign_pk, action) VALUES ('b0000000-0000-0000-0000-000000000001','ca000000-0000-0000-0000-000000000001','x')$q$, '23503');
-- C-08: جدولة على حساب عميل آخر
SELECT t.raises('CON-08 schedule(A) on ad account of B rejected',
  $q$INSERT INTO core.schedules (tenant_id, platform, ad_account_external_id, campaign_external_id, action, repeat) VALUES ('a0000000-0000-0000-0000-000000000001','meta','act_B1','c','on','once')$q$, '23503');
-- C-09: active_config_version لنسخة إعدادات عميل آخر أو غير موجودة
SELECT t.raises('CON-09a active_config_version must exist for the same tenant',
  $q$UPDATE core.tenants SET active_config_version = 99 WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001'$q$, '23503');
INSERT INTO core.config_versions (tenant_id, version, config, author) VALUES (:B, 7, '{}', 'x');
SELECT t.raises('CON-09b active_config_version cannot point at another tenant''s config (A -> B v7)',
  $q$UPDATE core.tenants SET active_config_version = 7 WHERE tenant_id = 'a0000000-0000-0000-0000-000000000001'$q$, '23503');
-- C-10: بوتات: نفس بوت تيليجرام عند عميلين، وبوتين نشطين لنفس العميل
SELECT t.raises('CON-10a same telegram bot id cannot serve two tenants',
  $q$INSERT INTO core.bots (tenant_id, bot_public_id, telegram_bot_id, secret_ref, webhook_secret_hash, status) VALUES ('b0000000-0000-0000-0000-000000000001','botZZZZZZZZZZZZZZZZZZZZZZZZ',111,'ref-z',ext.digest('z','sha256'),'pending')$q$, '23505');
SELECT t.raises('CON-10b one active bot per tenant',
  $q$INSERT INTO core.bots (tenant_id, bot_public_id, telegram_bot_id, secret_ref, webhook_secret_hash, status) VALUES ('a0000000-0000-0000-0000-000000000001','botYYYYYYYYYYYYYYYYYYYYYYYY',999,'ref-y',ext.digest('y','sha256'),'active')$q$, '23505');
SELECT t.raises('CON-10c bot_public_id must be long enough (>=22)',
  $q$INSERT INTO core.bots (tenant_id, bot_public_id, telegram_bot_id, secret_ref, webhook_secret_hash, status) VALUES ('a0000000-0000-0000-0000-000000000001','short',998,'ref-s',ext.digest('s','sha256'),'pending')$q$, '23514');
-- C-11: updates المعالجة تخص بوتات نفس الـ tenant
SELECT t.raises('CON-11 processed_update(A) with bot of B rejected',
  $q$INSERT INTO core.processed_updates (tenant_id, bot_id, update_id) SELECT 'a0000000-0000-0000-0000-000000000001', bot_id, 1 FROM core.bots WHERE tenant_id = 'b0000000-0000-0000-0000-000000000001'$q$, '23503');
-- C-12: لا READY بدون نسخة إعدادات
-- (يُرفض بإحدى طبقتين: trigger الجاهزية أولاً ثم CHECK ready_needs_config؛ المهم أن READY بلا إعدادات مستحيل)
SELECT t.raises('CON-12 READY without active_config_version is impossible',
  $q$INSERT INTO core.tenants (slug, display_name, status, active_config_version) VALUES ('x-nocfg','X','READY',NULL)$q$);
-- C-13: ثوابت أخرى
SELECT t.raises('CON-13a knowledge global must be approved',
  $q$INSERT INTO core.knowledge_docs (scope, title, body) VALUES ('global','t','b')$q$, '23514');
SELECT t.raises('CON-13b knowledge tenant-scope needs tenant_id',
  $q$INSERT INTO core.knowledge_docs (scope, title, body) VALUES ('tenant','t','b')$q$, '23514');
SELECT t.raises('CON-13c solution cannot be verified without a passing test',
  $q$INSERT INTO core.solutions (fingerprint, cause, fix_steps, verified) VALUES ('fp1','c','f',true)$q$, '23514');
SELECT t.raises('CON-13d idempotency key must be long enough',
  $q$INSERT INTO core.campaign_requests (tenant_id, idempotency_key, request_hash, status) VALUES ('a0000000-0000-0000-0000-000000000001','k','\x00','received')$q$, '23514');
SELECT t.raises('CON-13e negative budget rejected',
  $q$INSERT INTO core.campaigns (tenant_id, platform, ad_account_external_id, external_id, name, status, daily_budget_minor) VALUES ('a0000000-0000-0000-0000-000000000001','meta','act_A1','neg','n','PAUSED',-1)$q$, '23514');
-- cleanup مؤقتات هذا الملف
DELETE FROM core.config_versions WHERE tenant_id = :B AND version = 7;
