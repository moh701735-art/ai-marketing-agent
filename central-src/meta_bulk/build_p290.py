import json, os, base64, lzma
H = os.path.dirname(os.path.abspath(__file__))
HELPER = open(os.path.join(H, "..", "ops", "meta-accounts-print.py"), encoding="utf-8").read()
T = r'''import os, re, shutil, sys
BASE = os.environ.get('P290_BASE', '/opt/central/')
HELPER = @@HELPER@@
pj = 'ops/link-meta-web.py'
def die(m): sys.exit('PATCH FAIL (nothing written): ' + m)
def lines_with(t, k): return ' | '.join(ascii(l.strip()[:200]) for l in t.split('\n') if k in l)[:700]
if not os.path.exists(BASE + pj): die(pj + ' not found')
s = open(BASE + pj, encoding='utf-8').read()
hp = BASE + 'ops/meta-accounts-print.py'
if 'p290' in s:
    open(hp, 'w', encoding='utf-8').write(HELPER)
    print('APPLY290_OK changed=0 (link-meta-web already p290; helper refreshed)'); sys.exit(0)
fails = []
mA = list(re.finditer(r'len\(out\)\s*>\s*5\b', s))
if len(mA) != 1: fails.append('account-limit anchor count=%d; lines: %s' % (len(mA), lines_with(s, 'len(out)')))
mP = list(re.finditer(r'limit=25\b', s))
if len(mP) != 1: fails.append('pages limit anchor count=%d; lines: %s' % (len(mP), lines_with(s, 'limit=')))
if fails: die(' || '.join(fails))
new = s[:mA[0].start()] + 'len(out) > 30' + s[mA[0].end():]
new = new.replace('limit=25', 'limit=100', 1)
# the refusal message may mention the old limit (5) in the same/next line: update only standalone 5 inside a line with Arabic text
ls = new.split('\n'); msgfix = 0
for i, l in enumerate(ls):
    if 'len(out) > 30' in l:
        for j in (i, i + 1):
            if j < len(ls) and re.search(r'[؀-ۿ]', ls[j]) and re.search(r'(?<![0-9A-Za-z_.])5(?![0-9A-Za-z_.])', ls[j]):
                ls[j] = re.sub(r'(?<![0-9A-Za-z_.])5(?![0-9A-Za-z_.])', '30', ls[j]); msgfix += 1
new = '\n'.join(ls)
if not new.endswith('\n'): new += '\n'
new += '# p290: up to 30 ad accounts and 100 pages per run\n'
try: compile(new, pj, 'exec')
except SyntaxError as e: die('syntax %s' % e)
shutil.copy(BASE + pj, BASE + pj + '.pre290')
open(BASE + pj, 'w', encoding='utf-8').write(new)
open(hp, 'w', encoding='utf-8').write(HELPER)
print('APPLY290_OK link-meta-web.py: up to 30 ad accounts + 100 pages per run (message lines fixed: %d); ops/meta-accounts-print.py installed' % msgfix)
'''
body = T.replace("@@HELPER@@", json.dumps(HELPER, ensure_ascii=False))
open(os.path.join(H, "..", "ops", "p290-meta-bulk.py.txt"), "w", encoding="utf-8").write(body)
b = base64.b64encode(lzma.compress(body.encode("utf-8"), preset=9 | lzma.PRESET_EXTREME)).decode()
line = "cd /opt/central && echo '%s' | base64 -d | xz -d | python3 && grep -c p290 ops/link-meta-web.py && ls -l ops/meta-accounts-print.py\n" % b
open(os.path.join(H, "..", "..", "out", "p290s.txt"), "w").write(line)
print(len(line))
