import os, re, shutil, subprocess, sys
BASE = os.environ.get('P236_BASE', '/opt/central/')
CT = 'broker/app/catalog.py'
ct = open(BASE + CT, encoding='utf-8').read()
if 'p236' in ct: print('APPLY236_OK changed=0 (already applied)'); sys.exit(0)
NEWP = '"budget_auto_adjust_strategy": P("enum", values=("AUTO_BUDGET_INCREASE", "UNSET"))'
fails = []
def block(name):
    i = ct.find('Op("%s"' % name)
    if i < 0: fails.append('catalog Op %s not found' % name); return None
    j = ct.find('\n    Op(', i + 5); k = ct.find('\n    #', i + 5)
    ends = [x for x in (j, k) if x > 0]
    return i, (min(ends) if ends else len(ct))
camp = block('tiktok.sp_create_campaign'); adg = block('tiktok.sp_create_adgroup')
edits = []
if camp:
    m = list(re.finditer(r'"budget_mode": P\("enum", required=True, values=\("BUDGET_MODE_TOTAL", "BUDGET_MODE_DYNAMIC_DAILY"\)\)', ct[camp[0]:camp[1]]))
    if len(m) != 1: fails.append('sp_create_campaign budget_mode param anchor count=%d' % len(m))
    else: edits.append((camp[0] + m[0].end(), ', ' + NEWP))
if adg:
    m = list(re.finditer(r'"phone_number": P\("id", required=True\)\}', ct[adg[0]:adg[1]]))
    if len(m) != 1: fails.append('sp_create_adgroup phone_number param anchor count=%d' % len(m))
    else: edits.append((adg[0] + m[0].end() - 1, ', ' + NEWP))
if fails: sys.exit('PATCH FAIL (nothing written): ' + ' || '.join(fails) + ' || lines: ' + ' | '.join(ascii(l.strip()[:160]) for l in ct.split('\n') if 'sp_create' in l)[:400])
new = ct
for pos, txt in sorted(edits, reverse=True): new = new[:pos] + txt + new[pos:]
new = new.rstrip('\n') + '\n# p236: budget_auto_adjust_strategy (AUTO_BUDGET_INCREASE|UNSET) اختياري لعمليات Smart+ (اختبار الزر الأخضر)\n'
try: compile(new, CT, 'exec')
except SyntaxError as e: sys.exit('PATCH FAIL (nothing written): syntax: %s' % e)
TEST = @@TEST@@
shutil.copy(BASE + CT, BASE + CT + '.pre236')
open(BASE + CT, 'w', encoding='utf-8').write(new)
if os.path.isdir(BASE + 'ops'):
    open(BASE + 'ops/tt-smart-toggle-test.py', 'w', encoding='utf-8').write(TEST); os.chmod(BASE + 'ops/tt-smart-toggle-test.py', 0o755)
print('APPLY236_OK catalog: optional budget_auto_adjust_strategy on tiktok.sp_create_campaign / sp_create_adgroup + ops/tt-smart-toggle-test.py')
