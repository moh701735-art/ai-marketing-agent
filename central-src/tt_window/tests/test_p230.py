import importlib.util, json, os, shutil, subprocess, sys, tempfile, textwrap, unittest, datetime
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..")
subprocess.run([sys.executable, os.path.join(ROOT, "build_patch.py")], check=True, capture_output=True)
PATCH = os.path.join(ROOT, "..", "ops", "p230-tt-window.py.txt")
SPARK = '''import datetime, re
CODE_RE = re.compile(r"[A-Za-z0-9_\\-]{10,200}")
def validate(params: dict, allowed_countries=None):
    """(clean, error_msg)"""
    allowed = {"campaign_name", "landing_url", "objective", "budget", "budget_mode", "days", "spark_codes", "page_name", "product", "ad_text", "interest_count", "interest_ids", "interest_names", "use_interests", "activate_now", "auto_activate"}
    if not isinstance(params, dict) or set(params) - allowed:
        return None, "unknown params"
    days = params.get("days")
    if not isinstance(days, int) or not 1 <= days <= 90:
        return None, "days"
    codes = params.get("spark_codes") or []
    ic = 0
    return {**params, "spark_codes": codes, "auto_activate": params.get("auto_activate"), "activate_now": params.get("activate_now"), "interest_count": ic, "use_interests": False}, None

def adgroup_params(p: dict, campaign_id: str, name: str, now: datetime.datetime, interest_ids=None) -> dict:
    start = now + datetime.timedelta(minutes=10)
    end = start + datetime.timedelta(days=p["days"])
    f = "%Y-%m-%d %H:%M:%S"
    a = {"campaign_id": campaign_id, "adgroup_name": name, "budget": p["budget"],
         "schedule_type": "SCHEDULE_START_END", "schedule_start_time": start.strftime(f), "schedule_end_time": end.strftime(f), "billing_event": "OCPM"}
    return a
'''
SERVICE = '''import datetime
from . import spark
class S:
    async def a(self, p, now):
        g = spark.adgroup_params(p, "1", "n", datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None))
    async def _launch_smart(self, ctx, ad_account, params, idem):
        p = params
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        fmt = "%Y-%m-%d %H:%M:%S"
        start = now + datetime.timedelta(minutes=10)
        end = start + datetime.timedelta(days=p["days"])
        return start.strftime(fmt), end.strftime(fmt)
'''
INGRESS = '''A = r"""
const mode = 'x';
const launch = { campaign_name: 'c', budget: 30, days: 1 };
if (mode === 'zz') return say('no');
return [{ json: { ...d, launch, key: 'tgupd-' + d.chatId + '-' + d.updateId + '-launch', cur: 'USD' } }];
"""
B = r"""
const L = d.launch; const msg = 'head' + (dd.product_seen ? '\\nP: ' + dd.product_seen : '') + (L.countries && L.countries.length ? '\\nC: ' + L.countries.join(', ') : '') + '\\nend';
"""
'''


def mk(spark=SPARK, service=SERVICE, ingress=INGRESS):
    d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "broker/app")); os.makedirs(os.path.join(d, "n8n"))
    for rel, txt in (("broker/app/spark.py", spark), ("broker/app/service.py", service), ("n8n/wf_ingress.py", ingress)):
        open(os.path.join(d, rel), "w", encoding="utf-8").write(txt)
    return d


def apply(d):
    return subprocess.run([sys.executable, PATCH], env={**os.environ, "P230_BASE": d + "/"}, capture_output=True, text=True)


def load(path, name="spark_t"):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def node(js, d, it, ):
    code = "const f = new Function('d','it','say', process.argv[1]); const r = f(JSON.parse(process.argv[2]), JSON.parse(process.argv[3]), (m) => ({say: m})); console.log(JSON.stringify(r));"
    r = subprocess.run(["node", "-e", code, js, json.dumps(d), json.dumps(it)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


class T(unittest.TestCase):
    def setUp(self): self.d = mk()
    def tearDown(self): shutil.rmtree(self.d, ignore_errors=True)

    def test_01_apply_markers_backups_and_idempotent(self):
        r = apply(self.d); self.assertIn("APPLY230_OK", r.stdout, r.stdout + r.stderr)
        for rel in ("broker/app/spark.py", "broker/app/service.py", "n8n/wf_ingress.py"):
            self.assertIn("p230", open(os.path.join(self.d, rel), encoding="utf-8").read()); self.assertTrue(os.path.exists(os.path.join(self.d, rel + ".pre230")))
        self.assertEqual(open(os.path.join(self.d, "broker/app/spark.py.pre230"), encoding="utf-8").read(), SPARK)
        r2 = apply(self.d); self.assertIn("changed=0", r2.stdout)

    def test_02_spark_window_and_validation(self):
        apply(self.d); m = load(os.path.join(self.d, "broker/app/spark.py"))
        now = datetime.datetime(2026, 11, 22, 12, 0, 0)
        p = {"budget": 30, "days": 1}
        s, e = m.window(p, now); self.assertEqual((s, e), (now + datetime.timedelta(minutes=10), now + datetime.timedelta(minutes=10, days=1)))   # بدون نافذة = السلوك القديم حرفياً
        pw = {**p, "start_at": "2026-11-22 19:00:00", "end_at": "2026-11-23 07:00:00"}
        self.assertEqual(m.window(pw, now), (datetime.datetime(2026, 11, 22, 19), datetime.datetime(2026, 11, 23, 7)))
        a = m.adgroup_params(pw, "9", "n", now)
        self.assertEqual((a["schedule_start_time"], a["schedule_end_time"], a["schedule_type"]), ("2026-11-22 19:00:00", "2026-11-23 07:00:00", "SCHEDULE_START_END"))
        a0 = m.adgroup_params(p, "9", "n", now); self.assertEqual(a0["schedule_start_time"], "2026-11-22 12:10:00")
        # validate: النافذة تمر عبر القائمة المسموحة، وتُرفض المعطوبة
        fut = (datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(hours=3))
        f = "%Y-%m-%d %H:%M:%S"; good = {"budget": 30, "days": 1, "start_at": fut.strftime(f), "end_at": (fut + datetime.timedelta(hours=12)).strftime(f)}
        c, err = m.validate(good); self.assertIsNone(err); self.assertEqual(c["start_at"], good["start_at"])
        for bad, why in (({"start_at": good["start_at"]}, "one only"), ({**good, "end_at": "غلط"}, "format"), ({**good, "start_at": (fut - datetime.timedelta(hours=5)).strftime(f), "end_at": good["end_at"]}, "past"),
                         ({**good, "end_at": (fut + datetime.timedelta(minutes=10)).strftime(f)}, "too short"), ({**good, "end_at": (fut + datetime.timedelta(days=8)).strftime(f)}, "too long"),
                         ({**good, "start_at": (fut + datetime.timedelta(days=40)).strftime(f), "end_at": (fut + datetime.timedelta(days=40, hours=2)).strftime(f)}, "too far"),
                         ({**good, "start_at": "2026-02-31 10:00:00"}, "no such date")):
            c, err = m.validate(bad); self.assertIsNone(c, why); self.assertTrue(err, why)
        c, err = m.validate({"budget": 30, "days": 1}); self.assertIsNone(err)          # بدون نافذة: ما تغيّر شي
        c, err = m.validate({"budget": 30, "days": 1, "unknown": 1}); self.assertEqual(err, "unknown params")

    def test_03_service_smart_path_uses_window(self):
        apply(self.d); txt = open(os.path.join(self.d, "broker/app/service.py"), encoding="utf-8").read()
        self.assertIn("start, end = spark.window(p, now)", txt); self.assertEqual(txt.count("p230"), 1); compile(txt, "service.py", "exec")

    def test_04_ingress_block_and_card_run_in_node(self):
        apply(self.d); txt = open(os.path.join(self.d, "n8n/wf_ingress.py"), encoding="utf-8").read()
        self.assertEqual(txt.count("/*p230*/"), 1); self.assertEqual(txt.count("// p230:"), 1)
        ns = {}; exec(txt, ns)
        js = ns["A"]; self.assertLess(js.index("// p230:"), js.index("return [{ json:"))
        # نافذة حقيقية → launch يحمل start_at/end_at
        far = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).strftime("%d")
        out = node(js, {"text": "روجها بكرة 22:00 وقفها 10:00 صباحا ميزانية 30 دولار", "chatId": 1, "updateId": 2}, {"budget": 30})
        self.assertIn("start_at", out[0]["json"]["launch"]); self.assertEqual(out[0]["json"]["launch"]["budget"], 30)
        out = node(js, {"text": "ارفع حمله 30 دولار يوم واحد", "chatId": 1, "updateId": 2}, {"budget": 30})
        self.assertNotIn("start_at", out[0]["json"]["launch"])
        out = node(js, {"text": "روجها 22:00 وقفها 10:00", "chatId": 1, "updateId": 2}, {"budget": 30})     # غامض → توقف
        self.assertIn("say", out); self.assertIn("ما أنشأت أي حملة", out["say"])
        cardjs = ns["B"]
        r = subprocess.run(["node", "-e", "const f = new Function('d','dd', process.argv[1] + '; return msg;'); console.log(JSON.stringify([f({launch:{start_at:'2026-11-22 19:00:00', end_at:'2026-11-23 07:00:00', countries:['IQ']}}, {}), f({launch:{countries:['IQ']}}, {})]))", cardjs], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr); w, plain = json.loads(r.stdout)
        self.assertIn("2026-11-22 22:00", w); self.assertIn("2026-11-23 10:00", w); self.assertIn("C: IQ", w); self.assertNotIn("النافذة", plain)

    def test_05_embedded_block_equals_block_js(self):
        t = open(PATCH, encoding="utf-8").read(); blk = open(os.path.join(ROOT, "block_v1.js"), encoding="utf-8").read().rstrip("\n")
        self.assertIn("BLOCK = r'''" + blk + "'''", t)

    def test_06_anchor_failures_write_nothing(self):
        cases = {"spark: two timedelta pairs": (SPARK + SPARK.split("def adgroup_params")[1].join(["def adgroup_params2", ""]), SERVICE, INGRESS),
                 "service: no start/end lines": (SPARK, SERVICE.replace("start = now + datetime.timedelta(minutes=10)", "start = now"), INGRESS),
                 "ingress: no launch key": (SPARK, SERVICE, INGRESS.replace("-launch", "-go")),
                 "ingress: card missing": (SPARK, SERVICE, INGRESS.replace("L.countries && L.countries.length", "x")),
                 "spark: no allowed set": (SPARK.replace("allowed = {", "allowed = set(["), SERVICE, INGRESS)}
        for name, (a, b, c) in cases.items():
            d = mk(a, b, c)
            try:
                before = {rel: open(os.path.join(d, rel), encoding="utf-8").read() for rel in ("broker/app/spark.py", "broker/app/service.py", "n8n/wf_ingress.py")}
                r = apply(d); self.assertNotEqual(r.returncode, 0, name); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr, name)
                for rel, txt in before.items():
                    self.assertEqual(open(os.path.join(d, rel), encoding="utf-8").read(), txt, name); self.assertFalse(os.path.exists(os.path.join(d, rel + ".pre230")), name)
            finally: shutil.rmtree(d, ignore_errors=True)

    def test_07_half_applied_state_refused(self):
        d = mk(SPARK + "\n# p230\n", SERVICE, INGRESS)
        try: r = apply(d); self.assertIn("half-applied", r.stdout + r.stderr)
        finally: shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
