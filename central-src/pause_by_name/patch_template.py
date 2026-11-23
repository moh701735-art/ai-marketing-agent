import os, re, shutil, sys
BASE = os.environ.get('P240A_BASE', '/opt/central/')
SV = 'broker/app/service.py'
sv = open(BASE + SV, encoding='utf-8').read()
if 'p240a' in sv: print('APPLY240A_OK changed=0 (already applied)'); sys.exit(0)
METHOD = r'''@@METHOD@@'''
if "'''" in METHOD: sys.exit('PATCH FAIL (nothing written): method contains triple single quotes')
fails = []
def lines_with(txt, kw): return ' | '.join(ascii(l.strip()[:200]) for l in txt.split('\n') if kw in l)[:500] or 'none'
m_def = list(re.finditer(r'(?m)^    async def _find_campaign\(', sv))
if len(m_def) != 1: fails.append('_find_campaign def anchor count=%d' % len(m_def))
m_if = list(re.finditer(r'(?m)^([ \t]*)if (\w+) == "meta" and (\w+) in \("meta\.resolve_post"', sv))
m_ret = list(re.finditer(r'(?m)^([ \t]*)return await metaflow\.run\(([^)\n]*)\)[ \t]*$', sv))
if len(m_if) != 1 or len(m_ret) != 1: fails.append('dispatch anchors: meta-if=%d metaflow.run=%d; lines: %s' % (len(m_if), len(m_ret), lines_with(sv, 'metaflow')))
if 'asyncio' not in sv: fails.append('service.py does not use asyncio')
if not fails:
    args = [a.strip() for a in m_ret[0].group(2).split(',')]
    if len(args) != 6 or args[0] != 'self': fails.append('metaflow.run args shape unexpected: %s' % ascii(m_ret[0].group(2)))
if fails: sys.exit('PATCH FAIL (nothing written): ' + ' || '.join(fails))
plat, opn = m_if[0].group(2), m_if[0].group(3); I = m_if[0].group(1)
ctx, params, idem = args[2], args[4], args[5]
disp = (I + 'if ' + plat + ' == "tiktok" and ' + opn + ' == "tiktok.pause_by_name":   # p240a\n'
        + I + '    return await self._pause_by_name(' + ctx + ', ' + params + ', ' + idem + ')\n')
if m_if[0].start() > m_def[0].start(): sys.exit('PATCH FAIL (nothing written): dispatch is after _find_campaign (unexpected layout)')
new = sv[:m_if[0].start()] + disp + sv[m_if[0].start():m_def[0].start()] + METHOD + sv[m_def[0].start():]
try: compile(new, SV, 'exec')
except SyntaxError as e: sys.exit('PATCH FAIL (nothing written): syntax %s' % e)
shutil.copy(BASE + SV, BASE + SV + '.pre240a')
open(BASE + SV, 'w', encoding='utf-8').write(new)
print('APPLY240A_OK Broker composite op tiktok.pause_by_name (exact-name pause, DISABLE only, read-back) p240a')
