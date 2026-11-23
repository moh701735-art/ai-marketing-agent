import json, os, shutil, subprocess, sys, tempfile, unittest, importlib.util, asyncio
H = os.path.dirname(os.path.abspath(__file__)); OPS = os.path.join(H, "..", "..", "ops")
def load(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
ta = load("ta", os.path.join(H, "test_p240a.py")); tb = load("tb", os.path.join(H, "test_p240b.py"))
OLD_A = os.path.join(H, "fixtures", "p240a_v1.py.txt"); PC = os.path.join(OPS, "p240c-pause-by-name-fix.py.txt")
rd = lambda p: open(p, encoding="utf-8").read()
def mk_old():
    d = tempfile.mkdtemp(); os.makedirs(d + "/broker/app"); os.makedirs(d + "/n8n")
    open(d + "/broker/app/service.py", "w", encoding="utf-8").write(ta.SERVICE); open(d + "/n8n/wf_ingress.py", "w", encoding="utf-8").write(tb.INGRESS)
    r = subprocess.run([sys.executable, OLD_A], env={**os.environ, "P240A_BASE": d + "/"}, capture_output=True, text=True); assert "APPLY240A_OK" in r.stdout, r.stdout + r.stderr
    assert "APPLY240B_OK" in tb.apply(d).stdout
    return d
def apply_c(d): return subprocess.run([sys.executable, PC], env={**os.environ, "P240C_BASE": d + "/"}, capture_output=True, text=True)

class T(unittest.TestCase):
    def test_old_state_fails_then_fixed(self):
        d = mk_old()
        def run():
            ns = {}; exec(compile(rd(d + "/broker/app/service.py"), "s.py", "exec"), ns)
            w = ta.World({"7700000000000000001": [["1", "زوز", "ENABLE"]]}); S = w.svc(ns["Svc"])
            # ركّب الدالة الحقيقية: _rc الحي يمرر لـcall (توقيع صارم) — نحاكي call الحي بدون override لـ_rc
            class L(ns["Svc"]):
                async def call(self, ctx, platform, op, acct, prm, idem, internal=False):
                    return await w.svc(ns["Svc"]).call(ctx, platform, op, acct, prm, idem)
            return asyncio.run(L()._pause_by_name("c", {"name": "زوز", "accounts": ["7700000000000000001"]}, "tgupd-123456789-987654321-pbn"))
        st, e = run(); self.assertEqual(len(e["data"]["paused"]), 0)   # الحالة القديمة: _rc بدون idem → TypeError → حساب فاشل
        self.assertIn("TypeError", json.dumps(e["data"]["accounts_failed"]))
        r = apply_c(d); self.assertIn("APPLY240C_OK", r.stdout, r.stdout + r.stderr)
        st, e = run(); self.assertEqual(len(e["data"]["paused"]), 1); self.assertEqual(e["data"]["accounts_failed"], {})

    def test_idempotent_backup(self):
        d = mk_old(); sv0 = rd(d + "/broker/app/service.py"); ing0 = rd(d + "/n8n/wf_ingress.py"); self.assertIn("APPLY240C_OK", apply_c(d).stdout)
        a, b = rd(d + "/broker/app/service.py"), rd(d + "/n8n/wf_ingress.py"); self.assertIn("already applied", apply_c(d).stdout); self.assertEqual((a, b), (rd(d + "/broker/app/service.py"), rd(d + "/n8n/wf_ingress.py")))
        self.assertEqual((rd(d + "/broker/app/service.py.pre240c"), rd(d + "/n8n/wf_ingress.py.pre240c")), (sv0, ing0)); self.assertEqual(a.count("p240c"), 1); self.assertEqual(b.count("p240c"), 1)

    def test_needs_prior_patches_and_anchor_failures(self):
        d = tempfile.mkdtemp(); os.makedirs(d + "/broker/app"); os.makedirs(d + "/n8n")
        open(d + "/broker/app/service.py", "w").write("x=1\n"); open(d + "/n8n/wf_ingress.py", "w").write("y=1\n"); r = apply_c(d); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr)
        d = mk_old(); s = rd(d + "/broker/app/service.py").replace('{"page": page, "page_size": 100})', '{"page": page}'); open(d + "/broker/app/service.py", "w", encoding="utf-8").write(s)
        r = apply_c(d); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertFalse(os.path.exists(d + "/broker/app/service.py.pre240c"))

    def test_grouped_failure_note(self):
        d = mk_old(); apply_c(d); b = tb.body(d, "Stat: choose")
        A = ["77000000000000%05d" % i for i in range(40)]
        j = tb.runjs(b, {"nodes": {"Stat: prep": {"ctx": "c", "chatId": "9", "op": "tiktok.pause_by_name", "askedName": "زوز", "params": {"name": "زوز"}}},
                         "input": {"ok": True, "data": {"mode": "not_found", "similar": [], "paused": [], "accounts_failed": {a: "TypeError: boom" for a in A}}}})[0]["json"]["text"]
        self.assertIn("ما كدرت أقرأ 40 حساب: TypeError: boom (×40)", j); self.assertEqual(j.count("TypeError"), 1)
        j = tb.runjs(b, {"nodes": {"Stat: prep": {"ctx": "c", "chatId": "9", "op": "tiktok.pause_by_name", "askedName": "زوز", "params": {"name": "زوز"}}},
                         "input": {"ok": True, "data": {"mode": "not_found", "similar": [], "paused": [], "accounts_failed": {A[0]: "auth_expired"}}}})[0]["json"]["text"]
        self.assertIn("ما كدرت أقرأ 1 حساب: auth_expired [", j)

if __name__ == "__main__": unittest.main(verbosity=1)
