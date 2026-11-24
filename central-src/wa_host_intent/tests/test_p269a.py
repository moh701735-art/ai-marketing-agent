# -*- coding: utf-8 -*-
import json, os, re, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); P = os.path.join(H, "..", "..", "ops", "p269a-wa-host-intent.py.txt")
RUN = os.path.join(H, "..", "..", "pause_by_name", "tests", "run_node.cjs")
PLAN = r'''const d = $('Route').first().json; const it = { objective: 'المبيعات' };
const ntx = String(d.text || '').replace(/[#A-Za-z0-9+\/\\=_\-]{16,250}/g, ' ');
const wam = ntx.match(/(?<!\d)(?:\+?964|00964|0)?(7[0-9]{9})(?!\d)/) || /*p266*/ (String(d.text || '').match(/wa[.]me[/](?:[+]|%2B)?(?:964|00964|0)?(7[0-9]{9})(?![0-9])/i) || String(d.text || '').match(/whatsapp[.]com[/]send[/]?[?](?:[^ #]*&)?phone=(?:[+]|%2B)?(?:964|00964|0)?(7[0-9]{9})(?![0-9])/i));
const dmReq = false;
const mode = (/واتس|whats/i.test(ntx) || wam) ? 'واتساب' : dmReq ? 'tiktok_dm' : ({ 'المبيعات': 'المبيعات' }[it.objective]);
if (mode === 'واتساب' && !wam) return [{ json: { halt: 'need_number' } }];
return [{ json: { mode, num: wam ? wam[1] : null } }];
'''
ING = 'x = 1 # p266\nplan = code(w, "AI: plan", r"""\n' + PLAN + '""")\nother = code(w, "Other", r"""\nconst mode = (/واتس|whats/i.test(ntx) || wam) ? 1 : 2;\n""")\n'
rd = lambda p: open(p, encoding="utf-8").read()
def mk(src=ING, build=None):
    d = tempfile.mkdtemp(); os.makedirs(d + "/n8n"); open(d + "/n8n/wf_ingress.py", "w", encoding="utf-8").write(src)
    if build: open(d + "/n8n/build.py", "w").write(build)
    return d
def apply(d): return subprocess.run([sys.executable, P], env={**os.environ, "P269A_BASE": d + "/"}, capture_output=True, text=True)
def body(d):
    s = rd(d + "/n8n/wf_ingress.py"); m = re.search(r'code\(w, "AI: plan", r"""', s); return s[m.end(): s.index('"""', m.end())]
def run(b, text):
    t = tempfile.mkdtemp(); open(t + "/b.js", "w", encoding="utf-8").write(b); open(t + "/c.json", "w", encoding="utf-8").write(json.dumps({"nodes": {"Route": {"text": text}}}))
    r = subprocess.run(["node", RUN, t + "/b.js", t + "/c.json"], capture_output=True, text=True); assert r.returncode == 0, r.stderr; return json.loads(r.stdout)[0]["json"]


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = mk(); r = apply(cls.d); assert "APPLY269A_OK" in r.stdout, r.stdout + r.stderr; cls.b = body(cls.d); cls.base = body(mk())

    def test_before_falls_back_to_sales(self):
        self.assertEqual(run(self.base, "مبيعات https://wa.twasuliraq.com/w/hcnvkwua")["mode"], "المبيعات")           # المشكلة الأصلية

    def test_intent_without_number_halts(self):
        for t in ("مبيعات https://wa.twasuliraq.com/w/hcnvkwua", "مبيعات https://wa.me/966501234567", "مبيعات https://api.whatsapp.com/send?phone=966501234567",
                  "مبيعات https://www.whatsapp.com/", "ارفع حملة wa.me/abc", "مبيعات https://wa.shop.example.com/x", "مبيعات واتساب"):
            self.assertEqual(run(self.b, t).get("halt"), "need_number", t)

    def test_number_still_proceeds(self):
        for t in ("مبيعات https://wa.me/9647701234567", "مبيعات https://wa.me/07701234567", "مبيعات واتساب 07701234567", "مبيعات https://api.whatsapp.com/send?phone=9647701234567"):
            r = run(self.b, t); self.assertEqual((r.get("mode"), r.get("num")), ("واتساب", "7701234567"), t)

    def test_unrelated_unchanged(self):
        for t in ("ارفع حملة مبيعات https://example.com/shop", "مبيعات https://swa.me/x", "ارفع حملة مبيعات 5 دولار", "مبيعات https://twa.example.com/p"):
            r = run(self.b, t); self.assertEqual((r.get("mode"), r.get("halt")), ("المبيعات", None), t)

    def test_only_mode_line_changed_no_backslash(self):
        a, b = rd(self.d + "/n8n/wf_ingress.py.pre269a").split("\n"), rd(self.d + "/n8n/wf_ingress.py").split("\n")
        self.assertEqual(len(a), len(b)); diff = [(x, y) for x, y in zip(a, b) if x != y]; self.assertEqual(len(diff), 1); self.assertIn("p269a", diff[0][1])
        self.assertEqual(diff[0][1].count("\\"), diff[0][0].count("\\")); self.assertIn("const mode = (/واتس|whats/i.test(ntx) || wam) ? 1 : 2;", rd(self.d + "/n8n/wf_ingress.py"))

    def test_idempotent(self):
        self.assertIn("changed=0", apply(self.d).stdout); self.assertEqual(rd(self.d + "/n8n/wf_ingress.py").count("p269a"), 1)

    def test_fail_closed(self):
        for src in ("x = 1 # p266\n", ING.replace(PLAN, PLAN + PLAN), ING.replace("const mode = (", "const modee = ("), ING.replace("if (mode === 'واتساب' && !wam)", "if (false)"), ING.replace("# p266", "").replace("/*p266*/", "")):
            d = mk(src); before = rd(d + "/n8n/wf_ingress.py"); r = apply(d)
            self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertEqual(rd(d + "/n8n/wf_ingress.py"), before); self.assertFalse(os.path.exists(d + "/n8n/wf_ingress.py.pre269a"))

    def test_build_failure_restores(self):
        d = mk(build="import sys; sys.exit(1)\n"); before = rd(d + "/n8n/wf_ingress.py"); r = apply(d)
        self.assertIn("restored", r.stdout + r.stderr); self.assertEqual(rd(d + "/n8n/wf_ingress.py"), before)


if __name__ == "__main__":
    unittest.main(verbosity=1)
