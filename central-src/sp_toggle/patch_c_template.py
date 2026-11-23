import os, shutil, sys
BASE = os.environ.get('P236C_BASE', '/opt/central/')
CT = 'broker/app/catalog.py'
ct = open(BASE + CT, encoding='utf-8').read()
if 'p236c' in ct: print('APPLY236C_OK changed=0 (already applied)'); sys.exit(0)
if 'p236b' not in ct: sys.exit('PATCH FAIL (nothing written): p236b must be applied first')
i = ct.find('Op("tiktok.sp_create_campaign"')
if i < 0: sys.exit('PATCH FAIL (nothing written): sp_create_campaign op not found')
j = ct.find('\n    Op(', i + 5); k = ct.find('\n    #', i + 5); ends = [x for x in (j, k) if x > 0]; end = min(ends) if ends else len(ct)
OLD = '"budget_auto_adjust_strategy": P("enum", values=("AUTO_BUDGET_INCREASE", "UNSET"))'
blk = ct[i:end]
if blk.count(OLD) != 1: sys.exit('PATCH FAIL (nothing written): toggle param anchor count=%d' % blk.count(OLD))
new = ct[:i] + blk.replace(OLD, OLD + ', "request_id": P("id")') + ct[end:]
new = new.rstrip('\n') + '\n# p236c: request_id رقمي اختياري لـsp_create_campaign (Smart+ يطلبه)\n'
try: compile(new, CT, 'exec')
except SyntaxError as e: sys.exit('PATCH FAIL (nothing written): syntax: %s' % e)
TEST = @@TEST@@
shutil.copy(BASE + CT, BASE + CT + '.pre236c')
open(BASE + CT, 'w', encoding='utf-8').write(new)
if os.path.isdir(BASE + 'ops'):
    dst = BASE + 'ops/tt-smart-toggle-test.py'
    if os.path.exists(dst): shutil.copy(dst, dst + '.pre236c')
    open(dst, 'w', encoding='utf-8').write(TEST); os.chmod(dst, 0o755)
print('APPLY236C_OK catalog: optional request_id on sp_create_campaign + test script v3 (sends request_id, prints error message as hex)')
