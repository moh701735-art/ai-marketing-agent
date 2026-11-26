import json, os, base64, lzma
H = os.path.dirname(os.path.abspath(__file__))
PRE = open(os.path.join(H, "prelude.js.txt"), encoding="utf-8").read()
T = r'''import os, re, shutil, subprocess, sys
BASE = os.environ.get('P289_BASE', '/opt/central/')
PRE = @@PRE@@
pj = 'n8n/wf_job_report.py'
def die(m): sys.exit('PATCH FAIL (nothing written): ' + m)
s = open(BASE + pj, encoding='utf-8').read()
if 'p289' in s: print('APPLY289_OK changed=0 (already applied)'); sys.exit(0)
if 'metacamp-block' not in s: die('p173 (metacamp-block) is not in wf_job_report.py')
def lines_with(t, k): return ' | '.join(ascii(l.strip()[:230]) for l in t.split('\n') if k in l)[:600]
fails = []
mF = list(re.finditer(r"campaign_id,campaign_name,spend,impressions,reach,clicks,inline_link_clicks,ctr,actions,account_currency,account_name(?=['\"])", s))
if len(mF) != 1: fails.append('insights fields literal count=%d; lines: %s' % (len(mF), lines_with(s, 'inline_link_clicks')))
mM = list(re.finditer(r"(?m)^([ \t]*)const msg = getA\(c\.actions, 'onsite_conversion\.messaging_conversation_started_7d'\);[ \t]*$", s))
if len(mM) != 1: fails.append('message line anchor count=%d; lines: %s' % (len(mM), lines_with(s, 'messaging_conversation_started_7d')))
if fails: die(' || '.join(fails))
ind = mM[0].group(1)
blk = ''.join((ind + ln[8:] if ln.startswith('        ') else ln) + '\n' for ln in PRE.splitlines())
new = s[:mM[0].start()] + blk + s[mM[0].start():]
new = new.replace(mF[0].group(0), mF[0].group(0) + ',objective', 1)
try: compile(new, pj, 'exec')
except SyntaxError as e: die('syntax %s' % e)
shutil.copy(BASE + pj, BASE + pj + '.pre289'); open(BASE + pj, 'w', encoding='utf-8').write(new)
if os.path.exists(BASE + 'n8n/build.py'):
    r = subprocess.run(['python3', 'n8n/build.py'], cwd=BASE, capture_output=True, text=True)
    if r.returncode:
        shutil.copy(BASE + pj + '.pre289', BASE + pj); sys.exit('PATCH FAIL: build failed, restored: ' + (r.stderr or r.stdout)[-400:])
print('APPLY289_OK hourly Meta report: result label by objective (reach / link clicks / engagement); WhatsApp message logic unchanged')
'''
body = T.replace("@@PRE@@", json.dumps(PRE, ensure_ascii=False))
open(os.path.join(H, "..", "ops", "p289-meta-report-labels.py.txt"), "w", encoding="utf-8").write(body)
b = base64.b64encode(lzma.compress(body.encode("utf-8"), preset=9 | lzma.PRESET_EXTREME)).decode()
line = "echo '%s' | base64 -d | xz -d | python3 && cd /opt/central && bash deploy/update.sh && echo \"markers: job_report p289=$(grep -c p289 n8n/wf_job_report.py) (expect >=1)\"\n" % b
open(os.path.join(H, "..", "..", "out", "p289s.txt"), "w").write(line)
print(len(line))
