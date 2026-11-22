import os, shutil, subprocess, sys
BASE = os.environ.get('P230D_BASE', '/opt/central/')
IN = 'n8n/wf_ingress.py'
ing = open(BASE + IN, encoding='utf-8').read()
if 'p230d' in ing: print('APPLY230D_OK changed=0 (already applied)'); sys.exit(0)
HEAD = '// p230: نافذة جدولة التيك توك'
if ing.count(HEAD) != 1: sys.exit('PATCH FAIL (nothing written): p230 block anchor count=%d (p230 must be applied first)' % ing.count(HEAD))
OLD = r'''@@OLD@@'''
NEW = r'''@@NEW@@'''
i = ing.index(HEAD); ls = ing.rfind('\n', 0, i) + 1; IND = ing[ls:i]
if IND.strip(): sys.exit('PATCH FAIL (nothing written): block not at line start')
def ind(b): return ''.join((IND + ln if ln.strip() else ln) + '\n' for ln in b.rstrip('\n').split('\n'))
old_t, new_t = ind(OLD), ind(NEW)
if ing[ls:ls + len(old_t)] != old_t:
    k = 0
    while k < len(old_t) and ing[ls + k] == old_t[k]: k += 1
    sys.exit('PATCH FAIL (nothing written): installed p230 block differs from the expected one at char %d: installed=%s expected=%s' % (k, ascii(ing[ls + k:ls + k + 80]), ascii(old_t[k:k + 80])))
new_ing = ing[:ls] + new_t + ing[ls + len(old_t):]
shutil.copy(BASE + IN, BASE + IN + '.pre230d')
open(BASE + IN, 'w', encoding='utf-8').write(new_ing)
if os.path.exists(BASE + 'n8n/build.py'):
    r = subprocess.run(['python3', 'n8n/build.py'], cwd=BASE, capture_output=True, text=True)
    if r.returncode:
        shutil.copy(BASE + IN + '.pre230d', BASE + IN)
        sys.exit('PATCH FAIL: build failed, restored: ' + (r.stderr or r.stdout)[-400:])
print('APPLY230D_OK clock parser works without a start verb (ارفع حمله ساعه 10 بليل وقفها ساعه 7 صبح) + noun words between verb and clock')
