import json, os, base64, lzma
H = os.path.dirname(os.path.abspath(__file__))
TOOL = open(os.path.join(H, "ops", "tt_live_b2.py"), encoding="utf-8").read()
T = r'''import os, sys
BASE = os.environ.get('P280_BASE', '/opt/central/')
SRC = @@TOOL@@
if not os.path.exists(BASE + 'ops/wa-diagnose.py'): sys.exit('PATCH FAIL (nothing written): missing ops/wa-diagnose.py (apply p263 first)')
if 'p277' not in open(BASE + 'broker/app/catalog.py', encoding='utf-8').read(): sys.exit('PATCH FAIL (nothing written): catalog has no p277 probe ops')
try: compile(SRC, 'tt-live-b2.py', 'exec')
except SyntaxError as e: sys.exit('PATCH FAIL (nothing written): syntax %s' % e)
p = BASE + 'ops/tt-live-b2.py'
if os.path.exists(p):
    old = open(p, encoding='utf-8').read()
    if old == SRC: print('APPLY280_OK changed=0 (already installed)'); sys.exit(0)
    open(p + '.pre280', 'w', encoding='utf-8').write(old)
open(p, 'w', encoding='utf-8').write(SRC); os.chmod(p, 0o755)
print('APPLY280_OK ops/tt-live-b2.py installed (B2: one PAUSED probe campaign + invalid-value ad group probes; no ad group/ad is created)')
'''
body = T.replace("@@TOOL@@", json.dumps(TOOL, ensure_ascii=False))
open(os.path.join(H, "..", "ops", "p280-live-b2.py.txt"), "w", encoding="utf-8").write(body)
b = base64.b64encode(lzma.compress(body.encode("utf-8"), preset=9 | lzma.PRESET_EXTREME)).decode()
line = "echo '%s' | base64 -d | xz -d | python3 && cd /opt/central && python3 ops/tt-live-b2.py 2>&1 | LC_ALL=C sed -E 's/[^ -~]/?/g'\n" % b
open(os.path.join(H, "..", "..", "out", "p280s.txt"), "w").write(line)
print(len(line))
