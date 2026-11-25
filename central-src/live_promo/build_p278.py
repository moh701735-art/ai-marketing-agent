import json, os, base64, lzma
H = os.path.dirname(os.path.abspath(__file__))
TOOL = open(os.path.join(H, "ops", "tt_live_create_probe.py"), encoding="utf-8").read()
T = r'''import os, sys
BASE = os.environ.get('P278_BASE', '/opt/central/')
SRC = @@TOOL@@
if not os.path.exists(BASE + 'ops/wa-diagnose.py'): sys.exit('PATCH FAIL (nothing written): missing ops/wa-diagnose.py (apply p263 first)')
if not os.path.exists(BASE + 'ops/tt-live-create-probe.py'): sys.exit('PATCH FAIL (nothing written): ops/tt-live-create-probe.py missing (apply p277 first)')
try: compile(SRC, 'tt-live-create-probe.py', 'exec')
except SyntaxError as e: sys.exit('PATCH FAIL (nothing written): syntax %s' % e)
p = BASE + 'ops/tt-live-create-probe.py'
old = open(p, encoding='utf-8').read()
if old == SRC: print('APPLY278_OK changed=0 (already installed)'); sys.exit(0)
open(p + '.pre278', 'w', encoding='utf-8').write(old)
open(p, 'w', encoding='utf-8').write(SRC); os.chmod(p, 0o755)
print('APPLY278_OK ops/tt-live-create-probe.py v2 (flexible parser, one value per line + letter-spaced; still sends ONLY an invalid objective; no campaign)')
'''
body = T.replace("@@TOOL@@", json.dumps(TOOL, ensure_ascii=False))
open(os.path.join(H, "..", "ops", "p278-live-create-probe-v2.py.txt"), "w", encoding="utf-8").write(body)
b = base64.b64encode(lzma.compress(body.encode("utf-8"), preset=9 | lzma.PRESET_EXTREME)).decode()
line = "echo '%s' | base64 -d | xz -d | python3 && echo \"marker: $(grep -c 'v2 / p278' /opt/central/ops/tt-live-create-probe.py) (expect 1)\" && cd /opt/central && python3 ops/tt-live-create-probe.py 2>&1 | LC_ALL=C sed -E 's/[^ -~]/?/g'\n" % b
open(os.path.join(H, "..", "..", "out", "p278s.txt"), "w").write(line)
print(len(line))
