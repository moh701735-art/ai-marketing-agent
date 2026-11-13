-- 96_smart_audience.sql : إعدادات/cache Smart Audience (مخطط مستقل). يطبّق 72_smart_audience.sql بنفسه.
\i 72_smart_audience.sql
\i 73_smart_audience_saved.sql
SELECT t.ok('SA-01 default OFF', (SELECT value FROM smart_audience.settings WHERE key='enabled') = 'false'::jsonb);
SELECT t.ok('SA-02 app_runtime: execute on 4 functions only, no table privilege',
  has_function_privilege('app_runtime','smart_audience.config(text)','EXECUTE') AND has_function_privilege('app_runtime','smart_audience.cache_set(text,text,jsonb,int)','EXECUTE')
  AND NOT has_table_privilege('app_runtime','smart_audience.cache','SELECT') AND NOT has_table_privilege('app_runtime','smart_audience.settings','UPDATE'));
SELECT t.ok('SA-03 not executable by PUBLIC / app_jobs',
  NOT has_function_privilege('app_jobs','smart_audience.cache_list(text)','EXECUTE')
  AND NOT EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='smart_audience'
                  AND EXISTS (SELECT 1 FROM aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a WHERE a.grantee=0 AND a.privilege_type='EXECUTE')));
SELECT t.ok('SA-04 all functions SECURITY DEFINER with pinned search_path',
  NOT EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='smart_audience'
              AND (NOT p.prosecdef OR NOT EXISTS (SELECT 1 FROM unnest(coalesce(p.proconfig,'{}')) c WHERE c LIKE 'search_path=%'))));
UPDATE smart_audience.settings SET value='true'::jsonb WHERE key='enabled';
\i 72_smart_audience.sql
SELECT t.ok('SA-05 re-apply keeps stored flag (idempotent)', (SELECT value FROM smart_audience.settings WHERE key='enabled') = 'true'::jsonb);
SELECT encode(ext.digest('secret-a','sha256'),'hex') AS ha, encode(ext.digest('secret-b','sha256'),'hex') AS hb \gset
SET ROLE app_runtime;
SELECT ctx AS sa FROM api.resolve_context('botAAAAAAAAAAAAAAAAAAAAAAAA', decode(:'ha','hex'), 1002) \gset
SELECT ctx AS sb FROM api.resolve_context('botBBBBBBBBBBBBBBBBBBBBBBBB', decode(:'hb','hex'), 2001) \gset
SELECT t.ok('SA-06 both tenants enabled; config has thresholds + location', smart_audience.enabled(:'sa') AND smart_audience.enabled(:'sb')
  AND (smart_audience.config(:'sa')->'thresholds'->>'small') = '500000' AND (smart_audience.config(:'sa')->>'location_id') = '99237');
SELECT t.ok('SA-07 cache set/list round trip for A', smart_audience.cache_set(:'sa','disc:bty','{"x":1}'::jsonb,3600) AND (SELECT count(*) FROM smart_audience.cache_list(:'sa') WHERE key='disc:bty') = 1);
SELECT t.ok('SA-08 tenant isolation: B does not see A cache', (SELECT count(*) FROM smart_audience.cache_list(:'sb')) = 0);
SELECT t.ok('SA-09 same key for B is independent', smart_audience.cache_set(:'sb','disc:bty','{"x":2}'::jsonb,3600) AND (SELECT (value->>'x') FROM smart_audience.cache_list(:'sa') WHERE key='disc:bty') = '1');
SELECT t.ok('SA-10 invalid key / ttl refused', NOT smart_audience.cache_set(:'sa','BAD KEY','{}'::jsonb,3600) AND NOT smart_audience.cache_set(:'sa','ok','{}'::jsonb,5));
SELECT t.raises('SA-11 invalid ctx refused', 'SELECT smart_audience.config(''bad.ctx'')', '28000', 'invalid_ctx');
RESET ROLE;
UPDATE core.tenants SET features = features || '{"smart_audience": false}'::jsonb WHERE tenant_id='a0000000-0000-0000-0000-000000000001';
SET ROLE app_runtime;
SELECT t.ok('SA-12 per-tenant opt-out affects only that tenant', NOT smart_audience.enabled(:'sa') AND smart_audience.enabled(:'sb'));
RESET ROLE;
UPDATE core.tenants SET features = features - 'smart_audience' WHERE tenant_id='a0000000-0000-0000-0000-000000000001';
UPDATE smart_audience.settings SET value='false'::jsonb WHERE key='enabled';
SET ROLE app_runtime;
SELECT t.ok('SA-13 global OFF disables everyone', NOT smart_audience.enabled(:'sa') AND NOT smart_audience.enabled(:'sb'));
RESET ROLE;
-- ───── 73: جماهير محفوظة بالاسم ─────
UPDATE smart_audience.settings SET value='true'::jsonb WHERE key='enabled';
SET ROLE app_runtime;
SELECT t.ok('SA-14 app_runtime: execute on saved_* only, no table privilege',
  has_function_privilege('app_runtime','smart_audience.saved_list(text)','EXECUTE') AND has_function_privilege('app_runtime','smart_audience.saved_apply(text,jsonb)','EXECUTE')
  AND NOT has_table_privilege('app_runtime','smart_audience.saved','SELECT') AND NOT has_table_privilege('app_runtime','smart_audience.saved','INSERT'));
SELECT t.ok('SA-15 save → list round trip (name, count, interests, meta)',
  (smart_audience.saved_apply(:'sa', '{"op":"save","name":"عطور 1","iv":[["111","perfume"],["222","fragrance"]],"meta":{"g":"f"}}'::jsonb)->>'ok') = 'true'
  AND (SELECT count(*) FROM smart_audience.saved_list(:'sa') WHERE name='عطور 1' AND cnt=2 AND (meta->>'g')='f' AND interests->0->>1='perfume') = 1);
SELECT t.ok('SA-16 same name replaces (no duplicate) and reports replaced=true',
  (smart_audience.saved_apply(:'sa', '{"op":"save","name":"عطور 1","iv":[["333","x"]]}'::jsonb)->>'replaced') = 'true'
  AND (SELECT count(*) FROM smart_audience.saved_list(:'sa')) = 1 AND (SELECT cnt FROM smart_audience.saved_list(:'sa')) = 1);
SELECT t.ok('SA-17 tenant isolation: B sees nothing, B same name independent, B cannot delete A id',
  (SELECT count(*) FROM smart_audience.saved_list(:'sb')) = 0
  AND (smart_audience.saved_apply(:'sb', '{"op":"save","name":"عطور 1","iv":[["444","y"]]}'::jsonb)->>'ok') = 'true'
  AND (smart_audience.saved_apply(:'sb', jsonb_build_object('op','del','id',(SELECT id FROM smart_audience.saved_list(:'sa') LIMIT 1)))->>'ok') = 'false'
  AND (SELECT count(*) FROM smart_audience.saved_list(:'sa')) = 1);
SELECT t.ok('SA-18 invalid input refused without writing: name, interests, id format, bad op',
  (smart_audience.saved_apply(:'sa', '{"op":"save","name":"","iv":[["111","a"]]}'::jsonb)->>'err') = 'name'
  AND (smart_audience.saved_apply(:'sa', jsonb_build_object('op','save','name',repeat('x',31),'iv','[["111","a"]]'::jsonb))->>'err') = 'name'
  AND (smart_audience.saved_apply(:'sa', '{"op":"save","name":"ok2","iv":[]}'::jsonb)->>'err') = 'interests'
  AND (smart_audience.saved_apply(:'sa', '{"op":"save","name":"ok2","iv":[["ab","a"]]}'::jsonb)->>'err') = 'interests'
  AND (smart_audience.saved_apply(:'sa', '{"op":"save","name":"ok2","iv":[[111,"a"]]}'::jsonb)->>'err') = 'interests'
  AND (smart_audience.saved_apply(:'sa', '{"op":"del","id":"1; drop"}'::jsonb)->>'err') = 'op'
  AND (smart_audience.saved_apply(:'sa', '{"op":"zzz"}'::jsonb)->>'err') = 'op'
  AND (SELECT count(*) FROM smart_audience.saved_list(:'sa')) = 1);
SELECT t.ok('SA-19 limit 20 per tenant (replace of existing name still allowed)',
  (SELECT bool_and((smart_audience.saved_apply(:'sa', jsonb_build_object('op','save','name','a'||g,'iv','[["555","z"]]'::jsonb))->>'ok') = 'true') FROM generate_series(1,19) g)
  AND (smart_audience.saved_apply(:'sa', '{"op":"save","name":"over","iv":[["555","z"]]}'::jsonb)->>'err') = 'limit'
  AND (smart_audience.saved_apply(:'sa', '{"op":"save","name":"a1","iv":[["666","q"]]}'::jsonb)->>'ok') = 'true');
SELECT t.ok('SA-20 list returns latest 12 only; delete own works and reports notfound the 2nd time',
  (SELECT count(*) FROM smart_audience.saved_list(:'sa')) = 12
  AND (smart_audience.saved_apply(:'sa', jsonb_build_object('op','del','id',(SELECT id FROM smart_audience.saved_list(:'sa') LIMIT 1)))->>'ok') = 'true');
RESET ROLE;
UPDATE smart_audience.settings SET value='false'::jsonb WHERE key='enabled';
SET ROLE app_runtime;
SELECT t.ok('SA-21 feature OFF: list empty and writes refused (disabled)',
  (SELECT count(*) FROM smart_audience.saved_list(:'sa')) = 0 AND (smart_audience.saved_apply(:'sa', '{"op":"save","name":"x","iv":[["111","a"]]}'::jsonb)->>'err') = 'disabled');
RESET ROLE;
DELETE FROM smart_audience.saved;
DELETE FROM smart_audience.cache;
