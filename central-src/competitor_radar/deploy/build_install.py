#!/usr/bin/env python3
"""يبني ops/p251-radar-install-files.py.txt: باتش ملفات فقط (بدون إعادة تشغيل شي) يضع الخدمة/الهجرة/Dockerfile/الأداة بمجلد competitor_radar الجديد."""
import os
H = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(H, "..")
files = {}
for f in sorted(os.listdir(os.path.join(R, "service"))):
    if f.endswith(".py"): files["competitor_radar/service/" + f] = open(os.path.join(R, "service", f), encoding="utf-8").read()
for f in ("80_competitor_radar.sql", "80_competitor_radar_down.sql"): files["competitor_radar/db/" + f] = open(os.path.join(R, "db", f), encoding="utf-8").read()
files["competitor_radar/deploy/Dockerfile"] = open(os.path.join(H, "Dockerfile"), encoding="utf-8").read()
files["ops/competitor-radar.py"] = open(os.path.join(H, "competitor_radar_ctl.py"), encoding="utf-8").read()
SRC = '''import os, shutil, sys
BASE = os.environ.get('P251_BASE', '/opt/central/')
FILES = %r
ALLOWED = ('competitor_radar/', 'ops/competitor-radar.py')
bad = [p for p in FILES if not p.startswith(ALLOWED) or '..' in p]
if bad: sys.exit('PATCH FAIL (nothing written): unexpected paths %%s' %% bad)
for p, c in FILES.items():
    if p.endswith('.py'):
        try: compile(c, p, 'exec')
        except SyntaxError as e: sys.exit('PATCH FAIL (nothing written): syntax %%s: %%s' %% (p, e))
changed = 0
for p, c in FILES.items():
    f = BASE + p
    if os.path.exists(f) and open(f, encoding='utf-8').read() == c: continue
    os.makedirs(os.path.dirname(f), exist_ok=True)
    if os.path.exists(f): shutil.copy(f, f + '.pre251')
    open(f, 'w', encoding='utf-8').write(c); changed += 1
os.chmod(BASE + 'ops/competitor-radar.py', 0o755)
print('APPLY251_OK files=%%d changed=%%d (service + db 80 + Dockerfile + ops/competitor-radar.py); nothing restarted, nothing enabled. Next: python3 ops/competitor-radar.py install' %% (len(FILES), changed))
''' % files
open(os.path.join(R, "..", "ops", "p251-radar-install-files.py.txt"), "w", encoding="utf-8").write(SRC)
print("built", len(files))
