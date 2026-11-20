import asyncio, importlib.util, os, subprocess, sys, tempfile, unittest
H = os.path.dirname(__file__)
P225 = os.path.join(H, "..", "..", "ops", "p225-tt-cover-unique.py.txt"); P226 = os.path.join(H, "..", "..", "ops", "p226-tt-suggest-cover.py.txt")
spec = importlib.util.spec_from_file_location("t225", os.path.join(H, "test_p225.py")); t225 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t225)
SRC = t225.SRC.replace('self.call(step, "tiktok.read_ad_video"', 'self.call(step("video_wait"), "tiktok.read_ad_video"').replace('self.call(step, "tiktok.upload_image_url"', 'self.call(step("cover"), "tiktok.upload_image_url"')
CAT = '''
class P:
    def __init__(self, kind, **k): self.kind = kind; self.k = k
class Op:
    def __init__(self, name, platform, method, path, **k): self.name = name; self.platform = platform; self.method = method; self.path = path; self.k = k
OPS = [
    Op("tiktok.read_ad_video", "tiktok", "GET", "/file/video/ad/info/", bearer=False, advertiser_param="advertiser_id", params={"video_ids": P("safelist", required=True)}),
    Op("tiktok.read_identity_videos", "tiktok", "GET", "/identity/video/get/", bearer=False, advertiser_param="advertiser_id",
       params={"identity_id": P("safe", required=True)}),
]
'''
def run(code, base, env=None): return subprocess.run([sys.executable, "-"], input=code, text=True, capture_output=True, env=dict(os.environ, **(env or {})))
class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); os.makedirs(self.d + "/broker/app"); open(self.d + "/broker/app/service.py", "w", encoding="utf-8").write(SRC); open(self.d + "/broker/app/catalog.py", "w", encoding="utf-8").write(CAT)
        r = run(open(P225, encoding="utf-8").read(), self.d, {"P225_BASE": self.d + "/"}); assert "APPLY225_OK" in r.stdout, r.stderr
    def p226(self): return run(open(P226, encoding="utf-8").read(), self.d, {"P226_BASE": self.d + "/"})
    def svc(self, cover="", suggest=None, upload_fail=False):
        spec = importlib.util.spec_from_file_location("s", self.d + "/broker/app/service.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); s = m.Svc(); s.ops = []
        async def call(stepobj, op, params, *a):
            s.ops.append(op)
            if op == "tiktok.read_ad_video": return ({"list": [{"video_cover_url": cover}]}, None)
            if op == "tiktok.suggest_cover": return (({"list": suggest} if suggest is not None else None), (None if suggest is not None else (200, {"ok": False})))
            if op == "tiktok.upload_image_url": return (None, (200, {"ok": False})) if upload_fail else ({"image_id": "IMG"}, None)
        s.call = call; return s
    def go(self, s):
        step = lambda label: label
        return asyncio.run(s._prepare_video(step, "c", "a", {"campaign_name": "n"}, {}, "i"))
    def test_01_apply_both_files_idempotent_backups(self):
        r = self.p226(); self.assertIn("APPLY226_OK", r.stdout, r.stderr)
        for f in ("service.py", "catalog.py"): self.assertTrue(os.path.exists(self.d + "/broker/app/%s.pre226" % f))
        self.assertIn("changed=0", self.p226().stdout)
    def test_02_catalog_has_new_read_op_and_stays_valid_python(self):
        self.p226(); ns = {}; exec(open(self.d + "/broker/app/catalog.py", encoding="utf-8").read(), ns)
        ops = {o.name: o for o in ns["OPS"]}; o = ops["tiktok.suggest_cover"]; self.assertEqual((o.method, o.path), ("GET", "/file/video/suggestcover/get/")); self.assertEqual(sorted(o.k["params"]), ["poster_number", "video_id"])
        self.assertFalse(o.k.get("write", False)); self.assertEqual(list(ops)[:3], ["tiktok.read_ad_video", "tiktok.suggest_cover", "tiktok.read_identity_videos"])
    def test_03_no_cover_uses_suggested_cover_and_succeeds(self):
        self.p226(); s = self.svc(cover="", suggest=[{"id": "1", "url": "https://x/c1.jpg"}]); r = self.go(s)
        self.assertIsNone(r[1]); self.assertEqual(r[0]["image_id"], "IMG"); self.assertIn("tiktok.suggest_cover", s.ops)
    def test_04_existing_cover_does_not_call_suggest(self):
        self.p226(); s = self.svc(cover="https://x/auto.jpg", suggest=[]); r = self.go(s); self.assertEqual(r[0]["image_id"], "IMG"); self.assertNotIn("tiktok.suggest_cover", s.ops)
    def test_05_still_no_cover_stops_with_correct_failure_shape_no_valueerror(self):
        self.p226(); s = self.svc(cover="", suggest=[]); r = self.go(s)
        self.assertIsNone(r[0]); status, env = r[1]; self.assertEqual(status, 200); self.assertFalse(env["ok"]); self.assertEqual(env["data"]["stage"], "cover")
        vid, fv = r; st, ev = fv     # كما يفعل main.py: فك قيمتين فقط
    def test_06_suggest_call_failure_also_stops_cleanly(self):
        self.p226(); s = self.svc(cover="", suggest=None); r = self.go(s); self.assertIsNone(r[0]); self.assertEqual(r[1][1]["data"]["stage"], "cover")
    def test_07_missing_anchor_in_either_file_writes_nothing(self):
        open(self.d + "/broker/app/catalog.py", "w", encoding="utf-8").write("x = 1\n"); before = open(self.d + "/broker/app/service.py", encoding="utf-8").read()
        r = self.p226(); self.assertIn("PATCH FAIL (nothing written)", r.stderr); self.assertEqual(open(self.d + "/broker/app/service.py", encoding="utf-8").read(), before)
if __name__ == "__main__": unittest.main(verbosity=1)
