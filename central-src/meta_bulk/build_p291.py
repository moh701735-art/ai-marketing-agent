import json, os, base64, lzma
H = os.path.dirname(os.path.abspath(__file__))
HELPER = open(os.path.join(H, "..", "ops", "meta-accounts-print.py"), encoding="utf-8").read()
T = r'''import os, shutil, sys
BASE = os.environ.get('P291_BASE', '/opt/central/')
HELPER = @@HELPER@@
def die(m): sys.exit('PATCH FAIL (nothing written): ' + m)
if not os.path.isdir(BASE + 'ops'): die('ops/ not found under ' + BASE)
hp = BASE + 'ops/meta-accounts-print.py'
if os.path.exists(hp) and 'p291' in open(hp, encoding='utf-8').read():
    print('APPLY291_OK changed=0 (already p291)'); sys.exit(0)
if os.path.exists(hp): shutil.copy(hp, hp + '.pre291')
open(hp, 'w', encoding='utf-8').write(HELPER)
os.chmod(hp, 0o755)
print('APPLY291_OK ops/meta-accounts-print.py now also reads every business (me/businesses -> owned/client ad accounts)')
'''
body = T.replace("@@HELPER@@", json.dumps(HELPER, ensure_ascii=False))
open(os.path.join(H, "..", "ops", "p291-meta-printer.py.txt"), "w", encoding="utf-8").write(body)
b = base64.b64encode(lzma.compress(body.encode("utf-8"), preset=9 | lzma.PRESET_EXTREME)).decode()
open(os.path.join(H, "..", "..", "out", "p291s.txt"), "w").write("cd /opt/central && echo '%s' | base64 -d | xz -d | python3 && grep -c p291 ops/meta-accounts-print.py\n" % b)
