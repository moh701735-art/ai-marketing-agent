import importlib.util, os, subprocess, sys, tempfile, unittest, asyncio
PATCH = os.path.join(os.path.dirname(__file__), "..", "..", "ops", "p224-tt-unique-video-name.py.txt")
SRC = '''
class Svc:
    async def _prepare_video(self, step, ctx: str, ad_account: str, p: dict, made: dict, idem: str):
        """تجهيز الفيديو"""
        fname = (p["campaign_name"][:100] + ".mp4")
        if p.get("video_url"):
            return ("url", fname)
        else:
            return ("bytes", fname)
'''
def apply(d): return subprocess.run([sys.executable, "-"], input=open(PATCH, encoding="utf-8").read(), text=True, capture_output=True, env=dict(os.environ, P224_BASE=d + "/"))
class T(unittest.TestCase):
    def setUp(self): self.d = tempfile.mkdtemp(); os.makedirs(self.d + "/broker/app"); open(self.d + "/broker/app/service.py", "w", encoding="utf-8").write(SRC)
    def load(self):
        spec = importlib.util.spec_from_file_location("s", self.d + "/broker/app/service.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
    def names(self, p, n=5):
        s = self.load().Svc(); return [asyncio.run(s._prepare_video("v", "c", "a", p, {}, "idem-1"))[1] for _ in range(n)]
    def test_01_apply_idempotent_backup(self):
        r = apply(self.d); self.assertIn("APPLY224_OK TikTok", r.stdout, r.stderr); self.assertTrue(os.path.exists(self.d + "/broker/app/service.py.pre224")); self.assertIn("changed=0", apply(self.d).stdout)
    def test_02_names_are_unique_per_upload_even_with_same_idem(self):
        apply(self.d); ns = self.names({"campaign_name": "فستان هودي", "tg_file_id": "x"}); self.assertEqual(len(set(ns)), len(ns), ns)
    def test_03_name_keeps_campaign_prefix_mp4_and_limit(self):
        apply(self.d); n = self.names({"campaign_name": "فستان هودي"}, 1)[0]; self.assertTrue(n.startswith("فستان هودي-") and n.endswith(".mp4"), n)
        long = self.names({"campaign_name": "x" * 300}, 1)[0]; self.assertLessEqual(len(long), 100)
    def test_04_both_upload_paths_get_the_unique_name(self):
        apply(self.d); s = self.load().Svc(); a = asyncio.run(s._prepare_video("v", "c", "a", {"campaign_name": "n", "video_url": "https://x/v.mp4"}, {}, "i")); b = asyncio.run(s._prepare_video("v", "c", "a", {"campaign_name": "n"}, {}, "i"))
        self.assertEqual(a[0], "url"); self.assertEqual(b[0], "bytes"); self.assertRegex(a[1], r"^n-[0-9a-f]{6}\.mp4$"); self.assertRegex(b[1], r"^n-[0-9a-f]{6}\.mp4$")
    def test_05_missing_anchor_writes_nothing(self):
        open(self.d + "/broker/app/service.py", "w", encoding="utf-8").write("x = 1\n"); r = apply(self.d); self.assertIn("PATCH FAIL (nothing written)", r.stderr); self.assertEqual(open(self.d + "/broker/app/service.py").read(), "x = 1\n")
if __name__ == "__main__": unittest.main(verbosity=1)
