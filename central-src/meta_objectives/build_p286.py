import json, os, base64, lzma
H = os.path.dirname(os.path.abspath(__file__))
rd = lambda n: open(os.path.join(H, n), encoding="utf-8").read()
FLOW, CAT, BUILD, TOOL = rd("flow.py.txt"), rd("catalog.py.txt"), rd("build_block.py.txt"), rd("ops/meta_obj_test.py")
T = r'''import os, re, sys, shutil
BASE = os.environ.get('P286_BASE', '/opt/central/')
MF, SV, CT, TL = 'broker/app/metaflow.py', 'broker/app/service.py', 'broker/app/catalog.py', 'ops/meta-obj-test.py'
FLOW = @@FLOW@@
CAT = @@CAT@@
BUILD = @@BUILD@@
TOOL = @@TOOL@@
def die(m): sys.exit('PATCH FAIL (nothing written): ' + m)
mf, sv, ct = [open(BASE + f, encoding='utf-8').read() for f in (MF, SV, CT)]
have = [('p286' in mf), ('p286' in sv), ('p286' in ct)]
if all(have):
    tp = BASE + TL
    if os.path.exists(tp) and open(tp, encoding='utf-8').read() == TOOL: print('APPLY286_OK changed=0 (already applied)'); sys.exit(0)
    die('p286 markers present but the test tool differs')
if any(have): die('p286 is partially applied (%s) - restore the .pre286 files first' % have)
for nm in ('def launch_whatsapp', 'def _bad', 'def _fail', 'def _call', 'def resolve_post'):
    if not re.search(r'(?m)^(async )?' + re.escape(nm) + r'\b', mf): die('metaflow.py lacks ' + nm)
if not re.search(r'(?m)^ACCT_RE\b', mf): die('metaflow.py lacks ACCT_RE')
rx = re.compile(r'(?m)^(?P<ind>[ \t]*)(?P<kw>if|elif) (?P<v>\w+) == "meta\.launch_whatsapp":[ \t]*\n(?P=ind)[ \t]+return (?:await )?launch_whatsapp\((?P<args>[^\n]*)\)')
ms = list(rx.finditer(mf))
if len(ms) != 1: die('dispatcher anchor count=%d (expected 1)' % len(ms))
m = ms[0]; args = [a.strip() for a in m.group('args').split(',')]
if len(args) < 4: die('unexpected launch_whatsapp call shape: ' + m.group('args'))
pn = args[3]
ins = '%sif %s == "meta.launch_whatsapp" and isinstance(%s, dict) and %s.get("objective_key"):   # p286\n%s    return await launch_objective(%s)\n' % (m.group('ind'), m.group('v'), pn, pn, m.group('ind'), m.group('args'))
new_mf = mf[:m.start()] + ins + mf[m.start():] + '\n' + FLOW
rx2 = re.compile(r'(?m)^(?P<ind>[ \t]*)if op\.name == "meta\.search_related":')
m2 = list(rx2.finditer(sv))
if len(m2) != 1: die('service _build anchor count=%d (expected 1)' % len(m2))
ind = m2[0].group('ind')
blk = ''.join((ind + ln[8:] if ln.startswith('        ') else ln) + '\n' for ln in BUILD.splitlines())
new_sv = sv[:m2[0].start()] + blk + sv[m2[0].start():]
if 'meta.create_adset"' not in ct: die('catalog lacks meta.create_adset')
new_ct = ct.rstrip('\n') + '\n' + CAT
for name, src in ((MF, new_mf), (SV, new_sv), (CT, new_ct), (TL, TOOL)):
    try: compile(src, name, 'exec')
    except SyntaxError as e: die('syntax %s %s' % (name, e))
for f, src in ((MF, new_mf), (SV, new_sv), (CT, new_ct)):
    shutil.copy(BASE + f, BASE + f + '.pre286'); open(BASE + f, 'w', encoding='utf-8').write(src)
tp = BASE + TL
if os.path.exists(tp): shutil.copy(tp, tp + '.pre286')
open(tp, 'w', encoding='utf-8').write(TOOL); os.chmod(tp, 0o755)
print('APPLY286_OK meta objectives (awareness/traffic/engagement): metaflow.launch_objective + service._build branches + catalog ops + ops/meta-obj-test.py; Broker rebuild needed')
'''
body = T
for k, v in (("@@FLOW@@", FLOW), ("@@CAT@@", CAT), ("@@BUILD@@", BUILD), ("@@TOOL@@", TOOL)): body = body.replace(k, json.dumps(v, ensure_ascii=False))
open(os.path.join(H, "..", "ops", "p286-meta-objectives.py.txt"), "w", encoding="utf-8").write(body)
b = base64.b64encode(lzma.compress(body.encode("utf-8"), preset=9 | lzma.PRESET_EXTREME)).decode()
line = "echo '%s' | base64 -d | xz -d | python3 && cd /opt/central && bash deploy/update.sh && echo \"markers: metaflow p286=$(grep -c p286 broker/app/metaflow.py) service=$(grep -c p286 broker/app/service.py) catalog=$(grep -c p286 broker/app/catalog.py) (expect >=1 each)\"\n" % b
open(os.path.join(H, "..", "..", "out", "p286s.txt"), "w").write(line)
print(len(line))
