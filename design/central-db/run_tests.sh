#!/usr/bin/env bash
# تشغيل المخطط والاختبارات على PostgreSQL محلي معزول. لا يمس أي قاعدة إنتاج.
# الاستعمال: PGHOST=/tmp/pgsock PGPORT=55432 PGUSER=postgres ./run_tests.sh
set -euo pipefail
cd "$(dirname "$0")"
export PGHOST="${PGHOST:-/tmp/pgsock}" PGPORT="${PGPORT:-55432}" PGUSER="${PGUSER:-postgres}"
DB=central_test; VDB=vault_test
psql -qAt -d postgres -c "DROP DATABASE IF EXISTS $DB" -c "DROP DATABASE IF EXISTS $VDB" -c "CREATE DATABASE $DB" -c "CREATE DATABASE $VDB" >/dev/null
psql -q -d postgres -f 00_roles.sql >/dev/null
psql -q -d "$DB" -c "REVOKE ALL ON DATABASE $DB FROM PUBLIC; GRANT CONNECT ON DATABASE $DB TO app_runtime, app_jobs, app_ops, app_owner, app_resolver, app_ops_fn; GRANT TEMPORARY ON DATABASE $DB TO app_owner;" >/dev/null
psql -q -d "$VDB" -c "REVOKE ALL ON DATABASE $VDB FROM PUBLIC; GRANT CONNECT ON DATABASE $VDB TO broker_rw;" >/dev/null 2>&1 || true
for f in 10_schema.sql 20_rls.sql 30_functions.sql 40_partitions.sql; do psql -q -v ON_ERROR_STOP=1 -d "$DB" -f "$f" >/dev/null; done
psql -q -v ON_ERROR_STOP=1 -d "$VDB" -f 50_vault.sql >/dev/null
psql -q -d "$VDB" -c "REVOKE ALL ON DATABASE $VDB FROM PUBLIC; GRANT CONNECT ON DATABASE $VDB TO broker_rw;" >/dev/null
echo "schema applied"
for t in tests/[0-9]*.sql; do echo "── $t"; psql -q -o /dev/null -v ON_ERROR_STOP=1 -d "$DB" -f "$t"; done

echo "── concurrency (جلسات متوازية حقيقية)"
HA=$(psql -qAt -d "$DB" -c "select encode(ext.digest('secret-a','sha256'),'hex')")
CTX=$(PGOPTIONS='-c role=app_runtime' psql -qAt -d "$DB" -c "select ctx from api.resolve_context('botAAAAAAAAAAAAAAAAAAAAAAAA', decode('$HA','hex'), 1003)")
OUT=$(mktemp -d)
for i in $(seq 1 10); do
  ( PGOPTIONS='-c role=app_runtime' psql -qAt -d "$DB" -c "select state from api.begin_campaign_request('$CTX','concurrent-key-0123456789','\\x01')" >> "$OUT/idem" ) &
  ( PGOPTIONS='-c role=app_runtime' psql -qAt -d "$DB" -c "select api.claim_update('$CTX', 424242)" >> "$OUT/claim" ) &
done; wait
NEW=$(grep -c '^new$' "$OUT/idem" || true); INP=$(grep -c '^in_progress$' "$OUT/idem" || true)
TRUES=$(grep -c '^t$' "$OUT/claim" || true)
psql -qAt -o /dev/null -d "$DB" -c "select t.ok('IDEM-13 10 parallel creation requests with one key: exactly ONE proceeds', $NEW = 1 and $INP = 9, 'new=$NEW in_progress=$INP')"
psql -qAt -o /dev/null -d "$DB" -c "select t.ok('IDEM-14 10 parallel deliveries of the same Telegram update: exactly ONE is processed', $TRUES = 1, 'true=$TRUES')"
# سباق ربط نفس الحساب الإعلاني بعميلين بنفس اللحظة: واحد فقط ينجح
SA=$(PGOPTIONS='-c role=app_jobs' psql -qAt -d "$DB" -c "select ctx from api.job_contexts('schedule',10) where tenant_id='a0000000-0000-0000-0000-000000000001'")
SB=$(PGOPTIONS='-c role=app_jobs' psql -qAt -d "$DB" -c "select ctx from api.job_contexts('schedule',10) where tenant_id='b0000000-0000-0000-0000-000000000001'")
rm -f "$OUT/link"
for i in 1 2 3 4 5; do
  ( PGOPTIONS='-c role=app_jobs' psql -qAt -d "$DB" -c "select api.link_ad_account('$SA','meta','act_RACE','a1000000-0000-0000-0000-000000000001','race','USD')" >/dev/null 2>>"$OUT/link_err" && echo A_ok >> "$OUT/link" ) &
  ( PGOPTIONS='-c role=app_jobs' psql -qAt -d "$DB" -c "select api.link_ad_account('$SB','meta','act_RACE','b1000000-0000-0000-0000-000000000001','race','USD')" >/dev/null 2>>"$OUT/link_err" && echo B_ok >> "$OUT/link" ) &
done; wait
LINKED=$(psql -qAt -d "$DB" -c "select count(*) from core.ad_accounts where external_id='act_RACE' and unlinked_at is null")
OKS=$(cat "$OUT/link" 2>/dev/null | sort -u | wc -l)
psql -qAt -o /dev/null -d "$DB" -c "select t.ok('ISO-G1 10 racing link attempts of one ad account by 2 tenants: exactly ONE active link', $LINKED = 1, 'linked=$LINKED')"
rm -rf "$OUT"
psql -qAt -d "$DB" -c "SELECT format('RESULT: %s passed, %s failed', count(*) FILTER (WHERE ok), count(*) FILTER (WHERE NOT ok)) FROM t.results"
FAILS=$(psql -qAt -d "$DB" -c "SELECT count(*) FROM t.results WHERE NOT ok")
if [ "$FAILS" != "0" ]; then psql -qAt -d "$DB" -c "SELECT 'FAIL: '||name||' — '||coalesce(detail,'') FROM t.results WHERE NOT ok ORDER BY id"; exit 1; fi
