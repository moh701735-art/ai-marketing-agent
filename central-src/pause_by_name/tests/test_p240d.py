import asyncio, importlib.util, os, subprocess, sys, tempfile, unittest
from unittest import mock
H = os.path.dirname(os.path.abspath(__file__)); PD = os.path.join(H, "..", "..", "ops", "p240d-pause-by-name-ratelimit.py.txt")
def load(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
ta = load("ta", os.path.join(H, "test_p240a.py")); rd = ta.rd
RL = "rate_limited App 7688 reaches the QPS limit 10, current QPS is 11"
def mk():
    d = ta.mk(); assert "APPLY240A_OK" in ta.apply(d).stdout; return d
def apply_d(d): return subprocess.run([sys.executable, PD], env={**os.environ, "P240D_BASE": d + "/"}, capture_output=True, text=True)
A, B, C = "7700000000000000001", "7700000000000000002", "7700000000000000003"

class Flaky(ta.World):
    """حدّ QPS: أول n قراءة لكل حساب في fail_first ترفض"""
    def __init__(s, data, fail_first, **k): super().__init__(data, **k); s.ff = dict(fail_first); s.cnt = {}
    def svc(s, cls):
        S = super().svc(cls); orig = S._rc; w = s
        async def _rc(ctx, platform, op, acct, prm, idem):
            w.cnt[acct] = w.cnt.get(acct, 0) + 1
            if w.cnt[acct] <= w.ff.get(acct, 0): return 200, {"ok": False, "error": {"class": "rate_limited", "message": RL}}
            return await orig(ctx, platform, op, acct, prm, idem)
        S._rc = _rc; return S

class T(unittest.TestCase):
    def go(self, w, cls, name="زوز", accts=(A, B, C)):
        with mock.patch("asyncio.sleep", new=lambda s: asyncio.sleep(0)) if False else mock.patch.object(asyncio, "sleep", mock.AsyncMock()):
            return asyncio.run(w.svc(cls)._pause_by_name("c", {"name": name, "accounts": list(accts)}, "tgupd-123456789-987654321-pbn"))
    def cls(self, d):
        ns = {}; exec(compile(rd(d + "/broker/app/service.py"), "s.py", "exec"), ns); return ns["Svc"]
    def data(self): return {A: [["1", "x", "ENABLE"]], B: [["2", "زوز", "ENABLE"]], C: [["3", "y", "ENABLE"]]}

    def test_before_patch_rate_limited_account_is_lost(self):
        d = mk(); _, e = self.go(Flaky(self.data(), {B: 1}), self.cls(d)); self.assertEqual(e["data"]["paused"], []); self.assertIn(B, e["data"]["accounts_failed"])

    def test_after_patch_retry_finds_and_pauses(self):
        d = mk(); self.assertIn("APPLY240D_OK", apply_d(d).stdout); w = Flaky(self.data(), {B: 2, C: 1}); _, e = self.go(w, self.cls(d)); dd = e["data"]
        self.assertEqual([p["campaign_id"] for p in dd["paused"]], ["2"]); self.assertEqual(dd["accounts_failed"], {}); self.assertTrue(dd["paused"][0]["verified"])

    def test_persistent_rate_limit_still_reported_honestly(self):
        d = mk(); apply_d(d); w = Flaky(self.data(), {B: 99}); _, e = self.go(w, self.cls(d)); dd = e["data"]
        self.assertEqual(dd["paused"], []); self.assertIn(B, dd["accounts_failed"]); self.assertEqual(w.cnt[B], 4)   # 1 + 3 جولات فقط
        self.assertEqual(dd["mode"], "not_found")

    def test_non_rate_errors_not_retried(self):
        d = mk(); apply_d(d); w = ta.World(self.data(), read_fail=[B]); cnt = {}
        _, e = self.go(w, self.cls(d)); self.assertIn(B, e["data"]["accounts_failed"]); self.assertEqual(len([r for r in w.reads if r[0] == B]), 1)

    def test_idempotent_backup_and_anchors(self):
        d = mk(); sv0 = rd(d + "/broker/app/service.py"); apply_d(d); a = rd(d + "/broker/app/service.py"); self.assertIn("already applied", apply_d(d).stdout)
        self.assertEqual(rd(d + "/broker/app/service.py.pre240d"), sv0); self.assertEqual(a.count("p240d"), 2); self.assertIn("Semaphore(4)", a)
        d2 = mk(); s = rd(d2 + "/broker/app/service.py").replace("Semaphore(8)", "Semaphore(9)"); open(d2 + "/broker/app/service.py", "w", encoding="utf-8").write(s)
        r = apply_d(d2); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertFalse(os.path.exists(d2 + "/broker/app/service.py.pre240d"))

if __name__ == "__main__": unittest.main(verbosity=1)
