-- يرجّع كل شي لما قبل 81 (بيانات بوابة الويب تنحذف). الدور web_rt يبقى NOLOGIN بدون صلاحيات.
\set ON_ERROR_STOP on
DO $$ BEGIN EXECUTE format('REVOKE CONNECT ON DATABASE %I FROM web_rt', current_database()); END $$;
DROP SCHEMA IF EXISTS web CASCADE;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'web_rt') THEN ALTER ROLE web_rt NOLOGIN; END IF; END $$;
