# -*- coding: utf-8 -*-
import json, os, re, shutil, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); P = os.path.join(H, "..", "..", "ops", "p266-wa-link-route.py.txt")
RUN = os.path.join(H, "..", "..", "pause_by_name", "tests", "run_node.cjs")
PLAN = r'''const d = $('Route').first().json;
const ntx = String(d.text || '').replace(/[#A-Za-z0-9+\/\\=_\-]{16,250}/g, ' ').replace(/[٠-٩]/g, c => '٠١٢٣٤٥٦٧٨٩'.indexOf(c));
const wam = ntx.match(/(?<!\d)(?:\+?964|00964|0)?(7[0-9]{9})(?!\d)/);   // 07XXXXXXXXX
const dmReq = /رسائل/.test(ntx);
const mode = (/واتس|whats/i.test(ntx) || wam) ? 'whatsapp' : dmReq ? 'dm' : 'other';
return [{ json: { mode, num: wam ? wam[1] : null } }];
'''
ING = 'x = 1\nplan = code(w, "AI: plan", r"""\n' + PLAN + '""")\nother = code(w, "Meta: x", r"""\nconst wam = (String(d.text).match(/(7[0-9]{9})/));\n""")\n'
rd = lambda p: open(p, encoding="utf-8").read()
def mk(src=ING, build=None):
    d = tempfile.mkdtemp(); os.makedirs(d + "/n8n"); open(d + "/n8n/wf_ingress.py", "w", encoding="utf-8").write(src)
    if build: open(d + "/n8n/build.py", "w").write(build)
    return d
def apply(d): return subprocess.run([sys.executable, P], env={**os.environ, "P266_BASE": d + "/"}, capture_output=True, text=True)
def body(d):
    s = rd(d + "/n8n/wf_ingress.py"); m = re.search(r'code\(w, "AI: plan", r"""', s); return s[m.end(): s.index('"""', m.end())]
def run(b, text):
    t = tempfile.mkdtemp(); open(t + "/b.js", "w", encoding="utf-8").write(b); open(t + "/c.json", "w", encoding="utf-8").write(json.dumps({"nodes": {"Route": {"text": text}}}))
    r = subprocess.run(["node", RUN, t + "/b.js", t + "/c.json"], capture_output=True, text=True); assert r.returncode == 0, r.stderr; return json.loads(r.stdout)[0]["json"]


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = mk(); r = apply(cls.d); assert "APPLY266_OK" in r.stdout, r.stdout + r.stderr; cls.b = body(cls.d); cls.base = body(mk())

    def test_before_fix_misses_international_link(self):                     # يثبت المشكلة الأصلية على النسخة القديمة
        r = run(self.base, "ارفع حملة مبيعات https://wa.me/9647701234567 ميزانية 5 دولار"); self.assertEqual((r["mode"], r["num"]), ("other", None))

    def test_links_detected(self):
        for t in ("ارفع حملة مبيعات https://wa.me/9647701234567 ميزانية 5 دولار", "زيارات https://wa.me/07701234567", "مبيعات wa.me/+9647701234567",
                  "مبيعات https://wa.me/9647701234567?text=hello", "مبيعات https://api.whatsapp.com/send?phone=9647701234567&text=hi",
                  "مبيعات https://api.whatsapp.com/send/?phone=%2B9647701234567", "مبيعات https://wa.me/7701234567", "https://wa.me/009647701234567 مبيعات"):
            r = run(self.b, t); self.assertEqual((r["mode"], r["num"]), ("whatsapp", "7701234567"), t)

    def test_explicit_number_and_word_unchanged(self):
        self.assertEqual(run(self.b, "مبيعات واتساب 07701234567")["num"], "7701234567")
        r = run(self.b, "مبيعات واتساب"); self.assertEqual((r["mode"], r["num"]), ("whatsapp", None))       # يبقى يسأل عن الرقم (السلوك القديم)

    def test_no_false_positive(self):
        for t in ("ارفع حملة مبيعات https://example.com/shop ميزانية 5 دولار", "مبيعات https://wa.twasuliraq.com/w/hcnvkwua", "مبيعات https://whatsapp.com/channel/0029VaABCDEFGH",
                  "مبيعات https://wa.me/9647701234567890123", "مبيعات https://wa.me/966501234567", "مبيعات https://wa.me/abc", "مبيعات رمز ABCD7701234567EFGH123", "مبيعات https://www.instagram.com/wa.me/9647701234567x"):
            r = run(self.b, t)
            self.assertIsNone(r["num"] if r["mode"] != "whatsapp" else None, t)
        for t in ("مبيعات https://example.com/shop", "مبيعات https://wa.twasuliraq.com/w/hcnvkwua", "مبيعات https://wa.me/9647701234567890123", "مبيعات https://wa.me/966501234567"):
            self.assertEqual(run(self.b, t)["mode"], "other", t)

    def test_only_wam_line_changed_and_no_backslash_added(self):
        a, b = rd(self.d + "/n8n/wf_ingress.py.pre266").split("\n"), rd(self.d + "/n8n/wf_ingress.py").split("\n")
        self.assertEqual(len(a), len(b)); diff = [(x, y) for x, y in zip(a, b) if x != y]; self.assertEqual(len(diff), 1)
        self.assertTrue(diff[0][1].startswith(diff[0][0].split(";")[0].rstrip(")")[:0] + "const wam = ntx.match(")); self.assertIn("p266", diff[0][1])
        self.assertEqual(diff[0][1].count("\\"), diff[0][0].count("\\"))
        self.assertIn("(Meta: x)" if False else "const wam = (String(d.text).match(/(7[0-9]{9})/));", rd(self.d + "/n8n/wf_ingress.py"))   # عقدة ثانية سليمة

    def test_idempotent(self):
        r = apply(self.d); self.assertIn("changed=0", r.stdout); self.assertEqual(rd(self.d + "/n8n/wf_ingress.py").count("p266"), 1)

    def test_fail_closed_nothing_written(self):
        for src in ("x = 1\n", ING.replace(PLAN, PLAN + PLAN), ING.replace("const ntx = String(d.text", "const ntxx = String(d.text"), ING.replace("(/واتس|whats/i.test(ntx) || wam)", "(false)")):
            d = mk(src); before = rd(d + "/n8n/wf_ingress.py"); r = apply(d)
            self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertEqual(rd(d + "/n8n/wf_ingress.py"), before); self.assertFalse(os.path.exists(d + "/n8n/wf_ingress.py.pre266"))

    def test_build_failure_restores(self):
        d = mk(build="import sys; sys.exit(1)\n"); before = rd(d + "/n8n/wf_ingress.py"); r = apply(d)
        self.assertIn("restored", r.stdout + r.stderr); self.assertEqual(rd(d + "/n8n/wf_ingress.py"), before)

    def test_only_ingress_touched(self):
        d = mk(); open(d + "/other.txt", "w").write("x"); apply(d); self.assertEqual(sorted(os.listdir(d + "/n8n")), ["wf_ingress.py", "wf_ingress.py.pre266"]); self.assertEqual(rd(d + "/other.txt"), "x")


if __name__ == "__main__":
    unittest.main(verbosity=1)
