import json, os, base64, lzma
H = os.path.dirname(os.path.abspath(__file__))
WIZ = open(os.path.join(H, "wizard.py"), encoding="utf-8").read()
T = r'''import os, re, shutil, subprocess, sys
BASE = os.environ.get('P292_BASE', '/opt/central/')
WIZ = @@WIZ@@
MF = BASE + 'broker/app/metaflow.py'; WP = BASE + 'meta_wizard/wizard.py'
def die(m): sys.exit('PATCH FAIL (nothing written): ' + m)
for f in (MF, WP):
    if not os.path.exists(f): die(f + ' not found (p286 / p287 must be applied first)')
mf = open(MF, encoding='utf-8').read(); cur = open(WP, encoding='utf-8').read()
if 'p292' in mf:
    if cur == WIZ: print('APPLY292_OK changed=0 (already applied)'); sys.exit(0)
    die('p292 is in metaflow.py but the wizard file differs')
if 'p286' not in mf: die('p286 (meta objectives) is not applied')
if 'p287' not in cur and 'FM2' not in cur and 'SEQ' not in cur: die('meta_wizard/wizard.py does not look like the p287 wizard')
def lines_with(t, k): return ' | '.join(ascii(l.strip()[:200]) for l in t.split('\n') if k in l)[:600]
A1 = '    if q.get("cta"): out["cta"] = str(q["cta"])[:30]\n    return out, None\n'
A2 = '    post, f = await resolve_post(svc, ctx, p["post_url"])\n    if f: return f\n    # 1) حملة (PAUSED بالكتالوج)\n'
fails = []
if mf.count(A1) != 1: fails.append('_obj_clean end anchor count=%d; lines: %s' % (mf.count(A1), lines_with(mf, 'out["cta"]')))
if mf.count(A2) != 1: fails.append('resolve_post anchor count=%d; lines: %s' % (mf.count(A2), lines_with(mf, 'resolve_post(svc')))
if fails: die(' || '.join(fails))
N1 = ('    if q.get("cta"): out["cta"] = str(q["cta"])[:30]\n'
      '    if q.get("page_id") is not None and str(q.get("page_id")).strip() != "":   # p292: الصفحة المختارة بالمعالج\n'
      '        pid = str(q["page_id"]).strip()\n'
      '        if not _re.fullmatch(r"[0-9]{5,25}", pid): return None, "page_id لازم رقم الصفحة"\n'
      '        out["page_id"] = pid\n'
      '    return out, None\n')
N2 = ('    post, f = await resolve_post(svc, ctx, p["post_url"])\n    if f: return f\n'
      '    if p.get("page_id") and str(post.get("page_id") or "") != p["page_id"]:   # p292: المنشور لازم يكون من الصفحة المختارة، قبل أي إنشاء\n'
      '        return _fail("post", "post_not_from_selected_page")\n'
      '    # 1) حملة (PAUSED بالكتالوج)\n')
new_mf = mf.replace(A1, N1, 1).replace(A2, N2, 1)
for name, src in (('metaflow', new_mf), ('wizard', WIZ)):
    try: compile(src, name, 'exec')
    except SyntaxError as e: die('syntax %s %s' % (name, e))
shutil.copy(MF, MF + '.pre292'); shutil.copy(WP, WP + '.pre292')
open(MF, 'w', encoding='utf-8').write(new_mf); open(WP, 'w', encoding='utf-8').write(WIZ)
if os.path.exists(BASE + 'n8n/build.py'):
    r = subprocess.run(['python3', 'n8n/build.py'], cwd=BASE, capture_output=True, text=True)
    if r.returncode:
        shutil.copy(MF + '.pre292', MF); shutil.copy(WP + '.pre292', WP); sys.exit('PATCH FAIL: build failed, restored: ' + (r.stderr or r.stdout)[-400:])
print('APPLY292_OK page step with full names in the Facebook objectives wizard + Broker check post_not_from_selected_page; Broker rebuild needed')
'''
body = T.replace("@@WIZ@@", json.dumps(WIZ, ensure_ascii=False))
open(os.path.join(H, "..", "ops", "p292-meta-wizard-pages.py.txt"), "w", encoding="utf-8").write(body)
b = base64.b64encode(lzma.compress(body.encode("utf-8"), preset=9 | lzma.PRESET_EXTREME)).decode()
line = "echo '%s' | base64 -d | xz -d | python3 && cd /opt/central && bash deploy/update.sh && echo \"markers: metaflow p292=$(grep -c p292 broker/app/metaflow.py) wizard p292=$(grep -c p292 meta_wizard/wizard.py) (expect >=2)\"\n" % b
open(os.path.join(H, "..", "..", "out", "p292s.txt"), "w").write(line)
print(len(line))
