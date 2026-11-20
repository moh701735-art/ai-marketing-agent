# يحاكي مقاطع service.py (المعاد بناؤها من شاشة السيرفر) ويطبّق رقعة p223 ثم يشغّل المنطق المعدّل.
import asyncio, os, re, subprocess, sys, tempfile, textwrap, unittest, importlib.util
HERE = os.path.dirname(__file__); PATCH = os.path.join(HERE, "..", "..", "ops", "p223-tt-authorized-identity.py.txt")
SERVICE = '''
class Svc:
    async def call(self, *a, **k): raise NotImplementedError

    async def _video_ident(self, step, p, v, video_id, idem, made):
        cover = str(v.get("video_cover_url") or v.get("poster_url") or "")
        image_id = ""
        made["cover"] = bool(image_id)
        name = (p.get("identity_name") or p["campaign_name"]).strip()[:40]
        if p["objective"] == "tiktok_dm":         # الإعلان لازم يطلع بهوية حساب تيك توك فعلي (TT_USER أو BC_AUTH_TT)
            dmi, fdm = await self._dm_identity(step, name)
            if fdm:
                return fdm
            return {"video_id": video_id, "image_id": image_id, **dmi}, None
        lst, fl = await self.call(step, "tiktok.read_identities", {"identity_type": "CUSTOMIZED_USER", "page_size": 100})
        return {"video_id": video_id, "image_id": image_id, "identity_id": "custom", "identity_type": "CUSTOMIZED_USER"}, None

    async def _dm_identity(self, step, name: str) -> tuple:
        """هوية حساب تيك توك للإعلانات (TT_USER/BC_AUTH_TT)."""
        cands = []
        for itype in ("TT_USER", "BC_AUTH_TT"):
            li, fi = await self.call(step, "tiktok.read_identities", {"identity_type": itype, "page_size": 100})
            if fi:
                continue
            for x in (li.get("identity_list") or li.get("list") or []):
                if isinstance(x, dict) and str(x.get("available_status") or "") == "AVAILABLE":
                    cands.append((itype, x))
        ok_ = [c for c in cands if c[1].get("can_manage_message")]
        want = (name or "").lower()
        nm_ = [c for c in ok_ if want and want == str(c[1].get("display_name") or "").lower()]
        pick = nm_[0] if nm_ else (ok_[0] if len(ok_) == 1 else None)
        if not pick:
            return 200, {"ok": False, "error": {"class": "bad_request", "message": "retryable: no_dm_identity ambiguous"}, "data": {"stage": "identity"}}
        return {"identity_id": str(pick[1]["identity_id"]), "identity_type": pick[0], "identity_bc": str(pick[1].get("identity_authorized_bc_id") or "")}, None
'''

def apply(base):
    return subprocess.run([sys.executable, "-"], input=open(PATCH, encoding="utf-8").read(), text=True, capture_output=True, env=dict(os.environ, P223_BASE=base + "/"))

class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); os.makedirs(self.d + "/broker/app"); open(self.d + "/broker/app/service.py", "w", encoding="utf-8").write(SERVICE)
    def load(self):
        spec = importlib.util.spec_from_file_location("svc", self.d + "/broker/app/service.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
    def mk(self, ids):
        m = self.load(); s = m.Svc()
        async def call(step, op, params, *a):
            if op == "tiktok.read_identities": return ({"identity_list": ids.get(params["identity_type"], [])}, None)
            raise AssertionError(op)
        s.call = call; return s
    def run_(self, s, obj, name="X"):
        made = {}; r = asyncio.run(s._video_ident("identity", {"objective": obj, "campaign_name": name}, {}, "V1", "idem", made)); return r, made
    def test_01_patch_applies_idempotent_and_backup(self):
        r = apply(self.d); self.assertIn("APPLY223_OK video", r.stdout, r.stderr); self.assertTrue(os.path.exists(self.d + "/broker/app/service.py.pre223"))
        r2 = apply(self.d); self.assertIn("changed=0", r2.stdout)
        src = open(self.d + "/broker/app/service.py", encoding="utf-8").read(); self.assertEqual(src.count("p223"), 1); self.assertIn("need_dm: bool = True", src); self.assertNotIn('if p["objective"] == "tiktok_dm":', src)
    def test_02_lead_ad_uses_authorized_identity_without_dm_capability(self):
        apply(self.d); s = self.mk({"TT_USER": [{"identity_id": "U1", "display_name": "benin", "available_status": "AVAILABLE", "can_manage_message": False}]})
        (vid, err), made = self.run_(s, "lead_gen"); self.assertIsNone(err); self.assertEqual(vid["identity_type"], "TT_USER"); self.assertEqual(vid["identity_id"], "U1"); self.assertEqual(vid["video_id"], "V1")
    def test_03_dm_objective_still_requires_dm_capability(self):
        apply(self.d); s = self.mk({"TT_USER": [{"identity_id": "U1", "display_name": "benin", "available_status": "AVAILABLE", "can_manage_message": False}]})
        r, made = self.run_(s, "tiktok_dm"); self.assertFalse(r["ok"]); self.assertEqual(r["data"]["stage"], "identity")   # فرع الفشل يرجّع fdm كما هو بكود السيرفر (نفس سلوك DM الحالي)
        s = self.mk({"TT_USER": [{"identity_id": "U1", "display_name": "benin", "available_status": "AVAILABLE", "can_manage_message": True}]})
        (vid, err), _ = self.run_(s, "tiktok_dm"); self.assertEqual(vid["identity_id"], "U1")
    def test_04_no_authorized_identity_stops_clearly_never_custom(self):
        apply(self.d); s = self.mk({}); r, made = self.run_(s, "lead_gen"); self.assertFalse(r["ok"]); self.assertEqual(r["data"]["stage"], "identity")
    def test_05_bc_auth_tt_carries_bc_id(self):
        apply(self.d); s = self.mk({"BC_AUTH_TT": [{"identity_id": "B1", "display_name": "x", "available_status": "AVAILABLE", "identity_authorized_bc_id": "999"}]})
        (vid, err), _ = self.run_(s, "traffic"); self.assertEqual((vid["identity_type"], vid["identity_bc"]), ("BC_AUTH_TT", "999"))
    def test_06_two_identities_pick_by_name_else_ambiguous(self):
        apply(self.d); ids = {"TT_USER": [{"identity_id": "A", "display_name": "benin", "available_status": "AVAILABLE"}, {"identity_id": "B", "display_name": "other", "available_status": "AVAILABLE"}]}
        (vid, err), _ = self.run_(self.mk(ids), "lead_gen", "benin"); self.assertEqual(vid["identity_id"], "A")
        r, _ = self.run_(self.mk(ids), "lead_gen", "zzz"); self.assertFalse(r["ok"])
    def test_07_anchor_failure_writes_nothing_and_prints_lines(self):
        open(self.d + "/broker/app/service.py", "w", encoding="utf-8").write("def _dm_identity(self, a, b, c):\n  pass\n")
        before = open(self.d + "/broker/app/service.py", encoding="utf-8").read(); r = apply(self.d); self.assertIn("PATCH FAIL (nothing written)", r.stderr); self.assertEqual(open(self.d + "/broker/app/service.py", encoding="utf-8").read(), before)
    def test_08_duplicate_filter_anchor_refuses(self):
        src = SERVICE + '\n        ok_ = [c for c in cands if c[1].get("can_manage_message")]\n'; open(self.d + "/broker/app/service.py", "w", encoding="utf-8").write(src)
        r = apply(self.d); self.assertIn("ok_ filter count=2", r.stderr)

if __name__ == "__main__": unittest.main(verbosity=1)
