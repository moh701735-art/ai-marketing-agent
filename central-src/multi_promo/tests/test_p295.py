# -*- coding: utf-8 -*-
import importlib.util, json, os, re, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); MOD = os.path.dirname(H); ROOT = os.path.dirname(MOD)
spec = importlib.util.spec_from_file_location("t287", os.path.join(ROOT, "meta_wizard", "tests", "test_p287.py")); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
P295 = os.path.join(ROOT, "ops", "p295-multi-promo.py.txt"); rd = t.rd
def prep():
    d = t.tree(); r = t.apply(d); assert "APPLY287_OK" in r.stdout, r.stdout + r.stderr; return d
def ap(d): return subprocess.run([sys.executable, P295], env={**os.environ, "P295_BASE": d + "/"}, capture_output=True, text=True)
class T(unittest.TestCase):
    def test_apply_edits_and_idempotent(self):
        d = prep(); r = ap(d); self.assertIn("APPLY295_OK", r.stdout, r.stdout + r.stderr); s = rd(d + "/n8n/wf_ingress.py"); compile(s, "x", "exec")
        self.assertIn("ck === 'mp'", s); self.assertIn("promo: 39, promocb: 39", s); self.assertIn('"numberOutputs": 40', s); self.assertNotIn('"numberOutputs": 39', s)
        self.assertIn("_mpm.build(b, w, sw, 39, reply, CRT)", s); self.assertLess(s.index("_fmm.build"), s.index("_mpm.build")); self.assertLess(s.index("cmd = 'promo'"), s.index("if (SNV && !SAN")); self.assertLess(s.index("cmd = 'fmin'"), s.index("cmd = 'promo'"))
        self.assertTrue(os.path.exists(d + "/multi_promo/promo.py")); self.assertTrue(os.path.exists(d + "/n8n/wf_ingress.py.pre295"))
        self.assertIn("changed=0", ap(d).stdout)
    def test_fail_closed(self):
        for old, new in (("ck === 'fm'", "ck === 'fx'"), ("fbobj: 38", "fbo: 38"), ('"numberOutputs": 39', '"numberOutputs": 38'), ("_fmm.build(b, w, sw, 38", "_fmm.build(b, w, sw, 36"), ("if (SNV && !SAN", "if (SNX && !SAN")):
            d = prep(); s = rd(d + "/n8n/wf_ingress.py").replace(old, new, 1); open(d + "/n8n/wf_ingress.py", "w", encoding="utf-8").write(s)
            r = ap(d); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr, old); self.assertEqual(rd(d + "/n8n/wf_ingress.py"), s); self.assertFalse(os.path.exists(d + "/multi_promo"))
    def test_requires_p287(self):
        d = t.tree(); self.assertIn("PATCH FAIL", ap(d).stdout + ap(d).stderr)
    def test_build_failure_restores(self):
        d = prep(); open(d + "/n8n/build.py", "w").write("import sys; sys.exit(1)\n"); before = rd(d + "/n8n/wf_ingress.py"); r = ap(d)
        self.assertIn("PATCH FAIL", r.stdout + r.stderr); self.assertEqual(rd(d + "/n8n/wf_ingress.py"), before)
    def test_adapts_to_future_output_count(self):
        d = prep(); s = rd(d + "/n8n/wf_ingress.py").replace('"numberOutputs": 39', '"numberOutputs": 41').replace("_fmm.build(b, w, sw, 38", "_fmm.build(b, w, sw, 40"); open(d + "/n8n/wf_ingress.py", "w", encoding="utf-8").write(s)
        r = ap(d); self.assertIn("APPLY295_OK", r.stdout, r.stdout + r.stderr); s = rd(d + "/n8n/wf_ingress.py"); self.assertIn("promo: 41", s); self.assertIn('"numberOutputs": 42', s)
    def test_routing_rule_semantics(self):
        d = prep(); ap(d); s = rd(d + "/n8n/wf_ingress.py"); rule = [l for l in s.split("\n") if "cmd = 'promo'" in l][0].strip(); rule = re.sub(r"\s*//.*$", "", rule)
        script = "function t(d, cmd0){ let cmd = cmd0, args = ''; " + rule + " return [cmd, args.slice(0, 12)]; }\nconst D = o => Object.assign({ text: '', cb: '' }, o);\n" \
                 "console.log(JSON.stringify([t(D({text:'روّج: تيك توك + فيسبوك + سناب\\nالميزانية: 20'}), 'text'), t(D({text:'روج: فيس'}), 'text'), t(D({caption:'روّج: سناب'}), 'snapin'), t(D({text:'ارفع حمله تيك توك'}), 'text'), t(D({text:'روّج: منتجي'}), 'text'), t(D({text:'/start'}), 'start'), t(D({text:'روّج: تيك توك', cb:'x'}), 'fmwiz'), t(D({text:'promo: tiktok'}), 'text'), t(D({text:'ارفع: فيسبوك'}), 'text')]))"
        r = subprocess.run(["node", "-e", script], capture_output=True, text=True); self.assertEqual(r.returncode, 0, r.stderr); out = json.loads(r.stdout)
        self.assertEqual(out[0][0], "promo"); self.assertEqual(out[1][0], "promo"); self.assertEqual(out[2][0], "promo"); self.assertEqual(out[3][0], "text"); self.assertEqual(out[4][0], "text"); self.assertEqual(out[5][0], "start"); self.assertEqual(out[6][0], "fmwiz"); self.assertEqual(out[7][0], "promo"); self.assertEqual(out[8][0], "promo")
    def test_oneliner_and_module_embedded(self):
        s = rd(os.path.join(ROOT, "..", "out", "p295s.txt")); self.assertEqual(s.count("\n"), 1); self.assertIn("bash deploy/update.sh", s)
        import base64, lzma; self.assertEqual(lzma.decompress(base64.b64decode(re.search(r"echo '([^']+)'", s).group(1))).decode(), rd(P295))
if __name__ == "__main__": unittest.main()
