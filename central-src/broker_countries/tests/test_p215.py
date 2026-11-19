"""يطبّق p215 على نسخ اصطناعية من central.py/spark.py/service.py (بنفس شكل السيرفر) ويختبر السلوك. بدون شبكة وبدون قاعدة."""
import asyncio, importlib.util, os, shutil, subprocess, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATCH = os.path.join(ROOT, "ops", "p215-tenant-countries.py.txt")
PATCH_OLD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "p215_v3_old.py.txt")
PATCH_B = os.path.join(ROOT, "ops", "p215b-rename-allowed.py.txt")
CENTRAL = '''
class Central:
    def __init__(self, pool): self.pool = pool

    async def authorize(self, ctx: str, platform: str, ad_account: str, access: str) -> dict:
        return {"tenant_id": "t"}

    async def report_connection(self, ctx: str, platform: str, secret_ref: str, status: str) -> bool:
        try:
            async with self.pool.connection() as c:
                r = await (await c.execute("SELECT api.report_connection(%s,%s,%s,%s)", (ctx, platform, secret_ref, status))).fetchone()
            return bool(r[0])
        except Exception:
            return False
'''
SPARK = '''
def validate(params: dict):
    if not isinstance(params, dict): return None, "x"
    allowed = {"countries", "smart", "budget"}   # الحقيقي: قائمة بيضاء لأسماء البارامترات،
    extra = [k for k in params if k not in allowed]
    if extra: return None, "unknown: " + ",".join(sorted(extra))
    cs = params.get("countries", ["IQ"])
    if not isinstance(cs, list) or not (1 <= len(cs) <= 8) or any(not isinstance(x, str) for x in cs):
        return None, "countries must be a list"
    cs = list(dict.fromkeys(cs))
    if __import__("os").environ.get("BROKER_TT_IRAQ_ONLY", "1") != "0" and cs != ["IQ"]:  # p207
        return None, "الاستهداف مقفل على العراق فقط، أي دولة ثانية غير مسموحة (BROKER_TT_IRAQ_ONLY)"
    if params.get("smart") and cs != ["IQ"]:
        return None, "smart"
    return {"countries": cs}, None
'''
SERVICE = '''
import spark

class Svc:
    def __init__(self, central): self.central = central

    async def launch(self, ctx: str, ad_account: str, params: dict, idem: str):
        def bad(msg):
            return 400, {"ok": False, "error": {"class": "invalid_params", "message": msg, "retryable": False}}
        allowed = {"keep", "me"}
        p, err = spark.validate(params)
        if err: return bad(err)
        return 200, {"ok": True, "p": p, "allowed_kept": sorted(allowed)}
'''
class FakeConn:
    def __init__(self, row, boom=False): self.row, self.boom = row, boom
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def execute(self, sql, args):
        if self.boom: raise RuntimeError("db down")
        outer = self
        class R:
            async def fetchone(s): return outer.row
        return R()
class Pool:
    def __init__(self, row, boom=False): self.row, self.boom = row, boom
    def connection(self): return FakeConn(self.row, self.boom)
class T(unittest.TestCase):
    UPGRADE = False
    @classmethod
    def apply_patches(cls):
        env = dict(os.environ, P215_BASE=cls.tmp + "/", P215_NODB="1", P215B_BASE=cls.tmp + "/")
        if cls.UPGRADE:
            r = subprocess.run([sys.executable, PATCH_OLD], env=env, capture_output=True, text=True); assert "APPLY215_OK" in r.stdout, r.stdout + r.stderr
            r = subprocess.run([sys.executable, PATCH_B], env=env, capture_output=True, text=True); assert "APPLY215B_OK" in r.stdout, r.stdout + r.stderr
        else:
            r = subprocess.run([sys.executable, PATCH], env=env, capture_output=True, text=True); assert "APPLY215_OK" in r.stdout, r.stdout + r.stderr
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(); os.makedirs(cls.tmp + "/broker/app")
        for n, s in (("central", CENTRAL), ("spark", SPARK), ("service", SERVICE)): open(cls.tmp + "/broker/app/%s.py" % n, "w", encoding="utf-8").write(s)
        cls.apply_patches()
        def load(n):
            spec = importlib.util.spec_from_file_location(n, cls.tmp + "/broker/app/%s.py" % n); m = importlib.util.module_from_spec(spec); sys.modules[n] = m; spec.loader.exec_module(m); return m
        cls.central, cls.spark = load("central"), load("spark"); cls.service = load("service")
    @classmethod
    def tearDownClass(cls): shutil.rmtree(cls.tmp, ignore_errors=True)
    def launch(self, countries, row=None, boom=False, env=None):
        os.environ.pop("BROKER_TT_IRAQ_ONLY", None)
        if env is not None: os.environ["BROKER_TT_IRAQ_ONLY"] = env
        try:
            svc = self.service.Svc(self.central.Central(Pool(row, boom))); return asyncio.run(svc.launch("CTX", "123", {"countries": countries}, "i" * 20))
        finally: os.environ.pop("BROKER_TT_IRAQ_ONLY", None)
    GULF = [["IQ", "SA", "KW", "AE", "QA", "BH", "OM"]]
    def test_regression_validate_whitelist_local_not_clobbered(self):   # the p215 v1-v3 production bug
        st, env = self.launch(["IQ"], row=None); self.assertEqual(st, 200, env); self.assertEqual(env["allowed_kept"], ["keep", "me"])
        st, env = self.launch(["IQ"], row=[["IQ"]]); self.assertEqual(st, 200, env)
    def test_default_tenant_is_iraq_only(self):
        st, env = self.launch(["IQ"], row=[["IQ"]]); self.assertEqual(st, 200)
        st, env = self.launch(["SA"], row=[["IQ"]]); self.assertEqual(st, 400); self.assertIn("العراق فقط", env["error"]["message"])
    def test_gulf_tenant_accepts_listed_countries(self):
        st, env = self.launch(["SA", "KW", "AE", "QA", "BH", "OM"], row=self.GULF); self.assertEqual(st, 200); self.assertEqual(env["p"]["countries"], ["SA", "KW", "AE", "QA", "BH", "OM"])
    def test_gulf_tenant_still_blocks_unlisted(self):
        st, env = self.launch(["SA", "TR"], row=self.GULF); self.assertEqual(st, 400); self.assertIn("مسموح فقط للدول", env["error"]["message"]); self.assertIn("SA", env["error"]["message"]); self.assertNotIn("TR,", env["error"]["message"])
    def test_lookup_failure_is_fail_closed(self):
        self.assertEqual(self.launch(["SA"], boom=True)[0], 400); self.assertEqual(self.launch(["IQ"], boom=True)[0], 200)
    def test_missing_or_empty_row_is_iraq_only(self):
        self.assertEqual(self.launch(["SA"], row=None)[0], 400); self.assertEqual(self.launch(["SA"], row=[None])[0], 400); self.assertEqual(self.launch(["SA"], row=[[]])[0], 400)
    def test_env_off_disables_the_lock_globally(self):
        self.assertEqual(self.launch(["SA", "TR"], row=[["IQ"]], env="0")[0], 200)
    def test_lowercase_from_db_is_normalized(self):
        self.assertEqual(self.launch(["SA"], row=[["iq", "sa"]])[0], 200)
    def test_central_tenant_countries_shapes(self):
        c = self.central.Central(Pool([["sa", "iq"]])); self.assertEqual(asyncio.run(c.tenant_countries("x")), ["SA", "IQ"])
        self.assertIsNone(asyncio.run(self.central.Central(Pool(None)).tenant_countries("x"))); self.assertIsNone(asyncio.run(self.central.Central(Pool([["x"]], True)).tenant_countries("x")))
    def test_idempotent_and_backups(self):
        r = subprocess.run([sys.executable, PATCH], env=dict(os.environ, P215_BASE=self.tmp + "/", P215_NODB="1"), capture_output=True, text=True); self.assertIn("changed=0", r.stdout)
        r = subprocess.run([sys.executable, PATCH_B], env=dict(os.environ, P215B_BASE=self.tmp + "/"), capture_output=True, text=True); self.assertIn("changed=0", r.stdout)
        for n in ("central", "spark", "service"): self.assertTrue(os.path.exists(self.tmp + "/broker/app/%s.py.pre215" % n))
    def test_service_anchor_tolerates_trailing_whitespace_comment_and_crlf(self):
        for variant in ("p, err = spark.validate(params)   ", "p, err = spark.validate(params)  # validate", "p,err=spark.validate( params )", "params2, e = spark.validate(params)", "pp, msg = spark.validate(params)"):
            tmp = tempfile.mkdtemp(); os.makedirs(tmp + "/broker/app")
            for n, s in (("central", CENTRAL), ("spark", SPARK), ("service", SERVICE.replace("p, err = spark.validate(params)", variant))): open(tmp + "/broker/app/%s.py" % n, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if "crlf" in variant else s)
            r = subprocess.run([sys.executable, PATCH], env=dict(os.environ, P215_BASE=tmp + "/", P215_NODB="1"), capture_output=True, text=True); self.assertIn("APPLY215_OK", r.stdout, variant + r.stdout + r.stderr)
            self.assertIn("spark.validate(params, allowed_countries=tt_ctry)", open(tmp + "/broker/app/service.py", encoding="utf-8").read()); self.assertTrue(open(tmp + "/broker/app/service.py", encoding="utf-8").read().count("= spark.validate(params, allowed_countries=tt_ctry)") == 1); shutil.rmtree(tmp)
    def test_anchor_failure_writes_nothing(self):
        tmp = tempfile.mkdtemp(); os.makedirs(tmp + "/broker/app")
        for n, s in (("central", CENTRAL), ("spark", SPARK), ("service", SERVICE.replace("launch(self, ctx: str,", "launch(self, c: str,"))): open(tmp + "/broker/app/%s.py" % n, "w", encoding="utf-8").write(s)
        r = subprocess.run([sys.executable, PATCH], env=dict(os.environ, P215_BASE=tmp + "/", P215_NODB="1"), capture_output=True, text=True); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr)
        self.assertEqual(open(tmp + "/broker/app/spark.py", encoding="utf-8").read(), SPARK); shutil.rmtree(tmp)
class Upgrade(T):
    UPGRADE = True
if __name__ == "__main__": unittest.main()
