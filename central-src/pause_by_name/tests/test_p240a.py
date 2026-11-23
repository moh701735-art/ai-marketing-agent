import asyncio, os, shutil, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); P = os.path.join(H, "..", "..", "ops", "p240a-pause-by-name.py.txt")
SERVICE = '''import asyncio, json
class Svc:
    async def call(self, ctx, platform, op_name, ad_account, params, idem, internal=False):
        if platform == "meta" and op_name in ("meta.resolve_post", "meta.x"):
            from . import metaflow
            return await metaflow.run(self, op_name, ctx, ad_account, params or {}, idem)
        return 200, {"ok": True, "data": {"plain": op_name}}

    async def _rc(self, *a, **k):
        return await self.call(*a, **k)

    async def _find_campaign(self, ctx, params):
        return 200, {"ok": True}
'''
rd = lambda p: open(p, encoding="utf-8").read()


def mk(service=SERVICE):
    d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "broker/app"))
    open(os.path.join(d, "broker/app/service.py"), "w", encoding="utf-8").write(service); return d


def apply(d): return subprocess.run([sys.executable, P], env={**os.environ, "P240A_BASE": d + "/"}, capture_output=True, text=True)


def load(d):
    ns = {}; exec(compile(rd(os.path.join(d, "broker/app/service.py")), "service.py", "exec"), ns); return ns["Svc"]


IDEM = "tgupd-1-2-pausebyname"


class World:
    def __init__(s, data, per_page=100, read_fail=(), write_fail=(), write_raise=(), stick=()):
        s.d = {a: [list(c) for c in lst] for a, lst in data.items()}; s.pp = per_page; s.rf = set(read_fail); s.wf = set(write_fail); s.wr = set(write_raise); s.stick = set(stick)
        s.writes = []; s.reads = []

    def svc(s, cls):
        w = s

        class S(cls):
            async def _rc(self, ctx, platform, op, acct, prm):
                w.reads.append((acct, dict(prm)))
                if acct in w.rf: return 200, {"ok": False, "error": {"class": "auth_expired", "message": "token dead"}}
                lst = w.d[acct]; pg = prm["page"]; n = max(1, -(-len(lst) // w.pp))
                return 200, {"ok": True, "data": {"data": {"list": [{"campaign_id": c[0], "campaign_name": c[1], "operation_status": c[2]} for c in lst[(pg - 1) * w.pp: pg * w.pp]], "page_info": {"total_page": n}}}}

            async def call(self, ctx, platform, op, acct, prm, key, internal=False):
                if op == "tiktok.read_campaigns": return await self._rc(ctx, platform, op, acct, prm)
                w.writes.append((acct, op, dict(prm), key)); cid = prm["campaign_ids"][0]
                if cid in w.wr: raise RuntimeError("boom")
                if cid in w.wf: return 200, {"ok": False, "error": {"class": "bad_request", "message": "no permission"}}
                if cid not in w.stick:
                    for c in w.d[acct]:
                        if c[0] == cid: c[2] = prm["operation_status"]
                return 200, {"ok": True, "data": {"data": {}}}
        return S()


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = mk(); r = apply(cls.dir); assert "APPLY240A_OK" in r.stdout, r.stdout + r.stderr; cls.cls = load(cls.dir)

    def run_op(self, w, name, accts, idem=IDEM):
        return asyncio.run(w.svc(self.cls)._pause_by_name("ctx", {"name": name, "accounts": accts}, idem))

    A, B = "7700000000000000001", "7700000000000000002"

    def test_exact_single(self):
        w = World({self.A: [["11", "زوز", "ENABLE"], ["12", "other", "ENABLE"]]})
        st, e = self.run_op(w, "زوز", [self.A]); d = e["data"]
        self.assertEqual((st, e["ok"], d["mode"], d["matched"]), (200, True, "exact", 1))
        self.assertEqual([p["campaign_id"] for p in d["paused"]], ["11"]); self.assertTrue(d["paused"][0]["verified"])
        self.assertEqual(len(w.writes), 1); self.assertEqual(w.writes[0][1:3], ("tiktok.set_campaign_status", {"campaign_ids": ["11"], "operation_status": "DISABLE"}))
        self.assertEqual([c[2] for c in w.d[self.A]], ["DISABLE", "ENABLE"])

    def test_multi_account_all_pause(self):
        w = World({self.A: [["11", "زوز", "ENABLE"]], self.B: [["21", "زوز", "ENABLE"], ["22", "زوز", "ENABLE"]]})
        _, e = self.run_op(w, "زوز", [self.A, self.B]); d = e["data"]
        self.assertEqual(d["matched"], 3); self.assertEqual(sorted(p["campaign_id"] for p in d["paused"]), ["11", "21", "22"])
        self.assertTrue(all(p["verified"] for p in d["paused"])); self.assertEqual(len({x[3] for x in w.writes}), 3)   # مفتاح لكل حملة
        self.assertTrue(all(16 <= len(x[3]) <= 128 for x in w.writes))

    def test_normalization(self):
        w = World({self.A: [["1", "  الحَمْلَة   ٢ ", "ENABLE"], ["2", "اسم أحمد", "ENABLE"]]})
        _, e = self.run_op(w, "الحمله 2", [self.A]); self.assertEqual(e["data"]["matched"], 1)
        _, e = self.run_op(w, "اسم احمد", [self.A]); self.assertEqual(e["data"]["matched"], 1)
        _, e = self.run_op(w, "ZOZ", [self.A]); self.assertEqual(e["data"]["mode"], "not_found")

    def test_case_and_punct(self):
        w = World({self.A: [["1", "Zoz-Test!", "ENABLE"]]})
        _, e = self.run_op(w, "zoz test", [self.A]); self.assertEqual(e["data"]["matched"], 1); self.assertEqual(len(e["data"]["paused"]), 1)

    def test_already_paused_not_written(self):
        w = World({self.A: [["1", "زوز", "DISABLE"]]})
        _, e = self.run_op(w, "زوز", [self.A]); d = e["data"]
        self.assertEqual((d["matched"], d["paused"], len(d["already_paused"])), (1, [], 1)); self.assertEqual(w.writes, [])

    def test_mixed_enabled_and_paused_same_name(self):
        w = World({self.A: [["1", "زوز", "DISABLE"], ["2", "زوز", "ENABLE"]]})
        _, e = self.run_op(w, "زوز", [self.A]); d = e["data"]
        self.assertEqual([p["campaign_id"] for p in d["paused"]], ["2"]); self.assertEqual([p["campaign_id"] for p in d["already_paused"]], ["1"])

    def test_delete_ignored(self):
        w = World({self.A: [["1", "زوز", "DELETE"]]})
        _, e = self.run_op(w, "زوز", [self.A]); self.assertEqual(e["data"]["mode"], "not_found"); self.assertEqual(w.writes, [])

    def test_contains_single_acts(self):
        w = World({self.A: [["1", "زوز مبيعات رمضان", "ENABLE"], ["2", "ثاني", "ENABLE"]]})
        _, e = self.run_op(w, "زوز", [self.A]); d = e["data"]
        self.assertEqual((d["mode"], [p["campaign_id"] for p in d["paused"]]), ("contains", ["1"]))

    def test_contains_ambiguous_asks(self):
        w = World({self.A: [["1", "زوز مبيعات", "ENABLE"], ["2", "حملة زوز 2", "ENABLE"], ["3", "زوز قديمة", "DISABLE"]]})
        _, e = self.run_op(w, "زوز", [self.A]); d = e["data"]
        self.assertEqual((d["mode"], d["matched"], d["paused"]), ("ambiguous", 0, [])); self.assertEqual(len(d["ambiguous"]), 2); self.assertEqual(w.writes, [])

    def test_exact_wins_over_contains(self):
        w = World({self.A: [["1", "زوز", "ENABLE"], ["2", "زوز مبيعات", "ENABLE"]]})
        _, e = self.run_op(w, "زوز", [self.A]); d = e["data"]
        self.assertEqual((d["mode"], [p["campaign_id"] for p in d["paused"]]), ("exact", ["1"])); self.assertEqual(w.d[self.A][1][2], "ENABLE")

    def test_not_found_similar(self):
        w = World({self.A: [["1", "زوز مبيعات", "DISABLE"], ["2", "قهوه", "ENABLE"]]})
        _, e = self.run_op(w, "زوز مبيعات رمضان", [self.A]); d = e["data"]
        self.assertEqual(d["mode"], "not_found"); self.assertIn("زوز مبيعات", d["similar"]); self.assertNotIn("قهوه", d["similar"]); self.assertEqual(w.writes, [])

    def test_account_read_failure_reported_others_work(self):
        w = World({self.A: [["1", "زوز", "ENABLE"]], self.B: [["2", "زوز", "ENABLE"]]}, read_fail=[self.B])
        _, e = self.run_op(w, "زوز", [self.A, self.B]); d = e["data"]
        self.assertEqual([p["campaign_id"] for p in d["paused"]], ["1"]); self.assertIn(self.B, d["accounts_failed"]); self.assertIn("auth_expired", d["accounts_failed"][self.B])

    def test_all_accounts_unreadable_not_found_with_failures(self):
        w = World({self.A: []}, read_fail=[self.A])
        _, e = self.run_op(w, "زوز", [self.A]); d = e["data"]
        self.assertEqual(d["mode"], "not_found"); self.assertIn(self.A, d["accounts_failed"])

    def test_write_failure_reported_not_paused(self):
        w = World({self.A: [["1", "زوز", "ENABLE"], ["2", "زوز", "ENABLE"]]}, write_fail=["2"])
        _, e = self.run_op(w, "زوز", [self.A]); d = e["data"]
        self.assertEqual([p["campaign_id"] for p in d["paused"]], ["1"]); self.assertEqual([p["campaign_id"] for p in d["failed"]], ["2"]); self.assertIn("no permission", d["failed"][0]["why"])

    def test_write_exception_reported(self):
        w = World({self.A: [["1", "زوز", "ENABLE"]]}, write_raise=["1"])
        _, e = self.run_op(w, "زوز", [self.A]); d = e["data"]
        self.assertEqual((d["paused"], len(d["failed"])), ([], 1)); self.assertIn("RuntimeError", d["failed"][0]["why"])

    def test_verification_mismatch_flagged(self):
        w = World({self.A: [["1", "زوز", "ENABLE"]]}, stick=["1"])
        _, e = self.run_op(w, "زوز", [self.A]); d = e["data"]
        self.assertEqual(len(d["paused"]), 1); self.assertFalse(d["paused"][0]["verified"])

    def test_pagination(self):
        data = {self.A: [["%d" % i, "n%d" % i, "ENABLE"] for i in range(1, 250)] + [["999", "زوز", "ENABLE"]]}
        w = World(data, per_page=100); _, e = self.run_op(w, "زوز", [self.A]); d = e["data"]
        self.assertEqual([p["campaign_id"] for p in d["paused"]], ["999"]); self.assertGreaterEqual(len([r for r in w.reads if r[0] == self.A]), 3)

    def test_validation(self):
        w = World({self.A: []}); S = w.svc(self.cls)
        for prm in ({"name": "", "accounts": [self.A]}, {"name": "x" * 81, "accounts": [self.A]}, {"name": "x", "accounts": []}, {"name": "x", "accounts": ["abc"]},
                    {"name": "x", "accounts": [self.A], "extra": 1}, {"name": 5, "accounts": [self.A]}, {"name": "x", "accounts": [self.A] * 41}, {"name": "!!!", "accounts": [self.A]}):
            st, e = asyncio.run(S._pause_by_name("ctx", prm, IDEM)); self.assertEqual((st, e["ok"], e["error"]["class"]), (400, False, "invalid_params"), prm)
        st, e = asyncio.run(S._pause_by_name("ctx", {"name": "x", "accounts": [self.A]}, "short")); self.assertEqual(st, 400)
        self.assertEqual((w.reads, w.writes), ([], []))

    def test_only_disable_ever(self):
        w = World({self.A: [["1", "زوز", "ENABLE"], ["2", "زوز", "DISABLE"]]}); self.run_op(w, "زوز", [self.A])
        self.assertTrue(all(x[1] == "tiktok.set_campaign_status" and x[2]["operation_status"] == "DISABLE" for x in w.writes))
        src = open(os.path.join(self.dir, "broker/app/service.py"), encoding="utf-8").read(); body = src[src.index("async def _pause_by_name"): src.index("async def _find_campaign")]
        self.assertNotIn('"ENABLE"}', body); self.assertEqual(body.count('operation_status": "DISABLE"'), 1)

    def test_dispatch_and_existing_untouched(self):
        S = self.cls
        async def marker(self, ctx, params, idem): return 200, {"pbn": (ctx, params, idem)}
        class S2(S): pass
        S2._pause_by_name = marker
        st, e = asyncio.run(S2().call("c", "tiktok", "tiktok.pause_by_name", None, {"name": "x"}, "k" * 20)); self.assertEqual(e, {"pbn": ("c", {"name": "x"}, "k" * 20)})
        st, e = asyncio.run(S2().call("c", "tiktok", "tiktok.other", None, {}, "k" * 20)); self.assertEqual(e["data"]["plain"], "tiktok.other")
        src = open(os.path.join(self.dir, "broker/app/service.py"), encoding="utf-8").read()
        self.assertIn("async def _find_campaign(self, ctx, params):", src); self.assertEqual(src.count("p240a"), 2)

    def test_idempotent_and_backup(self):
        d = mk(); r = apply(d); self.assertIn("APPLY240A_OK", r.stdout); a = rd(d + "/broker/app/service.py")
        r2 = apply(d); self.assertIn("already applied", r2.stdout); self.assertEqual(a, rd(d + "/broker/app/service.py"))
        self.assertEqual(rd(d + "/broker/app/service.py.pre240a"), SERVICE)

    def test_anchor_failures_write_nothing(self):
        for bad in (SERVICE.replace("async def _find_campaign(", "async def _other("), SERVICE.replace('"meta.resolve_post", ', ""), SERVICE + SERVICE.split("class Svc:")[1].replace("call", "call2")):
            d = mk(bad); r = apply(d); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr, r.stdout + r.stderr); self.assertEqual(rd(d + "/broker/app/service.py"), bad)
            self.assertFalse(os.path.exists(d + "/broker/app/service.py.pre240a"))

    def test_other_dispatch_var_names(self):
        s = SERVICE.replace("platform", "plat").replace("op_name", "opn").replace("params", "prm").replace("idem", "key").replace("ctx", "cx")
        d = mk(s); r = apply(d); self.assertIn("APPLY240A_OK", r.stdout, r.stdout + r.stderr); src = rd(d + "/broker/app/service.py")
        self.assertIn('if plat == "tiktok" and opn == "tiktok.pause_by_name":', src); self.assertIn("return await self._pause_by_name(cx, prm or {}, key)", src)


if __name__ == "__main__": unittest.main(verbosity=1)
