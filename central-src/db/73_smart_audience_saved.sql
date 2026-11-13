-- 73_smart_audience_saved.sql : جماهير محفوظة بالاسم (Smart Audience، تيك توك فقط). مخطط smart_audience الموجود (72). ترقية آمنة (idempotent).
-- كل بوت/عميل يرى جماهيره فقط (private.cur_tenant من السياق الموقّع)؛ ما يظهر شي إذا الميزة مطفأة؛ حد 20 جمهور لكل عميل، حتى 50 اهتمام لكل جمهور.
\set ON_ERROR_STOP on
SET ROLE app_owner;

CREATE TABLE IF NOT EXISTS smart_audience.saved (
  id         bigserial PRIMARY KEY,
  tenant_id  uuid NOT NULL,
  name       text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 30),
  interests  jsonb NOT NULL CHECK (jsonb_typeof(interests) = 'array' AND jsonb_array_length(interests) BETWEEN 1 AND 50),
  meta       jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name)
);
REVOKE ALL ON smart_audience.saved FROM PUBLIC;
GRANT USAGE, SELECT ON SEQUENCE smart_audience.saved_id_seq TO app_owner;

CREATE OR REPLACE FUNCTION smart_audience.saved_list(p_ctx text) RETURNS TABLE (id bigint, name text, cnt int, interests jsonb, meta jsonb, age_s int)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  IF NOT coalesce((smart_audience.config(p_ctx)->>'enabled')::boolean, false) THEN RETURN; END IF;
  RETURN QUERY SELECT s.id, s.name, jsonb_array_length(s.interests), s.interests, s.meta, extract(epoch FROM now() - s.updated_at)::int
    FROM smart_audience.saved s WHERE s.tenant_id = private.cur_tenant() ORDER BY s.updated_at DESC, s.id DESC LIMIT 12;
END $$;

-- p_op: {"op":"save","name":"..","iv":[["id","اسم"],...],"meta":{..}} أو {"op":"del","id":123}. يرجّع jsonb {ok, ...} (ما يرمي أخطاء للمستخدم).
CREATE OR REPLACE FUNCTION smart_audience.saved_apply(p_ctx text, p_op jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
DECLARE v_t uuid; v_op text; v_name text; v_iv jsonb; v_meta jsonb; v_id bigint; v_cnt int; v_exists boolean; v_bad boolean; v_n int;
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  IF NOT coalesce((smart_audience.config(p_ctx)->>'enabled')::boolean, false) THEN RETURN jsonb_build_object('ok', false, 'err', 'disabled'); END IF;
  IF p_op IS NULL OR jsonb_typeof(p_op) <> 'object' THEN RETURN jsonb_build_object('ok', false, 'err', 'op'); END IF;
  v_t := private.cur_tenant(); v_op := p_op->>'op';
  IF v_op = 'save' THEN
    v_name := btrim(regexp_replace(coalesce(p_op->>'name', ''), '[[:cntrl:]]', ' ', 'g'));
    IF char_length(v_name) NOT BETWEEN 1 AND 30 THEN RETURN jsonb_build_object('ok', false, 'err', 'name'); END IF;
    v_iv := p_op->'iv';
    IF v_iv IS NULL OR jsonb_typeof(v_iv) <> 'array' OR jsonb_array_length(v_iv) NOT BETWEEN 1 AND 50 THEN RETURN jsonb_build_object('ok', false, 'err', 'interests'); END IF;
    SELECT coalesce(bool_or(NOT (jsonb_typeof(e) = 'array' AND jsonb_array_length(e) = 2 AND jsonb_typeof(e->0) = 'string' AND (e->>0) ~ '^[0-9]{3,25}$'
                                 AND jsonb_typeof(e->1) = 'string' AND char_length(e->>1) <= 60)), true) INTO v_bad FROM jsonb_array_elements(v_iv) e;
    IF v_bad THEN RETURN jsonb_build_object('ok', false, 'err', 'interests'); END IF;
    v_meta := CASE WHEN jsonb_typeof(p_op->'meta') = 'object' AND length((p_op->'meta')::text) <= 2000 THEN p_op->'meta' ELSE '{}'::jsonb END;
    SELECT EXISTS (SELECT 1 FROM smart_audience.saved s WHERE s.tenant_id = v_t AND s.name = v_name) INTO v_exists;
    SELECT count(*) INTO v_cnt FROM smart_audience.saved s WHERE s.tenant_id = v_t;
    IF NOT v_exists AND v_cnt >= 20 THEN RETURN jsonb_build_object('ok', false, 'err', 'limit'); END IF;
    INSERT INTO smart_audience.saved (tenant_id, name, interests, meta) VALUES (v_t, v_name, v_iv, v_meta)
    ON CONFLICT (tenant_id, name) DO UPDATE SET interests = EXCLUDED.interests, meta = EXCLUDED.meta, updated_at = now()
    RETURNING saved.id INTO v_id;
    RETURN jsonb_build_object('ok', true, 'id', v_id, 'n', jsonb_array_length(v_iv), 'replaced', v_exists);
  ELSIF v_op = 'del' THEN
    IF coalesce(p_op->>'id', '') !~ '^[0-9]{1,18}$' THEN RETURN jsonb_build_object('ok', false, 'err', 'op'); END IF;
    DELETE FROM smart_audience.saved s WHERE s.tenant_id = v_t AND s.id = (p_op->>'id')::bigint;
    GET DIAGNOSTICS v_n = ROW_COUNT;
    RETURN CASE WHEN v_n > 0 THEN jsonb_build_object('ok', true, 'n', v_n) ELSE jsonb_build_object('ok', false, 'err', 'notfound') END;
  END IF;
  RETURN jsonb_build_object('ok', false, 'err', 'op');
END $$;

ALTER FUNCTION smart_audience.saved_list(text) OWNER TO app_owner;
ALTER FUNCTION smart_audience.saved_apply(text, jsonb) OWNER TO app_owner;
REVOKE ALL ON FUNCTION smart_audience.saved_list(text), smart_audience.saved_apply(text, jsonb) FROM PUBLIC;
RESET ROLE;
GRANT EXECUTE ON FUNCTION smart_audience.saved_list(text), smart_audience.saved_apply(text, jsonb) TO app_runtime;
