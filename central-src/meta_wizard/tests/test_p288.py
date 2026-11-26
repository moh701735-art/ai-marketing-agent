# -*- coding: utf-8 -*-
import json, os, re, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); MOD = os.path.dirname(H); ROOT = os.path.dirname(os.path.dirname(MOD))
P87 = os.path.join(os.path.dirname(MOD), "ops", "p287-meta-wizard.py.txt"); P88 = os.path.join(os.path.dirname(MOD), "ops", "p288-meta-wizard-entry.py.txt")
rd = lambda p: open(p, encoding="utf-8").read()
sys.path.insert(0, H); import test_p287 as t87


def tree():
    d = t87.tree(); r = subprocess.run([sys.executable, P87], env={**os.environ, "P287_BASE": d + "/"}, capture_output=True, text=True); assert "APPLY287_OK" in r.stdout, r.stdout + r.stderr; return d
def apply(d): return subprocess.run([sys.executable, P88], env={**os.environ, "P288_BASE": d + "/"}, capture_output=True, text=True)


class Patch(unittest.TestCase):
    def test_apply_after_p287(self):
        d = tree(); r = apply(d); self.assertIn("APPLY288_OK", r.stdout, r.stdout + r.stderr); s = rd(d + "/n8n/wf_ingress.py"); compile(s, "x", "exec")
        self.assertIn("'fp_pass'", s); self.assertIn("const FMP =", s); self.assertIn("wz:ac:(?:act_", s)
        self.assertLess(s.index("UNION ALL SELECT 'fp_pass'"), s.index("ORDER BY 2")); self.assertLess(s.index("const FMI"), s.index("const FMP")); self.assertLess(s.index("cmd = 'fmwiz'; uiv = String(d.cb); }   // p288"), s.index("if (FMI &&"))
        self.assertTrue(os.path.exists(d + "/n8n/wf_ingress.py.pre288")); self.assertTrue(os.path.exists(d + "/meta_wizard/wizard.py.pre288")); self.assertIn("viaWz", rd(d + "/meta_wizard/wizard.py")); self.assertNotIn("viaWz", rd(d + "/meta_wizard/wizard.py.pre288"))
        self.assertIn("changed=0", apply(d).stdout)

    def test_upgrade_from_first_p288(self):
        d = tree(); apply(d); p = d + "/n8n/wf_ingress.py"; s = rd(p)
        old = s.replace("/^wz:ac:(?:act_[0-9]{5,25}|[0-9]{5,17})$/", "/^wz:ac:act_[0-9]{5,25}$/"); open(p, "w", encoding="utf-8").write(old); open(d + "/meta_wizard/wizard.py", "w", encoding="utf-8").write(rd(d + "/meta_wizard/wizard.py.pre288"))
        r = apply(d); self.assertIn("APPLY288_OK upgraded", r.stdout, r.stdout + r.stderr); self.assertIn("(?:act_[0-9]{5,25}|[0-9]{5,17})", rd(p)); self.assertIn("viaWz", rd(d + "/meta_wizard/wizard.py")); self.assertIn("changed=0", apply(d).stdout)
        self.assertTrue(os.path.exists(p + ".pre288b"))

    def test_requires_p287(self):
        d = t87.tree(); r = apply(d); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr)

    def test_fail_closed_anchors(self):
        for old, new in (("'fm_' ||", "'fx_' ||"), ("const FMI =", "const FMX ="), ("if (FMI && cmd !== 'snapin'", "if (FMX && cmd !== 'snapin'")):
            d = tree(); p = d + "/n8n/wf_ingress.py"; s = rd(p).replace(old, new, 1); open(p, "w", encoding="utf-8").write(s)
            r = apply(d); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr, old); self.assertEqual(rd(p), s); self.assertFalse(os.path.exists(d + "/meta_wizard/wizard.py.pre288"))

    def test_build_failure_restores_both(self):
        d = tree(); before_i = rd(d + "/n8n/wf_ingress.py"); before_w = rd(d + "/meta_wizard/wizard.py"); open(d + "/n8n/build.py", "w").write("import sys; sys.exit(1)\n")
        r = apply(d); self.assertIn("PATCH FAIL", r.stdout + r.stderr); self.assertEqual(rd(d + "/n8n/wf_ingress.py"), before_i); self.assertEqual(rd(d + "/meta_wizard/wizard.py"), before_w)

    def test_oneliner(self):
        s = rd(os.path.join(ROOT, "out", "p288s.txt")); self.assertEqual(s.count("\n"), 1); self.assertIn("bash deploy/update.sh", s)

    def test_routing_semantics(self):
        d = tree(); apply(d); s = rd(d + "/n8n/wf_ingress.py")
        fmi = re.sub(r"\s*//.*$", "", [l for l in s.split("\n") if "const FMI" in l][0].strip()); fmp = re.sub(r"\s*//.*$", "", [l for l in s.split("\n") if "const FMP" in l][0].strip())
        rule = re.sub(r"\s*//.*$", "", [l for l in s.split("\n") if "cmd = 'fmwiz'; uiv = String(d.cb); }   // p288" in l][0].strip())
        script = ("let ROWS; const $input = { all: () => ROWS };\nfunction t(rows, d, cmd0){ ROWS = rows; let cmd = cmd0, uiv = ''; " + fmi + " " + fmp + " " + rule + " return [cmd, uiv]; }\n"
                  "const none = [], pass = [{ json: { step: 'fp_pass' } }], other = [{ json: { step: 'fm_post' } }];\n"
                  "console.log(JSON.stringify([t(none, { cb: 'wz:ac:act_123456789' }, 'wiz'), t(pass, { cb: 'wz:ac:act_123456789' }, 'wiz'), t(none, { cb: 'wz:ac:7691331863249256500' }, 'wiz'), t(none, { cb: 'wz:p:fb' }, 'wiz'), t(none, { cb: '' , text: 'hi' }, 'text'), t(other, { cb: 'wz:ac:act_123456789' }, 'wiz'), t(none, { cb: 'wz:ac:act_12' }, 'wiz'), t(none, { cb: 'wz:ac:1143673748321865' }, 'wiz'), t(none, { cb: 'wz:ac:7593807340588253185' }, 'wiz'), t(pass, { cb: 'wz:ac:1143673748321865' }, 'wiz')]));")
        r = subprocess.run(["node", "-e", script], capture_output=True, text=True); self.assertEqual(r.returncode, 0, r.stderr); out = json.loads(r.stdout)
        self.assertEqual(out[0], ["fmwiz", "wz:ac:act_123456789"]); self.assertEqual(out[1], ["wiz", ""]); self.assertEqual(out[2], ["wiz", ""]); self.assertEqual(out[3], ["wiz", ""]); self.assertEqual(out[4], ["text", ""]); self.assertEqual(out[5], ["fmwiz", "wz:ac:act_123456789"]); self.assertEqual(out[6], ["wiz", ""]); self.assertEqual(out[7], ["fmwiz", "wz:ac:1143673748321865"]); self.assertEqual(out[8], ["wiz", ""]); self.assertEqual(out[9], ["wiz", ""])
        # الصف fp_pass لا يطابق /^fm_/ فلا يلتهم النصوص العادية
        self.assertFalse(re.match(r"^fm_", "fp_pass"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
