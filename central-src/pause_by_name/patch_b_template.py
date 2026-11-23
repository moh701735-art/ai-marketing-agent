import os, re, shutil, subprocess, sys
BASE = os.environ.get('P240B_BASE', '/opt/central/')
IN = 'n8n/wf_ingress.py'
ing = open(BASE + IN, encoding='utf-8').read()
if 'p240b' in ing: print('APPLY240B_OK changed=0 (already applied)'); sys.exit(0)
if 'p240a' not in open(BASE + 'broker/app/service.py', encoding='utf-8').read(): sys.exit('PATCH FAIL (nothing written): p240a (Broker) must be applied first')
DECIDE = r'''@@DECIDE@@'''
CHOOSE = r'''@@CHOOSE@@'''
for b in (DECIDE, CHOOSE):
    if '"""' in b or "'''" in b: sys.exit('PATCH FAIL (nothing written): snippet contains triple quotes')
fails = []
def block(name):
    ms = list(re.finditer(r'code\(w,\s*["\']' + re.escape(name) + r'["\'],\s*r"""', ing))
    if len(ms) != 1: fails.append('node %s start anchor count=%d; lines: %s' % (name, len(ms), ' | '.join(ascii(l.strip()[:120]) for l in ing.split('\n') if name in l)[:300])); return None
    e = ing.find('"""', ms[0].end())
    if e < 0: fails.append('node %s end not found' % name); return None
    return ms[0].end(), e
bd, bp, bc = block('AI: decide'), block('Stat: prep'), block('Stat: choose')
edits = []
if bd:
    txt = ing[bd[0]:bd[1]]; A = 'const r = $input.first().json;'
    if txt.count(A) != 1: fails.append('decide anchor count=%d; lines: %s' % (txt.count(A), ' | '.join(ascii(l.strip()[:160]) for l in txt.split('\n') if '$input' in l)[:400]))
    else: i = bd[0] + txt.index(A); edits.append((i, i + len(A), DECIDE.rstrip('\n')))
if bp:
    txt = ing[bp[0]:bp[1]]; A = "op: 'tiktok.find_campaign',"
    if txt.count(A) != 1: fails.append('prep anchor count=%d; lines: %s' % (txt.count(A), ' | '.join(ascii(l.strip()[:200]) for l in txt.split('\n') if 'find_campaign' in l or 'return [' in l)[:500]))
    else:
        i = bp[0] + txt.index(A)
        new = ("op: (($('AI: decide').first().json.it || {}).act === 'pause') ? 'tiktok.pause_by_name' : 'tiktok.find_campaign', "
               "...((($('AI: decide').first().json.it || {}).act === 'pause') ? { idem: 'tgupd-' + $('Route').first().json.chatId + '-' + $('Route').first().json.updateId + '-pbn' } : {}), /* p240b */ ")   # p240b
        edits.append((i, i + len(A), new))
if bc: edits.append((bc[0], bc[0], '\n' + CHOOSE.rstrip('\n')))
if fails: sys.exit('PATCH FAIL (nothing written): ' + ' || '.join(fails))
new_ing = ing
for a, b, t in sorted(edits, key=lambda e: -e[0]): new_ing = new_ing[:a] + t + new_ing[b:]
shutil.copy(BASE + IN, BASE + IN + '.pre240b')
open(BASE + IN, 'w', encoding='utf-8').write(new_ing)
if os.path.exists(BASE + 'n8n/build.py'):
    r = subprocess.run(['python3', 'n8n/build.py'], cwd=BASE, capture_output=True, text=True)
    if r.returncode:
        shutil.copy(BASE + IN + '.pre240b', BASE + IN)
        sys.exit('PATCH FAIL: build failed, restored: ' + (r.stderr or r.stdout)[-400:])
print('APPLY240B_OK text "طفي حملة X" -> pause-by-name via Stat chain (decide override + prep op + choose reply) p240b')
