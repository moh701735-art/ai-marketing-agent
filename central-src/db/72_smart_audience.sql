-- 72_smart_audience.sql : إعدادات + cache لميزة Smart Audience (smart_audience/). مخطط جديد مستقل، لا يمس أي جدول/دالة قديمة.
-- ترقية آمنة (idempotent). الافتراضي مطفأ؛ يُفعَّل بـ ops/smart-audience-sync.sh on.
\set ON_ERROR_STOP on
CREATE SCHEMA IF NOT EXISTS smart_audience AUTHORIZATION app_owner;
REVOKE ALL ON SCHEMA smart_audience FROM PUBLIC;
SET ROLE app_owner;

CREATE TABLE IF NOT EXISTS smart_audience.settings (
  key        text PRIMARY KEY,
  value      jsonb NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON smart_audience.settings FROM PUBLIC;
-- العتبات قابلة للتعديل (AUDIENCE_*_THRESHOLD): ضيق < small ≤ متوسط < medium ≤ جيد < large ≤ واسع < very_large ≤ واسع جداً. التقييم بمنتصف نطاق تيك توك.
INSERT INTO smart_audience.settings (key, value) VALUES
  ('enabled', 'false'::jsonb),
  ('thresholds', '{"small": 500000, "medium": 2000000, "large": 6000000, "very_large": 12000000}'::jsonb),
  ('location_id', '"99237"'::jsonb),
  ('country_name', '"العراق"'::jsonb)
ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS smart_audience.cache (
  tenant_id  uuid NOT NULL,
  key        text NOT NULL CHECK (key ~ '^[a-z0-9:_-]{1,80}$'),
  value      jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  PRIMARY KEY (tenant_id, key)
);
REVOKE ALL ON smart_audience.cache FROM PUBLIC;

-- الإعدادات الفعّالة لهذا العميل (مفتاح عام + features.smart_audience للعميل ليس 'false'). سياق موقّع؛ لا يرى إلا عميله.
CREATE OR REPLACE FUNCTION smart_audience.config(p_ctx text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
DECLARE v_on boolean; v_feat text; v_th jsonb; v_loc text; v_cn text;
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  SELECT (s.value) = 'true'::jsonb INTO v_on FROM smart_audience.settings s WHERE s.key = 'enabled';
  SELECT t.features->>'smart_audience' INTO v_feat FROM core.tenants t WHERE t.tenant_id = private.cur_tenant();
  SELECT s.value INTO v_th FROM smart_audience.settings s WHERE s.key = 'thresholds';
  SELECT s.value #>> '{}' INTO v_loc FROM smart_audience.settings s WHERE s.key = 'location_id';
  SELECT s.value #>> '{}' INTO v_cn FROM smart_audience.settings s WHERE s.key = 'country_name';
  RETURN jsonb_build_object('enabled', coalesce(v_on, false) AND coalesce(v_feat, 'true') <> 'false', 'thresholds', coalesce(v_th, '{}'::jsonb), 'location_id', v_loc, 'country', v_cn);
END $$;

CREATE OR REPLACE FUNCTION smart_audience.enabled(p_ctx text) RETURNS boolean
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$ SELECT (smart_audience.config(p_ctx)->>'enabled')::boolean $$;

CREATE OR REPLACE FUNCTION smart_audience.cache_list(p_ctx text) RETURNS TABLE (key text, value jsonb, age_s int)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  RETURN QUERY SELECT c.key, c.value, extract(epoch FROM now() - c.created_at)::int FROM smart_audience.cache c
    WHERE c.tenant_id = private.cur_tenant() AND c.expires_at > now() ORDER BY c.created_at DESC LIMIT 40;
END $$;

CREATE OR REPLACE FUNCTION smart_audience.cache_set(p_ctx text, p_key text, p_value jsonb, p_ttl int) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  IF p_key !~ '^[a-z0-9:_-]{1,80}$' OR p_ttl NOT BETWEEN 30 AND 172800 OR length(p_value::text) > 40000 THEN RETURN false; END IF;
  INSERT INTO smart_audience.cache (tenant_id, key, value, expires_at) VALUES (private.cur_tenant(), p_key, p_value, now() + make_interval(secs => p_ttl))
  ON CONFLICT (tenant_id, key) DO UPDATE SET value = EXCLUDED.value, created_at = now(), expires_at = EXCLUDED.expires_at;
  DELETE FROM smart_audience.cache WHERE tenant_id = private.cur_tenant() AND (expires_at <= now()
    OR key NOT IN (SELECT c2.key FROM smart_audience.cache c2 WHERE c2.tenant_id = private.cur_tenant() ORDER BY c2.created_at DESC LIMIT 60));
  RETURN true;
END $$;

ALTER FUNCTION smart_audience.config(text) OWNER TO app_owner;
ALTER FUNCTION smart_audience.enabled(text) OWNER TO app_owner;
ALTER FUNCTION smart_audience.cache_list(text) OWNER TO app_owner;
ALTER FUNCTION smart_audience.cache_set(text, text, jsonb, int) OWNER TO app_owner;
REVOKE ALL ON FUNCTION smart_audience.config(text), smart_audience.enabled(text), smart_audience.cache_list(text), smart_audience.cache_set(text, text, jsonb, int) FROM PUBLIC;
RESET ROLE;
GRANT USAGE ON SCHEMA smart_audience TO app_runtime;
GRANT EXECUTE ON FUNCTION smart_audience.config(text), smart_audience.enabled(text), smart_audience.cache_list(text), smart_audience.cache_set(text, text, jsonb, int) TO app_runtime;
