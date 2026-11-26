import json, os, base64, lzma
H = os.path.dirname(os.path.abspath(__file__))
WIZ = open(os.path.join(H, "wizard.py"), encoding="utf-8").read()
T = r'''import os, re, shutil, subprocess, sys
BASE = os.environ.get('P288_BASE', '/opt/central/')
WIZ = @@WIZ@@
pi = 'n8n/wf_ingress.py'; wp = BASE + 'meta_wizard/wizard.py'
def die(m): sys.exit('PATCH FAIL (nothing written): ' + m)
s = open(BASE + pi, encoding='utf-8').read()
NEW_RX = "/^wz:ac:(?:act_[0-9]{5,25}|[0-9]{5,17})$/"
OLD_RX = "/^wz:ac:act_[0-9]{5,25}$/"
if 'p288' in s:
    # ترقية: النسخة الأولى كانت تقبل act_ فقط. نحدّث القاعدة والمعالج.
    cur = open(wp, encoding='utf-8').read() if os.path.exists(wp) else ''
    if NEW_RX in s and cur == WIZ: print('APPLY288_OK changed=0 (already applied)'); sys.exit(0)
    if NEW_RX not in s and s.count(OLD_RX) != 1: die('p288 rule has an unexpected shape; lines: %s' % ' | '.join(ascii(l.strip()[:230]) for l in s.split('\n') if 'wz:ac:' in l)[:600])
    up = s.replace(OLD_RX, NEW_RX, 1) if NEW_RX not in s else s
    for name, src in (('ingress', up), ('wizard', WIZ)):
        try: compile(src, name, 'exec')
        except SyntaxError as e: die('syntax %s %s' % (name, e))
    if os.path.exists(wp): shutil.copy(wp, wp + '.pre288b')
    open(wp, 'w', encoding='utf-8').write(WIZ)
    if up != s:
        shutil.copy(BASE + pi, BASE + pi + '.pre288b'); open(BASE + pi, 'w', encoding='utf-8').write(up)
    if os.path.exists(BASE + 'n8n/build.py'):
        r = subprocess.run(['python3', 'n8n/build.py'], cwd=BASE, capture_output=True, text=True)
        if r.returncode:
            if os.path.exists(BASE + pi + '.pre288b') and up != s: shutil.copy(BASE + pi + '.pre288b', BASE + pi)
            if os.path.exists(wp + '.pre288b'): shutil.copy(wp + '.pre288b', wp)
            sys.exit('PATCH FAIL: build failed, restored: ' + (r.stderr or r.stdout)[-400:])
    print('APPLY288_OK upgraded: accepts Facebook accounts stored with or without the act_ prefix'); sys.exit(0)
if 'p287' not in s or not os.path.exists(wp): die('p287 is not applied (meta_wizard missing)')
def lines_with(t, k): return ' | '.join(ascii(l.strip()[:230]) for l in t.split('\n') if k in l)[:600]
fails = []
SQL_OLD = "UNION ALL SELECT 'fm_' || (data::jsonb->>'st'), 3 FROM api.ui_get($1, 'fm:' || $2) WHERE (data::jsonb->>'st') IN ('post', 'url', 'nm') AND age_s < 1800"
if s.count(SQL_OLD) != 1: fails.append('p287 wzs SQL anchor count=%d; lines: %s' % (s.count(SQL_OLD), lines_with(s, "'fm_'")))
mE = list(re.finditer(r"(?m)^([ \t]*)const FMI = [^\n]*$", s))
if len(mE) != 1: fails.append('FMI definition anchor count=%d' % len(mE))
mF = list(re.finditer(r"(?m)^([ \t]*)if \(FMI && cmd !== 'snapin'[^\n]*$", s))
if len(mF) != 1: fails.append('FMI routing rule anchor count=%d' % len(mF))
if fails: die(' || '.join(fails))
SQL_ADD = " UNION ALL SELECT 'fp_pass', 3 FROM api.ui_get($1, 'fm:' || $2) WHERE (data::jsonb->>'via') = 'wz' AND (data::jsonb->>'st') = 'obj' AND age_s < 900"
DEF = "\n" + mE[0].group(1) + "const FMP = $input.all().some(i => i.json && String(i.json.step) === 'fp_pass');   // p288: قائمة الأهداف معروضة الآن (واتساب يمرّ للمعالج القديم)"
RULE = mF[0].group(1) + "if (d.cb && /^wz:ac:(?:act_[0-9]{5,25}|[0-9]{5,17})$/.test(String(d.cb)) && !FMP) { cmd = 'fmwiz'; uiv = String(d.cb); }   // p288: قائمة الأهداف بعد اختيار حساب فيسبوك بالمعالج\n"
edits = [(mF[0].start(), mF[0].start(), RULE), (mE[0].end(), mE[0].end(), DEF), (s.index(SQL_OLD) + len(SQL_OLD), s.index(SQL_OLD) + len(SQL_OLD), SQL_ADD)]
new = s
for a0, b0, txt in sorted(edits, key=lambda x: -x[0]): new = new[:a0] + txt + new[b0:]
for name, src in (('ingress', new), ('wizard', WIZ)):
    try: compile(src, name, 'exec')
    except SyntaxError as e: die('syntax %s %s' % (name, e))
shutil.copy(wp, wp + '.pre288'); open(wp, 'w', encoding='utf-8').write(WIZ)
shutil.copy(BASE + pi, BASE + pi + '.pre288'); open(BASE + pi, 'w', encoding='utf-8').write(new)
if os.path.exists(BASE + 'n8n/build.py'):
    r = subprocess.run(['python3', 'n8n/build.py'], cwd=BASE, capture_output=True, text=True)
    if r.returncode:
        shutil.copy(BASE + pi + '.pre288', BASE + pi); shutil.copy(wp + '.pre288', wp); sys.exit('PATCH FAIL: build failed, restored: ' + (r.stderr or r.stdout)[-400:])
print('APPLY288_OK objective list after choosing a Facebook ad account in the creation wizard (WhatsApp stays on the legacy flow)')
'''
body = T.replace("@@WIZ@@", json.dumps(WIZ, ensure_ascii=False))
open(os.path.join(H, "..", "ops", "p288-meta-wizard-entry.py.txt"), "w", encoding="utf-8").write(body)
b = base64.b64encode(lzma.compress(body.encode("utf-8"), preset=9 | lzma.PRESET_EXTREME)).decode()
line = "echo '%s' | base64 -d | xz -d | python3 && cd /opt/central && bash deploy/update.sh && echo \"markers: ingress p288=$(grep -c p288 n8n/wf_ingress.py) (expect >=1)\"\n" % b
open(os.path.join(H, "..", "..", "out", "p288s.txt"), "w").write(line)
print(len(line))
