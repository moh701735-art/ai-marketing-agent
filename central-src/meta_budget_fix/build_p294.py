import json, os, base64, lzma
H = os.path.dirname(os.path.abspath(__file__))
T = r'''import os, re, shutil, sys
BASE = os.environ.get('P294_BASE', '/opt/central/')
MF = BASE + 'broker/app/metaflow.py'
def die(m): sys.exit('PATCH FAIL (nothing written): ' + m)
if not os.path.exists(MF): die(MF + ' not found')
s = open(MF, encoding='utf-8').read()
NEWC = '("daily_budget" if (p["budget_mode"] == "daily" and int(p.get("days") or 0) > 1) else "lifetime_budget")'
if NEWC in s and 'p294' in s: print('APPLY294_OK changed=0 (already applied)'); sys.exit(0)
rx = re.compile(r'\("daily_budget" if p\["budget_mode"\] == "daily" else "lifetime_budget"\)')
ms = list(rx.finditer(s))
if len(ms) != 2: die('daily/lifetime anchor count=%d (expected 2: launch_whatsapp + launch_objective); lines: %s' % (len(ms), ' | '.join(ascii(l.strip()[:230]) for l in s.split('\n') if 'daily_budget' in l)[:700]))
new = rx.sub(lambda m: NEWC, s)
new = new.rstrip('\n') + '\n# p294: daily budget + 1 day => lifetime budget (Meta subcode 1487793: daily-budget ad sets must run >= 24h); cap unchanged\n'
try: compile(new, 'metaflow.py', 'exec')
except SyntaxError as e: die('syntax %s' % e)
shutil.copy(MF, MF + '.pre294'); open(MF, 'w', encoding='utf-8').write(new)
print('APPLY294_OK daily budget with a 1-day campaign now uses a lifetime budget of the same amount (2 places); Broker rebuild needed')
'''
open(os.path.join(H, "..", "ops", "p294-meta-daily-1day.py.txt"), "w", encoding="utf-8").write(T)
b = base64.b64encode(lzma.compress(T.encode("utf-8"), preset=9 | lzma.PRESET_EXTREME)).decode()
line = "echo '%s' | base64 -d | xz -d | python3 && cd /opt/central && bash deploy/update.sh && echo \"markers: metaflow p294=$(grep -c p294 broker/app/metaflow.py) (expect 1)\"\n" % b
open(os.path.join(H, "..", "..", "out", "p294s.txt"), "w").write(line)
print(len(line))
