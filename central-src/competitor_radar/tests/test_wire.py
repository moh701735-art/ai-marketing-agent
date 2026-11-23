import json, os, shutil, stat, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..", "..")
subprocess.run([sys.executable, os.path.join(H, "..", "deploy", "build_wire.py")], check=True, capture_output=True)
PATCH = os.path.join(ROOT, "ops", "p250-radar-wiring.py.txt")
PAGES = open(os.path.join(H, "..", "pages.py"), encoding="utf-8").read()
INGRESS = '''import os, importlib.util
def build_all(b, w, sw, reply, CRT):
    if True:
        _snwm = None
    _gdp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'guide', 'pages.py')   # p209: دليل الاستخدام
    if os.path.exists(_gdp):
        _gds = importlib.util.spec_from_file_location('guide_pages', _gdp); _gdm = importlib.util.module_from_spec(_gds); _gds.loader.exec_module(_gdm)
        _gdm.build(b, w, sw, 36, reply, CRT)
ROUTE = r"""
  const SAN = (!d.cb && $input.all().some(i => i.json && String(i.json.step) === 'sa_name')) ? String(d.text || '').trim() : '';
  const SNU = (!d.cb && $input.all().some(i => i.json && String(i.json.step) === 'sn_url')) ? String(d.text || '').trim() : '';   // p195d
  let ck = String(d.cb || '').split(':')[0];
  if (ck === 'sn') { cmd = 'snapin'; } else if (ck === 'sn') { cmd = 'snapwiz'; uiv = String(d.cb); } else if (ck === 'gd') { cmd = 'guide'; uiv = String(d.cb); }
  if (SAN && !SAN.startsWith('/') && cmd !== 'wiz') { cmd = 'audience'; args = SAN; }
  if (SNU && SNU.indexOf('http') === 0 && !SAN && cmd !== 'wiz') { cmd = 'snaplink'; args = SNU; }   // p195d: رابط عادي بخطوة رابط معالج سناب
  const map = { guide: 36, 'دليل': 36, snapin: 35, snaplink: 35, wiz: 31 };
  const idx = (expired) ? 6 : cmd in map ? map[cmd] : cmd === 'text' ? 7 : 1;
"""
WZS = "SELECT step, n FROM x WHERE age_s < 300 UNION ALL SELECT 'sa_name', 1 FROM api.ui_get($1, 'sa:' || $2) WHERE age_s < 300 UNION ALL SELECT 'sn_url', 3 FROM api.ui_get($1, 'sn:' || $2) WHERE (data::jsonb->>'st') = 'url' AND age_s < 1800 ORDER BY 2"
CMD = ("Command", "n8n-nodes-base.switch", 3.5, {"mode": "expression", "numberOutputs": 37, "output": "={{ $json.idx }}"})
'''
UIP = '''SQL = ("SELECT 'prem' AS kind, premium.enabled($1)::text, NULL, NULL, NULL, NULL, NULL "
            "UNION ALL SELECT 'sa', smart_audience.enabled($1)::text, NULL, NULL, NULL, NULL, NULL")
JS = r"""
  const P = { rows: 1, premOn: rows.some(r => r.kind === 'prem' && r.a === 'true'), saOn: rows.some(r => r.kind === 'sa' && r.a === 'true') };
  if (P.premOn) kb.push([{ t: '🧠 الذكاء التسويقي', c: 'pm' }]);
  if (P.saOn) kb.push([{ t: '🎯 منشئ الجمهور الذكي', c: 'sa' }]);      // smart_audience (مطفأ = بلا زر)
  kb.push([{ t: 'x', c: 'y' }]);
"""
'''
OKROW = "competitor_radar.config(text)|competitor_radar.service_key()|true"


def mk(ing=INGRESS, ui=UIP, with_build=False):
    d = tempfile.mkdtemp(); os.makedirs(d + "/n8n")
    open(d + "/n8n/wf_ingress.py", "w", encoding="utf-8").write(ing); open(d + "/n8n/ui_pages.py", "w", encoding="utf-8").write(ui)
    if with_build: open(d + "/n8n/build.py", "w").write("import sys; sys.exit(3)\n")
    return d


def fake_psql(out):
    p = tempfile.mkdtemp() + "/psql.sh"; open(p, "w").write("#!/bin/sh\necho '%s'\n" % out); os.chmod(p, 0o755); return p


def apply(d, psql_out=OKROW):
    p = fake_psql(psql_out)
    return subprocess.run([sys.executable, PATCH], env={**os.environ, "P250_BASE": d + "/", "P250_PSQL": p + " -c"}, capture_output=True, text=True)


rd = lambda p: open(p, encoding="utf-8").read()


class Wire(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = mk(); r = apply(cls.d); assert "APPLY250_OK" in r.stdout, r.stdout + r.stderr; cls.ing = rd(cls.d + "/n8n/wf_ingress.py"); cls.ui = rd(cls.d + "/n8n/ui_pages.py")

    def test_ingress_hunks(self):
        for frag in ("else if (ck === 'cr') { cmd = 'radar'; uiv = String(d.cb); }", "radar: 37, 'رادار': 37", '"numberOutputs": 38', "_crm.build(b, w, sw, 37, reply, CRT)", "'cr_in', 4 FROM api.ui_get($1, 'cr:' || $2)", "const CRI = ",
                     "if (CRI && CRI.charAt(0) !== '/' && !SAN && !SNU && cmd === 'text') { cmd = 'radar'; args = CRI; }"): self.assertEqual(self.ing.count(frag), 1, frag)
        self.assertNotIn('"numberOutputs": 37', self.ing); self.assertEqual(self.ing.count("p250"), 3)
        self.assertLess(self.ing.index("'cr_in', 4"), self.ing.index("ORDER BY 2")); self.assertIn("age_s < 1800 UNION ALL SELECT 'cr_in', 4", self.ing)

    def test_ui_hunks(self):
        self.assertIn("UNION ALL SELECT 'cr', competitor_radar.config($1)->>'enabled', NULL, NULL, NULL, NULL, NULL\")", self.ui); self.assertIn(", crOn: rows.some(r => r.kind === 'cr' && r.a === 'true') }", self.ui)
        self.assertIn("if (P.crOn && kb.length < 8) kb.push([{ t: '🕵️ رادار المنافسين', c: 'cr:m' }]);", self.ui); self.assertLess(self.ui.index("P.saOn) kb.push"), self.ui.index("P.crOn")); self.assertLess(self.ui.index("P.crOn"), self.ui.index("kb.push([{ t: 'x'"))
        self.assertEqual(self.ui.count("p250"), 1)

    def test_patched_files_are_valid_python_and_mount_works(self):
        compile(self.ing, "i", "exec"); compile(self.ui, "u", "exec")
        shutil.copytree(os.path.join(H, ".."), self.d + "/competitor_radar", dirs_exist_ok=True)   # كما يضع الباتش pages.py
        ns = {"__file__": self.d + "/n8n/wf_ingress.py"}; exec(compile(self.ing.split('ROUTE = r"""')[0], "i", "exec"), ns)
        class W:
            nodes, links = [], []
            def add(s, n, t, v, p): d = {"name": n}; s.nodes.append(d); return d
            def link(s, a, b, i=0): s.links.append((a["name"] if isinstance(a, dict) else a, b["name"] if isinstance(b, dict) else b, i if isinstance(i, int) else 0))
            def chain(s, *n): pass
        class B:
            def code(s, w, n, js): return w.add(n, "c", 1, {})
            def pg(s, w, n, q, p, c, always=False): return w.add(n, "p", 1, {})
        w = W(); ns["os"].path.exists  # noqa
        class G:   # دليل وهمي كي لا نعتمد على مجلد guide
            pass
        import types; sys.modules.setdefault("guide_pages_stub", types.ModuleType("x"))
        os.makedirs(self.d + "/guide", exist_ok=True); open(self.d + "/guide/pages.py", "w").write("def build(b, w, sw, idx, reply, CRT):\n    w.add('GD', 'x', 1, {})\n")
        ns["build_all"](B(), w, {"name": "Command"}, lambda n, j: w.add(n, "r", 1, {}), None)
        names = [n["name"] for n in w.nodes]; self.assertIn("CR: data", names); self.assertIn(("Command", "CR: data", 37), w.links); self.assertIn("GD", names)

    def run_route(self, step_rows, text, cmd="text", san="", snu=""):
        lines = [l for l in self.ing.split("\n") if "const CRI = " in l or "if (CRI &&" in l]; self.assertEqual(len(lines), 2)
        js = ("const d = %s; const SAN = %s; const SNU = %s; let cmd = %s, args = ''; const $input = { all: () => %s.map(s => ({ json: { step: s } })) };\n" % (json.dumps({"text": text}), json.dumps(san), json.dumps(snu), json.dumps(cmd), json.dumps(step_rows))
              + lines[0] + "\n" + lines[1] + "\nconsole.log(JSON.stringify({ cmd, args }));")
        f = tempfile.mkdtemp() + "/r.js"; open(f, "w", encoding="utf-8").write(js)
        return json.loads(subprocess.run(["node", f], capture_output=True, text=True, check=True).stdout)

    def test_route_rule_truth_table(self):
        self.assertEqual(self.run_route(["cr_in"], "متجر الأناقة"), {"cmd": "radar", "args": "متجر الأناقة"})
        self.assertEqual(self.run_route(["cr_in"], "متجر\nhttps://x.com/a"), {"cmd": "radar", "args": "متجر\nhttps://x.com/a"})
        self.assertEqual(self.run_route([], "متجر")["cmd"], "text")                                  # بدون حالة إدخال: لا تغيير
        self.assertEqual(self.run_route(["cr_in"], "/start", cmd="start")["cmd"], "start")           # أوامر أخرى لا تُخطف
        self.assertEqual(self.run_route(["cr_in"], "/radar")["cmd"], "text")                        # نص يبدأ بـ/ مو إدخال
        self.assertEqual(self.run_route(["cr_in"], "نص", cmd="wizard")["cmd"], "wizard")             # المعالج الأقدم يغلب
        self.assertEqual(self.run_route(["cr_in"], "نص", cmd="audience", san="نص")["cmd"], "audience")
        self.assertEqual(self.run_route(["cr_in", "sn_url"], "https://wa.me/1", cmd="snaplink", snu="https://wa.me/1")["cmd"], "snaplink")
        self.assertEqual(self.run_route(["cr_in"], "")["cmd"], "text")                              # فارغ: لا شي

    def test_idempotent_and_backups(self):
        d = mk(); self.assertIn("APPLY250_OK", apply(d).stdout); a, b = rd(d + "/n8n/wf_ingress.py"), rd(d + "/n8n/ui_pages.py")
        self.assertIn("already applied", apply(d).stdout); self.assertEqual((a, b), (rd(d + "/n8n/wf_ingress.py"), rd(d + "/n8n/ui_pages.py")))
        self.assertEqual((rd(d + "/n8n/wf_ingress.py.pre250"), rd(d + "/n8n/ui_pages.py.pre250")), (INGRESS, UIP)); self.assertEqual(rd(d + "/competitor_radar/pages.py"), PAGES)

    def test_db_precondition_blocks_everything(self):
        for out in ("MISSING|MISSING|f", "competitor_radar.config(text)|competitor_radar.service_key()|false", "", "ERR"):
            d = mk(); r = apply(d, out); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr, out); self.assertIn("DB precondition", r.stdout + r.stderr)
            self.assertEqual((rd(d + "/n8n/wf_ingress.py"), rd(d + "/n8n/ui_pages.py")), (INGRESS, UIP)); self.assertFalse(os.path.exists(d + "/competitor_radar"))

    def test_anchor_failures_write_nothing(self):
        cases = [(INGRESS.replace("guide: 36", "guide: 35"), UIP), (INGRESS.replace("'gd'", "'gx'"), UIP), (INGRESS.replace('"numberOutputs": 37', '"numberOutputs": 40'), UIP), (INGRESS.replace("_gdm.build(b, w, sw, 36", "_gdm.build(b, w, sw, 35"), UIP),
                 (INGRESS.replace("age_s < 1800 ORDER BY 2", "age_s < 900 ORDER BY 2"), UIP), (INGRESS.replace("const SNU", "const SNX"), UIP), (INGRESS, UIP.replace("saOn: rows", "sa0n: rows")), (INGRESS, UIP.replace("smart_audience.enabled($1)::text, NULL, NULL, NULL, NULL, NULL\")", "smart_audience.enabled($1)::text\")")),
                 (INGRESS, UIP.replace("if (P.saOn)", "if (P.saX)")), (INGRESS + INGRESS, UIP)]
        for ing, ui in cases:
            d = mk(ing, ui); r = apply(d); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertEqual((rd(d + "/n8n/wf_ingress.py"), rd(d + "/n8n/ui_pages.py")), (ing, ui)); self.assertFalse(os.path.exists(d + "/competitor_radar"))

    def test_build_failure_restores(self):
        d = mk(with_build=True); r = apply(d); self.assertIn("build failed", r.stdout + r.stderr); self.assertEqual((rd(d + "/n8n/wf_ingress.py"), rd(d + "/n8n/ui_pages.py")), (INGRESS, UIP))

    def test_half_applied_refused(self):
        d = mk(INGRESS + "# p250\n"); r = apply(d); self.assertIn("half-applied", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=1)
