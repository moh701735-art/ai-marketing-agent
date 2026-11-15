-- 97_snapchat.sql : منصة snapchat (74_snapchat.sql). يطبّق الملف بنفسه ثم يتحقق.
\i 74_snapchat.sql
SELECT t.ok('SNAP-01 core.platform has snapchat', EXISTS (SELECT 1 FROM pg_enum e JOIN pg_type y ON y.oid = e.enumtypid WHERE y.typname = 'platform' AND e.enumlabel = 'snapchat'));
SELECT t.ok('SNAP-02 platform checks accept snapchat on connections and ad_accounts',
  (SELECT bool_and(pg_get_constraintdef(oid) LIKE '%snapchat%') FROM pg_constraint WHERE conname IN ('platform_connections_platform_check','ad_accounts_platform_check')));
\i 74_snapchat.sql
SELECT t.ok('SNAP-03 idempotent re-run keeps one constraint each',
  (SELECT count(*) FROM pg_constraint WHERE conname IN ('platform_connections_platform_check','ad_accounts_platform_check')) = 2);
