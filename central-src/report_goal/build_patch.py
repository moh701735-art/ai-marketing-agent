import json, os
H = os.path.dirname(os.path.abspath(__file__))
LOOP = open(os.path.join(H, "loop_v2.js"), encoding="utf-8").read().rstrip("\n")
OLD = open(os.path.join(H, "..", "report_v2", "loop.js"), encoding="utf-8").read().rstrip("\n")
T = r'''import os, re, shutil, subprocess, sys
BASE = os.environ.get('P269B_BASE', '/opt/central/')
SV, JR = 'broker/app/service.py', 'n8n/wf_job_report.py'
sv = open(BASE + SV, encoding='utf-8').read(); jr = open(BASE + JR, encoding='utf-8').read()
if 'p269b' in sv or 'p269b' in jr:
    if 'p269b' in sv and 'p269b' in jr: print('APPLY269B_OK changed=0 (already applied)'); sys.exit(0)
    sys.exit('PATCH FAIL (nothing written): half-applied state (service=%s job_report=%s)' % ('p269b' in sv, 'p269b' in jr))
if 'p229' not in sv or 'p229' not in jr: sys.exit('PATCH FAIL (nothing written): p229 (report v2) must be applied first')
OLDLOOP = @@OLD@@
NEWLOOP = @@NEW@@
def lines_with(txt, kw): return ' | '.join(ascii(l.strip()[:200]) for l in txt.split('\n') if kw in l)[:600] or 'none'
fails = []
rx = re.compile(r'(?m)^([ \t]*)if op_name == "tiktok\.day_report":[ \t]*# p229[^\n]*$')
ms = list(rx.finditer(sv))
if len(ms) != 1: fails.append('service p229 day_report anchor count=%d; lines: %s' % (len(ms), lines_with(sv, 'day_report')))
rl = re.compile(r'(?m)^for \(const g of Object\.values\(groups\)\) \{[^\n]*\n[\s\S]*?\n\}\n(?=return out;)')
ml = list(rl.finditer(jr))
if len(ml) != 1: fails.append('job_report loop anchor count=%d; lines: %s' % (len(ml), lines_with(jr, 'Object.values')))
elif ml[0].group(0).rstrip('\n') != OLDLOOP: fails.append('job_report loop is not the exact p229 text (modified?); refusing to overwrite; first line: ' + ascii(ml[0].group(0)[:120]))
if fails: sys.exit('PATCH FAIL (nothing written): ' + ' || '.join(fails))
I = ms[0].group(1)
BLK = (I + 'if op_name == "tiktok.day_report":   # p269b: هدف التحسين لكل حملة (محادثات أم لا) من adgroups\n' +
       I + '    gl_ = {}\n' + I + '    ids_ = [str(t["campaign_id"]) for t in rows]\n' +
       I + '    for i_ in range(0, len(ids_), 10):\n' + I + '        try:\n' +
       I + '            ag_ = await rd(acct, "tiktok.read_adgroups", {"campaign_ids": ids_[i_:i_ + 10], "page_size": 100})\n' +
       I + '        except Exception:\n' + I + '            ag_ = None\n' +
       I + '        for g_ in ((ag_ or {}).get("list") or []):\n' + I + '            gl_.setdefault(str(g_.get("campaign_id")), []).append(g_)\n' +
       I + '    for t in rows:\n' +
       I + '        t["goal"] = ",".join(sorted({str(g_.get("optimization_goal") or g_.get("optimize_goal") or "") for g_ in gl_.get(t["campaign_id"], [])} - {""}))\n')
new_sv = sv[:ms[0].start()] + BLK + sv[ms[0].start():]
try: compile(new_sv, SV, 'exec')
except SyntaxError as e: sys.exit('PATCH FAIL (nothing written): service syntax %s' % e)
new_jr = jr[:ml[0].start()] + NEWLOOP + '\n' + jr[ml[0].end():]
for f, s in ((SV, sv), (JR, jr)): shutil.copy(BASE + f, BASE + f + '.pre269b')
open(BASE + SV, 'w', encoding='utf-8').write(new_sv); open(BASE + JR, 'w', encoding='utf-8').write(new_jr)
if os.path.exists(BASE + 'n8n/build.py'):
    r = subprocess.run(['python3', 'n8n/build.py'], cwd=BASE, capture_output=True, text=True)
    if r.returncode:
        for f in (SV, JR): shutil.copy(BASE + f + '.pre269b', BASE + f)
        sys.exit('PATCH FAIL: build failed, restored: ' + (r.stderr or r.stdout)[-400:])
print('APPLY269B_OK report labels by optimization goal: «محادثات» only for CONVERSATION campaigns (Broker day_report adds goal; hourly report wording); other goals = «ليست محادثات» (p269b)')
'''
out = T.replace('@@OLD@@', json.dumps(OLD, ensure_ascii=False)).replace('@@NEW@@', json.dumps(LOOP, ensure_ascii=False))
open(os.path.join(H, "..", "ops", "p269b-report-goal.py.txt"), "w", encoding="utf-8").write(out); print(len(out))
