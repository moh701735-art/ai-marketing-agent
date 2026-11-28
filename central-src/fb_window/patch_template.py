import os, re, shutil, subprocess, sys
BASE = os.environ.get('P296_BASE', '/opt/central/')
ING = 'n8n/wf_ingress.py'; MF = 'broker/app/metaflow.py'
BLOCK = r'''@@BLOCK@@'''
def die(m): sys.exit('PATCH FAIL (nothing written): ' + m)
for f in (ING, MF):
    if not os.path.exists(BASE + f): die('missing ' + f)
ing = open(BASE + ING, encoding='utf-8').read(); mf = open(BASE + MF, encoding='utf-8').read()
a, b = ('// p296' in ing), ('# p296' in mf)
if a and b: print('APPLY296_OK changed=0 (already applied)'); sys.exit(0)
if a != b: die('half applied (ingress=%s broker=%s): restore the .pre296 file first' % (a, b))
def lines_with(t, k): return ' | '.join(ascii(l.strip()[:200]) for l in t.split('\n') if k in l)[:500]
fails = []
# ---------- ingress (عقدة FBC الخاصة بخطة فيسبوك النصية) ----------
mo = list(re.finditer(r'(?m)^[ \t]*fbcplan = code\(w, "FBC:[^\n]*r"""[ \t]*\n', ing))
if len(mo) != 1: fails.append('ingress: fbcplan node opener count=%d (expected 1 raw triple-quoted string)' % len(mo))
R0 = R1 = -1
if len(mo) == 1:
    R0 = mo[0].end(); R1 = ing.find('"""', R0)
    if R1 < 0: fails.append('ingress: fbcplan node has no closing triple quote')
if R0 >= 0 and R1 > R0:
    reg = ing[R0:R1]
    for w in ('WIN', 'endAt'):
        if re.search(r'\b' + w + r'\b', reg): fails.append('ingress: name %s already used in the node' % w)
    if 'halt(' not in reg or not re.search(r'\bbody\b', reg): fails.append('ingress: node has no halt()/body (unexpected shape)')
    m1 = list(re.finditer(r"(?m)^([ \t]*)let startAt = '', startTxt = '';[ \t]*\n([ \t]*)if \((/.+/[a-z]*\.test\(nb\))\) \{[ \t]*$", reg))
    if len(m1) != 1: fails.append("ingress: 'let startAt…' + start-cue guard count=%d; lines: %s" % (len(m1), lines_with(reg, 'startAt')))
    m2 = list(re.finditer(r'(?m)^([ \t]*)const days = ', reg))
    if len(m2) != 1: fails.append("ingress: 'const days =' count=%d" % len(m2))
    m3 = list(re.finditer(r'start_at: startAt( *)\}', reg))
    if len(m3) != 1: fails.append('ingress: params start_at anchor count=%d; lines: %s' % (len(m3), lines_with(reg, 'start_at')))
    if not fails and not (m2[0].start() < m1[0].start()): fails.append('ingress: const days must come before the start parser')
# ---------- broker (launch_whatsapp القديم) ----------
al = [l for l in mf.split('\n') if '"start_at"' in l and '"post_url"' in l]
if len(al) != 1: fails.append('broker: allowed-params line count=%d' % len(al))
mv_all = list(re.finditer(r'(?m)^([ \t]*)pv = params\.get\("provinces", \[\]\)[ \t]*$', mf))
def _seg(m):
    t = mf[:m.start()]; k = max(t.rfind('\ndef '), t.rfind('\n    def '), t.rfind('async def '), t.rfind('\nclass '))
    return t[k:] if k >= 0 else t
mv = [m for m in mv_all if 'days=60' in _seg(m)[-900:] and 'sdt' in _seg(m)[-900:]]   # المسار القديم فقط (قبله فحص start_at)
if len(mv) != 1: fails.append('broker: validation anchor (pv = params.get("provinces") right after the start_at check) count=%d of %d' % (len(mv), len(mv_all)))
mo2 = list(re.finditer(r'"start_at": sa(?![A-Za-z0-9_])', mf))
if len(mo2) != 1: fails.append('broker: output dict "start_at": sa count=%d' % len(mo2))
me = list(re.finditer(r'(?m)^([ \t]*)end = \(base \+ datetime\.timedelta\(days=p\["days"\]\)\)\.strftime\("%Y-%m-%dT%H:%M:%S\+0000"\)[ \t]*$', mf))
if len(me) != 1: fails.append('broker: end = (base + timedelta(days)) line count=%d; lines: %s' % (len(me), lines_with(mf, 'end = ')))
if fails: die(' || '.join(fails))
# ---------- بناء النصوص ----------
def ind(t, I): return ''.join((I + ln if ln.strip() else ln) + '\n' for ln in t.rstrip('\n').split('\n'))
m1 = m1[0]; I1 = m1.group(1); I2 = m1.group(2)
new_head = ind(BLOCK, I1) + I1 + "let startAt = '', startTxt = '';\n" + I1 + 'if (WIN) { startAt = WIN.start_at; endAt = WIN.end_at; startTxt = WIN.txt; days = WIN.days; }\n' + I2 + 'if (!WIN && ' + m1.group(3) + ') {'
reg2 = reg[:m1.start()] + new_head + reg[m1.end():]
reg2 = re.sub(r'(?m)^([ \t]*)const days = ', lambda m: m.group(1) + 'let days = ', reg2, count=1)
reg2 = reg2.replace('start_at: startAt' + m3[0].group(1) + '}', 'start_at: startAt, end_at: endAt' + m3[0].group(1) + '}', 1)
new_ing = ing[:R0] + reg2 + ing[R1:]
I = mv[0].group(1)
VAL = ('# p296: end_at (نافذة فيسبوك: بداية + إيقاف)\nea = params.get("end_at", "")\nif ea != "":\n'
       '    if not isinstance(ea, str) or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\\+0000", ea):\n        return None, "end_at: YYYY-MM-DDTHH:MM:SS+0000"\n'
       '    if sa == "":\n        return None, "end_at needs start_at"\n'
       '    if params.get("budget_mode") == "daily":\n        return None, "end_at needs a total budget (budget_mode total), not daily"\n'
       '    try:\n        edt = datetime.datetime.strptime(ea[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc)\n    except ValueError:\n        return None, "end_at: invalid date"\n'
       '    if not (sdt + datetime.timedelta(minutes=30) <= edt <= sdt + datetime.timedelta(days=7)):\n        return None, "end_at must be 30 minutes to 7 days after start_at"\n')
edits = [(mv[0].start(), mv[0].start(), ind(VAL, I)), (me[0].end(), me[0].end(), '\n' + me[0].group(1) + 'if p.get("end_at"): end = str(p["end_at"])[:19] + "+0000"   # p296'),
         (mo2[0].start(), mo2[0].end(), '"start_at": sa, "end_at": ea')]
alline = al[0]; pos = mf.index(alline); edits.append((pos + alline.index('"start_at"'), pos + alline.index('"start_at"') + len('"start_at"'), '"start_at", "end_at"'))
new_mf = mf
for a0, b0, txt in sorted(edits, key=lambda x: -x[0]): new_mf = new_mf[:a0] + txt + new_mf[b0:]
try: compile(new_mf, 'metaflow', 'exec')
except SyntaxError as e: die('broker syntax %s' % e)
try: compile(new_ing, 'ingress', 'exec')
except SyntaxError as e: die('ingress syntax %s' % e)
for f, old in ((ING, ing), (MF, mf)): shutil.copy(BASE + f, BASE + f + '.pre296')
open(BASE + ING, 'w', encoding='utf-8').write(new_ing); open(BASE + MF, 'w', encoding='utf-8').write(new_mf)
if os.path.exists(BASE + 'n8n/build.py'):
    r = subprocess.run(['python3', 'n8n/build.py'], cwd=BASE, capture_output=True, text=True)
    if r.returncode:
        for f in (ING, MF): shutil.copy(BASE + f + '.pre296', BASE + f)
        sys.exit('PATCH FAIL: build failed, restored: ' + (r.stderr or r.stdout)[-400:])
print('APPLY296_OK Facebook window: start + stop time (ارفعها الساعة 6 بالليل وقفها 6 الصبح) + Broker end_at (total budget, 30 min..7 days)')
