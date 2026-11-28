-- 83_web_links.sql : طلبات ربط تيك توك من بوابة الويب. الموقع (المكشوف للإنترنت) يكتب طلب فقط (رمز تفويض لمرة وحدة + state)؛ عامل خاص على السيرفر (ops/web-linker.py) هو الوحيد اللي يبدّل الرمز
-- بتوكن ويحفظه بالخزنة ويربط الحسابات. الموقع ما يمسك توكن ولا مفتاح. فقط مخطط web (يُطبَّق بعد 81). التراجع: 83_web_links_down.sql
\set ON_ERROR_STOP on
SET ROLE app_owner;

CREATE TABLE IF NOT EXISTS web.link_states (
  state_hash text PRIMARY KEY CHECK (state_hash ~ '^[0-9a-f]{64}$'),
  user_id uuid NOT NULL REFERENCES web.users(user_id) ON DELETE CASCADE,
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS web.link_requests (
  req_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES web.users(user_id) ON DELETE CASCADE,
  tenant_id uuid NOT NULL,
  platform text NOT NULL DEFAULT 'tiktok' CHECK (platform IN ('tiktok')),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processing','done','failed','expired')),
  auth_code text CHECK (auth_code IS NULL OR auth_code ~ '^[A-Za-z0-9._~+/=-]{8,255}$'),
  message text,
  result jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS web_link_requests_user_idx ON web.link_requests (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS web_link_requests_status_idx ON web.link_requests (status) WHERE status IN ('pending','processing');
REVOKE ALL ON web.link_states, web.link_requests FROM PUBLIC;

-- state جديد (حماية OAuth من CSRF): يُخزَّن هاشه فقط، صلاحية 15 دقيقة
CREATE OR REPLACE FUNCTION web.link_state_new(p_user uuid, p_hash text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, web AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM web.users WHERE user_id = p_user AND status = 'active') THEN RAISE EXCEPTION 'user_inactive' USING ERRCODE = '28000'; END IF;
  DELETE FROM web.link_states WHERE expires_at < now() - interval '1 day';
  INSERT INTO web.link_states (state_hash, user_id, expires_at) VALUES (p_hash, p_user, now() + interval '15 minutes');
END $$;

-- بداية الطلب: يتحقق من state (لنفس المستخدم، غير مستعمل، غير منتهي)، ويرفض لو عنده طلب جاري. يرجع req_id
CREATE OR REPLACE FUNCTION web.link_begin(p_user uuid, p_state_hash text, p_code text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, web AS $$
DECLARE v_tid uuid; v_req uuid;
BEGIN
  UPDATE web.link_states SET used_at = now() WHERE state_hash = p_state_hash AND user_id = p_user AND used_at IS NULL AND expires_at > now();
  IF NOT FOUND THEN RAISE EXCEPTION 'state_invalid' USING ERRCODE = '28000'; END IF;
  SELECT tenant_id INTO v_tid FROM web.users WHERE user_id = p_user AND status = 'active';
  IF v_tid IS NULL THEN RAISE EXCEPTION 'user_inactive' USING ERRCODE = '28000'; END IF;
  IF EXISTS (SELECT 1 FROM web.link_requests WHERE user_id = p_user AND status IN ('pending','processing') AND created_at > now() - interval '15 minutes') THEN RAISE EXCEPTION 'request_in_progress' USING ERRCODE = '55000'; END IF;
  INSERT INTO web.link_requests (user_id, tenant_id, auth_code) VALUES (p_user, v_tid, p_code) RETURNING req_id INTO v_req;
  RETURN jsonb_build_object('req_id', v_req);
END $$;

-- آخر طلب للمستخدم (للعرض): بدون الرمز نفسه
CREATE OR REPLACE FUNCTION web.link_status(p_user uuid) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, web AS $$
  SELECT jsonb_build_object('req_id', r.req_id, 'status', r.status, 'message', r.message, 'result', r.result, 'created_at', r.created_at)
  FROM web.link_requests r WHERE r.user_id = p_user ORDER BY r.created_at DESC LIMIT 1 $$;

ALTER FUNCTION web.link_state_new(uuid, text) OWNER TO app_owner;
ALTER FUNCTION web.link_begin(uuid, text, text) OWNER TO app_owner;
ALTER FUNCTION web.link_status(uuid) OWNER TO app_owner;
REVOKE ALL ON FUNCTION web.link_state_new(uuid, text), web.link_begin(uuid, text, text), web.link_status(uuid) FROM PUBLIC;
RESET ROLE;
GRANT EXECUTE ON FUNCTION web.link_state_new(uuid, text), web.link_begin(uuid, text, text), web.link_status(uuid) TO web_rt;
-- العامل (ops/web-linker.py) يشتغل بصلاحية postgres عبر docker exec مثل أدوات الربط الحالية؛ ما نحتاج دور له.
