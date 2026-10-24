-- 60_partitions.sql : أقسام التقارير والأخطاء الشهرية (T-PART).
\set A '\'a0000000-0000-0000-0000-000000000001\''
SET ROLE app_ops;
SELECT t.ok('PART-01 ensure_partitions is idempotent (nothing new on second call)', api_admin.ensure_partitions(3, 1) = 0);
SELECT t.ok('PART-02 partition_health: current+next partitions exist and default partitions are empty',
  (SELECT bool_and(ok) FROM api_admin.partition_health()) AND (SELECT count(*) FROM api_admin.partition_health()) = 6);
RESET ROLE;

SELECT t.ok('PART-03 current-month snapshot lands in the current month partition (not default)',
  (SELECT tableoid::regclass::text FROM core.report_snapshots WHERE campaign_external_id = 'camp_A_1' LIMIT 1)
  = 'core.report_snapshots_p' || to_char(now() AT TIME ZONE 'UTC', 'YYYYMM'));

-- صف لشهر بعيد لم يُنشأ له قسم => يذهب للافتراضي (لا يفشل INSERT) والصحة تُنبّه
INSERT INTO core.report_snapshots (tenant_id, platform, campaign_external_id, taken_at, spend)
VALUES (:A, 'meta', 'camp_A_1', date_trunc('month', now()) + interval '7 months 2 days', 5);
SET ROLE app_ops;
SELECT t.ok('PART-04 row beyond the created range goes to DEFAULT and partition_health flags it',
  EXISTS (SELECT 1 FROM api_admin.partition_health() WHERE check_name = 'report_snapshots:default_empty' AND NOT ok));
-- ensure يغطي الشهر ويُرحّل الصف من الافتراضي (بدون فشل ATTACH)
SELECT t.ok('PART-05 ensure_partitions creates the missing month and relocates rows out of DEFAULT',
  api_admin.ensure_partitions(8, 1) >= 2);
RESET ROLE;
SELECT t.ok('PART-06 relocated row is now in its monthly partition and DEFAULT is empty again',
  (SELECT tableoid::regclass::text FROM core.report_snapshots WHERE spend = 5)
    = 'core.report_snapshots_p' || to_char(date_trunc('month', now() AT TIME ZONE 'UTC') + interval '7 months', 'YYYYMM')
  AND (SELECT count(*) FROM core.report_snapshots_default) = 0);

-- حذف الأقسام القديمة (احتفاظ)
SET ROLE app_ops;
SELECT api_admin.ensure_partitions(0, 14);   -- أنشئ أقساماً قديمة (حتى 14 شهراً للخلف) لاختبار الحذف
RESET ROLE;
INSERT INTO core.report_snapshots (tenant_id, platform, campaign_external_id, taken_at, spend)
VALUES (:A, 'meta', 'camp_old', date_trunc('month', now()) - interval '13 months' + interval '3 days', 1);
SET ROLE app_ops;
SELECT t.ok('PART-07 drop_old_partitions(6 months) drops old partitions only',
  api_admin.drop_old_partitions('report_snapshots', 6) >= 7);
RESET ROLE;
SELECT t.ok('PART-08 old row is gone, current data is intact',
  (SELECT count(*) FROM core.report_snapshots WHERE campaign_external_id = 'camp_old') = 0
  AND (SELECT count(*) FROM core.report_snapshots WHERE campaign_external_id = 'camp_A_1') >= 1);
SET ROLE app_ops;
SELECT t.raises('PART-09 retention below 1 month is refused', $q$SELECT api_admin.drop_old_partitions('report_snapshots', 0)$q$, NULL, 'keep_at_least_1_month');
SELECT t.raises('PART-10 only known partitioned tables can be dropped from', $q$SELECT api_admin.drop_old_partitions('tenants', 6)$q$, NULL, 'not_partitioned_table');
RESET ROLE;

-- عزل الـ tenant عبر الأقسام: بيانات A وB بأشهر مختلفة، والاستعلام بدور مقيّد لا يجمعها
INSERT INTO core.report_snapshots (tenant_id, platform, campaign_external_id, taken_at, spend)
VALUES ('b0000000-0000-0000-0000-000000000001','meta','camp_B_1', date_trunc('month', now()) + interval '1 month 1 day', 77);
SET ROLE app_owner; SET app.tenant_id = 'a0000000-0000-0000-0000-000000000001';
SELECT t.ok('PART-11 RLS holds across partitions: tenant A never sees B snapshots in any month',
  (SELECT count(*) FROM core.report_snapshots WHERE spend = 77) = 0);
RESET app.tenant_id; RESET ROLE;
-- error_log كذلك
SELECT t.ok('PART-12 error_log rows are in monthly partitions', 
  (SELECT bool_and(tableoid::regclass::text LIKE 'core.error_log_p%') FROM core.error_log));
