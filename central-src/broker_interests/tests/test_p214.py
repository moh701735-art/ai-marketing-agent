"""يطبّق p214 على نسخة service.py اصطناعية (نفس شكل كتلة p157) ويختبر السلوك بـ call مزيّف. لا شبكة."""
import asyncio, importlib.util, os, shutil, subprocess, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATCH = os.path.join(ROOT, "ops", "p214-validate-interests.py.txt")
SYN = '''
class Svc:
    async def call(self, ctx, platform, op, ad_account, params, *a, **k):
        raise NotImplementedError

    async def _product_interests(self, ctx: str, ad_account: str, product_text: str, posters: list, want: int):
        return [], [], "", "", {}

    async def launch(self, p, ctx, ad_account):
        made = {}
        names, iids = [], []
        if p["use_interests"] and not p.get("interest_ids"):
            names, iids, seen_prod, why, idbg = await self._product_interests(ctx, ad_account, "x", [], 5)
        else:
            names, iids, seen_prod, why, idbg = [], [], "", "", {}
        if p.get("interest_ids"):
            iids = [str(x) for x in p["interest_ids"]][:500]
            names = [str(x) for x in (p.get("interest_names") or [])][:8]
            seen_prod, why, idbg = "", "", {}
        made["interests"] = names
        made["interests_n"] = len(iids)
        made["interests_note"] = why or ""
        made["ids"] = iids
        return 200, {"ok": True, "data": made}
'''
def kw(ids, bad=()): return (200, {"ok": True, "data": {"code": 0, "data": {"keywords": [{"keyword_id": i, "status": ("INACTIVE" if i in bad else "EFFECTIVE")} for i in ids]}}})
class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(); os.makedirs(cls.tmp + "/broker/app"); open(cls.tmp + "/broker/app/service.py", "w", encoding="utf-8").write(SYN)
        env = dict(os.environ, P214_BASE=cls.tmp + "/"); r = subprocess.run([sys.executable, PATCH], env=env, capture_output=True, text=True)
        assert "APPLY214_OK" in r.stdout, r.stdout + r.stderr
        spec = importlib.util.spec_from_file_location("svc", cls.tmp + "/broker/app/service.py"); cls.m = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.m)
    @classmethod
    def tearDownClass(cls): shutil.rmtree(cls.tmp, ignore_errors=True)
    def run_launch(self, ids, script):
        s = self.m.Svc(); calls = []
        async def call(ctx, platform, op, acct, params, *a, **k):
            calls.append((op, list(params["keyword_ids"]))); return script(params["keyword_ids"], len(calls))
        s.call = call
        return asyncio.run(s.launch({"use_interests": True, "interest_ids": ids, "interest_names": ["n"]}, "CTX", "ACC")), calls
    def test_idempotent_and_backup(self):
        r = subprocess.run([sys.executable, PATCH], env=dict(os.environ, P214_BASE=self.tmp + "/"), capture_output=True, text=True); self.assertIn("changed=0", r.stdout); self.assertTrue(os.path.exists(self.tmp + "/broker/app/service.py.pre214"))
    def test_all_valid_unchanged(self):
        (st, env), calls = self.run_launch(["111111", "222222"], lambda ids, n: kw(ids)); d = env["data"]
        self.assertTrue(env["ok"]); self.assertEqual(d["ids"], ["111111", "222222"]); self.assertEqual(d["interests_note"], ""); self.assertEqual(len(calls), 1)
    def test_inactive_dropped_and_reported(self):
        (st, env), _ = self.run_launch(["111111", "3412382896", "333333"], lambda ids, n: kw(ids, bad=("3412382896",))); d = env["data"]
        self.assertTrue(env["ok"]); self.assertEqual(d["ids"], ["111111", "333333"]); self.assertEqual(d["interests_n"], 2); self.assertIn("شلت 1 اهتمام", d["interests_note"]); self.assertEqual(d["interests_dropped"], 1)
    def test_unreturned_id_is_not_judged(self):
        (st, env), _ = self.run_launch(["111111", "222222"], lambda ids, n: kw(["111111"])); self.assertEqual(env["data"]["ids"], ["111111", "222222"])
    def test_all_invalid_halts_before_anything(self):
        (st, env), _ = self.run_launch(["111111", "222222"], lambda ids, n: kw(ids, bad=tuple(ids))); self.assertFalse(env["ok"]); self.assertEqual(env["data"]["stage"], "interests"); self.assertIn("ما أنشأت أي حملة", env["error"]["message"]); self.assertEqual(env["error"]["class"], "invalid_params")
    def test_batches_of_50(self):
        ids = [str(100000 + i) for i in range(120)]; (st, env), calls = self.run_launch(ids, lambda i, n: kw(i)); self.assertEqual([len(c[1]) for c in calls], [50, 50, 20]); self.assertEqual(len(env["data"]["ids"]), 120)
    def test_check_failure_never_blocks_launch(self):
        (st, env), _ = self.run_launch(["111111"], lambda ids, n: (500, {"ok": False, "error": {"class": "internal"}})); d = env["data"]
        self.assertTrue(env["ok"]); self.assertEqual(d["ids"], ["111111"]); self.assertIn("ما قدرت أتحقق", d["interests_note"])
    def test_exception_in_check_never_blocks_launch(self):
        def boom(ids, n): raise RuntimeError("x")
        (st, env), _ = self.run_launch(["111111"], boom); self.assertTrue(env["ok"]); self.assertEqual(env["data"]["ids"], ["111111"])
    def test_partial_failure_uses_what_was_read(self):
        ids = [str(100000 + i) for i in range(60)]
        (st, env), _ = self.run_launch(ids, lambda i, n: kw(i, bad=(ids[0],)) if n == 1 else (500, {"ok": False})); self.assertEqual(len(env["data"]["ids"]), 59); self.assertNotIn(ids[0], env["data"]["ids"])
    def test_anchor_failure_writes_nothing(self):
        tmp = tempfile.mkdtemp(); os.makedirs(tmp + "/broker/app"); open(tmp + "/broker/app/service.py", "w").write("class X:\n    pass\n")
        r = subprocess.run([sys.executable, PATCH], env=dict(os.environ, P214_BASE=tmp + "/"), capture_output=True, text=True); self.assertIn("PATCH FAIL (nothing written)", r.stderr + r.stdout); self.assertEqual(open(tmp + "/broker/app/service.py").read(), "class X:\n    pass\n"); shutil.rmtree(tmp)
if __name__ == "__main__": unittest.main()
