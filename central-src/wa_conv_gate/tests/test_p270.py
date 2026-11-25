# -*- coding: utf-8 -*-
import json, os, re, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); OPS = os.path.join(H, "..", "..", "ops"); P266 = os.path.join(OPS, "p266-wa-link-route.py.txt"); P269 = os.path.join(OPS, "p269a-wa-host-intent.py.txt"); P270 = os.path.join(OPS, "p270-wa-conv-gate.py.txt")
RUN = os.path.join(H, "..", "..", "pause_by_name", "tests", "run_node.cjs")
PLAN = r'''const d = $('Route').first().json; const it = { objective: 'المبيعات' };
const ntx = String(d.text || '').replace(/[#A-Za-z0-9+\/\\=_\-]{16,250}/g, ' ');
const wam = ntx.match(/(?<!\d)(?:\+?964|00964|0)?(7[0-9]{9})(?!\d)/);   // 07XXXXXXXXX
const dmReq = false;
const mode = (/واتس|whats/i.test(ntx) || wam) ? 'whatsapp' : dmReq ? 'tiktok_dm' : ({ 'المبيعات': 'المبيعات' }[it.objective]);
if (mode === 'whatsapp' && !wam) return [{ json: { halt: 'need_number' } }];
return [{ json: { mode, num: wam ? wam[1] : null } }];
'''
ING = 'plan = code(w, "AI: plan", r"""\n' + PLAN + '""")\n'
rd = lambda p: open(p, encoding="utf-8").read()
def sh(path, d, var, build=False): return subprocess.run([sys.executable, path], env={**os.environ, var: d + "/"}, capture_output=True, text=True)
def mk(build=None):
    d = tempfile.mkdtemp(); os.makedirs(d + "/n8n"); open(d + "/n8n/wf_ingress.py", "w", encoding="utf-8").write(ING)
    s = rd(d + "/n8n/wf_ingress.py").replace("const wam = ntx.match(/(?<!\\d)(?:\\+?964|00964|0)?(7[0-9]{9})(?!\\d)/);", "const wam = ntx.match(/(?<!\\d)(?:\\+?964|00964|0)?(7[0-9]{9})(?!\\d)/);")
    open(d + "/n8n/wf_ingress.py", "w", encoding="utf-8").write(s)
    for p, v in ((P266, "P266_BASE"), (P269, "P269A_BASE")):
        r = sh(p, d, v); assert "APPLY" in r.stdout, r.stdout + r.stderr
    if build: open(d + "/n8n/build.py", "w").write(build)
    return d
def body(d):
    s = rd(d + "/n8n/wf_ingress.py"); m = re.search(r'code\(w, "AI: plan", r"""', s); return s[m.end(): s.index('"""', m.end())]
def run(b, text):
    t = tempfile.mkdtemp(); open(t + "/b.js", "w", encoding="utf-8").write(b); open(t + "/c.json", "w", encoding="utf-8").write(json.dumps({"nodes": {"Route": {"text": text}}}))
    r = subprocess.run(["node", RUN, t + "/b.js", t + "/c.json"], capture_output=True, text=True); assert r.returncode == 0, r.stderr; return json.loads(r.stdout)[0]["json"]


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pre = mk(); cls.before = body(cls.pre); cls.d = mk(); r = sh(P270, cls.d, "P270_BASE"); assert "APPLY270_OK" in r.stdout, r.stdout + r.stderr; cls.b = body(cls.d)

    def test_before_p270_sales_with_wa_page_halts(self):                     # المشكلة اللي نصلحها: يعطّل المبيعات
        self.assertEqual(run(self.before, "مبيعات https://wa.twasuliraq.com/w/hcnvkwua").get("halt"), "need_number")
        self.assertEqual(run(self.before, "مبيعات https://wa.me/9647701234567").get("mode"), "whatsapp")

    def test_sales_and_traffic_with_links_are_normal(self):
        for t in ("مبيعات https://wa.twasuliraq.com/w/hcnvkwua", "ارفع حملة مبيعات https://wa.me/9647701234567", "زيارات https://wa.me/9647701234567",
                  "مبيعات https://wa.me/966501234567", "مبيعات https://example.com/shop"):
            r = run(self.b, t); self.assertEqual((r.get("mode"), r.get("halt")), ("المبيعات", None), t)

    def test_explicit_conversations_get_p266_and_p269a(self):
        for t in ("ارفع حملة محادثات https://wa.me/9647701234567", "رسائل واتساب https://wa.me/9647701234567", "ارفع حملة رسايل واتساب https://api.whatsapp.com/send?phone=9647701234567", "conversations https://wa.me/9647701234567"):
            r = run(self.b, t); self.assertEqual((r.get("mode"), r.get("num")), ("whatsapp", "7701234567"), t)
        for t in ("محادثات https://wa.twasuliraq.com/w/hcnvkwua", "محادثات https://wa.me/966501234567", "رسائل واتساب https://www.whatsapp.com/"):
            self.assertEqual(run(self.b, t).get("halt"), "need_number", t)

    def test_api_whatsapp_link_without_conversations_word_keeps_original_behaviour(self):   # كلمة whats داخل الرابط كانت تفعّل وضع واتساب أصلاً قبل أي باتش من اليوم
        orig = ING.split('code(w, "AI: plan", r"""\n')[1].split('"""')[0]                                            # الكود الأصلي قبل أي باتش
        self.assertEqual(run(orig, "مبيعات https://api.whatsapp.com/send?phone=9647701234567").get("halt"), "need_number")
        self.assertEqual(run(self.before, "مبيعات https://api.whatsapp.com/send?phone=9647701234567").get("mode"), "whatsapp")   # p266 كان يستخرجه
        self.assertEqual(run(self.b, "مبيعات https://api.whatsapp.com/send?phone=9647701234567").get("halt"), "need_number")

    def test_explicit_number_or_word_still_old_behaviour(self):
        self.assertEqual(run(self.b, "مبيعات واتساب 07701234567").get("num"), "7701234567")
        self.assertEqual(run(self.b, "مبيعات واتساب").get("halt"), "need_number")
        self.assertEqual(run(self.b, "مبيعات https://wa.me/07701234567").get("mode"), "whatsapp")        # الرقم المحلي صريح بالرابط: السلوك الأصلي

    def test_only_two_lines_changed_no_backslash_added(self):
        a, b = rd(self.d + "/n8n/wf_ingress.py.pre270").split("\n"), rd(self.d + "/n8n/wf_ingress.py").split("\n")
        self.assertEqual(len(a), len(b)); diff = [(x, y) for x, y in zip(a, b) if x != y]; self.assertEqual(len(diff), 2)
        for x, y in diff: self.assertEqual(x.count("\\"), y.count("\\"))

    def test_idempotent_and_requires_priors(self):
        self.assertIn("changed=0", sh(P270, self.d, "P270_BASE").stdout)
        d = tempfile.mkdtemp(); os.makedirs(d + "/n8n"); open(d + "/n8n/wf_ingress.py", "w", encoding="utf-8").write(ING); r = sh(P270, d, "P270_BASE"); self.assertIn("must be applied first", r.stdout + r.stderr)

    def test_fail_closed_and_build_restore(self):
        d = mk(); s = rd(d + "/n8n/wf_ingress.py"); open(d + "/n8n/wf_ingress.py", "w", encoding="utf-8").write(s.replace("/*p269a*/", "/*p26x*/ /*p269a*/ 1 ||")); before = rd(d + "/n8n/wf_ingress.py")
        r = sh(P270, d, "P270_BASE"); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertEqual(rd(d + "/n8n/wf_ingress.py"), before)
        d = mk(build="import sys; sys.exit(1)\n"); before = rd(d + "/n8n/wf_ingress.py"); r = sh(P270, d, "P270_BASE"); self.assertIn("restored", r.stdout + r.stderr); self.assertEqual(rd(d + "/n8n/wf_ingress.py"), before)


if __name__ == "__main__":
    unittest.main(verbosity=1)
