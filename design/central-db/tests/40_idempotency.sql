-- 40_idempotency.sql : منع تكرار إنشاء الحملات (T-IDEM). التزامن الفعلي (جلسات متوازية) بـ run_tests.sh.
\set A '\'a0000000-0000-0000-0000-000000000001\''
SELECT encode(ext.digest('secret-a','sha256'),'hex') AS ha, encode(ext.digest('secret-b','sha256'),'hex') AS hb \gset
SET ROLE app_runtime;
SELECT ctx AS a_mgr    FROM api.resolve_context('botAAAAAAAAAAAAAAAAAAAAAAAA', decode(:'ha','hex'), 1003) \gset
SELECT ctx AS a_viewer FROM api.resolve_context('botAAAAAAAAAAAAAAAAAAAAAAAA', decode(:'ha','hex'), 1002) \gset
SELECT ctx AS b_owner  FROM api.resolve_context('botBBBBBBBBBBBBBBBBBBBBBBBB', decode(:'hb','hex'), 2001) \gset

SELECT t.ok('IDEM-01 first request is "new"', (SELECT state FROM api.begin_campaign_request(:'a_mgr','upd-5001-create-campaign-x', '\x01')) = 'new');
SELECT t.ok('IDEM-02 same key while executing -> in_progress (no second creation)',
  (SELECT state FROM api.begin_campaign_request(:'a_mgr','upd-5001-create-campaign-x', '\x01')) = 'in_progress');
SELECT api.finish_campaign_request(:'a_mgr','upd-5001-create-campaign-x','succeeded','camp_ext_777');
SELECT t.ok('IDEM-03 after success the same key replays the stored result',
  (SELECT state || ':' || result_ref FROM api.begin_campaign_request(:'a_mgr','upd-5001-create-campaign-x','\x01')) = 'replay:camp_ext_777');
SELECT t.ok('IDEM-04 same key with different payload -> conflict',
  (SELECT state FROM api.begin_campaign_request(:'a_mgr','upd-5001-create-campaign-x','\x02')) = 'conflict');
SELECT t.ok('IDEM-05 same key in another tenant is independent',
  (SELECT state FROM api.begin_campaign_request(:'b_owner','upd-5001-create-campaign-x','\x01')) = 'new');
SELECT t.ok('IDEM-06 failed request can be retried',
  (SELECT state FROM api.begin_campaign_request(:'a_mgr','upd-6000-create-campaign-y','\x09')) = 'new');
SELECT api.finish_campaign_request(:'a_mgr','upd-6000-create-campaign-y','failed',NULL);
SELECT t.ok('IDEM-07 retry after failure returns new',
  (SELECT state FROM api.begin_campaign_request(:'a_mgr','upd-6000-create-campaign-y','\x09')) = 'new');
RESET ROLE;
UPDATE core.campaign_requests SET updated_at = now() - interval '11 minutes' WHERE idempotency_key = 'upd-6000-create-campaign-y';
SET ROLE app_runtime;
SELECT t.ok('IDEM-08 stale "executing" (>10 min, outcome unknown) -> needs_manual_check, never silently recreated',
  (SELECT state FROM api.begin_campaign_request(:'a_mgr','upd-6000-create-campaign-y','\x09')) = 'needs_manual_check');
SELECT t.raises('IDEM-09 viewer cannot begin a creation request',
  format('SELECT * FROM api.begin_campaign_request(%L,%L,%L)', :'a_viewer','upd-7000-create-campaign-z','\x01'), '42501', 'forbidden');
SELECT t.raises('IDEM-10 finishing an unknown key is an error',
  format('SELECT api.finish_campaign_request(%L,%L,%L,%L)', :'a_mgr','no-such-key-0123456789','succeeded','x'), 'P0002');
SELECT t.raises('IDEM-11 invalid final status rejected',
  format('SELECT api.finish_campaign_request(%L,%L,%L,%L)', :'a_mgr','upd-5001-create-campaign-x','bogus','x'), NULL, 'bad_status');
SELECT t.raises('IDEM-12 too-short key rejected by constraint',
  format('SELECT * FROM api.begin_campaign_request(%L,%L,%L)', :'a_mgr','short','\x01'), '23514');
RESET ROLE;
