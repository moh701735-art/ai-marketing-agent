-- 75_tenant_countries.sql (p215): الدول المسموحة لاستهداف تيك توك لكل عميل. الافتراضي العراق فقط (IQ).
-- القيمة بالقاعدة: core.tenants.features->'allowed_countries' = ["IQ","SA",...] (رمزان لاتينيان). الـBroker يقرأها قبل فحص القفل (BROKER_TT_IRAQ_ONLY).
\set ON_ERROR_STOP on
SET ROLE app_owner;
CREATE OR REPLACE FUNCTION api.tenant_countries(p_ctx text) RETURNS text[]
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
DECLARE v_f jsonb; v_out text[];
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  SELECT t.features->'allowed_countries' INTO v_f FROM core.tenants t WHERE t.tenant_id = private.cur_tenant();
  IF v_f IS NULL OR jsonb_typeof(v_f) <> 'array' THEN RETURN ARRAY['IQ']; END IF;
  SELECT array_agg(DISTINCT upper(e) ORDER BY upper(e)) INTO v_out FROM jsonb_array_elements_text(v_f) e WHERE e ~ '^[A-Za-z]{2}$';
  RETURN coalesce(v_out, ARRAY['IQ']);
END $$;
REVOKE ALL ON FUNCTION api.tenant_countries(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION api.tenant_countries(text) TO app_broker;
