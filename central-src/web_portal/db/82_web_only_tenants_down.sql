-- يرجّع R02/R03/R04 'always' وشرط R01 الأصلي. يرفض لو يوجد زبائن ويب (كانوا راح يصيرون غير صالحين).
\set ON_ERROR_STOP on
BEGIN;
DO $$ BEGIN IF EXISTS (SELECT 1 FROM core.tenants WHERE coalesce((features->>'web_only')::boolean, false)) THEN RAISE EXCEPTION 'web_only tenants exist; remove/convert them first'; END IF; END $$;
DROP TRIGGER IF EXISTS tenants_default_telegram ON core.tenants;
DROP FUNCTION IF EXISTS private.tenants_default_telegram();
UPDATE core.readiness_check_defs SET applies_when = 'always' WHERE check_code IN ('R02','R03','R04');
DO $$
DECLARE d text; n text := '(coalesce((t.features->>''web_only'')::boolean, false) OR (v_owners >= 1 AND v_bots >= 1)) THEN ''pass'''; o text := 'v_owners >= 1 AND v_bots >= 1 THEN ''pass'''; cnt int;
BEGIN
  SELECT pg_get_functiondef('api.readiness_local(text)'::regprocedure) INTO d;
  cnt := (length(d) - length(replace(d, n, ''))) / length(n);
  IF cnt = 0 THEN RETURN; END IF;
  IF cnt <> 1 THEN RAISE EXCEPTION 'unexpected R01 shape (%); nothing changed', cnt; END IF;
  EXECUTE replace(d, n, o);
END $$;
COMMIT;
