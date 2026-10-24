-- 30_functions.sql : الدوال. هذه هي السطح الوحيد الذي يراه app_runtime (n8n).
-- مبدأ التصميم: n8n لا يمرر tenant_id أبداً. يمرر ctx (توكن موقّع من القاعدة) صادر من resolve_context
-- أو job_contexts. كل دالة تفتح ctx بـ private.enter_ctx فيُضبط app.tenant_id محلياً بالمعاملة، فتحكم RLS.
\set ON_ERROR_STOP on

GRANT CREATE ON SCHEMA api, api_admin, private TO app_resolver, app_ops_fn;
SET ROLE app_owner;

-- ───────────── توقيع/فتح السياق ─────────────
CREATE FUNCTION private.sign_ctx(p_payload jsonb) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, private, ext AS $$
DECLARE v_hex text; v_key bytea;
BEGIN
  SELECT k INTO v_key FROM private.ctx_key WHERE id = 1;
  v_hex := encode(convert_to(p_payload::text, 'UTF8'), 'hex');
  RETURN v_hex || '.' || encode(hmac(convert_to(v_hex, 'UTF8'), v_key, 'sha256'), 'hex');
END $$;

CREATE FUNCTION private.enter_ctx(p_ctx text, p_min_role text DEFAULT 'viewer', p_need_ready boolean DEFAULT true)
RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private, ext AS $$
DECLARE
  v_hex text; v_sig text; v_key bytea; v_p jsonb; v_t uuid; v_rank int; v_need int;
  v_status core.tenant_status; v_u record;
  ranks CONSTANT jsonb := '{"viewer":1,"manager":2,"owner":3,"system":4}';
BEGIN
  IF p_ctx IS NULL OR position('.' IN p_ctx) = 0 THEN RAISE EXCEPTION 'invalid_ctx' USING ERRCODE = '28000'; END IF;
  v_hex := split_part(p_ctx, '.', 1); v_sig := split_part(p_ctx, '.', 2);
  SELECT k INTO v_key FROM private.ctx_key WHERE id = 1;
  IF encode(hmac(convert_to(v_hex, 'UTF8'), v_key, 'sha256'), 'hex') <> v_sig THEN
    RAISE EXCEPTION 'invalid_ctx' USING ERRCODE = '28000';
  END IF;
  v_p := convert_from(decode(v_hex, 'hex'), 'UTF8')::jsonb;
  IF (v_p->>'e')::bigint < extract(epoch FROM now())::bigint THEN
    RAISE EXCEPTION 'expired_ctx' USING ERRCODE = '28000';
  END IF;
  v_t := (v_p->>'t')::uuid;
  PERFORM set_config('app.tenant_id', v_t::text, true);
  PERFORM set_config('app.role', v_p->>'r', true);
  PERFORM set_config('app.user', coalesce(v_p->>'u', ''), true);
  v_rank := (ranks->>(v_p->>'r'))::int;  v_need := (ranks->>p_min_role)::int;
  IF v_rank IS NULL OR v_rank < v_need THEN RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501'; END IF;
  SELECT status INTO v_status FROM core.tenants WHERE tenant_id = v_t;
  IF NOT FOUND THEN RAISE EXCEPTION 'invalid_ctx' USING ERRCODE = '28000'; END IF;
  IF v_status = 'SUSPENDED' THEN RAISE EXCEPTION 'tenant_suspended' USING ERRCODE = '42501'; END IF;
  IF p_need_ready AND v_status <> 'READY' THEN RAISE EXCEPTION 'tenant_not_ready' USING ERRCODE = '42501'; END IF;
  IF v_p->>'r' <> 'system' THEN   -- المستخدم ما زال نشطاً وبنفس الدور؟ (سحب الصلاحية يسري فوراً)
    SELECT role::text AS role, active INTO v_u FROM core.tenant_users
      WHERE tenant_id = v_t AND telegram_user_id = (v_p->>'u')::bigint;
    IF NOT FOUND OR NOT v_u.active THEN RAISE EXCEPTION 'user_inactive' USING ERRCODE = '42501'; END IF;
    IF (ranks->>v_u.role)::int < v_need THEN RAISE EXCEPTION 'forbidden' USING ERRCODE = '42501'; END IF;
    v_p := jsonb_set(v_p, '{r}', to_jsonb(v_u.role));
    PERFORM set_config('app.role', v_u.role, true);
  END IF;
  RETURN v_p;
END $$;

-- ───────────── trigger جاهزية: لا READY بدون كل الفحوصات الإلزامية ─────────────
CREATE FUNCTION private.guard_ready() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core AS $$
DECLARE v_missing text;
BEGIN
  IF NEW.status = 'READY' AND (TG_OP = 'INSERT' OR OLD.status <> 'READY') THEN
    PERFORM set_config('app.tenant_id', NEW.tenant_id::text, true);   -- RLS مفروضة حتى على المالك: نقرأ فحوصات هذا الـ tenant فقط
    SELECT string_agg(d.check_code, ',' ORDER BY d.check_code) INTO v_missing
    FROM core.readiness_check_defs d
    LEFT JOIN core.readiness_checks c ON c.tenant_id = NEW.tenant_id AND c.check_code = d.check_code
    WHERE d.mandatory
      AND (d.applies_when = 'always' OR coalesce((NEW.features->>d.applies_when)::boolean, false))
      AND (c.status IS DISTINCT FROM 'pass' OR c.expires_at <= now());
    IF v_missing IS NOT NULL THEN
      RAISE EXCEPTION 'not_ready: failing/missing/expired checks: %', v_missing USING ERRCODE = 'P0001';
    END IF;
  END IF;
  NEW.updated_at := now();
  RETURN NEW;
END $$;
CREATE TRIGGER tenants_guard_ready BEFORE INSERT OR UPDATE ON core.tenants
  FOR EACH ROW EXECUTE FUNCTION private.guard_ready();

-- ───────────── api.* (مالكها app_owner، تحت RLS المفروضة) ─────────────
CREATE FUNCTION api.claim_update(p_ctx text, p_update_id bigint) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
DECLARE v jsonb; n int;
BEGIN
  v := private.enter_ctx(p_ctx, 'viewer');
  INSERT INTO core.processed_updates (tenant_id, bot_id, update_id)
  VALUES (private.cur_tenant(), (v->>'b')::uuid, p_update_id) ON CONFLICT DO NOTHING;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n = 1;          -- false = تكرار، تجاهله
END $$;

CREATE FUNCTION api.list_campaigns(p_ctx text, p_status text DEFAULT NULL) RETURNS SETOF core.campaigns
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  RETURN QUERY SELECT * FROM core.campaigns WHERE (p_status IS NULL OR status = p_status) ORDER BY created_at DESC;
END $$;

CREATE FUNCTION api.record_campaign(p_ctx text, p_platform text, p_ad_account text, p_external_id text,
                                    p_name text, p_objective text, p_budget numeric) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
DECLARE v jsonb; v_id uuid; v_max numeric;
BEGIN
  v := private.enter_ctx(p_ctx, 'manager');
  IF NOT EXISTS (SELECT 1 FROM core.ad_accounts WHERE platform = p_platform::core.platform AND external_id = p_ad_account
                 AND enabled AND unlinked_at IS NULL) THEN
    RAISE EXCEPTION 'ad_account_not_owned_or_disabled' USING ERRCODE = '42501';
  END IF;
  IF v->>'r' <> 'system' THEN
    SELECT max_daily_budget_usd INTO v_max FROM core.tenant_users
      WHERE telegram_user_id = (v->>'u')::bigint;     -- RLS يحصر بالـ tenant
    IF v_max IS NOT NULL AND p_budget > v_max THEN RAISE EXCEPTION 'budget_over_user_limit' USING ERRCODE = '42501'; END IF;
  END IF;
  INSERT INTO core.campaigns (tenant_id, platform, ad_account_external_id, external_id, name, objective, daily_budget_minor, status, created_by)
  VALUES (private.cur_tenant(), p_platform::core.platform, p_ad_account, p_external_id, p_name, p_objective, p_budget, 'PAUSED', nullif(v->>'u','')::bigint)
  RETURNING campaign_pk INTO v_id;
  INSERT INTO core.campaign_events (tenant_id, campaign_pk, actor_telegram_user_id, action, detail)
  VALUES (private.cur_tenant(), v_id, nullif(v->>'u','')::bigint, 'create', jsonb_build_object('budget', p_budget));
  RETURN v_id;
END $$;

-- منع تكرار الإنشاء: يُستدعى قبل أي مكالمة إنشاء خارجية
CREATE FUNCTION api.begin_campaign_request(p_ctx text, p_key text, p_hash bytea)
RETURNS TABLE (state text, result_ref text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
DECLARE r core.campaign_requests; n int;
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'manager');
  INSERT INTO core.campaign_requests (tenant_id, idempotency_key, request_hash, status)
  VALUES (private.cur_tenant(), p_key, p_hash, 'executing') ON CONFLICT (tenant_id, idempotency_key) DO NOTHING;
  GET DIAGNOSTICS n = ROW_COUNT;
  IF n = 1 THEN RETURN QUERY SELECT 'new'::text, NULL::text; RETURN; END IF;
  SELECT * INTO r FROM core.campaign_requests WHERE idempotency_key = p_key FOR UPDATE;
  IF r.request_hash <> p_hash THEN RETURN QUERY SELECT 'conflict'::text, NULL::text; RETURN; END IF;
  IF r.status = 'succeeded' THEN RETURN QUERY SELECT 'replay'::text, r.result_ref; RETURN; END IF;
  IF r.status = 'failed' THEN
    UPDATE core.campaign_requests SET status = 'executing', updated_at = now() WHERE request_id = r.request_id;
    RETURN QUERY SELECT 'new'::text, NULL::text; RETURN;
  END IF;
  IF r.status IN ('received','executing') AND r.updated_at > now() - interval '10 minutes' THEN
    RETURN QUERY SELECT 'in_progress'::text, NULL::text; RETURN;
  END IF;
  UPDATE core.campaign_requests SET status = 'needs_manual_check', updated_at = now() WHERE request_id = r.request_id;
  RETURN QUERY SELECT 'needs_manual_check'::text, r.result_ref;
END $$;

CREATE FUNCTION api.finish_campaign_request(p_ctx text, p_key text, p_status text, p_result_ref text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'manager');
  IF p_status NOT IN ('succeeded','failed','needs_manual_check') THEN RAISE EXCEPTION 'bad_status'; END IF;
  UPDATE core.campaign_requests SET status = p_status, result_ref = p_result_ref, updated_at = now()
   WHERE idempotency_key = p_key;
  IF NOT FOUND THEN RAISE EXCEPTION 'unknown_request' USING ERRCODE = 'P0002'; END IF;
END $$;

CREATE FUNCTION api.link_ad_account(p_ctx text, p_platform text, p_external_id text, p_connection_id uuid,
                                    p_name text, p_currency char) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'owner', false);       -- أثناء الربط قد لا يكون tenant READY بعد (system/owner)
  BEGIN
    INSERT INTO core.ad_accounts (tenant_id, platform, external_id, connection_id, name, currency)
    VALUES (private.cur_tenant(), p_platform::core.platform, p_external_id, p_connection_id, p_name, p_currency);
  EXCEPTION
    WHEN unique_violation THEN RAISE EXCEPTION 'account_already_linked' USING ERRCODE = '23505';
    WHEN foreign_key_violation THEN RAISE EXCEPTION 'connection_not_in_tenant_or_wrong_platform' USING ERRCODE = '23503';
  END;
END $$;

CREATE FUNCTION api.add_report_snapshot(p_ctx text, p_platform text, p_campaign text, p_taken_at timestamptz,
                                        p_spend numeric, p_impressions bigint, p_clicks bigint, p_messages int, p_currency char) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'system');
  INSERT INTO core.report_snapshots (tenant_id, platform, campaign_external_id, taken_at, spend, impressions, clicks, messages, currency)
  VALUES (private.cur_tenant(), p_platform::core.platform, p_campaign, p_taken_at, p_spend, p_impressions, p_clicks, p_messages, p_currency)
  ON CONFLICT DO NOTHING;
END $$;

CREATE FUNCTION api.get_report(p_ctx text, p_platform text, p_since timestamptz)
RETURNS TABLE (campaign_external_id text, taken_at timestamptz, spend numeric)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  RETURN QUERY SELECT s.campaign_external_id, s.taken_at, s.spend FROM core.report_snapshots s
   WHERE s.platform = p_platform::core.platform AND s.taken_at >= p_since ORDER BY s.taken_at;
END $$;

-- ctx اختياري: NULL = خطأ نظام (tenant_id NULL)
CREATE FUNCTION api.log_error(p_ctx text, p_class text, p_platform text, p_workflow text, p_node text,
                              p_execution text, p_code text, p_message text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private, ext AS $$
DECLARE v_t uuid; v_fp text;
BEGIN
  IF p_ctx IS NOT NULL THEN PERFORM private.enter_ctx(p_ctx, 'viewer', false); v_t := private.cur_tenant(); END IF;
  v_fp := encode(digest(concat_ws('|', p_class, p_platform, p_code, p_node), 'sha256'), 'hex');
  INSERT INTO core.error_log (tenant_id, class, platform, workflow, node, execution_id, code, message, fingerprint)
  VALUES (v_t, p_class::core.err_class, p_platform::core.platform, p_workflow, p_node, p_execution, p_code,
          -- طبقة دفاع ثانية: إخفاء أنماط التوكنات (المرشح الأساسي بالـ Broker)
          regexp_replace(regexp_replace(coalesce(p_message,''), '\d{8,10}:[A-Za-z0-9_-]{30,}', '[REDACTED]', 'g'),
                         'EAA[A-Za-z0-9]{20,}', '[REDACTED]', 'g'), v_fp);
END $$;

CREATE FUNCTION api.set_readiness(p_ctx text, p_code text, p_status text, p_evidence jsonb) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
DECLARE v_age interval;
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'system', false);
  SELECT max_age INTO v_age FROM core.readiness_check_defs WHERE check_code = p_code;
  IF NOT FOUND THEN RAISE EXCEPTION 'unknown_check' USING ERRCODE = 'P0002'; END IF;
  INSERT INTO core.readiness_checks (tenant_id, check_code, status, evidence, checked_at, expires_at)
  VALUES (private.cur_tenant(), p_code, p_status::core.check_status, coalesce(p_evidence, '{}'), now(), now() + v_age)
  ON CONFLICT (tenant_id, check_code) DO UPDATE
    SET status = EXCLUDED.status, evidence = EXCLUDED.evidence, checked_at = now(), expires_at = now() + v_age;
END $$;

CREATE FUNCTION api.promote_ready(p_ctx text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'system', false);
  UPDATE core.tenants SET status = 'READY' WHERE tenant_id = private.cur_tenant();   -- trigger يفرض الشروط
END $$;

CREATE FUNCTION api.search_knowledge(p_ctx text, p_query text) RETURNS TABLE (doc_id bigint, scope text, title text, body text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer');
  RETURN QUERY SELECT k.doc_id, k.scope, k.title, k.body FROM core.knowledge_docs k      -- RLS: global + tenant الحالي فقط
   WHERE k.title ILIKE '%' || p_query || '%' OR k.body ILIKE '%' || p_query || '%' LIMIT 20;
END $$;

CREATE FUNCTION api.list_errors(p_ctx text, p_limit int DEFAULT 50) RETURNS TABLE (error_id bigint, class core.err_class, code text, message text, occurred_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'viewer', false);
  RETURN QUERY SELECT e.error_id, e.class, e.code, e.message, e.occurred_at FROM core.error_log e ORDER BY e.occurred_at DESC LIMIT p_limit;
END $$;

CREATE FUNCTION api.add_tenant_knowledge(p_ctx text, p_title text, p_body text) RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
DECLARE v_id bigint;
BEGIN
  PERFORM private.enter_ctx(p_ctx, 'manager');
  INSERT INTO core.knowledge_docs (scope, tenant_id, title, body) VALUES ('tenant', private.cur_tenant(), p_title, p_body) RETURNING doc_id INTO v_id;
  RETURN v_id;
END $$;

-- ───────────── دوال عابرة للـ tenants (مالكها app_resolver) ─────────────
RESET ROLE;

CREATE FUNCTION api.resolve_context(p_bot_public_id text, p_secret_sha256 bytea, p_tg_user bigint)
RETURNS TABLE (ctx text, role text, config jsonb, features jsonb)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private, ext AS $$
DECLARE r record;
BEGIN
  SELECT b.bot_id, b.tenant_id, u.role::text AS urole, t.features AS feats, c.config AS cfg INTO r
  FROM core.bots b
  JOIN core.tenants t ON t.tenant_id = b.tenant_id AND t.status = 'READY'
  JOIN core.tenant_users u ON u.tenant_id = t.tenant_id AND u.telegram_user_id = p_tg_user AND u.active
  JOIN core.config_versions c ON c.tenant_id = t.tenant_id AND c.version = t.active_config_version
  WHERE b.bot_public_id = p_bot_public_id AND b.status = 'active'
    AND b.webhook_secret_hash = p_secret_sha256;
  IF NOT FOUND THEN RETURN; END IF;                 -- رد موحّد: لا كشف لسبب الرفض
  RETURN QUERY SELECT private.sign_ctx(jsonb_build_object(
      't', r.tenant_id, 'u', p_tg_user, 'r', r.urole, 'b', r.bot_id,
      'e', extract(epoch FROM now())::bigint + 600, 'k', 'user')),
    r.urole, r.cfg, r.feats;
END $$;
ALTER FUNCTION api.resolve_context(text, bytea, bigint) OWNER TO app_resolver;

-- مهام مجدولة: tenants الجاهزة التي فعّلت ميزة معيّنة (system ctx، صلاحية 15 دقيقة)
CREATE FUNCTION api.job_contexts(p_feature text, p_limit int DEFAULT 25, p_after uuid DEFAULT NULL)
RETURNS TABLE (tenant_id uuid, ctx text)
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
  SELECT t.tenant_id,
         private.sign_ctx(jsonb_build_object('t', t.tenant_id, 'r', 'system',
           'e', extract(epoch FROM now())::bigint + 900, 'k', 'system'))
  FROM core.tenants t
  WHERE t.status = 'READY' AND coalesce((t.features->>p_feature)::boolean, false)
    AND (p_after IS NULL OR t.tenant_id > p_after)
  ORDER BY t.tenant_id LIMIT p_limit
$$;
ALTER FUNCTION api.job_contexts(text, int, uuid) OWNER TO app_resolver;


-- Onboarding/Readiness: tenants بحالات غير READY (TESTING/NEEDS_REVIEW/..) تحتاج system ctx لتشغيل الفحوصات (job/readiness).
-- سياق محدود: لا يُسمح بتنفيذ الحملات به لأن enter_ctx يرفض tenant غير READY ما لم تطلب الدالة p_need_ready=false صراحة
-- (وهي فقط: set_readiness, promote_ready, link_ad_account, log_error).
CREATE FUNCTION api.job_contexts_for_status(p_statuses text[], p_limit int DEFAULT 25, p_after uuid DEFAULT NULL)
RETURNS TABLE (tenant_id uuid, status text, ctx text)
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
  SELECT t.tenant_id, t.status::text,
         private.sign_ctx(jsonb_build_object('t', t.tenant_id, 'r', 'system',
           'e', extract(epoch FROM now())::bigint + 900, 'k', 'system'))
  FROM core.tenants t
  WHERE t.status::text = ANY (p_statuses) AND t.status <> 'SUSPENDED'
    AND (p_after IS NULL OR t.tenant_id > p_after)
  ORDER BY t.tenant_id LIMIT p_limit
$$;
ALTER FUNCTION api.job_contexts_for_status(text[], int, uuid) OWNER TO app_resolver;

-- خفض READY تلقائياً إذا فشل/انتهى فحص إلزامي
CREATE FUNCTION api_admin.sweep_readiness() RETURNS int
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private AS $$
DECLARE n int;
BEGIN
  WITH bad AS (
    SELECT t.tenant_id FROM core.tenants t
    WHERE t.status = 'READY' AND EXISTS (
      SELECT 1 FROM core.readiness_check_defs d
      LEFT JOIN core.readiness_checks c ON c.tenant_id = t.tenant_id AND c.check_code = d.check_code
      WHERE d.mandatory AND (d.applies_when = 'always' OR coalesce((t.features->>d.applies_when)::boolean, false))
        AND (c.status IS DISTINCT FROM 'pass' OR c.expires_at <= now()))
  ) UPDATE core.tenants t SET status = 'NEEDS_REVIEW' FROM bad WHERE t.tenant_id = bad.tenant_id;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END $$;
ALTER FUNCTION api_admin.sweep_readiness() OWNER TO app_resolver;

-- ───────────── نشر معرفة عامة (إدارة فقط، بعد التنقية والموافقة) ─────────────
CREATE FUNCTION api_admin.publish_global_doc(p_title text, p_body text, p_source text, p_approved_by text) RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core AS $$
DECLARE v_id bigint;
BEGIN
  -- فحص تنقية آلي: لا أرقام طويلة (حسابات/حملات)، لا بريد، لا شبه توكن
  IF p_body ~ '\d{10,}' OR p_title ~ '\d{10,}' OR p_body ~ '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}'
     OR p_body ~ '[A-Za-z0-9_-]{30,}' THEN
    RAISE EXCEPTION 'sanitize_failed: contains identifiers/secrets-like content' USING ERRCODE = 'P0001';
  END IF;
  INSERT INTO core.knowledge_docs (scope, title, body, source, approved_by, approved_at)
  VALUES ('global', p_title, p_body, p_source, p_approved_by, now()) RETURNING doc_id INTO v_id;
  RETURN v_id;
END $$;
ALTER FUNCTION api_admin.publish_global_doc(text, text, text, text) OWNER TO app_ops_fn;

-- الدوال التي أُنشئت بـ superuser ثم نُقلت ملكيتها لا تتأثر بالافتراضيات أعلاه: نسحب PUBLIC صراحة
REVOKE ALL ON FUNCTION api.resolve_context(text, bytea, bigint), api.job_contexts(text, int, uuid), api.job_contexts_for_status(text[], int, uuid),
  api_admin.sweep_readiness(), api_admin.publish_global_doc(text, text, text, text) FROM PUBLIC;
-- ───────────── منح EXECUTE (أقل صلاحية) ─────────────
-- Workflows التفاعلية (Ingress/mod): app_runtime
GRANT EXECUTE ON FUNCTION
  api.claim_update(text, bigint), api.list_campaigns(text, text),
  api.record_campaign(text, text, text, text, text, text, numeric),
  api.begin_campaign_request(text, text, bytea), api.finish_campaign_request(text, text, text, text),
  api.get_report(text, text, timestamptz),
  api.log_error(text, text, text, text, text, text, text, text),
  api.search_knowledge(text, text), api.list_errors(text, int), api.add_tenant_knowledge(text, text, text),
  api.resolve_context(text, bytea, bigint)
TO app_runtime;
-- Workflows المجدولة (job/*): app_jobs. هو فقط من يستطيع طلب system ctx. لا يستدعي resolve_context.
GRANT EXECUTE ON FUNCTION
  api.job_contexts(text, int, uuid), api.job_contexts_for_status(text[], int, uuid), api.add_report_snapshot(text, text, text, timestamptz, numeric, bigint, bigint, int, char),
  api.set_readiness(text, text, text, jsonb), api.promote_ready(text),
  api.link_ad_account(text, text, text, uuid, text, char),
  api.list_campaigns(text, text), api.record_campaign(text, text, text, text, text, text, numeric),
  api.begin_campaign_request(text, text, bytea), api.finish_campaign_request(text, text, text, text),
  api.log_error(text, text, text, text, text, text, text, text),
  api.get_report(text, text, timestamptz)
TO app_jobs;
-- الربط (link_ad_account) يتم من job/onboarding بـ system ctx بعد تحقق الصلاحيات الفعلية (القسم 9)، لا من رسالة مستخدم.
GRANT EXECUTE ON FUNCTION api_admin.sweep_readiness(), api_admin.publish_global_doc(text, text, text, text) TO app_ops;
-- الدوال المساعدة private.* لا تُمنح لأي دور ثانٍ غير مالكيها (SECURITY DEFINER يستدعيها بصلاحية المالك).
-- app_resolver يحتاج EXECUTE على private.sign_ctx لأن resolve_context/job_contexts يعملان بصلاحيته:
GRANT EXECUTE ON FUNCTION private.sign_ctx(jsonb) TO app_resolver;

REVOKE CREATE ON SCHEMA api, api_admin, private FROM app_resolver, app_ops_fn;
