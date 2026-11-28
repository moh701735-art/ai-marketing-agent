\set ON_ERROR_STOP on
REVOKE EXECUTE ON FUNCTION web.link_state_new(uuid, text), web.link_begin(uuid, text, text), web.link_status(uuid) FROM web_rt;
DROP FUNCTION IF EXISTS web.link_state_new(uuid, text), web.link_begin(uuid, text, text), web.link_status(uuid);
DROP TABLE IF EXISTS web.link_requests; DROP TABLE IF EXISTS web.link_states;
