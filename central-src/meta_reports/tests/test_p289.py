# -*- coding: utf-8 -*-
import json, os, re, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); MOD = os.path.dirname(H); ROOT = os.path.dirname(os.path.dirname(MOD)); P = os.path.join(os.path.dirname(MOD), "ops", "p289-meta-report-labels.py.txt"); P173 = os.path.join(os.path.dirname(MOD), "ops", "p173-fb-campaign-blocks.py.txt")
rd = lambda p: open(p, encoding="utf-8").read()
p173 = rd(P173); BR = re.search(r'BR = r"""(.*?)"""\n', p173, re.S).group(1)
FIELDS = "campaign_id,campaign_name,spend,impressions,reach,clicks,inline_link_clicks,ctr,actions,account_currency,account_name"
def jr(extra_fields="", br=BR):
    return ('PLAN = """\nconst items = [];\nitems.unshift(..._mc.map(x => ({ json: { ...x.json, kind: \'camp\', params: { fields: \'' + FIELDS + extra_fields + '\', level: \'campaign\', limit: 100 } } })));\nreturn items;\n"""\n'
            'RES = r"""\nconst n2 = x => Number(x) || 0;\nfor (const r of R) {\n  const p = r.p; const g = G;\n' + br + '\n}\n"""\n')
def tree(src=None):
    d = tempfile.mkdtemp(); os.makedirs(d + "/n8n"); open(d + "/n8n/wf_job_report.py", "w", encoding="utf-8").write(src if src is not None else jr()); return d
def apply(d): return subprocess.run([sys.executable, P], env={**os.environ, "P289_BASE": d + "/"}, capture_output=True, text=True)


class Patch(unittest.TestCase):
    def test_apply_idempotent_backup(self):
        d = tree(); r = apply(d); self.assertIn("APPLY289_OK", r.stdout, r.stdout + r.stderr); s = rd(d + "/n8n/wf_job_report.py")
        self.assertIn(FIELDS + ",objective'", s); self.assertEqual(s.count("p289"), 1); self.assertLess(s.index("p289"), s.index("const msg = getA")); self.assertEqual(rd(d + "/n8n/wf_job_report.py.pre289"), jr())
        self.assertIn("changed=0", apply(d).stdout)

    def test_fail_closed(self):
        for src in (jr().replace("metacamp-block", "other"), jr().replace("inline_link_clicks,ctr", "inline_link_clicks,xx"), jr().replace("const msg = getA(", "const mx = getA(")):
            d = tree(src); r = apply(d); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertEqual(rd(d + "/n8n/wf_job_report.py"), src); self.assertFalse(os.path.exists(d + "/n8n/wf_job_report.py.pre289"))
        d = tree(jr() + "\n" + jr()); self.assertIn("count=2", apply(d).stdout + apply(d).stderr)

    def test_oneliner(self):
        s = rd(os.path.join(ROOT, "out", "p289s.txt")); self.assertEqual(s.count("\n"), 1); self.assertIn("bash deploy/update.sh", s)


class Behavior(unittest.TestCase):
    def run_js(self, rows, label="حساب"):
        d = tree(); apply(d); s = rd(d + "/n8n/wf_job_report.py"); js = re.search(r'RES = r"""(.*?)"""', s, re.S).group(1)
        script = ("const R = [{ p: { platform: 'meta', kind: 'camp', label: %s }, ok: true, r: null }];\nconst G = { fb: [], bad: [], meta: [], camps: [] };\n" % json.dumps(label, ensure_ascii=False)
                  + "const ROWS = %s;\n" % json.dumps(rows, ensure_ascii=False)
                  + "const run = (p, r, g) => { " + "const n2 = x => Number(x) || 0;\n" + BR.replace("const rows = (r.data && r.data.data) || [];", "const rows = ROWS;") .replace("\n  if (p.platform === 'meta' && g.fbDone", "\n  if (false && p.platform === 'meta' && g.fbDone") + " };\n")
        # شغّل الكتلة الأصلية المعدّلة (مع البريلود) على الصفوف
        blk = re.search(r"(  if \(p\.platform === 'meta' && p\.kind === 'camp'\) \{.*?\n    return;\n  \})", js, re.S).group(1)
        script = ("const n2 = x => Number(x) || 0;\nconst ROWS = %s; const out = [];\nfunction f(p, r, g) {\n%s\n}\nconst g = { fb: [], bad: [], meta: [] }; f({ platform: 'meta', kind: 'camp', label: %s }, { ok: true, data: { data: ROWS } }, g);\nconsole.log(JSON.stringify(g.fb.map(x => x.t)));" % (json.dumps(rows, ensure_ascii=False), blk, json.dumps(label, ensure_ascii=False)))
        r = subprocess.run(["node", "-e", script], capture_output=True, text=True); self.assertEqual(r.returncode, 0, r.stderr + script[:500]); return json.loads(r.stdout)

    def C(self, **k):
        c = {"campaign_id": "1", "campaign_name": "حملة", "spend": "3", "impressions": "1000", "reach": "800", "inline_link_clicks": "40", "ctr": "1.5", "account_currency": "USD", "actions": [], "objective": "OUTCOME_ENGAGEMENT"}; c.update(k); return c

    def test_awareness(self):
        t = self.run_js([self.C(objective="OUTCOME_AWARENESS", spend="2", reach="1000")])[0]; self.assertIn("👥 الوصول: 1,000", t); self.assertIn("سعر الألف وصول: $2.00", t); self.assertIn("بدون حكم", t); self.assertNotIn("رسائل: ", t.replace("مو رسائل", "")); self.assertNotIn("0.40", t)
    def test_traffic(self):
        t = self.run_js([self.C(objective="OUTCOME_TRAFFIC", spend="4", inline_link_clicks="40")])[0]; self.assertIn("🖱 نقرات الرابط: 40", t); self.assertIn("سعر النقرة: $0.10", t); self.assertIn("بدون حكم", t)
    def test_engagement_without_messages(self):
        t = self.run_js([self.C(actions=[{"action_type": "post_engagement", "value": "50"}], spend="5")])[0]; self.assertIn("👍 التفاعلات: 50", t); self.assertIn("سعر التفاعل: $0.10", t)
    def test_whatsapp_messages_unchanged(self):
        t = self.run_js([self.C(actions=[{"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": "10"}, {"action_type": "post_engagement", "value": "99"}], spend="3")])[0]
        self.assertIn("💬 الرسائل: 10", t); self.assertIn("سعر الرسالة: $0.30", t); self.assertIn("✅ ناجحة", t); self.assertNotIn("👍", t)
    def test_unknown_objective_and_zero_cases_use_old_logic(self):
        t = self.run_js([self.C(objective="", spend="3")])[0]; self.assertIn("💬 الرسائل: 0", t)
        t = self.run_js([self.C(objective="OUTCOME_ENGAGEMENT", spend="3")])[0]; self.assertIn("💬 الرسائل: 0", t)       # لا رسائل ولا تفاعل: السلوك القديم
        t = self.run_js([self.C(objective="OUTCOME_LEADS", spend="3")])[0]; self.assertIn("💬 الرسائل:", t)
    def test_zero_spend_skipped_and_iqd(self):
        self.assertEqual(self.run_js([self.C(objective="OUTCOME_TRAFFIC", spend="0")]), [])
        t = self.run_js([self.C(objective="OUTCOME_TRAFFIC", spend="15550", account_currency="IQD", inline_link_clicks="100")])[0]; self.assertIn("سعر النقرة: 156 د.ع", t); self.assertIn("الإنفاق: 15,550 د.ع", t)
    def test_mixed_rows(self):
        out = self.run_js([self.C(objective="OUTCOME_AWARENESS", campaign_name="A"), self.C(objective="OUTCOME_TRAFFIC", campaign_name="B"), self.C(actions=[{"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": "3"}], campaign_name="W")])
        self.assertEqual(len(out), 3); self.assertIn("A (فيسبوك)", out[0]); self.assertIn("الوصول", out[0]); self.assertIn("نقرات", out[1]); self.assertIn("الرسائل: 3", out[2])


if __name__ == "__main__":
    unittest.main(verbosity=1)
