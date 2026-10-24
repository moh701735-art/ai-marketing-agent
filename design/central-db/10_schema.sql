-- 10_schema.sql : مخطط القاعدة المركزية (v2). PostgreSQL 15+ (اختُبر على 16).
-- يُنفَّذ بحساب superuser أو بمالك قاعدة البيانات. كل الكائنات تُملَّك لـ app_owner.
-- لا أسرار هنا: الأسرار بقاعدة الـ Broker المنفصلة (50_vault.sql).
\set ON_ERROR_STOP on

CREATE SCHEMA IF NOT EXISTS ext;
CREATE EXTENSION IF NOT EXISTS pgcrypto SCHEMA ext;
CREATE EXTENSION IF NOT EXISTS citext SCHEMA ext;
GRANT USAGE ON SCHEMA ext TO app_owner, app_resolver, app_ops_fn;   -- ملاحظة: app_runtime لا يصل لـ ext

CREATE SCHEMA IF NOT EXISTS core    AUTHORIZATION app_owner;   -- الجداول
CREATE SCHEMA IF NOT EXISTS private AUTHORIZATION app_owner;   -- مساعدات داخلية (لا يصل إليها app_runtime)
CREATE SCHEMA IF NOT EXISTS api     AUTHORIZATION app_owner;   -- الدوال المكشوفة لـ n8n
CREATE SCHEMA IF NOT EXISTS api_admin AUTHORIZATION app_owner; -- دوال الإدارة (app_ops فقط)

REVOKE ALL ON SCHEMA public FROM PUBLIC;

SET ROLE app_owner;
SET search_path = core, private, ext, public;

-- ───────────── أنواع ─────────────
CREATE TYPE core.tenant_status AS ENUM
  ('INITIALIZING','CONFIGURATION_REQUIRED','CONNECTING','TESTING','READY','NEEDS_REVIEW','FAILED','SUSPENDED');
CREATE TYPE core.user_role  AS ENUM ('owner','manager','viewer');
CREATE TYPE core.platform   AS ENUM ('meta','tiktok','telegram');
CREATE TYPE core.check_status AS ENUM ('pass','fail','warn','unknown');
CREATE TYPE core.err_class AS ENUM
  ('TRANSIENT','AUTH_EXPIRED','AUTH_REVOKED','PERMISSION','RATE_LIMIT','VALIDATION','POLICY_REJECTED',
   'PLATFORM_REJECTED','BILLING','CONFIG','BUG','UNKNOWN');

-- ───────────── 1) tenants ─────────────
-- tenant_id يُستعمل كمفتاح أجنبي بالجداول الأخرى. active_config_version يُربط لاحقاً (FK مؤجَّل) لأن config_versions تحتاج tenants أولاً.
CREATE TABLE core.tenants (
  tenant_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug          ext.citext NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,48}$'),
  display_name  text   NOT NULL,
  status        core.tenant_status NOT NULL DEFAULT 'INITIALIZING',
  timezone      text   NOT NULL DEFAULT 'Asia/Baghdad',
  currency      char(3) NOT NULL DEFAULT 'USD',
  legacy_workflow_id text,
  features      jsonb  NOT NULL DEFAULT '{}'::jsonb,           -- {meta:true,tiktok:true,schedule:true,...}
  active_config_version int,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  -- لا READY بدون نسخة إعدادات معتمدة (يُكمّله trigger الجاهزية بالأسفل)
  CONSTRAINT ready_needs_config CHECK (status <> 'READY' OR active_config_version IS NOT NULL)
);

-- ───────────── 2) config_versions ─────────────
CREATE TABLE core.config_versions (
  tenant_id uuid NOT NULL REFERENCES core.tenants ON DELETE CASCADE,
  version   int  NOT NULL CHECK (version > 0),
  config    jsonb NOT NULL,
  author    text NOT NULL,
  reason    text,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, version)
);
-- ربط active_config_version: مفتاح أجنبي مركّب (نفس الـ tenant). ينشأ tenant بدون نسخة، ثم تُدرج النسخة 1، ثم يُحدَّث الحقل.
ALTER TABLE core.tenants
  ADD CONSTRAINT tenants_active_config_fk
  FOREIGN KEY (tenant_id, active_config_version)
  REFERENCES core.config_versions (tenant_id, version)
  DEFERRABLE INITIALLY IMMEDIATE;   -- فوري (يُفحص عند كل تعديل). التأجيل متاح بـ SET CONSTRAINTS عند الإنشاء بمعاملة واحدة.

-- ───────────── 3) bots ─────────────
CREATE TABLE core.bots (
  bot_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL REFERENCES core.tenants ON DELETE RESTRICT,
  bot_public_id   text NOT NULL UNIQUE CHECK (length(bot_public_id) >= 22),
  telegram_bot_id bigint NOT NULL,
  username        text,
  secret_ref      text NOT NULL UNIQUE,                  -- مؤشر معتم لسر بقاعدة الـ Broker (لا يُفك هنا)
  webhook_secret_hash bytea NOT NULL CHECK (octet_length(webhook_secret_hash) = 32),
  status          text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','active','revoked')),
  webhook_set_at  timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, bot_id)
);
-- نفس بوت تيليجرام لا يُربط بعميلين (إلا إذا كان revoked)
CREATE UNIQUE INDEX bots_telegram_active_uq ON core.bots (telegram_bot_id) WHERE status <> 'revoked';
CREATE UNIQUE INDEX bots_one_active_per_tenant ON core.bots (tenant_id) WHERE status = 'active';

-- ───────────── 4) tenant_users ─────────────
CREATE TABLE core.tenant_users (
  tenant_id        uuid NOT NULL REFERENCES core.tenants ON DELETE CASCADE,
  telegram_user_id bigint NOT NULL,
  role             core.user_role NOT NULL DEFAULT 'viewer',
  display_name     text,
  active           boolean NOT NULL DEFAULT true,
  max_daily_budget_usd numeric(12,2) CHECK (max_daily_budget_usd IS NULL OR max_daily_budget_usd >= 0),
  created_at       timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, telegram_user_id)
);

-- ───────────── 5) platform_connections ─────────────
CREATE TABLE core.platform_connections (
  connection_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL REFERENCES core.tenants ON DELETE CASCADE,
  platform      core.platform NOT NULL CHECK (platform IN ('meta','tiktok')),
  auth_mode     text NOT NULL CHECK (auth_mode IN ('oauth_user','system_user','tiktok_oauth')),
  external_user_id text NOT NULL,
  secret_ref    text NOT NULL UNIQUE,
  scopes_granted  text[] NOT NULL DEFAULT '{}',
  scopes_required text[] NOT NULL DEFAULT '{}',
  expires_at    timestamptz,
  status        text NOT NULL DEFAULT 'active' CHECK (status IN ('active','expired','revoked','error')),
  last_verified_at timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, platform, external_user_id),
  -- هدف المفاتيح الأجنبية المركّبة (يمنع ربط حساب/صفحة باتصال عميل آخر أو منصة أخرى)
  UNIQUE (tenant_id, platform, connection_id)
);
CREATE INDEX ON core.platform_connections (tenant_id, platform, status);

-- ───────────── 6) ad_accounts / pages ─────────────
CREATE TABLE core.ad_accounts (
  tenant_id     uuid NOT NULL,
  platform      core.platform NOT NULL CHECK (platform IN ('meta','tiktok')),
  external_id   text NOT NULL CHECK (length(external_id) > 0),
  connection_id uuid NOT NULL,
  name          text,
  currency      char(3),
  timezone      text,
  status        text,
  balance_minor numeric(18,2),
  enabled       boolean NOT NULL DEFAULT true,
  verified_at   timestamptz,
  linked_at     timestamptz NOT NULL DEFAULT now(),
  unlinked_at   timestamptz,                         -- فك الربط يسمح بنقل الحساب لاحقاً
  PRIMARY KEY (tenant_id, platform, external_id),
  -- نفس الـ tenant ونفس المنصة للاتصال:
  FOREIGN KEY (tenant_id, platform, connection_id)
    REFERENCES core.platform_connections (tenant_id, platform, connection_id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id) REFERENCES core.tenants ON DELETE CASCADE
);
-- الحساب الإعلاني لا يكون "مربوطاً" بأكثر من عميل بنفس الوقت:
CREATE UNIQUE INDEX ad_accounts_linked_uq ON core.ad_accounts (platform, external_id) WHERE unlinked_at IS NULL;

CREATE TABLE core.pages (
  tenant_id uuid NOT NULL,
  platform  core.platform NOT NULL DEFAULT 'meta' CHECK (platform = 'meta'),
  page_id   text NOT NULL,
  name      text,
  connection_id uuid NOT NULL,
  ig_business_id text,
  verified_at timestamptz,
  linked_at timestamptz NOT NULL DEFAULT now(),
  unlinked_at timestamptz,
  PRIMARY KEY (tenant_id, page_id),
  FOREIGN KEY (tenant_id, platform, connection_id)
    REFERENCES core.platform_connections (tenant_id, platform, connection_id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id) REFERENCES core.tenants ON DELETE CASCADE
);
CREATE UNIQUE INDEX pages_linked_uq ON core.pages (page_id) WHERE unlinked_at IS NULL;

-- ───────────── 7) campaigns & events ─────────────
CREATE TABLE core.campaigns (
  campaign_pk   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  platform      core.platform NOT NULL CHECK (platform IN ('meta','tiktok')),
  ad_account_external_id text NOT NULL,
  external_id   text NOT NULL,
  name          text NOT NULL,
  objective     text,
  daily_budget_minor numeric(18,2) CHECK (daily_budget_minor IS NULL OR daily_budget_minor >= 0),
  status        text NOT NULL,
  created_by    bigint,
  created_at    timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, platform, ad_account_external_id)
    REFERENCES core.ad_accounts (tenant_id, platform, external_id) ON DELETE RESTRICT,
  UNIQUE (tenant_id, platform, external_id),
  UNIQUE (tenant_id, campaign_pk)
);
CREATE INDEX ON core.campaigns (tenant_id, platform, status);
CREATE INDEX ON core.campaigns (tenant_id, lower(name));

CREATE TABLE core.campaign_events (
  event_id   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id  uuid NOT NULL,
  campaign_pk uuid NOT NULL,
  actor_telegram_user_id bigint,
  action     text NOT NULL,
  detail     jsonb NOT NULL DEFAULT '{}'::jsonb,
  at         timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, campaign_pk) REFERENCES core.campaigns (tenant_id, campaign_pk) ON DELETE CASCADE
);
CREATE INDEX ON core.campaign_events (tenant_id, at DESC);

CREATE TABLE core.campaign_requests (
  request_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       uuid NOT NULL REFERENCES core.tenants ON DELETE CASCADE,
  idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 16 AND 128),
  request_hash    bytea NOT NULL,
  status          text NOT NULL CHECK (status IN ('received','executing','succeeded','failed','needs_manual_check')),
  result_ref      text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, idempotency_key)
);

CREATE TABLE core.processed_updates (
  tenant_id   uuid NOT NULL REFERENCES core.tenants ON DELETE CASCADE,
  bot_id      uuid NOT NULL,
  update_id   bigint NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (bot_id, update_id),
  FOREIGN KEY (tenant_id, bot_id) REFERENCES core.bots (tenant_id, bot_id) ON DELETE CASCADE
);
CREATE INDEX ON core.processed_updates (received_at);

-- ───────────── 8) تقارير وأخطاء: أقسام شهرية (RANGE) ─────────────
CREATE TABLE core.report_snapshots (
  tenant_id uuid NOT NULL REFERENCES core.tenants ON DELETE CASCADE,
  platform  core.platform NOT NULL CHECK (platform IN ('meta','tiktok')),
  campaign_external_id text NOT NULL,
  taken_at  timestamptz NOT NULL,
  spend numeric(18,4), impressions bigint, clicks bigint, reach bigint,
  messages int, cost_per_message numeric(18,4), currency char(3),
  PRIMARY KEY (tenant_id, platform, campaign_external_id, taken_at)
) PARTITION BY RANGE (taken_at);

CREATE TABLE core.error_log (
  error_id    bigint GENERATED ALWAYS AS IDENTITY,
  tenant_id   uuid REFERENCES core.tenants,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  class       core.err_class NOT NULL,
  platform    core.platform,
  workflow    text, node text, execution_id text, code text,
  message     text,
  fingerprint text NOT NULL,
  repair_hint_id bigint,
  notified    boolean NOT NULL DEFAULT false,
  resolved_at timestamptz,
  PRIMARY KEY (error_id, occurred_at)
) PARTITION BY RANGE (occurred_at);
CREATE INDEX ON core.error_log (tenant_id, occurred_at DESC);
CREATE INDEX ON core.error_log (fingerprint, occurred_at DESC);

-- ───────────── 9) الجاهزية ─────────────
CREATE TABLE core.readiness_check_defs (
  check_code  text PRIMARY KEY,
  title       text NOT NULL,
  mandatory   boolean NOT NULL DEFAULT true,
  applies_when text NOT NULL DEFAULT 'always',      -- 'always' أو اسم ميزة بـ tenants.features (meta/tiktok)
  max_age     interval NOT NULL
);

CREATE TABLE core.readiness_checks (
  tenant_id  uuid NOT NULL REFERENCES core.tenants ON DELETE CASCADE,
  check_code text NOT NULL REFERENCES core.readiness_check_defs,
  status     core.check_status NOT NULL,
  evidence   jsonb NOT NULL DEFAULT '{}'::jsonb,
  checked_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  PRIMARY KEY (tenant_id, check_code),
  CHECK (expires_at > checked_at)
);

-- ───────────── 10) معرفة وحلول ─────────────
CREATE TABLE core.knowledge_docs (
  doc_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  scope     text NOT NULL CHECK (scope IN ('global','tenant')),
  tenant_id uuid REFERENCES core.tenants ON DELETE CASCADE,
  title text NOT NULL, body text NOT NULL, source text,
  version int NOT NULL DEFAULT 1,
  approved_by text, approved_at timestamptz,
  CHECK ((scope = 'global' AND tenant_id IS NULL AND approved_by IS NOT NULL AND approved_at IS NOT NULL)
      OR (scope = 'tenant' AND tenant_id IS NOT NULL))
);

CREATE TABLE core.solutions (
  solution_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  fingerprint text NOT NULL UNIQUE,
  platform core.platform, code text,
  cause text NOT NULL, fix_steps text NOT NULL,
  verified boolean NOT NULL DEFAULT false,
  verified_by_test text, verified_at timestamptz,
  CHECK (NOT verified OR (verified_by_test IS NOT NULL AND verified_at IS NOT NULL))
);

-- ───────────── 11) جداول التشغيل (من ترحيل Data Tables) ─────────────
CREATE TABLE core.pending_drafts (
  tenant_id uuid NOT NULL REFERENCES core.tenants ON DELETE CASCADE,
  telegram_user_id bigint NOT NULL,
  draft jsonb NOT NULL, expires_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, telegram_user_id)
);
CREATE TABLE core.chat_mutes (
  tenant_id uuid NOT NULL REFERENCES core.tenants ON DELETE CASCADE,
  telegram_user_id bigint NOT NULL, muted_until timestamptz NOT NULL,
  PRIMARY KEY (tenant_id, telegram_user_id)
);
CREATE TABLE core.schedules (
  schedule_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES core.tenants ON DELETE CASCADE,
  platform core.platform NOT NULL CHECK (platform IN ('meta','tiktok')),
  ad_account_external_id text NOT NULL, campaign_external_id text NOT NULL,
  action text NOT NULL CHECK (action IN ('on','off')),
  at_local time, repeat text NOT NULL CHECK (repeat IN ('once','daily')),
  next_run_at timestamptz, last_run_at timestamptz, last_result text,
  enabled boolean NOT NULL DEFAULT true,
  FOREIGN KEY (tenant_id, platform, ad_account_external_id)
    REFERENCES core.ad_accounts (tenant_id, platform, external_id) ON DELETE CASCADE
);
CREATE INDEX ON core.schedules (next_run_at) WHERE enabled;
CREATE TABLE core.cost_caps (
  tenant_id uuid NOT NULL REFERENCES core.tenants ON DELETE CASCADE,
  campaign_external_id text NOT NULL, cap_usd numeric(12,4) NOT NULL CHECK (cap_usd > 0),
  auto_stop boolean NOT NULL DEFAULT false, rotation jsonb,
  warned_at timestamptz, stopped_at timestamptz,
  PRIMARY KEY (tenant_id, campaign_external_id)
);
CREATE TABLE core.appeals (
  tenant_id uuid NOT NULL REFERENCES core.tenants ON DELETE CASCADE,
  ad_external_id text NOT NULL, attempts int NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  fails int NOT NULL DEFAULT 0, last_appeal_at timestamptz, last_result text,
  PRIMARY KEY (tenant_id, ad_external_id)
);
CREATE TABLE core.review_monitor (
  tenant_id uuid NOT NULL REFERENCES core.tenants ON DELETE CASCADE,
  campaign_external_id text NOT NULL, last_known_status text,
  backup_codes_ref text,                       -- مؤشر للـ Broker، ليس الأكواد نفسها
  active boolean NOT NULL DEFAULT true,
  PRIMARY KEY (tenant_id, campaign_external_id)
);
CREATE TABLE core.audience_tests (
  test_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES core.tenants ON DELETE CASCADE,
  campaign_external_id text NOT NULL, adgroup_external_id text, audience_label text,
  status text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), detail jsonb
);

-- ───────────── 12) سجل المراجعة ─────────────
CREATE TABLE core.audit_log (
  audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  at timestamptz NOT NULL DEFAULT now(),
  actor text NOT NULL,
  tenant_id uuid REFERENCES core.tenants ON DELETE SET NULL,
  action text NOT NULL, detail jsonb NOT NULL DEFAULT '{}'::jsonb
);

-- ───────────── ثوابت الجاهزية (R01..R15) ─────────────
INSERT INTO core.readiness_check_defs (check_code, title, mandatory, applies_when, max_age) VALUES
 ('R01','tenant record valid',            true,'always','7 days'),
 ('R02','telegram bot token valid',        true,'always','24 hours'),
 ('R03','webhook set and healthy',         true,'always','1 hour'),
 ('R04','owner user + round trip',         true,'always','7 days'),
 ('R05','tiktok connection valid',         true,'tiktok','24 hours'),
 ('R06','meta connection valid',           true,'meta','24 hours'),
 ('R07','meta scopes granted',             true,'meta','24 hours'),
 ('R08','ad account readable',             true,'always','24 hours'),
 ('R09','page / instagram access',         true,'meta','24 hours'),
 ('R10','isolation tests pass',            true,'always','7 days'),
 ('R11','safe create (dry-run) passes',    true,'always','7 days'),
 ('R12','read + reports pass',             true,'always','24 hours'),
 ('R13','error handling tests pass',       true,'always','7 days'),
 ('R14','no secrets in logs / n8n',        true,'always','24 hours'),
 ('R15','config version approved + rollback exists', true,'always','7 days');

RESET ROLE;
