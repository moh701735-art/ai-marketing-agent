-- 82_web_only_tenants.sql : زبائن الويب بدون تليجرام. تغيير مركزي ضيّق ومحمي (يمس حارس الجاهزية، فكل خطوة fail-closed):
--  1) فحوصات R02/R03/R04 (بوت/webhook/مالك تليجرام) تنطبق فقط على من features.telegram=true (كانت 'always').
--  2) كل الزبائن الحاليين يأخذون telegram=true بنفس العملية (يبقون يخضعون للفحوصات الثلاثة كما كانوا) + مشغّل يضيف telegram=true لأي زبون جديد ما حدد المفتاح صراحةً (فشل آمن).
--  3) فحص R01 (tenant_record_valid) داخل api.readiness_local: شرط «مالك + بوت» يُتخطى فقط عندما features.web_only=true؛ بقية الزبائن نفس الشرط حرفياً.
--  الحسابات/R08/R05..: زبون الويب ما يصير READY إلا بعد ربط حساب إعلاني (نفس بقية الفحوصات). guard_ready/sweep_readiness ما انلمسا.
-- يُطبَّق يدوياً بـops/web-portal.py enable-web-tenants. التراجع: 82_web_only_tenants_down.sql
\set ON_ERROR_STOP on
BEGIN;

DO $$ BEGIN
  IF (SELECT count(*) FROM core.readiness_check_defs WHERE check_code IN ('R02','R03','R04')) <> 3 THEN RAISE EXCEPTION 'readiness defs R02/R03/R04 not found (unexpected schema)'; END IF;
END $$;

-- (2) الزبائن الحاليون أولاً، حتى ما يوجد لحظة تنطبق فيها الفحوصات بدون المفتاح
SET LOCAL session_replication_role = replica;   -- تحديث بيانات فقط (بدون تشغيل guard_ready)؛ ينتهي بنهاية الـtransaction
UPDATE core.tenants SET features = coalesce(features, '{}'::jsonb) || '{"telegram": true}'::jsonb
 WHERE NOT (coalesce(features, '{}'::jsonb) ? 'telegram') AND NOT coalesce((features->>'web_only')::boolean, false);
SET LOCAL session_replication_role = origin;

CREATE OR REPLACE FUNCTION private.tenants_default_telegram() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT (coalesce(NEW.features, '{}'::jsonb) ? 'telegram') THEN NEW.features := coalesce(NEW.features, '{}'::jsonb) || '{"telegram": true}'::jsonb; END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS tenants_default_telegram ON core.tenants;
CREATE TRIGGER tenants_default_telegram BEFORE INSERT ON core.tenants FOR EACH ROW EXECUTE FUNCTION private.tenants_default_telegram();

-- (1) الانطباق
UPDATE core.readiness_check_defs SET applies_when = 'telegram' WHERE check_code IN ('R02','R03','R04') AND applies_when IN ('always','telegram');

-- (3) R01: استبدال نصي دقيق (مرة واحدة بالضبط) وإلا فشل كل شي
DO $$
DECLARE d text; o text := 'v_owners >= 1 AND v_bots >= 1 THEN ''pass'''; n text := '(coalesce((t.features->>''web_only'')::boolean, false) OR (v_owners >= 1 AND v_bots >= 1)) THEN ''pass'''; cnt int;
BEGIN
  SELECT pg_get_functiondef('api.readiness_local(text)'::regprocedure) INTO d;
  IF position('web_only' IN d) > 0 THEN RAISE NOTICE 'api.readiness_local already patched'; RETURN; END IF;
  cnt := (length(d) - length(replace(d, o, ''))) / length(o);
  IF cnt <> 1 THEN RAISE EXCEPTION 'R01 predicate found % times in api.readiness_local (expected exactly 1); nothing changed', cnt; END IF;
  EXECUTE replace(d, o, n);
END $$;
COMMIT;
