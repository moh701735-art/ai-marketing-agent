import json, os
H = os.path.dirname(os.path.abspath(__file__))
TOOL = open(os.path.join(H, "ops", "tt_live_create_probe.py"), encoding="utf-8").read()
T = r'''import os, sys, shutil
BASE = os.environ.get('P277_BASE', '/opt/central/')
CT = 'broker/app/catalog.py'
TOOL = @@TOOL@@
BLOCK = """

# p277: عمليتا اختبار (مشرف فقط؛ ما في عقدة n8n تستدعيهما): نسخ من create_campaign/create_adgroup حقول الـenum فيها نص حر، لقراءة قوائم allowed من تيك توك نفسه (ترويج البث). إن فشل التسجيل تغيب العمليتان فقط.
def _p277_register():
    import copy, dataclasses
    def clone(src, name, free):
        base = OPS.get(src)
        if base is None: return
        params = dict(base.params)
        for k in free:
            if k in params: params[k] = P("safe", max_len=60)
        try: op = dataclasses.replace(base, name=name, params=params)
        except Exception:
            op = copy.copy(base)
            object.__setattr__(op, "name", name); object.__setattr__(op, "params", params)
        OPS[name] = op
    clone("tiktok.create_campaign", "tiktok.probe_campaign", ("objective_type", "virtual_objective_type", "budget_mode"))
    clone("tiktok.create_adgroup", "tiktok.probe_adgroup", ("promotion_type", "promotion_target_type", "promotion_website_type", "optimization_goal", "optimization_event", "billing_event", "bid_type", "schedule_type", "messaging_app_type"))
try: _p277_register()
except Exception: pass
"""
if not os.path.exists(BASE + 'ops/wa-diagnose.py'): sys.exit('PATCH FAIL (nothing written): missing ops/wa-diagnose.py (apply p263 first)')
ct = open(BASE + CT, encoding='utf-8').read()
if 'p277' in ct:
    p = BASE + 'ops/tt-live-create-probe.py'
    if os.path.exists(p) and open(p, encoding='utf-8').read() == TOOL: print('APPLY277_OK changed=0 (already applied)'); sys.exit(0)
    sys.exit('PATCH FAIL (nothing written): catalog already has p277 but the tool file differs')
new = ct.rstrip('\n') + '\n' + BLOCK
for name, src in ((CT, new), ('tt-live-create-probe.py', TOOL)):
    try: compile(src, name, 'exec')
    except SyntaxError as e: sys.exit('PATCH FAIL (nothing written): syntax %s %s' % (name, e))
shutil.copy(BASE + CT, BASE + CT + '.pre277')
open(BASE + CT, 'w', encoding='utf-8').write(new)
p = BASE + 'ops/tt-live-create-probe.py'
if os.path.exists(p): shutil.copy(p, p + '.pre277')
open(p, 'w', encoding='utf-8').write(TOOL); os.chmod(p, 0o755)
print('APPLY277_OK catalog: probe ops tiktok.probe_campaign / tiktok.probe_adgroup (free-text enums, admin use only) + ops/tt-live-create-probe.py; Broker rebuild needed')
'''
open(os.path.join(H, "..", "ops", "p277-live-probe-op.py.txt"), "w", encoding="utf-8").write(T.replace("@@TOOL@@", json.dumps(TOOL, ensure_ascii=False)))
