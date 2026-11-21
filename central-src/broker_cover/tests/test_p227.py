import asyncio, importlib.util, os, subprocess, sys, tempfile, unittest
H = os.path.dirname(__file__)
P225 = os.path.join(H, "..", "..", "ops", "p225-tt-cover-unique.py.txt"); P226 = os.path.join(H, "..", "..", "ops", "p226-tt-suggest-cover.py.txt"); P227 = os.path.join(H, "..", "..", "ops", "p227-tt-cover-normalize.py.txt")
spec = importlib.util.spec_from_file_location("t226", os.path.join(H, "test_p226.py")); t226 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t226)
def run(code, env): return subprocess.run([sys.executable, "-"], input=code, text=True, capture_output=True, env=dict(os.environ, **env))
class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); os.makedirs(self.d + "/broker/app"); open(self.d + "/broker/app/service.py", "w", encoding="utf-8").write(t226.SRC); open(self.d + "/broker/app/catalog.py", "w", encoding="utf-8").write(t226.CAT)
        for p, k in ((P225, "P225_BASE"), (P226, "P226_BASE")):
            r = run(open(p, encoding="utf-8").read(), {k: self.d + "/"}); assert "APPLY22" in r.stdout, r.stderr
    def p227(self): return run(open(P227, encoding="utf-8").read(), {"P227_BASE": self.d + "/"})
    def svc(self, cover, suggest=None, fail_first_upload=False):
        spec = importlib.util.spec_from_file_location("s", self.d + "/broker/app/service.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); s = m.Svc(); s.log = []; s.up = 0
        async def call(stepobj, op, params, *a):
            s.log.append((op, params.get("image_url")))
            if op == "tiktok.read_ad_video": return ({"list": [{"video_cover_url": cover}]}, None)
            if op == "tiktok.suggest_cover": return (({"list": suggest} if suggest is not None else None), (None if suggest is not None else (200, {"ok": False})))
            if op == "tiktok.upload_image_url":
                s.up += 1
                if not params["image_url"].startswith("https://"): return (None, (200, {"ok": False}))
                if fail_first_upload and s.up == 1: return (None, (200, {"ok": False}))
                return ({"image_id": "IMG%d" % s.up}, None)
        s.call = call; return s
    def go(self, s): return asyncio.run(s._prepare_video(lambda l: l, "c", "a", {"campaign_name": "n"}, {}, "i"))
    def test_01_apply_idempotent_backup(self):
        r = self.p227(); self.assertIn("APPLY227_OK", r.stdout, r.stderr); self.assertTrue(os.path.exists(self.d + "/broker/app/service.py.pre227")); self.assertIn("changed=0", self.p227().stdout)
    def test_02_http_cover_is_upgraded_and_uploaded_without_suggest(self):
        self.p227(); s = self.svc("http://p16.example/c.jpg"); r = self.go(s); self.assertEqual(r[0]["image_id"], "IMG1"); self.assertIn(("tiktok.upload_image_url", "https://p16.example/c.jpg"), s.log); self.assertNotIn("tiktok.suggest_cover", [o for o, _ in s.log])
    def test_03_protocol_relative_cover(self):
        self.p227(); s = self.svc("//p16.example/c.jpg"); r = self.go(s); self.assertEqual(r[0]["image_id"], "IMG1"); self.assertIn(("tiktok.upload_image_url", "https://p16.example/c.jpg"), s.log)
    def test_04_garbage_cover_uses_suggested(self):
        self.p227(); s = self.svc("not-a-url", suggest=[{"url": "https://x/s.jpg"}]); r = self.go(s); self.assertEqual(r[0]["image_id"], "IMG1"); self.assertIn("tiktok.suggest_cover", [o for o, _ in s.log])
    def test_05_auto_cover_upload_fails_second_chance_suggested(self):
        self.p227(); s = self.svc("https://x/auto.jpg", suggest=[{"url": "http://x/s.jpg"}], fail_first_upload=True); r = self.go(s); self.assertIsNone(r[1]); self.assertEqual(r[0]["image_id"], "IMG2")
        self.assertIn(("tiktok.upload_image_url", "https://x/s.jpg"), s.log)
    def test_06_everything_fails_stops_with_valid_shape(self):
        self.p227(); s = self.svc("", suggest=[]); r = self.go(s); self.assertIsNone(r[0]); st, env = r[1]; self.assertEqual((st, env["data"]["stage"]), (200, "cover"))
    def test_07_good_https_cover_unchanged_single_upload(self):
        self.p227(); s = self.svc("https://x/ok.jpg"); r = self.go(s); self.assertEqual(r[0]["image_id"], "IMG1"); self.assertEqual(s.up, 1); self.assertNotIn("tiktok.suggest_cover", [o for o, _ in s.log])
    def test_08_missing_anchor_writes_nothing(self):
        open(self.d + "/broker/app/service.py", "w", encoding="utf-8").write("x = 1\n"); r = self.p227(); self.assertIn("PATCH FAIL (nothing written)", r.stderr); self.assertEqual(open(self.d + "/broker/app/service.py").read(), "x = 1\n")
if __name__ == "__main__": unittest.main(verbosity=1)
