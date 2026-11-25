import json, os, base64, lzma
H = os.path.dirname(os.path.abspath(__file__))
TOOL = open(os.path.join(H, "ops", "tt_live_b2.py"), encoding="utf-8").read()
T = r'''import os, sys, shutil
BASE = os.environ.get('P283_BASE', '/opt/central/')
CT = 'broker/app/catalog.py'
TOOL = @@TOOL@@
BLOCK = """

# p283: عملية اختبار للمشرف فقط (ما في عقدة n8n تستدعيها): نسخة من create_ad حقول الـenum فيها نص حر، لقراءة قائمة ad_format المسموحة من تيك توك (ترويج البث). إن فشل التسجيل تغيب العملية فقط.
def _p283_register():
    import copy, dataclasses
    base = OPS.get("tiktok.create_ad")
    if base is None: return
    params = dict(base.params)
    for k in ("ad_format", "call_to_action", "identity_type", "creative_type"):
        if k in params: params[k] = P("safe", max_len=60)
    try: op = dataclasses.replace(base, name="tiktok.probe_ad", params=params)
    except Exception:
        op = copy.copy(base)
        object.__setattr__(op, "name", "tiktok.probe_ad"); object.__setattr__(op, "params", params)
    OPS["tiktok.probe_ad"] = op
try: _p283_register()
except Exception: pass
"""
if not os.path.exists(BASE + 'ops/wa-diagnose.py'): sys.exit('PATCH FAIL (nothing written): missing ops/wa-diagnose.py (apply p263 first)')
ct = open(BASE + CT, encoding='utf-8').read()
if 'p277' not in ct: sys.exit('PATCH FAIL (nothing written): catalog has no p277 probe ops (apply p277 first)')
p = BASE + 'ops/tt-live-b2.py'
if 'p283' in ct:
    if os.path.exists(p) and open(p, encoding='utf-8').read() == TOOL: print('APPLY283_OK changed=0 (already applied)'); sys.exit(0)
    sys.exit('PATCH FAIL (nothing written): catalog already has p283 but the tool file differs')
new = ct.rstrip('\n') + '\n' + BLOCK
for name, src in ((CT, new), ('tt-live-b2.py', TOOL)):
    try: compile(src, name, 'exec')
    except SyntaxError as e: sys.exit('PATCH FAIL (nothing written): syntax %s %s' % (name, e))
shutil.copy(BASE + CT, BASE + CT + '.pre283')
open(BASE + CT, 'w', encoding='utf-8').write(new)
if os.path.exists(p): shutil.copy(p, p + '.pre283')
open(p, 'w', encoding='utf-8').write(TOOL); os.chmod(p, 0o755)
print('APPLY283_OK catalog: tiktok.probe_ad (admin-only, free-text enums) + ops/tt-live-b2.py v4; Broker rebuild needed')
'''
body = T.replace("@@TOOL@@", json.dumps(TOOL, ensure_ascii=False))
open(os.path.join(H, "..", "ops", "p283-live-probe-ad.py.txt"), "w", encoding="utf-8").write(body)
b = base64.b64encode(lzma.compress(body.encode("utf-8"), preset=9 | lzma.PRESET_EXTREME)).decode()
line = "echo '%s' | base64 -d | xz -d | python3 && cd /opt/central && bash deploy/update.sh && echo \"markers: catalog p283=$(grep -c p283 broker/app/catalog.py) (expect >=1) tool=$(grep -c 'v4 / p283' ops/tt-live-b2.py) (expect 1)\"\n" % b
open(os.path.join(H, "..", "..", "out", "p283s.txt"), "w").write(line)
open(os.path.join(H, "..", "..", "out", "p283r.txt"), "w").write("cd /opt/central && LB_ONLY=promotion_type,ad_format python3 ops/tt-live-b2.py 2>&1 | LC_ALL=C sed -E 's/[^ -~]/?/g'\n")
print(len(line))
