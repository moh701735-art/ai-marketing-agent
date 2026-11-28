import json, os, base64, lzma
H = os.path.dirname(os.path.abspath(__file__))
FILES = {"web_portal/Dockerfile": "Dockerfile", "web_portal/service/__init__.py": "service/__init__.py", "web_portal/service/app.py": "service/app.py", "web_portal/service/security.py": "service/security.py",
         "web_portal/service/pages.py": "service/pages.py", "web_portal/service/store.py": "service/store.py", "web_portal/db/81_web_portal.sql": "db/81_web_portal.sql",
         "web_portal/db/81_web_portal_down.sql": "db/81_web_portal_down.sql", "web_portal/db/82_web_only_tenants.sql": "db/82_web_only_tenants.sql", "web_portal/db/82_web_only_tenants_down.sql": "db/82_web_only_tenants_down.sql", "ops/web-portal.py": "deploy/web_portal_ctl.py"}
data = {dst: open(os.path.join(H, src), encoding="utf-8").read() for dst, src in FILES.items()}
T = r'''import os, shutil, sys
BASE = os.environ.get('P305_BASE', '/opt/central/')
FILES = @@FILES@@
def die(m): sys.exit('PATCH FAIL (nothing written): ' + m)
if not os.path.isdir(BASE) or not os.path.isdir(BASE + 'ops') or not os.path.isdir(BASE + 'deploy'): die('not an /opt/central tree: ' + BASE)
for dst, txt in FILES.items():
    try: compile(txt, dst, 'exec') if dst.endswith('.py') else None
    except SyntaxError as e: die('syntax %s %s' % (dst, e))
changed = 0
for dst, txt in FILES.items():
    p = BASE + dst
    if os.path.exists(p) and open(p, encoding='utf-8').read() == txt: continue
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if os.path.exists(p): shutil.copy(p, p + '.pre305')
    open(p, 'w', encoding='utf-8').write(txt); changed += 1
os.chmod(BASE + 'ops/web-portal.py', 0o755)
print('APPLY305_OK changed=%d files (web portal package written under web_portal/ + ops/web-portal.py; nothing started, no DB/Caddy change yet)' % changed)
'''
body = T.replace("@@FILES@@", json.dumps(data, ensure_ascii=False))
open(os.path.join(H, "..", "ops", "p305-web-portal-package.py.txt"), "w", encoding="utf-8").write(body)
b = base64.b64encode(lzma.compress(body.encode("utf-8"), preset=9 | lzma.PRESET_EXTREME)).decode()
open(os.path.join(H, "..", "..", "out", "p305s.txt"), "w").write("cd /opt/central && echo '%s' | base64 -d | xz -d | python3 && python3 ops/web-portal.py --help | head -3\n" % b)
print(len(b))
