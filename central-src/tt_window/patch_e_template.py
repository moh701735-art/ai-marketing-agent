import os, shutil, subprocess, sys
BASE = os.environ.get('P230E_BASE', '/opt/central/')
IN = 'n8n/wf_ingress.py'
ing = open(BASE + IN, encoding='utf-8').read()
if '// p230e' in ing: print('APPLY230E_OK changed=0 (already applied)'); sys.exit(0)
OLD = r'''@@OLD@@'''
NEW = r'''@@NEW@@'''
if ing.count(OLD) != 1: sys.exit('PATCH FAIL (nothing written): installed to24 line count=%d (p230d must be applied and the line unmodified); lines: %s' % (ing.count(OLD), ' | '.join(ascii(l.strip()[:160]) for l in ing.split('\n') if 'const to24' in l)[:500]))
new_ing = ing.replace(OLD, NEW, 1)
try: compile(new_ing, 'ingress', 'exec')
except SyntaxError as e: sys.exit('PATCH FAIL (nothing written): syntax %s' % e)
shutil.copy(BASE + IN, BASE + IN + '.pre230e')
open(BASE + IN, 'w', encoding='utf-8').write(new_ing)
if os.path.exists(BASE + 'n8n/build.py'):
    r = subprocess.run(['python3', 'n8n/build.py'], cwd=BASE, capture_output=True, text=True)
    if r.returncode:
        shutil.copy(BASE + IN + '.pre230e', BASE + IN)
        sys.exit('PATCH FAIL: build failed, restored: ' + (r.stderr or r.stdout)[-400:])
print('APPLY230E_OK TikTok window: «1-5 بالليل» = 01:00-05:00 بعد منتصف الليل، «6-11 بالليل» = 18:00-23:00')
