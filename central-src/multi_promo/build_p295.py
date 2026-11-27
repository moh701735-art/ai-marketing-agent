import json, os, base64, lzma
H = os.path.dirname(os.path.abspath(__file__))
MOD = open(os.path.join(H, "promo.py"), encoding="utf-8").read()
T = r'''import os, re, shutil, subprocess, sys
BASE = os.environ.get('P295_BASE', '/opt/central/')
MOD = @@MOD@@
pi = 'n8n/wf_ingress.py'; mp = BASE + 'multi_promo/promo.py'
def die(m): sys.exit('PATCH FAIL (nothing written): ' + m)
s = open(BASE + pi, encoding='utf-8').read()
if 'p295' in s:
    if os.path.exists(mp) and open(mp, encoding='utf-8').read() == MOD: print('APPLY295_OK changed=0 (already applied)'); sys.exit(0)
    die('ingress has p295 but multi_promo/promo.py differs')
def lines_with(t, k): return ' | '.join(ascii(l.strip()[:230]) for l in t.split('\n') if k in l)[:600]
fails = []
CBA = "else if (ck === 'fm') { cmd = 'fmwiz'; uiv = String(d.cb); }"
if s.count(CBA) != 1: fails.append("callback anchor (ck === 'fm', needs p287) count=%d; lines: %s" % (s.count(CBA), lines_with(s, "ck ===")))
mB = list(re.finditer(r"\bfbobj\s*:\s*(\d+)\b", s))
if len(mB) != 1: fails.append('cmd map anchor (fbobj: N, needs p287) count=%d' % len(mB))
mC = list(re.finditer(r'("Command",\s*"n8n-nodes-base\.switch",\s*[\d.]+,\s*\{[^}\n]*"numberOutputs":\s*)(\d+)\b', s))
if len(mC) != 1: fails.append('Command numberOutputs anchor count=%d; lines: %s' % (len(mC), lines_with(s, '"Command"')))
K = int(mC[0].group(2)) if len(mC) == 1 else 0
if len(mC) == 1 and K < 39: fails.append('Command numberOutputs=%d is below 39 (needs p287 meta wizard at 38)' % K)
if K and re.search(r'\.build\(b, w, sw, %d,' % K, s): fails.append('output index %d is already used by another module build' % K)
mD = list(re.finditer(r'(?m)^([ \t]*)(\w+)\.build\(b, w, sw, %d, (\w+), CRT\)[ \t]*$' % (K - 1), s)) if K else []
if len(mD) != 1: fails.append('last module build anchor (index %d) count=%d; lines: %s' % (K - 1, len(mD), lines_with(s, '.build(b, w, sw,')))
mF = list(re.finditer(r"(?m)^([ \t]*)if \(SNV && !SAN && cmd !== 'wiz' && d\.fileId\) \{ cmd = 'snapin'; \}[^\n]*$", s))
if len(mF) != 1: fails.append('SNV file routing rule anchor count=%d' % len(mF))
if fails: die(' || '.join(fails))
I = mD[0].group(1); rep = mD[0].group(3)
block = ('\n' + I + "_mpp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'multi_promo', 'promo.py')   # p295: كليشه واحدة لكل المنصات\n"
         + I + 'if os.path.exists(_mpp):\n'
         + I + "    _mps = importlib.util.spec_from_file_location('multi_promo', _mpp); _mpm = importlib.util.module_from_spec(_mps); _mps.loader.exec_module(_mpm)\n"
         + I + '    _mpm.build(b, w, sw, ' + str(K) + ', ' + rep + ', CRT)')
RULE = mF[0].group(1) + "if (!d.cb && /^[ ]*(?:رو[ّ]?ج|ارفع|promo)[ ]*[:：].*(?:تيك|تك ?توك|فيس|انستا|سناب|snap|tiktok|facebook|instagram|ميتا)/i.test(String(d.text || d.caption || '')) && !String(d.text || d.caption || '').trim().startsWith('/')) { cmd = 'promo'; args = String(d.text || d.caption || ''); }   // p295: كليشه المنصات المتعددة\n"
edits = [(mD[0].end(), mD[0].end(), block), (mF[0].start(), mF[0].start(), RULE), (s.index(CBA) + len(CBA), s.index(CBA) + len(CBA), " else if (ck === 'mp') { cmd = 'promocb'; uiv = String(d.cb); }"),
         (mB[0].end(), mB[0].end(), ", promo: %d, promocb: %d" % (K, K)), (mC[0].end(1), mC[0].end(2), str(K + 1))]
new = s
for a0, b0, txt in sorted(edits, key=lambda x: -x[0]): new = new[:a0] + txt + new[b0:]
try: compile(new, pi, 'exec')
except SyntaxError as e: die('syntax %s' % e)
try: compile(MOD, 'multi_promo/promo.py', 'exec')
except SyntaxError as e: die('module syntax %s' % e)
os.makedirs(BASE + 'multi_promo', exist_ok=True)
open(mp, 'w', encoding='utf-8').write(MOD)
shutil.copy(BASE + pi, BASE + pi + '.pre295'); open(BASE + pi, 'w', encoding='utf-8').write(new)
if os.path.exists(BASE + 'n8n/build.py'):
    r = subprocess.run(['python3', 'n8n/build.py'], cwd=BASE, capture_output=True, text=True)
    if r.returncode:
        shutil.copy(BASE + pi + '.pre295', BASE + pi); sys.exit('PATCH FAIL: build failed, restored: ' + (r.stderr or r.stdout)[-400:])
print('APPLY295_OK multi-platform promo klisheh: «روّج: تيك توك + فيسبوك + سناب» + callbacks mp: (cmd promo/promocb -> output ' + str(K) + ', Command outputs ' + str(K + 1) + ')')
'''
body = T.replace("@@MOD@@", json.dumps(MOD, ensure_ascii=False))
open(os.path.join(H, "..", "ops", "p295-multi-promo.py.txt"), "w", encoding="utf-8").write(body)
b = base64.b64encode(lzma.compress(body.encode("utf-8"), preset=9 | lzma.PRESET_EXTREME)).decode()
line = "echo '%s' | base64 -d | xz -d | python3 && cd /opt/central && bash deploy/update.sh && echo \"markers: ingress p295=$(grep -c p295 n8n/wf_ingress.py) (expect >=1) module=$(ls multi_promo/promo.py)\"\n" % b
open(os.path.join(H, "..", "..", "out", "p295s.txt"), "w").write(line)
print(len(line))
