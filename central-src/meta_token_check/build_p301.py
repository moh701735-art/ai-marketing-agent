import json, os, base64, lzma
H = os.path.dirname(os.path.abspath(__file__))
HELPER = open(os.path.join(H, "..", "ops", "meta-token-check.py"), encoding="utf-8").read()
T = r'''import os, sys
BASE = os.environ.get('P301_BASE', '/opt/central/')
HELPER = @@HELPER@@
def die(m): sys.exit('PATCH FAIL (nothing written): ' + m)
if not os.path.isdir(BASE + 'ops'): die('ops/ not found under ' + BASE)
hp = BASE + 'ops/meta-token-check.py'
if os.path.exists(hp) and open(hp, encoding='utf-8').read() == HELPER:
    print('APPLY301_OK changed=0 (already installed)'); sys.exit(0)
try: compile(HELPER, 'helper', 'exec')
except SyntaxError as e: die('syntax %s' % e)
open(hp, 'w', encoding='utf-8').write(HELPER)
os.chmod(hp, 0o755)
print('APPLY301_OK ops/meta-token-check.py installed (read-only: tells you if a Meta token is long-lived BEFORE you use it)')
'''
body = T.replace("@@HELPER@@", json.dumps(HELPER, ensure_ascii=False))
open(os.path.join(H, "..", "ops", "p301-meta-token-check.py.txt"), "w", encoding="utf-8").write(body)
b = base64.b64encode(lzma.compress(body.encode("utf-8"), preset=9 | lzma.PRESET_EXTREME)).decode()
open(os.path.join(H, "..", "..", "out", "p301s.txt"), "w").write("cd /opt/central && echo '%s' | base64 -d | xz -d | python3 && grep -c p301 ops/meta-token-check.py\n" % b)
