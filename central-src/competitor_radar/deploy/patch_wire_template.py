import os, re, shutil, subprocess, sys
BASE = os.environ.get('P250_BASE', '/opt/central/')
PSQL = os.environ.get('P250_PSQL', 'docker exec central-stg-pg psql -U postgres -d central -At -c')
PAGES = @@PAGES@@
def fail(m): sys.exit('PATCH FAIL (nothing written): ' + m)
pi, pu = 'n8n/wf_ingress.py', 'n8n/ui_pages.py'
si, su = open(BASE + pi, encoding='utf-8').read(), open(BASE + pu, encoding='utf-8').read()
pages_path = BASE + 'competitor_radar/pages.py'
files_ok = os.path.exists(pages_path) and open(pages_path, encoding='utf-8').read() == PAGES
if 'p250' in si and 'p250' in su and files_ok: print('APPLY250_OK changed=0 (already applied)'); sys.exit(0)
if ('p250' in si) != ('p250' in su): fail('half-applied state (ingress=%s ui_pages=%s)' % ('p250' in si, 'p250' in su))
def lines_with(s, kw, n=3): return ' | '.join([ascii(l.strip()[:230]) for l in s.split('\n') if kw in l][:n]) or 'none'
FAILS = []
# ---- شرط مسبق: مخطط الرادار موجود و app_runtime يقدر ينفّذ config (وإلا يكسر استعلام الرئيسية لكل العملاء) ----
chk = "select coalesce(to_regprocedure('competitor_radar.config(text)')::text,'MISSING') || '|' || coalesce(to_regprocedure('competitor_radar.service_key()')::text,'MISSING') || '|' || coalesce(has_function_privilege('app_runtime','competitor_radar.config(text)','EXECUTE')::text,'f')"
try:
    r = subprocess.run(PSQL.split() + [chk], capture_output=True, text=True, timeout=40)
    out = (r.stdout or '').strip()
except Exception as e:
    out = 'ERR %s' % type(e).__name__
if out != 'competitor_radar.config(text)|competitor_radar.service_key()|true': FAILS.append('DB precondition not met (apply p251 first: schema competitor_radar + grants): %s' % ascii(out[:200]))
new_i, new_u = si, su
if 'p250' not in si:
    mA = list(re.finditer(r"else if \(ck === 'gd'\) \{ cmd = 'guide'; uiv = String\(d\.cb\); \}", si))
    mB = list(re.finditer(r"\bguide\s*:\s*36\b", si))
    mC = list(re.finditer(r'("Command",\s*"n8n-nodes-base\.switch",\s*[\d.]+,\s*\{[^}\n]*"numberOutputs":\s*)37\b', si))
    mD = list(re.finditer(r"(?m)^([ \t]*)_gdm\.build\(b, w, sw, 36, (\w+), CRT\)[ \t]*$", si))
    mE = list(re.finditer(r"(AND age_s < 1800)(\s+ORDER BY 2)(\")", si))
    mF = list(re.finditer(r"(?m)^([ \t]*)const SNU = [^\n]*$", si))
    mG = list(re.finditer(r"(?m)^([ \t]*)if \(SNU && SNU\.indexOf\('http'\) === 0 && !SAN && cmd !== 'wiz'\) \{[^\n]*$", si))
    for nm, ms, kw in (('callback gd route', mA, 'ck ==='), ('cmd map guide:36', mB, 'guide'), ('Command numberOutputs 37', mC, '"Command"'), ('guide build line', mD, '.build(b, w, sw'),
                       ('wzs sn_url SQL tail', mE, 'sn_url'), ('const SNU', mF, 'SNU'), ('SNU routing rule', mG, 'SNU')):
        if len(ms) != 1: FAILS.append('ingress %s count=%d; lines: %s' % (nm, len(ms), lines_with(si, kw)))
    if re.search(r"\bradar\s*:\s*37\b", si): FAILS.append('ingress already has radar:37 without p250 marker')
if 'p250' not in su:
    uA = list(re.finditer(r"smart_audience\.enabled\(\$1\)::text, NULL, NULL, NULL, NULL, NULL\"\)", su))
    uB = list(re.finditer(r"saOn: rows\.some\(r => r\.kind === 'sa' && r\.a === 'true'\)( \};)", su))
    uC = list(re.finditer(r"(?m)^([ \t]*)if \(P\.saOn\) kb\.push\(\[\{ t: '[^'\n]*', c: 'sa' \}\]\);[^\n]*$", su))
    for nm, ms, kw in (('home SQL sa row', uA, 'smart_audience.enabled'), ('saOn flag', uB, 'saOn'), ('saOn button', uC, 'saOn')):
        if len(ms) != 1: FAILS.append('ui_pages %s count=%d; lines: %s' % (nm, len(ms), lines_with(su, kw)))
if FAILS: fail(' || '.join(FAILS))
if 'p250' not in si:
    I3 = mD[0].group(1); I = I3[:-4] if len(I3) >= 4 else ''; rep = mD[0].group(2); Ig = mF[0].group(1)
    block = ('\n' + I + "_crp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'competitor_radar', 'pages.py')   # p250: رادار المنافسين (مستقل؛ حذف المجلد = رجوع)\n"
             + I + 'if os.path.exists(_crp):\n'
             + I3 + "_crs = importlib.util.spec_from_file_location('competitor_radar_pages', _crp); _crm = importlib.util.module_from_spec(_crs); _crs.loader.exec_module(_crm)\n"
             + I3 + '_crm.build(b, w, sw, 37, ' + rep + ', CRT)')
    edits = [(mD[0].end(), block),
             (mG[0].end(), '\n' + mG[0].group(1) + "if (CRI && CRI.charAt(0) !== '/' && !SAN && !SNU && cmd === 'text') { cmd = 'radar'; args = CRI; }   // p250: نص حر بخطوة إدخال رادار المنافسين"),
             (mF[0].end(), '\n' + Ig + "const CRI = (!d.cb && $input.all().some(i => i.json && String(i.json.step) === 'cr_in')) ? String(d.text || '').trim() : '';   // p250"),
             (mE[0].start(2), " UNION ALL SELECT 'cr_in', 4 FROM api.ui_get($1, 'cr:' || $2) WHERE (data::jsonb->>'st') IN ('add', 'smp', 'mk') AND age_s < 1800"),
             (mB[0].end(), ", radar: 37, 'رادار': 37"),
             (mA[0].end(), " else if (ck === 'cr') { cmd = 'radar'; uiv = String(d.cb); }")]
    # ترتيب التطبيق من الأبعد للأقرب؛ numberOutputs يُعدَّل بدقة (37 -> 38)
    pos37 = mC[0].end(1)
    allp = sorted(edits + [(pos37, None)], key=lambda x: -x[0])
    for pos, txt in allp:
        if txt is None: new_i = new_i[:pos] + '38' + new_i[pos + 2:]
        else: new_i = new_i[:pos] + txt + new_i[pos:]
if 'p250' not in su:
    Ib = uC[0].group(1)
    eu = sorted([(uC[0].end(), '\n' + Ib + "if (P.crOn && kb.length < 8) kb.push([{ t: '\U0001F575️ رادار المنافسين', c: 'cr:m' }]);   // p250: رادار المنافسين (مطفأ = بلا زر)"),
                 (uB[0].start(1), ", crOn: rows.some(r => r.kind === 'cr' && r.a === 'true')"),
                 (uA[0].end() - 2, " \"\n            \"UNION ALL SELECT 'cr', competitor_radar.config($1)->>'enabled', NULL, NULL, NULL, NULL, NULL")], key=lambda x: -x[0])
    for pos, txt in eu: new_u = new_u[:pos] + txt + new_u[pos:]
for nm, t in ((pi, new_i), (pu, new_u)):
    try: compile(t, nm, 'exec')
    except SyntaxError as e: fail('syntax %s: %s' % (nm, e))
compile(PAGES, 'competitor_radar/pages.py', 'exec')
os.makedirs(BASE + 'competitor_radar/', exist_ok=True)
for f, o, n in ((pi, si, new_i), (pu, su, new_u)):
    if n != o: shutil.copy(BASE + f, BASE + f + '.pre250')
open(pages_path, 'w', encoding='utf-8').write(PAGES)
for f, o, n in ((pi, si, new_i), (pu, su, new_u)):
    if n != o: open(BASE + f, 'w', encoding='utf-8').write(n)
if (new_i != si or new_u != su) and os.path.exists(BASE + 'n8n/build.py'):
    r = subprocess.run(['python3', 'n8n/build.py'], cwd=BASE, capture_output=True, text=True)
    if r.returncode:
        for f in (pi, pu):
            if os.path.exists(BASE + f + '.pre250'): shutil.copy(BASE + f + '.pre250', BASE + f)
        sys.exit('PATCH FAIL: build failed, restored: ' + (r.stderr or r.stdout)[-400:])
print('APPLY250_OK radar wiring: /radar + cr: callbacks (Command output 37, outputs 38) + typed-input capture row + home button (flag-gated)')
