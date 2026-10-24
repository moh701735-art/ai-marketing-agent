-- 40_partitions.sql : إنشاء وإدارة أقسام التقارير والأخطاء الشهرية.
-- الجداول المقسّمة (RANGE بالشهر): core.report_snapshots(taken_at) و core.error_log(occurred_at).
-- التشغيل: Workflow صيانة يومي بـ n8n (job/maintenance) يستدعي api_admin.ensure_partitions(3) ثم api_admin.partition_health().
-- لماذا لا نعتمد على pg_cron/pg_partman: قد لا تتوفر بالاستضافة المُدارة. الدالة هنا تعمل بأي Postgres.
-- ملاحظة أمان: لا نفعّل RLS على الأقسام نفسها (السياسة على الجدول الأب). الحماية: لا أي دور غير المالك يملك صلاحية على أي قسم (يتحقق منه T-RLS-03).
-- القسم الافتراضي (_default) شبكة أمان فقط: وجود صفوف فيه = فشل صيانة (partition_health يُنبّه).
\set ON_ERROR_STOP on
SET ROLE app_owner;

CREATE FUNCTION api_admin.ensure_partitions(p_months_ahead int DEFAULT 3, p_months_back int DEFAULT 1) RETURNS int
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core AS $$
DECLARE
  t text; m int; v_start date; v_end date; v_name text; v_col text; n int := 0;
  parents CONSTANT text[] := ARRAY['report_snapshots', 'error_log'];
BEGIN
  IF p_months_ahead < 0 OR p_months_ahead > 24 THEN RAISE EXCEPTION 'bad_range'; END IF;
  FOREACH t IN ARRAY parents LOOP
    v_name := t || '_default';
    IF to_regclass(format('core.%I', v_name)) IS NULL THEN
      EXECUTE format('CREATE TABLE core.%I PARTITION OF core.%I DEFAULT', v_name, t);
      n := n + 1;
    END IF;
    FOR m IN -p_months_back .. p_months_ahead LOOP
      v_start := (date_trunc('month', now() AT TIME ZONE 'UTC') + make_interval(months => m))::date;
      v_end   := (v_start + interval '1 month')::date;
      v_name  := format('%s_p%s', t, to_char(v_start, 'YYYYMM'));
      IF to_regclass(format('core.%I', v_name)) IS NULL THEN
        -- إن كان القسم الافتراضي يحوي صفوفاً بهذا النطاق (تأخرت الصيانة)، ننقلها لجدول مؤقت أولاً، ثم ننشئ القسم، ثم نعيدها.
        -- (لا نستعمل ATTACH PARTITION: فحص مفتاح tenants الأجنبي أثناء ATTACH يُنفَّذ تحت RLS ويفشل. اكتشفه PART-05.
        --  أما فحوص المفاتيح الأجنبية عند INSERT العادي فتتجاوز RLS بتصميم PostgreSQL.)
        v_col := CASE t WHEN 'report_snapshots' THEN 'taken_at' ELSE 'occurred_at' END;
        EXECUTE format('CREATE TEMP TABLE _hold (LIKE core.%I) ON COMMIT DROP', t);
        EXECUTE format('WITH moved AS (DELETE FROM core.%I WHERE %I >= %L AND %I < %L RETURNING *) INSERT INTO _hold SELECT * FROM moved',
                       t || '_default', v_col, v_start::timestamptz, v_col, v_end::timestamptz);
        EXECUTE format('CREATE TABLE core.%I PARTITION OF core.%I FOR VALUES FROM (%L) TO (%L)', v_name, t, v_start::timestamptz, v_end::timestamptz);
        EXECUTE format('INSERT INTO core.%I SELECT * FROM _hold', v_name);
        DROP TABLE _hold;
        n := n + 1;
      END IF;
    END LOOP;
  END LOOP;
  RETURN n;       -- عدد الأقسام المُنشأة الآن (0 = لا شيء جديد)
END $$;

-- حذف أقسام أقدم من N شهر (احتفاظ). التقارير 6 أشهر، الأخطاء 12 شهراً افتراضياً.
CREATE FUNCTION api_admin.drop_old_partitions(p_parent text, p_keep_months int) RETURNS int
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core AS $$
DECLARE r record; v_cut date := (date_trunc('month', now() AT TIME ZONE 'UTC') - make_interval(months => p_keep_months))::date; n int := 0;
BEGIN
  IF p_parent NOT IN ('report_snapshots','error_log') THEN RAISE EXCEPTION 'not_partitioned_table'; END IF;
  IF p_keep_months < 1 THEN RAISE EXCEPTION 'keep_at_least_1_month'; END IF;
  FOR r IN
    SELECT c.relname, (regexp_match(c.relname, '_p(\d{6})$'))[1] AS ym
    FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid JOIN pg_class p ON p.oid = i.inhparent
    WHERE p.relname = p_parent AND c.relname ~ '_p\d{6}$'
  LOOP
    IF to_date(r.ym, 'YYYYMM') < v_cut THEN
      EXECUTE format('DROP TABLE core.%I', r.relname); n := n + 1;
    END IF;
  END LOOP;
  RETURN n;
END $$;

-- فحص صحة الأقسام: (أ) قسم الشهر الحالي والقادم موجود، (ب) القسم الافتراضي فارغ
CREATE FUNCTION api_admin.partition_health() RETURNS TABLE (check_name text, ok boolean, detail text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core AS $$
DECLARE t text; v_cur text; v_next text; n bigint;
  parents CONSTANT text[] := ARRAY['report_snapshots', 'error_log'];
BEGIN
  FOREACH t IN ARRAY parents LOOP
    v_cur  := format('%s_p%s', t, to_char(now() AT TIME ZONE 'UTC', 'YYYYMM'));
    v_next := format('%s_p%s', t, to_char((now() AT TIME ZONE 'UTC') + interval '1 month', 'YYYYMM'));
    RETURN QUERY SELECT t || ':current', to_regclass('core.' || v_cur) IS NOT NULL, v_cur;
    RETURN QUERY SELECT t || ':next',    to_regclass('core.' || v_next) IS NOT NULL, v_next;
    IF to_regclass(format('core.%I_default', t)) IS NOT NULL THEN
      EXECUTE format('SELECT count(*) FROM core.%I_default', t) INTO n;   -- المالك app_owner: يعمل بلا RLS-tenant لأن الجدول مقسّم ويُقرأ كاملاً
      RETURN QUERY SELECT t || ':default_empty', n = 0, n::text;
    END IF;
  END LOOP;
END $$;

RESET ROLE;
GRANT EXECUTE ON FUNCTION api_admin.ensure_partitions(int,int), api_admin.drop_old_partitions(text,int), api_admin.partition_health() TO app_ops;

-- عند التثبيت: أنشئ الأقسام الأولى (الافتراضي + شهر سابق + الحالي + 3 قادمة). بدونها أي INSERT بالتقارير/الأخطاء يفشل
-- (اكتشفه اختبار ISO-E4 أثناء التطوير). صيانة يومية بـ n8n تكمل: SELECT api_admin.ensure_partitions(3);
SELECT api_admin.ensure_partitions(3, 1);
