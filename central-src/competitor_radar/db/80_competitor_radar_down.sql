-- 80_competitor_radar_down.sql : تراجع كامل عن رادار المنافسين. لا يلمس أي شي خارج المخطط competitor_radar والدور radar_rt.
\set ON_ERROR_STOP on
DROP SCHEMA IF EXISTS competitor_radar CASCADE;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'radar_rt') THEN DROP ROLE radar_rt; END IF;
END $$;
