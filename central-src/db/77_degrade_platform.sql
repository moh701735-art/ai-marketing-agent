-- 77_degrade_platform.sql (p293): لمّا الـBroker يعلّم اتصال منصة «expired»، تُطفّأ تلك المنصة لنفس العميل تلقائياً (features.<platform>=false)
-- حتى لا تُسكِت منصةٌ واحدة فاشلة بوت العميل كله (فحوصات R05..R09 تنطبق حسب الميزة، وR08/R12 تتجاهل حسابات المنصة المطفّأة: p198).
-- لا يكتب أي pass ولا يغيّر status العميل ولا يرجّع شي تلقائياً. التفعيل يرجع فقط بالأدوات بعد تجديد التوكن (ops/platform-enable.py، link-*، relink-*).
-- يعدّل نص الدالة الحية بحقن كتلة بعد «GET DIAGNOSTICS <v> = ROW_COUNT;» (مرساة واحدة بالضبط، وإلا يفشل بلا تغيير). idempotent بعلامة p293_degrade.
DO $m$
DECLARE
  sig regprocedure; d text; v text; newd text; cnt int;
BEGIN
  SELECT p.oid::regprocedure INTO sig FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'api' AND p.proname = 'broker_report_connection';
  IF sig IS NULL THEN RAISE EXCEPTION 'p293: api.broker_report_connection not found'; END IF;
  d := pg_get_functiondef(sig);
  IF d LIKE '%p293_degrade%' THEN RAISE NOTICE 'p293 already applied'; RETURN; END IF;
  IF d !~* 'p_platform' OR d !~* 'p_secret_ref' OR d !~* 'p_status' THEN RAISE EXCEPTION 'p293: unexpected function signature: %', sig; END IF;
  SELECT count(*) INTO cnt FROM regexp_matches(d, 'GET\s+DIAGNOSTICS\s+\w+\s*=\s*ROW_COUNT\s*;', 'gi');
  IF cnt <> 1 THEN RAISE EXCEPTION 'p293: anchor GET DIAGNOSTICS ... ROW_COUNT count=% (expected 1)', cnt; END IF;
  v := (regexp_match(d, 'GET\s+DIAGNOSTICS\s+(\w+)\s*=\s*ROW_COUNT\s*;', 'i'))[1];
  newd := regexp_replace(d, '(GET\s+DIAGNOSTICS\s+\w+\s*=\s*ROW_COUNT\s*;)',
    E'\\1\n  /* p293_degrade */\n  IF p_status = ''expired'' AND ' || v || E' > 0 THEN\n'
    || E'    UPDATE core.tenants t SET features = coalesce(t.features, ''{}''::jsonb) || jsonb_build_object(p_platform::text, false)\n'
    || E'     WHERE t.tenant_id IN (SELECT c.tenant_id FROM core.platform_connections c WHERE c.platform = p_platform::core.platform AND c.secret_ref = p_secret_ref)\n'
    || E'       AND NOT EXISTS (SELECT 1 FROM core.platform_connections c2 WHERE c2.tenant_id = t.tenant_id AND c2.platform = p_platform::core.platform AND c2.status = ''active'');\n'
    || E'  END IF;', 'i');
  IF newd = d OR newd NOT LIKE '%p293_degrade%' THEN RAISE EXCEPTION 'p293: rewrite failed'; END IF;
  EXECUTE newd;
  RAISE NOTICE 'p293 applied to %', sig;
END
$m$;
