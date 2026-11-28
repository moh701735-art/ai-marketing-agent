-- 81_web_portal.sql : بوابة الزبائن على الويب (web_portal/). مخطط جديد مستقل (web) + دور web_rt؛ لا يغيّر أي جدول/دالة موجودة.
-- الصلاحية الوحيدة خارج المخطط: CONNECT على قاعدة central للدور الجديد web_rt. الدور ما يملك أي صلاحية على api.* ولا core.*.
-- يُطبَّق يدوياً (مثل 72/74/80) عبر ops/web-portal.py، مو عبر update.sh. التراجع: 81_web_portal_down.sql.
-- الدخول بدعوة من المدير فقط (ما فيه تسجيل مفتوح). كلمات السر تُخزَّن scrypt (يحسبها الـservice)، والجلسات تُخزَّن كـsha256 فقط.
\set ON_ERROR_STOP on
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'web_rt') THEN CREATE ROLE web_rt NOLOGIN; END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS web AUTHORIZATION app_owner;
REVOKE ALL ON SCHEMA web FROM PUBLIC;
SET ROLE app_owner;

CREATE TABLE IF NOT EXISTS web.users (
  user_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  email text NOT NULL CHECK (char_length(email) BETWEEN 5 AND 120 AND email ~ '^[^@[:space:]]+@[^@[:space:]]+[.][^@[:space:]]+$'),
  pwd text CHECK (pwd IS NULL OR pwd ~ '^scrypt[$][0-9]{1,2}[$][0-9]{1,2}[$][0-9]{1,2}[$][A-Za-z0-9+/=_-]{8,64}[$][A-Za-z0-9+/=_-]{32,128}$'),
  status text NOT NULL DEFAULT 'invited' CHECK (status IN ('invited','active','disabled')),
  failed int NOT NULL DEFAULT 0,
  locked_until timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  last_login_at timestamptz);
CREATE UNIQUE INDEX IF NOT EXISTS web_users_email_uq ON web.users (lower(email));
CREATE INDEX IF NOT EXISTS web_users_tenant_idx ON web.users (tenant_id);

CREATE TABLE IF NOT EXISTS web.invites (
  token_hash text PRIMARY KEY CHECK (token_hash ~ '^[0-9a-f]{64}$'),
  user_id uuid NOT NULL REFERENCES web.users(user_id) ON DELETE CASCADE,
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS web.sessions (
  session_hash text PRIMARY KEY CHECK (session_hash ~ '^[0-9a-f]{64}$'),
  user_id uuid NOT NULL REFERENCES web.users(user_id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL);
CREATE INDEX IF NOT EXISTS web_sessions_user_idx ON web.sessions (user_id);
REVOKE ALL ON web.users, web.invites, web.sessions FROM PUBLIC;

-- (إدارة فقط، بدون صلاحية لـ web_rt) دعوة/إعادة تعيين كلمة سر: الرمز يُولَّد بالأداة ويُخزَّن هاشه فقط
CREATE OR REPLACE FUNCTION web.invite_create(p_slug text, p_email text, p_hash text, p_ttl_h int) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, web AS $$
DECLARE v_tid uuid; v_uid uuid; v_email text := lower(btrim(p_email));
BEGIN
  SELECT tenant_id INTO v_tid FROM core.tenants WHERE slug = p_slug;
  IF v_tid IS NULL THEN RAISE EXCEPTION 'tenant_not_found' USING ERRCODE = '22023'; END IF;
  IF p_ttl_h IS NULL OR p_ttl_h NOT BETWEEN 1 AND 168 THEN RAISE EXCEPTION 'bad_ttl' USING ERRCODE = '22023'; END IF;
  SELECT user_id INTO v_uid FROM web.users WHERE lower(email) = v_email;
  IF v_uid IS NOT NULL AND (SELECT tenant_id FROM web.users WHERE user_id = v_uid) <> v_tid THEN RAISE EXCEPTION 'email_belongs_to_other_tenant' USING ERRCODE = '23505'; END IF;
  IF v_uid IS NULL THEN INSERT INTO web.users (tenant_id, email) VALUES (v_tid, v_email) RETURNING user_id INTO v_uid; END IF;
  INSERT INTO web.invites (token_hash, user_id, expires_at) VALUES (p_hash, v_uid, now() + make_interval(hours => p_ttl_h));
  RETURN jsonb_build_object('user_id', v_uid, 'email', v_email);
END $$;

-- قبول الدعوة: يضع كلمة السر (scrypt جاهزة) ويفعّل الحساب ويلغي كل جلساته القديمة
CREATE OR REPLACE FUNCTION web.invite_accept(p_hash text, p_pwd text) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, web AS $$
DECLARE v_uid uuid; v_email text;
BEGIN
  UPDATE web.invites i SET used_at = now() WHERE i.token_hash = p_hash AND i.used_at IS NULL AND i.expires_at > now() RETURNING i.user_id INTO v_uid;
  IF v_uid IS NULL THEN RAISE EXCEPTION 'invite_invalid' USING ERRCODE = '28000'; END IF;
  UPDATE web.users SET pwd = p_pwd, status = 'active', failed = 0, locked_until = NULL WHERE user_id = v_uid AND status <> 'disabled' RETURNING email INTO v_email;
  IF v_email IS NULL THEN RAISE EXCEPTION 'user_disabled' USING ERRCODE = '28000'; END IF;
  DELETE FROM web.sessions WHERE user_id = v_uid;
  RETURN jsonb_build_object('user_id', v_uid, 'email', v_email);
END $$;

CREATE OR REPLACE FUNCTION web.invite_peek(p_hash text) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, web AS $$
  SELECT jsonb_build_object('email', u.email) FROM web.invites i JOIN web.users u ON u.user_id = i.user_id
  WHERE i.token_hash = p_hash AND i.used_at IS NULL AND i.expires_at > now() AND u.status <> 'disabled' $$;

CREATE OR REPLACE FUNCTION web.login_lookup(p_email text) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, web AS $$
  SELECT jsonb_build_object('user_id', u.user_id, 'pwd', u.pwd, 'locked', (u.locked_until IS NOT NULL AND u.locked_until > now()), 'active', u.status = 'active')
  FROM web.users u WHERE lower(u.email) = lower(btrim(p_email)) $$;

CREATE OR REPLACE FUNCTION web.login_fail(p_user uuid) RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, web AS $$
  UPDATE web.users SET failed = CASE WHEN failed + 1 >= 5 THEN 0 ELSE failed + 1 END,
                       locked_until = CASE WHEN failed + 1 >= 5 THEN now() + interval '15 minutes' ELSE locked_until END
  WHERE user_id = p_user $$;

CREATE OR REPLACE FUNCTION web.login_ok(p_user uuid) RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, web AS $$
  UPDATE web.users SET failed = 0, locked_until = NULL, last_login_at = now() WHERE user_id = p_user $$;

CREATE OR REPLACE FUNCTION web.session_create(p_user uuid, p_hash text, p_ttl_h int) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, web AS $$
BEGIN
  IF p_ttl_h IS NULL OR p_ttl_h NOT BETWEEN 1 AND 720 THEN RAISE EXCEPTION 'bad_ttl' USING ERRCODE = '22023'; END IF;
  DELETE FROM web.sessions WHERE expires_at <= now();
  INSERT INTO web.sessions (session_hash, user_id, expires_at) VALUES (p_hash, p_user, now() + make_interval(hours => p_ttl_h));
  DELETE FROM web.sessions WHERE user_id = p_user AND session_hash NOT IN (SELECT session_hash FROM web.sessions WHERE user_id = p_user ORDER BY created_at DESC LIMIT 5);
END $$;

CREATE OR REPLACE FUNCTION web.session_get(p_hash text) RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, core, web AS $$
  SELECT jsonb_build_object('user_id', u.user_id, 'email', u.email, 'tenant_id', t.tenant_id, 'slug', t.slug, 'name', t.display_name, 'status', t.status::text)
  FROM web.sessions s JOIN web.users u ON u.user_id = s.user_id AND u.status = 'active' JOIN core.tenants t ON t.tenant_id = u.tenant_id
  WHERE s.session_hash = p_hash AND s.expires_at > now() $$;

CREATE OR REPLACE FUNCTION web.session_delete(p_hash text) RETURNS void
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, web AS $$ DELETE FROM web.sessions WHERE session_hash = p_hash $$;

-- الـctx يُوقَّع ويُستعمل داخل القاعدة فقط ولا يرجع للخدمة أبداً. enter_ctx الحي يرفض أي دور غير 'system' ما له سجل بـcore.tenant_users (مستخدمو تليجرام)،
-- فنستعمل نفس شكل ctx اللي توقّعه api.job_context_for_slug (r=system,k=system) لكن بصلاحية ضيّقة: الدالتان أدناه فقط (قراءة)، لعميل المستخدم فقط، 5 دقائق.
DROP FUNCTION IF EXISTS web.ctx(uuid);
CREATE OR REPLACE FUNCTION web.accounts(p_user uuid) RETURNS TABLE (platform text, external_id text, name text, currency text, status text, enabled boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private, web AS $$
DECLARE v_tid uuid; v_ctx text;
BEGIN
  SELECT t.tenant_id INTO v_tid FROM web.users u JOIN core.tenants t ON t.tenant_id = u.tenant_id WHERE u.user_id = p_user AND u.status = 'active' AND t.status::text <> 'CANCELLED';
  IF v_tid IS NULL THEN RETURN; END IF;
  v_ctx := private.sign_ctx(jsonb_build_object('t', v_tid, 'r', 'system', 'e', extract(epoch FROM now())::bigint + 300, 'k', 'system'));
  RETURN QUERY SELECT a.platform, a.external_id, a.name, a.currency, a.status, a.enabled FROM api.list_ad_accounts(v_ctx) a;
END $$;

CREATE OR REPLACE FUNCTION web.campaigns(p_user uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, core, private, web AS $$
DECLARE v_tid uuid; v_ctx text; v_out jsonb;
BEGIN
  SELECT t.tenant_id INTO v_tid FROM web.users u JOIN core.tenants t ON t.tenant_id = u.tenant_id WHERE u.user_id = p_user AND u.status = 'active' AND t.status::text <> 'CANCELLED';
  IF v_tid IS NULL THEN RETURN '[]'::jsonb; END IF;
  v_ctx := private.sign_ctx(jsonb_build_object('t', v_tid, 'r', 'system', 'e', extract(epoch FROM now())::bigint + 300, 'k', 'system'));
  SELECT coalesce(jsonb_agg(jsonb_build_object('name', coalesce(j->>'name', j->>'campaign_name'), 'external_id', j->>'external_id', 'status', j->>'status', 'created_at', j->>'created_at')), '[]'::jsonb)
    INTO v_out FROM (SELECT to_jsonb(x) AS j FROM api.list_campaigns(v_ctx, NULL) x LIMIT 50) s;
  RETURN v_out;
END $$;

ALTER FUNCTION web.invite_create(text, text, text, int) OWNER TO app_owner;
ALTER FUNCTION web.invite_accept(text, text) OWNER TO app_owner;
ALTER FUNCTION web.invite_peek(text) OWNER TO app_owner;
ALTER FUNCTION web.login_lookup(text) OWNER TO app_owner;
ALTER FUNCTION web.login_fail(uuid) OWNER TO app_owner;
ALTER FUNCTION web.login_ok(uuid) OWNER TO app_owner;
ALTER FUNCTION web.session_create(uuid, text, int) OWNER TO app_owner;
ALTER FUNCTION web.session_get(text) OWNER TO app_owner;
ALTER FUNCTION web.session_delete(text) OWNER TO app_owner;
ALTER FUNCTION web.accounts(uuid) OWNER TO app_owner;
ALTER FUNCTION web.campaigns(uuid) OWNER TO app_owner;
REVOKE ALL ON FUNCTION web.invite_create(text, text, text, int), web.invite_accept(text, text), web.invite_peek(text), web.login_lookup(text), web.login_fail(uuid), web.login_ok(uuid),
  web.session_create(uuid, text, int), web.session_get(text), web.session_delete(text), web.accounts(uuid), web.campaigns(uuid) FROM PUBLIC;
RESET ROLE;
-- الدور الجديد يحتاج صلاحية الاتصال بقاعدة central (الحية تمنعها عن PUBLIC): خطأ حي: «permission denied for database»
DO $$ BEGIN EXECUTE format('GRANT CONNECT ON DATABASE %I TO web_rt', current_database()); END $$;
GRANT USAGE ON SCHEMA web TO web_rt;
GRANT EXECUTE ON FUNCTION web.invite_accept(text, text), web.invite_peek(text), web.login_lookup(text), web.login_fail(uuid), web.login_ok(uuid),
  web.session_create(uuid, text, int), web.session_get(text), web.session_delete(text), web.accounts(uuid), web.campaigns(uuid) TO web_rt;
-- web.invite_create = إدارة فقط (يُنفَّذ بـpostgres من ops/web-portal.py)؛ لا صلاحية لـ web_rt.
-- نسخة سابقة (قبل هذا التعديل) منحت web_rt صلاحيات مباشرة على api.list_*؛ نسحبها (آمن لو ما كانت موجودة)
REVOKE EXECUTE ON FUNCTION api.list_ad_accounts(text), api.list_campaigns(text, text), api.list_pages(text) FROM web_rt;
REVOKE USAGE ON SCHEMA api FROM web_rt;
