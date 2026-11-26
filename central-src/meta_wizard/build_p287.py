import json, os, base64, lzma
H = os.path.dirname(os.path.abspath(__file__))
WIZ = open(os.path.join(H, "wizard.py"), encoding="utf-8").read()
T = r'''import os, re, shutil, subprocess, sys
BASE = os.environ.get('P287_BASE', '/opt/central/')
WIZ = @@WIZ@@
pi = 'n8n/wf_ingress.py'
def die(m): sys.exit('PATCH FAIL (nothing written): ' + m)
s = open(BASE + pi, encoding='utf-8').read()
wp = BASE + 'meta_wizard/wizard.py'
if 'p287' in s:
    if os.path.exists(wp) and open(wp, encoding='utf-8').read() == WIZ: print('APPLY287_OK changed=0 (already applied)'); sys.exit(0)
    die('ingress has p287 but meta_wizard/wizard.py differs')
def lines_with(t, k): return ' | '.join(ascii(l.strip()[:230]) for l in t.split('\n') if k in l)[:600]
fails = []
mA = list(re.finditer(r"else if \(ck === 'gd'\) \{ cmd = 'guide'; uiv = String\(d\.cb\); \}", s))
if len(mA) != 1: fails.append("callback anchor (ck === 'gd', needs p209) count=%d; lines: %s" % (len(mA), lines_with(s, "ck ===")))
mB = list(re.finditer(r"guide\s*:\s*36\s*,\s*'[^'\n]*'\s*:\s*36", s))
if len(mB) != 1: fails.append("cmd map anchor (guide: 36, ...: 36) count=%d" % len(mB))
mC = list(re.finditer(r'("Command",\s*"n8n-nodes-base\.switch",\s*[\d.]+,\s*\{[^}\n]*"numberOutputs":\s*)37\b', s))
if len(mC) != 1: fails.append('Command numberOutputs=37 anchor count=%d; lines: %s' % (len(mC), lines_with(s, '"Command"')))
mD = list(re.finditer(r'(?m)^([ \t]*)_gdm\.build\(b, w, sw, 36, (\w+), CRT\)[ \t]*$', s))
if len(mD) != 1: fails.append('guide build anchor (needs p209) count=%d' % len(mD))
OLD_SQL = "SELECT 'sn_' || (data::jsonb->>'st'), 3 FROM api.ui_get($1, 'sn:' || $2) WHERE (data::jsonb->>'st') IN ('url', 'vid', 'txt') AND age_s < 1800"
if s.count(OLD_SQL) != 1: fails.append('wzs SQL anchor (needs p197d) count=%d; lines: %s' % (s.count(OLD_SQL), lines_with(s, "'sn_'")))
mE = list(re.finditer(r"(?m)^([ \t]*)const SNV = [^\n]*$", s))
if len(mE) != 1: fails.append('SNV definition anchor count=%d' % len(mE))
mF = list(re.finditer(r"(?m)^([ \t]*)if \(SNV && !SAN && cmd !== 'wiz' && d\.fileId\) \{ cmd = 'snapin'; \}[^\n]*$", s))
if len(mF) != 1: fails.append('SNV file routing rule anchor count=%d' % len(mF))
if fails: die(' || '.join(fails))
I = mD[0].group(1); rep = mD[0].group(2)
block = ('\n' + I + "_fmp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'meta_wizard', 'wizard.py')   # p287: معالج فيسبوك بالأهداف\n"
         + I + 'if os.path.exists(_fmp):\n'
         + I + "    _fms = importlib.util.spec_from_file_location('meta_wizard', _fmp); _fmm = importlib.util.module_from_spec(_fms); _fms.loader.exec_module(_fmm)\n"
         + I + '    _fmm.build(b, w, sw, 37, ' + rep + ', CRT)')
DEF = "\n" + mE[0].group(1) + "const FMI = (!d.cb && $input.all().some(i => i.json && /^fm_/.test(String(i.json.step))));   // p287: معالج فيسبوك ينتظر رابط/اسم"
RULE = mF[0].group(1) + "if (FMI && cmd !== 'snapin' && !SAN && cmd !== 'wiz' && !d.fileId && String(d.text || '').trim() && !String(d.text || '').trim().startsWith('/')) { cmd = 'fmin'; args = String(d.text || '').trim(); }   // p287: نص بخطوة المنشور/الموقع/الاسم\n"
SQL_ADD = " UNION ALL SELECT 'fm_' || (data::jsonb->>'st'), 3 FROM api.ui_get($1, 'fm:' || $2) WHERE (data::jsonb->>'st') IN ('post', 'url', 'nm') AND age_s < 1800"
edits = [(mD[0].end(), mD[0].end(), block), (mF[0].start(), mF[0].start(), RULE), (mE[0].end(), mE[0].end(), DEF), (mA[0].end(), mA[0].end(), " else if (ck === 'fm') { cmd = 'fmwiz'; uiv = String(d.cb); }"),
         (mB[0].end(), mB[0].end(), ", fmwiz: 37, fmin: 37, fbobj: 37"), (s.index(OLD_SQL) + len(OLD_SQL), s.index(OLD_SQL) + len(OLD_SQL), SQL_ADD), (mC[0].end(1), mC[0].end(1) + 2, '38')]
new = s
for a0, b0, txt in sorted(edits, key=lambda x: -x[0]): new = new[:a0] + txt + new[b0:]
try: compile(new, pi, 'exec')
except SyntaxError as e: die('syntax %s' % e)
try: compile(WIZ, 'meta_wizard/wizard.py', 'exec')
except SyntaxError as e: die('wizard syntax %s' % e)
os.makedirs(BASE + 'meta_wizard', exist_ok=True)
open(wp, 'w', encoding='utf-8').write(WIZ)
shutil.copy(BASE + pi, BASE + pi + '.pre287'); open(BASE + pi, 'w', encoding='utf-8').write(new)
if os.path.exists(BASE + 'n8n/build.py'):
    r = subprocess.run(['python3', 'n8n/build.py'], cwd=BASE, capture_output=True, text=True)
    if r.returncode:
        shutil.copy(BASE + pi + '.pre287', BASE + pi); sys.exit('PATCH FAIL: build failed, restored: ' + (r.stderr or r.stdout)[-400:])
print('APPLY287_OK Facebook objectives wizard: /fbobj + callbacks fm: (cmd fmwiz/fmin -> output 37, Command outputs 38)')
'''
body = T.replace("@@WIZ@@", json.dumps(WIZ, ensure_ascii=False))
open(os.path.join(H, "..", "ops", "p287-meta-wizard.py.txt"), "w", encoding="utf-8").write(body)
b = base64.b64encode(lzma.compress(body.encode("utf-8"), preset=9 | lzma.PRESET_EXTREME)).decode()
line = "echo '%s' | base64 -d | xz -d | python3 && cd /opt/central && bash deploy/update.sh && echo \"markers: ingress p287=$(grep -c p287 n8n/wf_ingress.py) (expect >=1) wizard=$(ls meta_wizard/wizard.py)\"\n" % b
open(os.path.join(H, "..", "..", "out", "p287s.txt"), "w").write(line)
print(len(line))
