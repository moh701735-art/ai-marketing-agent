-- 80_competitor_radar.sql : رادار المنافسين (competitor_radar/). مخطط جديد مستقل بالكامل؛ لا يغيّر أي جدول/دالة/صلاحية موجودة.
-- ترقية آمنة (idempotent). الافتراضي مطفأ؛ يُفعَّل بـ ops/competitor-radar-sync.sh on. يُطبَّق يدوياً (مثل 72/74)، مو عبر update.sh.
-- التراجع: 80_competitor_radar_down.sql. كل الدوال SECURITY DEFINER وتفرض عزل العميل من ctx الموقّع (private.enter_ctx / cur_tenant)؛ الخدمة ما تعرف tenant_id.
\set ON_ERROR_STOP on
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'radar_rt') THEN CREATE ROLE radar_rt NOLOGIN; END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS competitor_radar AUTHORIZATION app_owner;
REVOKE ALL ON SCHEMA competitor_radar FROM PUBLIC;
SET ROLE app_owner;

CREATE TABLE IF NOT EXISTS competitor_radar.settings (
  key text PRIMARY KEY, value jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT now());
INSERT INTO competitor_radar.settings (key, value) VALUES ('enabled', 'false'::jsonb) ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS competitor_radar.competitors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  platform text NOT NULL CHECK (platform IN ('tiktok','instagram','facebook','snapchat','other')),
  name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 80),
  url text CHECK (url IS NULL OR char_length(url) <= 500),
  status text NOT NULL DEFAULT 'new' CHECK (status IN ('new','done','insufficient','failed')),
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS competitors_tenant_idx ON competitor_radar.competitors (tenant_id);

CREATE TABLE IF NOT EXISTS competitor_radar.samples (
  id bigserial PRIMARY KEY,
  tenant_id uuid NOT NULL,
  competitor_id uuid NOT NULL REFERENCES competitor_radar.competitors(id) ON DELETE CASCADE,
  sid text NOT NULL CHECK (sid ~ '^[0-9a-f]{12}$'),
  src text NOT NULL CHECK (src IN ('pasted','html_meta','oembed')),
  text text NOT NULL CHECK (char_length(text) BETWEEN 8 AND 1500),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (competitor_id, sid));

CREATE TABLE IF NOT EXISTS competitor_radar.reports (
  competitor_id uuid PRIMARY KEY REFERENCES competitor_radar.competitors(id) ON DELETE CASCADE,
  tenant_id uuid NOT NULL,
  report jsonb NOT NULL CHECK (length(report::text) <= 60000),
  confidence text NOT NULL CHECK (confidence IN ('high','medium','low')),
  created_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS competitor_radar.plans (
  competitor_id uuid PRIMARY KEY REFERENCES competitor_radar.competitors(id) ON DELETE CASCADE,
  tenant_id uuid NOT NULL,
  plan jsonb NOT NULL CHECK (length(plan::text) <= 30000),
  created_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS competitor_radar.cache (
  tenant_id uuid NOT NULL,
  key text NOT NULL CHECK (key ~ '^[a-z0-9:_-]{1,80}$'),
  value jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  PRIMARY KEY (tenant_id, key));
REVOKE ALL ON competitor_radar.settings, competitor_radar.competitors, competitor_radar.samples, competitor_radar.reports, competitor_radar.plans, competitor_radar.cache FROM PUBLIC;

-- داخلية (بدون صلاحية تنفيذ لأحد): الميزة مفعّلة عالمياً وللعميل (features.competitor_radar ليس 'false')
CREATE OR REPLACE FUNCTION competitor_radar._enabled() RETURNS boolean
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
  SELECT coalesce((SELECT s.value = 'true'::jsonb FROM competitor_radar.settings s WHERE s.key = 'enabled'), false)
     AND coalesce((SELECT t.features->>'competitor_radar' FROM core.tenants t WHERE t.tenant_id = private.cur_tenant()), 'true') <> 'false' $$;

CREATE OR REPLACE FUNCTION competitor_radar.config(p_ctx text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  RETURN jsonb_build_object('enabled', competitor_radar._enabled());
END $$;

CREATE OR REPLACE FUNCTION competitor_radar.competitor_add(p_ctx text, p_platform text, p_name text, p_url text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
DECLARE v_id uuid;
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  IF NOT competitor_radar._enabled() THEN RAISE EXCEPTION 'radar_disabled' USING ERRCODE = 'P0001'; END IF;
  IF p_platform NOT IN ('tiktok','instagram','facebook','snapchat','other') OR char_length(coalesce(p_name,'')) NOT BETWEEN 1 AND 80 OR char_length(coalesce(p_url,'')) > 500
    THEN RAISE EXCEPTION 'radar_invalid' USING ERRCODE = 'P0001'; END IF;
  IF (SELECT count(*) FROM competitor_radar.competitors c WHERE c.tenant_id = private.cur_tenant()) >= 20 THEN RAISE EXCEPTION 'radar_limit' USING ERRCODE = 'P0001'; END IF;
  INSERT INTO competitor_radar.competitors (tenant_id, platform, name, url) VALUES (private.cur_tenant(), p_platform, p_name, nullif(p_url, '')) RETURNING id INTO v_id;
  RETURN jsonb_build_object('id', v_id);
END $$;

CREATE OR REPLACE FUNCTION competitor_radar.competitor_list(p_ctx text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  IF NOT competitor_radar._enabled() THEN RAISE EXCEPTION 'radar_disabled' USING ERRCODE = 'P0001'; END IF;
  RETURN coalesce((SELECT jsonb_agg(jsonb_build_object('id', c.id, 'platform', c.platform, 'name', c.name, 'url', c.url, 'status', c.status,
           'confidence', r.confidence, 'samples', (SELECT count(*) FROM competitor_radar.samples s WHERE s.competitor_id = c.id),
           'analyzed_at', CASE WHEN r.created_at IS NULL THEN NULL ELSE extract(epoch FROM r.created_at)::bigint END) ORDER BY c.created_at DESC)
         FROM competitor_radar.competitors c LEFT JOIN competitor_radar.reports r ON r.competitor_id = c.id WHERE c.tenant_id = private.cur_tenant()), '[]'::jsonb);
END $$;

CREATE OR REPLACE FUNCTION competitor_radar.competitor_get(p_ctx text, p_id uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
DECLARE v jsonb;
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  IF NOT competitor_radar._enabled() THEN RAISE EXCEPTION 'radar_disabled' USING ERRCODE = 'P0001'; END IF;
  SELECT jsonb_build_object('id', c.id, 'platform', c.platform, 'name', c.name, 'url', c.url, 'status', c.status, 'confidence', r.confidence,
           'samples', (SELECT count(*) FROM competitor_radar.samples s WHERE s.competitor_id = c.id),
           'analyzed_at', CASE WHEN r.created_at IS NULL THEN NULL ELSE extract(epoch FROM r.created_at)::bigint END)
    INTO v FROM competitor_radar.competitors c LEFT JOIN competitor_radar.reports r ON r.competitor_id = c.id
    WHERE c.id = p_id AND c.tenant_id = private.cur_tenant();
  RETURN v;
END $$;

CREATE OR REPLACE FUNCTION competitor_radar.competitor_delete(p_ctx text, p_id uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
DECLARE n int;
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  IF NOT competitor_radar._enabled() THEN RAISE EXCEPTION 'radar_disabled' USING ERRCODE = 'P0001'; END IF;
  DELETE FROM competitor_radar.competitors WHERE id = p_id AND tenant_id = private.cur_tenant();
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN to_jsonb(n > 0);
END $$;

CREATE OR REPLACE FUNCTION competitor_radar.samples_add(p_ctx text, p_id uuid, p_samples jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
DECLARE e jsonb; v_t uuid; n int;
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  IF NOT competitor_radar._enabled() THEN RAISE EXCEPTION 'radar_disabled' USING ERRCODE = 'P0001'; END IF;
  v_t := private.cur_tenant();
  IF NOT EXISTS (SELECT 1 FROM competitor_radar.competitors c WHERE c.id = p_id AND c.tenant_id = v_t) THEN RAISE EXCEPTION 'radar_not_found' USING ERRCODE = 'P0001'; END IF;
  IF jsonb_typeof(p_samples) <> 'array' OR jsonb_array_length(p_samples) > 30 THEN RAISE EXCEPTION 'radar_invalid' USING ERRCODE = 'P0001'; END IF;
  FOR e IN SELECT * FROM jsonb_array_elements(p_samples) LOOP
    IF (e->>'id') !~ '^[0-9a-f]{12}$' OR (e->>'src') NOT IN ('pasted','html_meta','oembed') OR char_length(coalesce(e->>'text','')) NOT BETWEEN 8 AND 1500 THEN RAISE EXCEPTION 'radar_invalid' USING ERRCODE = 'P0001'; END IF;
    INSERT INTO competitor_radar.samples (tenant_id, competitor_id, sid, src, text) VALUES (v_t, p_id, e->>'id', e->>'src', e->>'text') ON CONFLICT (competitor_id, sid) DO NOTHING;
  END LOOP;
  DELETE FROM competitor_radar.samples WHERE competitor_id = p_id AND id NOT IN (SELECT s.id FROM competitor_radar.samples s WHERE s.competitor_id = p_id ORDER BY s.id DESC LIMIT 60);
  SELECT count(*) INTO n FROM competitor_radar.samples WHERE competitor_id = p_id;
  RETURN to_jsonb(n);
END $$;

CREATE OR REPLACE FUNCTION competitor_radar.samples_list(p_ctx text, p_id uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  IF NOT competitor_radar._enabled() THEN RAISE EXCEPTION 'radar_disabled' USING ERRCODE = 'P0001'; END IF;
  IF NOT EXISTS (SELECT 1 FROM competitor_radar.competitors c WHERE c.id = p_id AND c.tenant_id = private.cur_tenant()) THEN RAISE EXCEPTION 'radar_not_found' USING ERRCODE = 'P0001'; END IF;
  RETURN coalesce((SELECT jsonb_agg(jsonb_build_object('id', s.sid, 'src', s.src, 'text', s.text) ORDER BY s.id) FROM competitor_radar.samples s WHERE s.competitor_id = p_id AND s.tenant_id = private.cur_tenant()), '[]'::jsonb);
END $$;

CREATE OR REPLACE FUNCTION competitor_radar.report_save(p_ctx text, p_id uuid, p_report jsonb, p_status text, p_conf text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
DECLARE v_t uuid;
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  IF NOT competitor_radar._enabled() THEN RAISE EXCEPTION 'radar_disabled' USING ERRCODE = 'P0001'; END IF;
  v_t := private.cur_tenant();
  IF NOT EXISTS (SELECT 1 FROM competitor_radar.competitors c WHERE c.id = p_id AND c.tenant_id = v_t) THEN RAISE EXCEPTION 'radar_not_found' USING ERRCODE = 'P0001'; END IF;
  IF p_status NOT IN ('done','insufficient','failed') OR p_conf NOT IN ('high','medium','low') THEN RAISE EXCEPTION 'radar_invalid' USING ERRCODE = 'P0001'; END IF;
  IF length(p_report::text) > 60000 THEN RAISE EXCEPTION 'radar_too_large' USING ERRCODE = 'P0001'; END IF;
  UPDATE competitor_radar.competitors SET status = p_status, updated_at = now() WHERE id = p_id AND tenant_id = v_t;
  INSERT INTO competitor_radar.reports (competitor_id, tenant_id, report, confidence) VALUES (p_id, v_t, p_report, p_conf)
    ON CONFLICT (competitor_id) DO UPDATE SET report = EXCLUDED.report, confidence = EXCLUDED.confidence, created_at = now();
  RETURN to_jsonb(true);
END $$;

CREATE OR REPLACE FUNCTION competitor_radar.report_get(p_ctx text, p_id uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
DECLARE v jsonb;
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  IF NOT competitor_radar._enabled() THEN RAISE EXCEPTION 'radar_disabled' USING ERRCODE = 'P0001'; END IF;
  IF NOT EXISTS (SELECT 1 FROM competitor_radar.competitors c WHERE c.id = p_id AND c.tenant_id = private.cur_tenant()) THEN RAISE EXCEPTION 'radar_not_found' USING ERRCODE = 'P0001'; END IF;
  SELECT jsonb_build_object('report', r.report, 'confidence', r.confidence, 'age_s', extract(epoch FROM now() - r.created_at)::int) INTO v
    FROM competitor_radar.reports r WHERE r.competitor_id = p_id AND r.tenant_id = private.cur_tenant();
  RETURN v;
END $$;

CREATE OR REPLACE FUNCTION competitor_radar.plan_save(p_ctx text, p_id uuid, p_plan jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
DECLARE v_t uuid;
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  IF NOT competitor_radar._enabled() THEN RAISE EXCEPTION 'radar_disabled' USING ERRCODE = 'P0001'; END IF;
  v_t := private.cur_tenant();
  IF NOT EXISTS (SELECT 1 FROM competitor_radar.competitors c WHERE c.id = p_id AND c.tenant_id = v_t) THEN RAISE EXCEPTION 'radar_not_found' USING ERRCODE = 'P0001'; END IF;
  IF length(p_plan::text) > 30000 THEN RAISE EXCEPTION 'radar_too_large' USING ERRCODE = 'P0001'; END IF;
  INSERT INTO competitor_radar.plans (competitor_id, tenant_id, plan) VALUES (p_id, v_t, p_plan)
    ON CONFLICT (competitor_id) DO UPDATE SET plan = EXCLUDED.plan, created_at = now();
  RETURN to_jsonb(true);
END $$;

CREATE OR REPLACE FUNCTION competitor_radar.plan_get(p_ctx text, p_id uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
DECLARE v jsonb;
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  IF NOT competitor_radar._enabled() THEN RAISE EXCEPTION 'radar_disabled' USING ERRCODE = 'P0001'; END IF;
  IF NOT EXISTS (SELECT 1 FROM competitor_radar.competitors c WHERE c.id = p_id AND c.tenant_id = private.cur_tenant()) THEN RAISE EXCEPTION 'radar_not_found' USING ERRCODE = 'P0001'; END IF;
  SELECT jsonb_build_object('plan', p.plan, 'age_s', extract(epoch FROM now() - p.created_at)::int) INTO v
    FROM competitor_radar.plans p WHERE p.competitor_id = p_id AND p.tenant_id = private.cur_tenant();
  RETURN v;
END $$;

CREATE OR REPLACE FUNCTION competitor_radar.cache_get(p_ctx text, p_key text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  IF NOT competitor_radar._enabled() THEN RAISE EXCEPTION 'radar_disabled' USING ERRCODE = 'P0001'; END IF;
  RETURN (SELECT c.value FROM competitor_radar.cache c WHERE c.tenant_id = private.cur_tenant() AND c.key = p_key AND c.expires_at > now());
END $$;

CREATE OR REPLACE FUNCTION competitor_radar.cache_set(p_ctx text, p_key text, p_value jsonb, p_ttl int) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  IF NOT competitor_radar._enabled() THEN RAISE EXCEPTION 'radar_disabled' USING ERRCODE = 'P0001'; END IF;
  IF p_key !~ '^[a-z0-9:_-]{1,80}$' OR p_ttl NOT BETWEEN 30 AND 172800 OR length(p_value::text) > 40000 THEN RETURN to_jsonb(false); END IF;
  INSERT INTO competitor_radar.cache (tenant_id, key, value, expires_at) VALUES (private.cur_tenant(), p_key, p_value, now() + make_interval(secs => p_ttl))
    ON CONFLICT (tenant_id, key) DO UPDATE SET value = EXCLUDED.value, created_at = now(), expires_at = EXCLUDED.expires_at;
  DELETE FROM competitor_radar.cache WHERE tenant_id = private.cur_tenant() AND (expires_at <= now()
    OR key NOT IN (SELECT c2.key FROM competitor_radar.cache c2 WHERE c2.tenant_id = private.cur_tenant() ORDER BY c2.created_at DESC LIMIT 60));
  RETURN to_jsonb(true);
END $$;

ALTER FUNCTION competitor_radar._enabled() OWNER TO app_owner;
ALTER FUNCTION competitor_radar.config(text) OWNER TO app_owner;
ALTER FUNCTION competitor_radar.competitor_add(text, text, text, text) OWNER TO app_owner;
ALTER FUNCTION competitor_radar.competitor_list(text) OWNER TO app_owner;
ALTER FUNCTION competitor_radar.competitor_get(text, uuid) OWNER TO app_owner;
ALTER FUNCTION competitor_radar.competitor_delete(text, uuid) OWNER TO app_owner;
ALTER FUNCTION competitor_radar.samples_add(text, uuid, jsonb) OWNER TO app_owner;
ALTER FUNCTION competitor_radar.samples_list(text, uuid) OWNER TO app_owner;
ALTER FUNCTION competitor_radar.report_save(text, uuid, jsonb, text, text) OWNER TO app_owner;
ALTER FUNCTION competitor_radar.report_get(text, uuid) OWNER TO app_owner;
ALTER FUNCTION competitor_radar.plan_save(text, uuid, jsonb) OWNER TO app_owner;
ALTER FUNCTION competitor_radar.plan_get(text, uuid) OWNER TO app_owner;
ALTER FUNCTION competitor_radar.cache_get(text, text) OWNER TO app_owner;
ALTER FUNCTION competitor_radar.cache_set(text, text, jsonb, int) OWNER TO app_owner;
REVOKE ALL ON FUNCTION competitor_radar._enabled(), competitor_radar.config(text), competitor_radar.competitor_add(text, text, text, text), competitor_radar.competitor_list(text),
  competitor_radar.competitor_get(text, uuid), competitor_radar.competitor_delete(text, uuid), competitor_radar.samples_add(text, uuid, jsonb), competitor_radar.samples_list(text, uuid),
  competitor_radar.report_save(text, uuid, jsonb, text, text), competitor_radar.report_get(text, uuid), competitor_radar.plan_save(text, uuid, jsonb), competitor_radar.plan_get(text, uuid),
  competitor_radar.cache_get(text, text), competitor_radar.cache_set(text, text, jsonb, int) FROM PUBLIC;
RESET ROLE;
-- الخدمة (radar_rt) تستدعي كل الدوال العامة؛ app_runtime (n8n) يقرأ config فقط (لإظهار/إخفاء الزر) — بدون أي صلاحية جداول
GRANT USAGE ON SCHEMA competitor_radar TO radar_rt, app_runtime;
GRANT EXECUTE ON FUNCTION competitor_radar.config(text), competitor_radar.competitor_add(text, text, text, text), competitor_radar.competitor_list(text),
  competitor_radar.competitor_get(text, uuid), competitor_radar.competitor_delete(text, uuid), competitor_radar.samples_add(text, uuid, jsonb), competitor_radar.samples_list(text, uuid),
  competitor_radar.report_save(text, uuid, jsonb, text, text), competitor_radar.report_get(text, uuid), competitor_radar.plan_save(text, uuid, jsonb), competitor_radar.plan_get(text, uuid),
  competitor_radar.cache_get(text, text), competitor_radar.cache_set(text, text, jsonb, int) TO radar_rt;
GRANT EXECUTE ON FUNCTION competitor_radar.config(text) TO app_runtime;
