import asyncio, importlib.util, os, subprocess, sys, tempfile, unittest
PATCH = os.path.join(os.path.dirname(__file__), "..", "..", "ops", "p225-tt-cover-unique.py.txt")
SRC = '''
class Svc:
    async def sleep(self, t): pass
    async def _prepare_video(self, step, ctx, ad_account, p, made, idem):
        video_id = "V1"
        made["video_id"] = video_id
        cover = ""
        for _ in range(8):
            await self.sleep(2.0 if _ == 0 else 3.0)
            info, fi = await self.call(step, "tiktok.read_ad_video", {"video_ids": [video_id]})
            if fi:
                return fi
            v = next((x for x in (info.get("list") or []) if isinstance(x, dict)), {})
            cover = str(v.get("video_cover_url") or v.get("poster_url") or "")
            if cover:
                break
        image_id = ""
        if cover.startswith("https://"):
            im, fim = await self.call(step, "tiktok.upload_image_url", {"image_url": cover, "file_name": "cover.jpg"}, f"{idem}-ci")
            if not fim:
                ims = im if isinstance(im, list) else [im]
                image_id = str(next((x.get("image_id") for x in ims if isinstance(x, dict) and x.get("image_id")), "") or "")
        made["cover"] = bool(image_id)
        name = "n"
        return {"video_id": video_id, "image_id": image_id, "identity_id": "I"}, None
'''
def apply(d): return subprocess.run([sys.executable, "-"], input=open(PATCH, encoding="utf-8").read(), text=True, capture_output=True, env=dict(os.environ, P225_BASE=d + "/"))
class T(unittest.TestCase):
    def setUp(self): self.d = tempfile.mkdtemp(); os.makedirs(self.d + "/broker/app"); open(self.d + "/broker/app/service.py", "w", encoding="utf-8").write(SRC)
    def mk(self, cover="https://x/c.jpg", taken=("cover.jpg",), upload_fail=False):
        spec = importlib.util.spec_from_file_location("s", self.d + "/broker/app/service.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); s = m.Svc(); s.names = []; s.taken = set(taken)
        async def call(step, op, params, *a):
            if op == "tiktok.read_ad_video": return ({"list": [{"video_cover_url": cover}]}, None)
            if op == "tiktok.upload_image_url":
                s.names.append(params["file_name"])
                if upload_fail or params["file_name"] in s.taken: return (None, (200, {"ok": False, "error": {"message": "Duplicated material name"}}))
                s.taken.add(params["file_name"]); return ({"image_id": "IMG" + str(len(s.names))}, None)
        s.call = call; return s
    def run_(self, s, idem="i"): return asyncio.run(s._prepare_video("v", "c", "a", {"campaign_name": "n"}, {}, idem))
    def test_01_apply_idempotent_backup(self):
        r = apply(self.d); self.assertIn("APPLY225_OK unique", r.stdout, r.stderr); self.assertTrue(os.path.exists(self.d + "/broker/app/service.py.pre225")); self.assertIn("changed=0", apply(self.d).stdout)
    def test_02_before_patch_duplicate_name_fails_after_patch_succeeds(self):
        s = self.mk(); r = self.run_(s)       # الكود القديم: cover.jpg مكرر ⇒ بدون صورة
        self.assertEqual(r[0]["image_id"], "")
        apply(self.d); s = self.mk(); r = self.run_(s); self.assertEqual(r[1], None); self.assertEqual(r[0]["image_id"], "IMG1"); self.assertRegex(s.names[0], r"^cover-[0-9a-f]{8}\.jpg$")
    def test_03_names_unique_each_call(self):
        apply(self.d); s = self.mk(); [self.run_(s) for _ in range(4)]; self.assertEqual(len(set(s.names)), 4)
    def test_04_no_cover_url_stops_with_stage_cover_before_campaign(self):
        apply(self.d); s = self.mk(cover=""); r = self.run_(s)
        self.assertEqual(r[0], 200); self.assertFalse(r[1]["ok"]); self.assertEqual(r[1]["data"]["stage"], "cover"); self.assertIn("video_id", r[1]["data"])
    def test_05_upload_failure_stops_too(self):
        apply(self.d); s = self.mk(upload_fail=True); r = self.run_(s); self.assertFalse(r[1]["ok"]); self.assertEqual(r[1]["data"]["stage"], "cover")
    def test_06_anchor_failure_writes_nothing(self):
        open(self.d + "/broker/app/service.py", "w", encoding="utf-8").write("x = 1\n"); r = apply(self.d); self.assertIn("PATCH FAIL (nothing written)", r.stderr); self.assertEqual(open(self.d + "/broker/app/service.py").read(), "x = 1\n")
if __name__ == "__main__": unittest.main(verbosity=1)
