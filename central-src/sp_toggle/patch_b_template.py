import os, re, shutil, sys
BASE = os.environ.get('P236B_BASE', '/opt/central/')
CT = 'broker/app/catalog.py'
ct = open(BASE + CT, encoding='utf-8').read()
if 'p236b' in ct: print('APPLY236B_OK changed=0 (already applied)'); sys.exit(0)
if 'p236' not in ct: sys.exit('PATCH FAIL (nothing written): p236 must be applied first')
i = ct.find('Op("tiktok.sp_create_campaign"')
if i < 0: sys.exit('PATCH FAIL (nothing written): sp_create_campaign op not found')
j = ct.find('\n    Op(', i + 5); k = ct.find('\n    #', i + 5); ends = [x for x in (j, k) if x > 0]; end = min(ends) if ends else len(ct)
OLD = '"budget_mode": P("enum", required=True, values=("BUDGET_MODE_TOTAL", "BUDGET_MODE_DYNAMIC_DAILY"))'
NEW = '"budget_mode": P("enum", required=True, values=("BUDGET_MODE_TOTAL", "BUDGET_MODE_DYNAMIC_DAILY", "BUDGET_MODE_DYNAMIC_DAILY_BUDGET"))'
blk = ct[i:end]
if blk.count(OLD) != 1: sys.exit('PATCH FAIL (nothing written): budget_mode enum anchor count=%d; line: %s' % (blk.count(OLD), ascii(blk[:400])))
new = ct[:i] + blk.replace(OLD, NEW) + ct[end:]
new = new.rstrip('\n') + '\n# p236b: BUDGET_MODE_DYNAMIC_DAILY_BUDGET (القيمة الصحيحة عند تيك توك) مسموحة لـsp_create_campaign؛ _launch_smart ما تغيّر\n'
try: compile(new, CT, 'exec')
except SyntaxError as e: sys.exit('PATCH FAIL (nothing written): syntax: %s' % e)
TEST = @@TEST@@
shutil.copy(BASE + CT, BASE + CT + '.pre236b')
open(BASE + CT, 'w', encoding='utf-8').write(new)
if os.path.isdir(BASE + 'ops'):
    dst = BASE + 'ops/tt-smart-toggle-test.py'
    if os.path.exists(dst): shutil.copy(dst, dst + '.pre236b')
    open(dst, 'w', encoding='utf-8').write(TEST); os.chmod(dst, 0o755)
print('APPLY236B_OK catalog: sp_create_campaign accepts BUDGET_MODE_DYNAMIC_DAILY_BUDGET + test script v2 (SA_MODE)')
