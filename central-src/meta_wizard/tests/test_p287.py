# -*- coding: utf-8 -*-
import os, re, subprocess, sys, tempfile, unittest, shutil
H = os.path.dirname(os.path.abspath(__file__)); MOD = os.path.dirname(H); ROOT = os.path.dirname(os.path.dirname(MOD)); P = os.path.join(os.path.dirname(MOD), "ops", "p287-meta-wizard.py.txt")
rd = lambda p: open(p, encoding="utf-8").read()
ING = '''import os, importlib.util
def make(b, w, sw, reply, CRT):
    wzs = pg(w, "wzs", "SELECT 'x', 1 UNION ALL SELECT 'sn_' || (data::jsonb->>'st'), 3 FROM api.ui_get($1, 'sn:' || $2) WHERE (data::jsonb->>'st') IN ('url', 'vid', 'txt') AND age_s < 1800 ORDER BY 2", "q", CRT)
    code(w, "Route", """
      const SAN = '';
      const SNU = '';
      const SNV = (!d.cb && $input.all().some(i => i.json && String(i.json.step) === 'sn_vid')); const SNT = (!d.cb && $input.all().some(i => i.json && String(i.json.step) === 'sn_txt'));   // p197d
      else if (ck === 'sa') { cmd = 'smartaud'; uiv = String(d.cb); } else if (ck === 'gd') { cmd = 'guide'; uiv = String(d.cb); }
      if (SNV && !SAN && cmd !== 'wiz' && d.fileId) { cmd = 'snapin'; }   // p197d
      else if ((SNV || SNT) && !SAN && cmd !== 'wiz' && !d.fileId && String(d.text || '').trim() && !String(d.text || '').trim().startsWith('/')) { cmd = 'snapin'; args = String(d.text || '').trim(); }   // p197d
      if (false) { }
      const map = { snapwiz: 35, snapin: 35, guide: 36, 'دليل': 36, other: 3 };
    """)
    sw = w.add("Command", "n8n-nodes-base.switch", 3.5, {"mode": "expression", "numberOutputs": 37, "output": "x"})
    _gdp = os.path.join('guide', 'pages.py')
    if os.path.exists(_gdp):
        _gds = importlib.util.spec_from_file_location('guide_pages', _gdp); _gdm = importlib.util.module_from_spec(_gds); _gds.loader.exec_module(_gdm)
        _gdm.build(b, w, sw, 36, reply, CRT)
'''
def tree(ing=ING):
    d = tempfile.mkdtemp(); os.makedirs(d + "/n8n"); open(d + "/n8n/wf_ingress.py", "w", encoding="utf-8").write(ing); return d
def apply(d): return subprocess.run([sys.executable, P], env={**os.environ, "P287_BASE": d + "/"}, capture_output=True, text=True)


class Patch(unittest.TestCase):
    def test_apply_all_edits(self):
        d = tree(); r = apply(d); self.assertIn("APPLY287_OK", r.stdout, r.stdout + r.stderr); s = rd(d + "/n8n/wf_ingress.py"); compile(s, "x", "exec")
        self.assertIn("ck === 'fm'", s); self.assertIn("fmwiz: 37, fmin: 37, fbobj: 37", s); self.assertIn('"numberOutputs": 38', s); self.assertNotIn('"numberOutputs": 37', s)
        self.assertIn("_fmm.build(b, w, sw, 37, reply, CRT)", s); self.assertIn("const FMI =", s); self.assertIn("'fm:' || $2", s)
        self.assertLess(s.index("UNION ALL SELECT 'fm_'"), s.index("ORDER BY 2"))                         # الاتحاد قبل الترتيب
        self.assertLess(s.index("const SNV"), s.index("const FMI")); self.assertLess(s.index("cmd = 'fmin'"), s.index("if (SNV && !SAN"))
        self.assertTrue(os.path.exists(d + "/n8n/wf_ingress.py.pre287")); self.assertEqual(rd(d + "/n8n/wf_ingress.py.pre287"), ING); self.assertIn("PROBE" if False else "FM2: plan", rd(d + "/meta_wizard/wizard.py"))
        self.assertIn("changed=0", apply(d).stdout)

    def test_fail_closed_each_anchor(self):
        for old, new in (("ck === 'gd'", "ck === 'gx'"), ("guide: 36", "guid: 36"), ('"numberOutputs": 37', '"numberOutputs": 36'), ("_gdm.build(b, w, sw, 36", "_gdm.build(b, w, sw, 35"),
                         ("IN ('url', 'vid', 'txt')", "IN ('url')"), ("const SNV =", "const SNX ="), ("if (SNV && !SAN", "if (SNX && !SAN")):
            d = tree(ING.replace(old, new)); before = rd(d + "/n8n/wf_ingress.py"); r = apply(d)
            self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr, old); self.assertEqual(rd(d + "/n8n/wf_ingress.py"), before); self.assertFalse(os.path.exists(d + "/meta_wizard"))

    def test_duplicate_anchor_refused(self):
        d = tree(ING + "\n# ck === 'gd' else if (ck === 'gd') { cmd = 'guide'; uiv = String(d.cb); }\n"); self.assertIn("count=2", apply(d).stdout + apply(d).stderr)

    def test_build_failure_restores(self):
        d = tree(); os.makedirs(d + "/n8n", exist_ok=True); open(d + "/n8n/build.py", "w").write("import sys; sys.exit(1)\n")
        r = apply(d); self.assertIn("PATCH FAIL", r.stdout + r.stderr); self.assertEqual(rd(d + "/n8n/wf_ingress.py"), ING)

    def test_oneliner(self):
        s = rd(os.path.join(ROOT, "out", "p287s.txt")); self.assertEqual(s.count("\n"), 1); self.assertIn("bash deploy/update.sh", s)

    def test_routing_js_semantics(self):
        # يشغّل قاعدة التوجيه الحقيقية بعد التعديل على حالات: نص بخطوة fm، callback، أمر، تعارض مع سناب
        d = tree(); apply(d); s = rd(d + "/n8n/wf_ingress.py")
        blk = s[s.index("const FMI"):]; fmi = blk.split("\n")[0]; rule = [l for l in s.split("\n") if "cmd = 'fmin'" in l][0].strip()
        fmi = re.sub(r"\s*//.*$", "", fmi); rule = re.sub(r"\s*//.*$", "", rule)
        js = "function t(rows, d, cmd0){ let cmd = cmd0, args = ''; const SAN = ''; " + fmi + " " + rule + " return [cmd, args]; }"
        js += "\nconst I = (st) => [{ json: { step: st } }];\nconst D = (o) => Object.assign({ text: 'hello', cb: '' }, o);\nconst r = []; function $input_all(x){ return x; }\n"
        script = "const $input = { all: () => ROWS };\nlet ROWS; " + js + "\nROWS = I('fm_post'); console.log(JSON.stringify([t(ROWS, D({}), 'text'), t(ROWS, D({ cb: 'fm:o:x' }), 'fmwiz'), t(ROWS, D({ text: '/start' }), 'start'), t(ROWS, D({ text: 'x', fileId: 'F' }), 'text'), t(ROWS, D({}), 'snapin'), (ROWS = I('sn_url'), t(ROWS, D({}), 'text')), (ROWS = [], t(ROWS, D({}), 'text'))]));"
        r = subprocess.run(["node", "-e", script], capture_output=True, text=True); self.assertEqual(r.returncode, 0, r.stderr)
        import json; out = json.loads(r.stdout)
        self.assertEqual(out[0], ["fmin", "hello"]); self.assertEqual(out[1], ["fmwiz", ""]); self.assertEqual(out[2], ["start", ""]); self.assertEqual(out[3], ["text", ""]); self.assertEqual(out[4], ["snapin", ""]); self.assertEqual(out[5], ["text", ""]); self.assertEqual(out[6], ["text", ""])


if __name__ == "__main__":
    unittest.main(verbosity=1)
