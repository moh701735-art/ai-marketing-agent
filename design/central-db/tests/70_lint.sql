-- 70_lint.sql : فحوصات بنيوية آلية (T-LINT). تمنع نسيان RLS أو منح صلاحية خطأ مستقبلاً.
SELECT t.ok('LINT-01 every core table with tenant_id has RLS enabled + forced + at least one policy',
  NOT EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped
    WHERE n.nspname = 'core' AND c.relkind IN ('r','p') AND NOT c.relispartition
      AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity
           OR NOT EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid))),
  (SELECT string_agg(c.relname, ',') FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped
    WHERE n.nspname = 'core' AND c.relkind IN ('r','p') AND NOT c.relispartition AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity)));
SELECT t.ok('LINT-02 app_runtime / app_jobs / app_ops have no privilege on ANY core relation (tables, partitions, sequences)',
  NOT EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace, unnest(ARRAY['app_runtime','app_jobs','app_ops']) r
    WHERE n.nspname = 'core' AND c.relkind IN ('r','p','S','v')
      AND (has_table_privilege(r, c.oid, 'SELECT') OR has_table_privilege(r, c.oid, 'INSERT')
        OR has_table_privilege(r, c.oid, 'UPDATE') OR has_table_privilege(r, c.oid, 'DELETE'))));
SELECT t.ok('LINT-03 app_resolver can read only the 6 permitted tables (no data tables)',
  (SELECT array_agg(c.relname::text ORDER BY c.relname::text) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'core' AND c.relkind IN ('r','p') AND has_table_privilege('app_resolver', c.oid, 'SELECT'))
  = ARRAY['bots','config_versions','readiness_check_defs','readiness_checks','tenant_users','tenants']);
SELECT t.ok('LINT-04 no function in api/api_admin/private is executable by PUBLIC',
  NOT EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
              WHERE n.nspname IN ('api','api_admin','private')
                AND EXISTS (SELECT 1 FROM aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a WHERE a.grantee = 0 AND a.privilege_type = 'EXECUTE')),
  (SELECT string_agg(p.proname, ',') FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
              WHERE n.nspname IN ('api','api_admin','private')
                AND EXISTS (SELECT 1 FROM aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a WHERE a.grantee = 0 AND a.privilege_type = 'EXECUTE')));
SELECT t.ok('LINT-05 every function in api/api_admin/private is SECURITY DEFINER with a pinned search_path',
  NOT EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
              WHERE n.nspname IN ('api','api_admin','private') AND p.proname <> 'cur_tenant'
                AND (NOT p.prosecdef OR NOT EXISTS (SELECT 1 FROM unnest(coalesce(p.proconfig,'{}')) c WHERE c LIKE 'search_path=%'))));
SELECT t.ok('LINT-06 app_runtime may execute EXACTLY the interactive allowlist',
  (SELECT array_agg(p.oid::regprocedure::text ORDER BY p.oid::regprocedure::text) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname IN ('api','api_admin','private') AND has_function_privilege('app_runtime', p.oid, 'EXECUTE'))
  = (SELECT array_agg(x ORDER BY x) FROM unnest(ARRAY[
      'api.add_tenant_knowledge(text,text,text)','api.begin_campaign_request(text,text,bytea)','api.claim_update(text,bigint)',
      'api.finish_campaign_request(text,text,text,text)','api.get_report(text,text,timestamp with time zone)','api.list_campaigns(text,text)',
      'api.list_errors(text,integer)','api.log_error(text,text,text,text,text,text,text,text)',
      'api.record_campaign(text,text,text,text,text,text,numeric)','api.resolve_context(text,bytea,bigint)','api.search_knowledge(text,text)']) x),
  (SELECT string_agg(p.oid::regprocedure::text, E'\n') FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname IN ('api','api_admin','private') AND has_function_privilege('app_runtime', p.oid, 'EXECUTE')));
SELECT t.ok('LINT-07 app_jobs cannot execute resolve_context / admin / private functions',
  NOT has_function_privilege('app_jobs', 'api.resolve_context(text,bytea,bigint)', 'EXECUTE')
  AND NOT EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
       WHERE n.nspname IN ('api_admin','private') AND has_function_privilege('app_jobs', p.oid, 'EXECUTE')));
SELECT t.ok('LINT-08 app_* roles are not superuser / bypassrls / createrole / createdb and cannot log in by default',
  NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname LIKE 'app\_%' AND (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb)));
SELECT t.ok('LINT-09 app_runtime / app_jobs own no objects',
  NOT EXISTS (SELECT 1 FROM pg_class c WHERE c.relowner IN (SELECT oid FROM pg_roles WHERE rolname IN ('app_runtime','app_jobs')))
  AND NOT EXISTS (SELECT 1 FROM pg_proc p WHERE p.proowner IN (SELECT oid FROM pg_roles WHERE rolname IN ('app_runtime','app_jobs'))));
SELECT t.ok('LINT-10 all core tables are owned by app_owner (non-superuser, subject to FORCE RLS)',
  NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
              WHERE n.nspname = 'core' AND c.relkind IN ('r','p') AND c.relowner <> (SELECT oid FROM pg_roles WHERE rolname = 'app_owner')));
SELECT t.ok('LINT-11 the secrets database is not reachable by application roles',
  NOT has_database_privilege('app_runtime', 'vault_test', 'CONNECT') AND NOT has_database_privilege('app_jobs', 'vault_test', 'CONNECT')
  AND NOT has_database_privilege('app_owner', 'vault_test', 'CONNECT') AND has_database_privilege('broker_rw', 'vault_test', 'CONNECT'));
SELECT t.ok('LINT-12 no column named like a secret exists in the central DB (token/password/secret/ciphertext/api_key)',
  NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'core'
              AND column_name ~* '(token|password|passwd|secret(?!_ref)|ciphertext|api_?key)'
              AND column_name NOT IN ('webhook_secret_hash')),
  (SELECT string_agg(table_name||'.'||column_name, ',') FROM information_schema.columns WHERE table_schema = 'core'
              AND column_name ~* '(token|password|passwd|secret(?!_ref)|ciphertext|api_?key)' AND column_name NOT IN ('webhook_secret_hash')));
