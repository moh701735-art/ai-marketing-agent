import json, os, re, shutil, subprocess, sys, tempfile, unittest, datetime, importlib.util
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..")
subprocess.run([sys.executable, os.path.join(ROOT, "build_p296.py")], check=True, capture_output=True)
PATCH = os.path.join(ROOT, "..", "ops", "p296-fb-window.py.txt")
rd = lambda p: open(p, encoding="utf-8").read()
OLD_JS = r'''    const body = String($input.first().json.text || '');
    const nb = body.replace(/[٠-٩]/g, c => String(c.charCodeAt(0) - 1632)).replace(/[أإآ]/g, 'ا').replace(/ة/g, 'ه').toLowerCase();
    const dm = body.match(/(\d+)\s*(?:ايام|يوم)/);
    const dw = /واحد/.test(nb) ? 1 : 0;
    const days = Math.min(90, Math.max(1, dm ? Number(dm[1]) : (dw || 3)));
    if (!/https?:/.test(nb)) return halt('no link');
    let startAt = '', startTxt = '';
    if (/(ابدا|تبدا|جدول|موعد)/.test(nb)) {
        const BG = 3 * 3600000, nowB = new Date(Date.now() + BG);
        const tm = nb.match(/(?:الساعه)\s*(\d{1,2})\s*(مساء|صباح)?/);
        const dOff = /بكره|بكرة|غدا/.test(nb) ? 1 : 0;
        let t = null;
        if (tm) {
            let h = Number(tm[1]); if (/مساء/.test(tm[2] || '') && h < 12) h += 12;
            t = new Date(Date.UTC(nowB.getUTCFullYear(), nowB.getUTCMonth(), nowB.getUTCDate() + dOff, h, 0, 0) - BG);
        }
        if (t) {
            if (t.getTime() < Date.now() + 10 * 60000) return halt('start passed');
            startAt = t.toISOString().slice(0, 19) + '+0000'; startTxt = new Date(t.getTime() + BG).toISOString().slice(0, 16).replace('T', ' ') + ' (بغداد)';
        }
    }
    const params = { post_url: 'u', budget_usd: 5, budget_mode: 'total', days: days, start_at: startAt };
    return [{ json: { params, startTxt } }];'''
ING = '''import os
OTHER = code(w, "FBC: other", r"""
    const x = 1;
""")
fbcplan = code(w, "FBC: خطة", r"""
%s
""")
fbcsw = w.add("FBC: ok?", "n8n-nodes-base.switch", 3.5, {})
'''
MF = '''import datetime, re

def validate_wa(params):
    out = {}
    sa = params.get("start_at", "")
    if sa != "":
        if not isinstance(sa, str) or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\\+0000", sa):
            return None, "start_at: YYYY-MM-DDTHH:MM:SS+0000"
        try:
            sdt = datetime.datetime.strptime(sa[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            return None, "start_at: invalid date"
        now = datetime.datetime.now(datetime.timezone.utc)
        if not (now + datetime.timedelta(minutes=5) <= sdt <= now + datetime.timedelta(days=60)):
            return None, "start_at: must be within 60 days"
    pv = params.get("provinces", [])
    PARAMS = ("post_url", "whatsapp", "name", "budget_usd", "budget_mode", "days", "ad_text", "countries", "start_at", "advantage_audience", "page_id")
    unknown = [k for k in params if k not in PARAMS]
    if unknown: return None, "unknown params: %s" % unknown
    out = {"days": int(params.get("days") or 1), "budget_mode": params.get("budget_mode") or "total", "start_at": sa, "advantage_audience": False}
    return out, None

def launch(p):
    base = datetime.datetime.strptime(p["start_at"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc) if p["start_at"] else datetime.datetime.now(datetime.timezone.utc)
    end = (base + datetime.timedelta(days=p["days"])).strftime("%Y-%m-%dT%H:%M:%S+0000")
    ads_prm = {"end_time": end, ("daily_budget" if (p["budget_mode"] == "daily" and int(p.get("days") or 0) > 1) else "lifetime_budget"): 500}
    if p["start_at"]:
        ads_prm["start_time"] = p["start_at"]
    return ads_prm
'''
def mk(old_js=OLD_JS):
    d = tempfile.mkdtemp(); os.makedirs(d + "/n8n"); os.makedirs(d + "/broker/app")
    open(d + "/n8n/wf_ingress.py", "w", encoding="utf-8").write(ING % old_js); open(d + "/broker/app/metaflow.py", "w", encoding="utf-8").write(MF)
    open(d + "/n8n/build.py", "w").write("import sys\nsys.exit(0)\n"); return d
def apply(d): return subprocess.run([sys.executable, PATCH], env={**os.environ, "P296_BASE": d + "/"}, capture_output=True, text=True)
def js_of(d): s = rd(d + "/n8n/wf_ingress.py"); return s.split('fbcplan = code(w, "FBC: خطة", r"""\n', 1)[1].split('"""', 1)[0]
NODE = r'''
const fs = require('fs'); const js = fs.readFileSync(process.argv[2], 'utf8'); const text = process.argv[3];
const NOW = Date.UTC(2026, 10, 22, 12, 0, 0); Date.now = () => NOW;
const f = new Function('$input', 'halt', js);
console.log(JSON.stringify(f({ first: () => ({ json: { text } }) }, (m) => ({ halt: m }))));
'''
def run_js(js, text):
    p = tempfile.mkdtemp(); open(p + "/n.js", "w", encoding="utf-8").write(NODE); open(p + "/code.js", "w", encoding="utf-8").write(js)
    r = subprocess.run(["node", p + "/n.js", p + "/code.js", text], capture_output=True, text=True); shutil.rmtree(p)
    assert r.returncode == 0, r.stderr; return json.loads(r.stdout)
def load_mf(d):
    spec = importlib.util.spec_from_file_location("mf%d" % id(d), d + "/broker/app/metaflow.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
def utc(h): return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%S+0000")


class T(unittest.TestCase):
    def test_01_apply_markers_backup_idempotent(self):
        d = mk(); r = apply(d); self.assertIn("APPLY296_OK Facebook window", r.stdout, r.stdout + r.stderr)
        self.assertTrue(os.path.exists(d + "/n8n/wf_ingress.py.pre296") and os.path.exists(d + "/broker/app/metaflow.py.pre296"))
        self.assertIn("changed=0", apply(d).stdout); self.assertEqual(rd(d + "/n8n/wf_ingress.py.pre296"), ING % OLD_JS)
        ing = rd(d + "/n8n/wf_ingress.py"); self.assertIn("let days = ", ing); self.assertNotIn("const days = ", ing); self.assertIn("end_at: endAt }", ing); self.assertIn("if (!WIN && /(ابدا|تبدا|جدول|موعد)/.test(nb)) {", ing)
        mf = rd(d + "/broker/app/metaflow.py"); self.assertEqual(mf.count("# p296"), 2); self.assertIn('"start_at", "end_at"', mf); self.assertIn('"start_at": sa, "end_at": ea', mf)

    def test_02_node_window_text(self):
        d = mk(); apply(d); js = js_of(d)
        r = run_js(js, "ارفع حمله فيس https://facebook.com/x ارفعها الساعة 6 بالليل وقفها 6 الصبح 20 دولار")
        p = r[0]["json"]["params"]; self.assertEqual(p["start_at"], "2026-11-22T15:00:00+0000"); self.assertEqual(p["end_at"], "2026-11-23T03:00:00+0000"); self.assertEqual(p["days"], 1)
        self.assertIn("من 2026-11-22 18:00 إلى 2026-11-23 06:00", r[0]["json"]["startTxt"])
        # مع كلمة بداية قديمة (ابدأ) المحلل الجديد يتقدّم والقديم يتخطّى
        r = run_js(js, "حمله https://f.com/x ابدأ الساعة 22:00 وقف الساعة 06:00 صباحا")
        self.assertEqual(r[0]["json"]["params"]["start_at"], "2026-11-22T19:00:00+0000"); self.assertEqual(r[0]["json"]["params"]["end_at"], "2026-11-23T03:00:00+0000")
        h = run_js(js, "حمله https://f.com/x ابدأ الساعة 6 وقف الساعة 7 صباحا"); self.assertIn("مو واضحة", h["halt"])
        h = run_js(js, "حمله https://f.com/x ابدأ الساعة 22:00 وقف الساعة 06:00 صباحا يومي"); self.assertIn("إجمالية", h["halt"])

    def test_03_old_paths_unchanged(self):
        d = mk(); apply(d); new = js_of(d); old = OLD_JS
        for t in ["حمله https://f.com/x 5 دولار", "حمله https://f.com/x تبدأ بكرة الساعة 8 مساء 3 ايام", "حمله https://f.com/x ابدأ الساعة 18:00 ", "حمله https://f.com/x جدول الساعة 2 العصر",
                  "حمله https://f.com/x 07829503973 من 18 الى 45 سنة", "بدون رابط"]:
            a = run_js(old, t); b = run_js(new, t)
            if isinstance(a, dict): self.assertEqual(a, b, t)
            else:
                pa = dict(a[0]["json"]["params"]); pb = dict(b[0]["json"]["params"]); self.assertEqual(pb.pop("end_at"), ""); self.assertEqual(pa, pb, t); self.assertEqual(a[0]["json"]["startTxt"], b[0]["json"]["startTxt"], t)

    def test_04_broker_validation_and_end(self):
        d = mk(); apply(d); m = load_mf(d)
        ok, e = m.validate_wa({"start_at": utc(3), "end_at": utc(3 + 12), "days": 1, "budget_mode": "total"}); self.assertIsNone(e); self.assertEqual(ok["end_at"], utc(3 + 12))
        for bad, why in (({"start_at": utc(3), "end_at": utc(3.2)}, "30 minutes"), ({"start_at": utc(3), "end_at": utc(3 + 24 * 8)}, "7 days"), ({"start_at": utc(3), "end_at": utc(2)}, "after start_at"),
                         ({"end_at": utc(5)}, "needs start_at"), ({"start_at": utc(3), "end_at": "2026-13-45T00:00:00+0000"}, "invalid date"), ({"start_at": utc(3), "end_at": "tomorrow"}, "YYYY"),
                         ({"start_at": utc(3), "end_at": utc(9), "budget_mode": "daily"}, "total budget")):
            o, e = m.validate_wa(bad); self.assertIsNone(o); self.assertIn(why, e, (bad, e))
        o, e = m.validate_wa({"days": 2}); self.assertIsNone(e); self.assertEqual(o["end_at"], "")
        o, e = m.validate_wa({"start_at": utc(3), "days": 2}); self.assertIsNone(e); self.assertEqual(o["end_at"], "")
        # نهاية النافذة = end_at بالحرف، بميزانية إجمالية؛ بدون end_at = المسار القديم
        o, e = m.validate_wa({"start_at": utc(3), "end_at": utc(15), "days": 1, "budget_mode": "total"}); a = m.launch(o)
        self.assertEqual(a["end_time"], utc(15)); self.assertIn("lifetime_budget", a); self.assertNotIn("daily_budget", a); self.assertEqual(a["start_time"], utc(3))
        o, e = m.validate_wa({"start_at": utc(3), "days": 2, "budget_mode": "daily"}); a = m.launch(o); self.assertIn("daily_budget", a); self.assertEqual(a["end_time"], (datetime.datetime.strptime(utc(3)[:19], "%Y-%m-%dT%H:%M:%S") + datetime.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S+0000"))
        o, e = m.validate_wa({"days": 1}); self.assertNotIn("end_at", m.launch(o)); self.assertIsNone(o.get("end_at") or None)

    def test_05_fail_closed(self):
        for name, mut in (("node opener", lambda s: s.replace("fbcplan = code(", "fbcplan2 = code(")), ("start line", lambda s: s.replace("let startAt = '', startTxt = '';", "var startAt = '', startTxt = '';")),
                          ("params", lambda s: s.replace("start_at: startAt }", "start_at: startAt, x: 1 }")), ("days", lambda s: s.replace("const days", "var days")),
                          ("name used", lambda s: s.replace("const x = 1;", "const x = 1;").replace("let startAt", "const WIN = 1; let startAt"))):
            d = mk(); p = d + "/n8n/wf_ingress.py"; s = rd(p); t = mut(s); 
            if name == "params": t = s.replace("start_at: startAt };", "start_at: startAt }; const q = { start_at: startAt };")
            open(p, "w", encoding="utf-8").write(t); before = (rd(p), rd(d + "/broker/app/metaflow.py")); r = apply(d)
            self.assertNotEqual(r.returncode, 0, name); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr, name); self.assertEqual((rd(p), rd(d + "/broker/app/metaflow.py")), before, name); self.assertFalse(os.path.exists(p + ".pre296"))
        for name, mut in (("end line", lambda s: s.replace('end = (base +', 'end2 = (base +')), ("pv", lambda s: s.replace('pv = params.get("provinces", [])', 'pv = 1')), ("out", lambda s: s.replace('"start_at": sa', '"start_at": sa2')), ("allowed", lambda s: s.replace('PARAMS = ("post_url", ', 'PARAMS = ("post_urlx", ').replace('"post_url", "name"', '"nm"'))):
            d = mk(); p = d + "/broker/app/metaflow.py"; open(p, "w", encoding="utf-8").write(mut(MF)); b = rd(d + "/n8n/wf_ingress.py"); r = apply(d)
            self.assertNotEqual(r.returncode, 0, name); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr, name); self.assertEqual(rd(d + "/n8n/wf_ingress.py"), b, name)

    def test_06_build_failure_restores_both(self):
        d = mk(); open(d + "/n8n/build.py", "w").write("import sys\nsys.exit(1)\n"); a = rd(d + "/n8n/wf_ingress.py"); b = rd(d + "/broker/app/metaflow.py"); r = apply(d)
        self.assertNotEqual(r.returncode, 0); self.assertIn("restored", r.stdout + r.stderr); self.assertEqual((rd(d + "/n8n/wf_ingress.py"), rd(d + "/broker/app/metaflow.py")), (a, b))

    def test_07_half_applied_refuses(self):
        d = mk(); apply(d); shutil.copy(d + "/broker/app/metaflow.py.pre296", d + "/broker/app/metaflow.py"); r = apply(d); self.assertNotEqual(r.returncode, 0); self.assertIn("half applied", r.stdout + r.stderr)

    def test_08_oneliner_matches(self):
        import base64, lzma
        s = rd(os.path.join(ROOT, "..", "..", "out", "p296s.txt")); self.assertEqual(s.count("\n"), 1); self.assertIn("bash deploy/update.sh", s)
        self.assertEqual(lzma.decompress(base64.b64decode(re.search(r"echo '([^']+)'", s).group(1))).decode(), rd(PATCH))

if __name__ == "__main__": unittest.main(verbosity=1)
