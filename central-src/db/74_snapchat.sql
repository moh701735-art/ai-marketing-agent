-- 74_snapchat.sql : إضافة منصة snapchat (قراءة فقط بالمرحلة الأولى). ترقية آمنة (idempotent) ولا تمس بيانات موجودة.
-- 1) نوع المنصة  2) قيود CHECK على platform_connections و ad_accounts (بمقارنة نصية حتى لا نستعمل قيمة enum جديدة بنفس المعاملة)
-- 3) أي دالة بـapi/core/private فيها قائمة المنصات ('meta','tiktok','telegram') تُعاد كتابتها بإضافة 'snapchat' (broker_authorize وغيرها).
\set ON_ERROR_STOP on
SET ROLE app_owner;

ALTER TYPE core.platform ADD VALUE IF NOT EXISTS 'snapchat';

ALTER TABLE core.platform_connections DROP CONSTRAINT IF EXISTS platform_connections_platform_check;
ALTER TABLE core.platform_connections ADD CONSTRAINT platform_connections_platform_check CHECK (platform::text IN ('meta','tiktok','snapchat'));
ALTER TABLE core.ad_accounts DROP CONSTRAINT IF EXISTS ad_accounts_platform_check;
ALTER TABLE core.ad_accounts ADD CONSTRAINT ad_accounts_platform_check CHECK (platform::text IN ('meta','tiktok','snapchat'));

DO $mig$
DECLARE r record; def text; pat constant text := '''meta''\s*,\s*''tiktok''\s*,\s*''telegram''';
BEGIN
  FOR r IN SELECT p.oid, n.nspname, p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
           WHERE n.nspname IN ('api','core','private') AND p.prokind = 'f' AND p.prosrc ~ pat LOOP
    def := pg_get_functiondef(r.oid);
    IF def ~ pat AND def !~ 'snapchat' THEN
      EXECUTE regexp_replace(def, pat, '''meta'',''tiktok'',''telegram'',''snapchat''', 'g');
      RAISE NOTICE 'snapchat added to %.%', r.nspname, r.proname;
    END IF;
  END LOOP;
END $mig$;

RESET ROLE;

-- 4) الخزنة: نوع سر جديد snap_oauth (JSON فيه access/refresh/exp/client) يُضاف لقيد kind على vault.secrets إن وُجد بنفس القاعدة.
DO $v$
DECLARE c record; nd text;
BEGIN
  IF to_regclass('vault.secrets') IS NULL THEN RETURN; END IF;
  FOR c IN SELECT conname, pg_get_constraintdef(oid) AS d FROM pg_constraint
           WHERE conrelid = 'vault.secrets'::regclass AND contype = 'c'
             AND pg_get_constraintdef(oid) LIKE '%meta_user_token%' AND pg_get_constraintdef(oid) NOT LIKE '%snap_oauth%' LOOP
    nd := regexp_replace(c.d, 'ARRAY\[', 'ARRAY[''snap_oauth''::text, ');
    EXECUTE format('ALTER TABLE vault.secrets DROP CONSTRAINT %I', c.conname);
    EXECUTE format('ALTER TABLE vault.secrets ADD CONSTRAINT %I %s', c.conname, nd);
    RAISE NOTICE 'snap_oauth kind added on vault.secrets (%)', c.conname;
  END LOOP;
EXCEPTION WHEN insufficient_privilege THEN
  RAISE WARNING 'snap_oauth kind NOT added on vault.secrets (run this file as the vault owner/superuser)';
END $v$;

