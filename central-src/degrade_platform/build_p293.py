import base64, lzma, os
H = os.path.dirname(os.path.abspath(__file__))
sql = open(os.path.join(H, "..", "db", "77_degrade_platform.sql"), "rb").read()
tool = open(os.path.join(H, "..", "ops", "platform-enable.py"), "rb").read()
bt = base64.b64encode(lzma.compress(tool, preset=9 | lzma.PRESET_EXTREME)).decode()
b = base64.b64encode(lzma.compress(sql, preset=9 | lzma.PRESET_EXTREME)).decode()
PSQL = "docker exec -i central-stg-pg psql -U postgres -d central"
chk = ("printf \"BEGIN;\\nSET LOCAL ROLE app_owner;\\nSELECT set_config('app.tenant_id', t.tenant_id::text, true) FROM core.tenants t WHERE slug='isolation-canary';\\n"
       "UPDATE core.tenants SET features = features || '{\\\"p293_probe\\\": false}'::jsonb WHERE slug='isolation-canary' RETURNING 'RLS_UPDATE_OK:' || slug;\\nROLLBACK;\\n\" | " + PSQL + " -At")
line = ("cd /opt/central && echo '%s' | base64 -d | xz -d > ops/platform-enable.py && chmod +x ops/platform-enable.py && python3 -c \"import ast;ast.parse(open('ops/platform-enable.py').read())\" && echo '%s' | base64 -d | xz -d | %s -v ON_ERROR_STOP=1 -f - && "
        "%s -At -c \"select 'MARKER:' || (pg_get_functiondef(p.oid) like '%%p293_degrade%%') from pg_proc p where p.proname='broker_report_connection'\" && "
        "echo ----RLS && %s && echo APPLY293_OK\n") % (bt, b, PSQL, PSQL, chk)
open(os.path.join(H, "..", "..", "out", "p293s.txt"), "w").write(line)
print(len(line)); print(line[-700:])
