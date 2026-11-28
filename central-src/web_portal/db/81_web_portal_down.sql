-- يرجّع كل شي لما قبل 81 (بيانات بوابة الويب تنحذف). الدور web_rt يبقى NOLOGIN بدون صلاحيات.
\set ON_ERROR_STOP on
REVOKE EXECUTE ON FUNCTION api.list_ad_accounts(text), api.list_campaigns(text, text), api.list_pages(text) FROM web_rt;
REVOKE USAGE ON SCHEMA api FROM web_rt;
DROP SCHEMA IF EXISTS web CASCADE;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'web_rt') THEN ALTER ROLE web_rt NOLOGIN; END IF; END $$;
