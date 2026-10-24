-- 50_vault.sql : قاعدة الـ Broker المنفصلة (لا تُنفَّذ بقاعدة التطبيق). تخزن الأسرار مشفّرة (AES-256-GCM يتم بالـ Broker)،
-- بقاعدة مستقلة وحساب مستقل لا يملكه n8n ولا app_runtime.
\set ON_ERROR_STOP on
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'broker_rw') THEN
    CREATE ROLE broker_rw NOLOGIN NOSUPERUSER NOBYPASSRLS;
  END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS vault AUTHORIZATION broker_rw;
SET ROLE broker_rw;
CREATE TABLE vault.secrets (
  secret_ref  text PRIMARY KEY,                -- المؤشر الذي تحتفظ به القاعدة المركزية
  tenant_id   uuid NOT NULL,
  kind        text NOT NULL CHECK (kind IN ('telegram_bot_token','meta_user_token','meta_system_token','tiktok_token','backup_code')),
  version     int  NOT NULL CHECK (version > 0),
  ciphertext  bytea NOT NULL,                  -- nonce(12) || AES-GCM(ciphertext||tag). AAD = tenant_id|kind|version|secret_ref
  dek_wrapped bytea NOT NULL,                  -- DEK مغلّف بـ KEK (بيئة الـ Broker فقط)
  created_at  timestamptz NOT NULL DEFAULT now(),
  rotated_at  timestamptz,
  revoked_at  timestamptz,
  UNIQUE (tenant_id, kind, version)
);
CREATE INDEX ON vault.secrets (tenant_id, kind, version DESC);
-- سجل المكالمات بدون أسرار، مقسّم شهرياً بنفس أسلوب 40_partitions.sql
CREATE TABLE vault.api_call_log (
  call_id bigint GENERATED ALWAYS AS IDENTITY, at timestamptz NOT NULL DEFAULT now(),
  tenant_id uuid NOT NULL, platform text NOT NULL, endpoint text NOT NULL,
  http_status int, duration_ms int, error_code text, idempotency_key text,
  PRIMARY KEY (call_id, at)
) PARTITION BY RANGE (at);
RESET ROLE;
