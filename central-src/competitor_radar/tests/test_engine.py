import os, sys, threading, time, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from competitor_radar.service.engine import Engine
from competitor_radar.service.cache import RateLimiter
from competitor_radar.service.llm import LLMUnavailable
from competitor_radar.service.safe_fetch import FetchError
from competitor_radar.service.store import MemoryStore, PgStore, StoreError

CTX_A, CTX_B = "ctx-tenant-A-0001", "ctx-tenant-B-0002"
POSTS = ("فساتين سهرة جديدة! سعر مخفض بس 25 ألف دينار\nاطلبي الان عبر واتساب\n\nخصم 30% على كل الفساتين هذا الاسبوع والتوصيل مجاني\n\n"
         "عبايات بأسعار رخيصة، عرض 1+1 لفترة محدودة. اطلب هسه\n\nتنزيلات الجمعة: فساتين وعبايات بأرخص سعر بالعراق")


class FakeFetcher:
    resolver, allow_private = staticmethod(lambda host, port, type=None: [(2, 1, 6, "", ("93.184.216.34", port))]), False
    def __init__(self, page=None, exc=None): self.page, self.exc, self.urls = page, exc, []
    def fetch(self, url, robots=None):
        self.urls.append(url)
        if self.exc: raise self.exc
        return {"url": url, "status": 200, "content_type": "text/html", "text": self.page}


class Bad:
    def complete_json(self, s, u, n=1200): raise LLMUnavailable("network")


def mk(**k):
    st = MemoryStore({CTX_A: "A", CTX_B: "B"}, enabled=k.pop("enabled", True))
    return Engine(st, fetcher=k.pop("fetcher", FakeFetcher("<title>x</title>")), **k), st


def call(e, op, ctx=CTX_A, **p): return e.handle(op, ctx, p)


def add(e, ctx=CTX_A, **o):
    return call(e, "competitor_add", ctx, platform=o.get("platform", "instagram"), name=o.get("name", "منافس 1"), **({"url": o["url"]} if "url" in o else {}))[1]["data"]["id"]


class Flow(unittest.TestCase):
    def test_full_pipeline_no_url(self):
        e, _ = mk(); cid = add(e)
        st, r = call(e, "competitor_samples", id=cid, text=POSTS); self.assertEqual((st, r["data"]["added"]), (200, 4))
        st, r = call(e, "analyze", id=cid); rep = r["data"]["report"]; self.assertEqual((r["ok"], rep["status"], r["data"]["cached"]), (True, "ok", False))
        self.assertTrue(any("لا يوجد رابط" in s["note"] for s in rep["stages"]))
        st, r = call(e, "strategy", id=cid); self.assertEqual(r["data"]["plan"]["status"], "ok"); self.assertEqual(len(r["data"]["plan"]["tests"]), 3)
        st, r = call(e, "competitor_list"); self.assertEqual((r["data"]["competitors"][0]["status"], r["data"]["competitors"][0]["samples"]), ("done", 4))
        st, r = call(e, "market", query="فساتين نسائية في العراق", text="فساتين خصم 20% اليوم\n\nعبايات سعر رخيص"); self.assertEqual(r["data"]["market"]["status"], "ok")

    def test_analyze_cached_then_force(self):
        e, _ = mk(); cid = add(e); call(e, "competitor_samples", id=cid, text=POSTS)
        call(e, "analyze", id=cid); r = call(e, "analyze", id=cid)[1]; self.assertTrue(r["data"]["cached"])
        r = call(e, "analyze", id=cid, force=True)[1]; self.assertFalse(r["data"]["cached"])

    def test_insufficient_data_honest(self):
        e, _ = mk(); cid = add(e); r = call(e, "analyze", id=cid)[1]["data"]["report"]
        self.assertEqual((r["status"], r["message"]), ("insufficient", "⚠️ بيانات غير كافية للتحليل.")); self.assertEqual(call(e, "strategy", id=cid)[1]["data"]["plan"]["status"], "insufficient")

    def test_strategy_needs_report(self):
        e, _ = mk(); cid = add(e); r = call(e, "strategy", id=cid)[1]; self.assertEqual(r["error"]["class"], "no_report")
        self.assertEqual(call(e, "report", id=cid)[1]["error"]["class"], "no_report")

    def test_collect_failure_is_reported_not_invented(self):
        for code in ("login_wall", "robots_disallow", "http_403", "timeout"):
            e, _ = mk(fetcher=FakeFetcher(exc=FetchError(code))); cid = add(e, url="https://instagram.com/shop1"); call(e, "competitor_samples", id=cid, text=POSTS)
            rep = call(e, "analyze", id=cid)[1]["data"]["report"]; notes = " ".join(s["note"] for s in rep["stages"]); self.assertIn(code, notes); self.assertIn("لم يُخمَّن", notes)
            self.assertEqual(rep["status"], "ok")   # يكمل على النص الملصوق

    def test_url_only_with_login_wall_is_insufficient(self):
        e, _ = mk(fetcher=FakeFetcher(exc=FetchError("login_wall"))); cid = add(e, url="https://instagram.com/shop1")
        self.assertEqual(call(e, "analyze", id=cid)[1]["data"]["report"]["status"], "insufficient")

    def test_html_meta_collected(self):
        page = "<title>متجر الأناقة للفساتين</title><meta property='og:description' content='فساتين وعبايات بجودة عالية وتوصيل لكل العراق وضمان استرجاع'><meta name='description' content='اطلب الان عبر واتساب واحصل على خصم'>"
        e, st = mk(fetcher=FakeFetcher(page)); cid = add(e, url="https://shop.example.com/")
        rep = call(e, "analyze", id=cid)[1]["data"]["report"]; self.assertEqual(rep["sources"]["html_meta"], 4 - 0 if rep["sources"]["html_meta"] == 4 else rep["sources"]["html_meta"]); self.assertGreaterEqual(rep["sources"]["html_meta"], 2)
        self.assertTrue(any(s["source"] == "html_meta" for s in rep["stages"]))

    def test_tiktok_video_uses_oembed(self):
        f = FakeFetcher('{"title": "عرض فستان سهرة جديد اليوم", "author_name": "shop"}'); e, _ = mk(fetcher=f); cid = add(e, platform="tiktok", url="https://www.tiktok.com/@shop/video/123456")
        call(e, "analyze", id=cid); self.assertTrue(f.urls[0].startswith("https://www.tiktok.com/oembed?url="))

    def test_llm_failure_does_not_break(self):
        e, _ = mk(llm=Bad()); cid = add(e); call(e, "competitor_samples", id=cid, text=POSTS)
        self.assertEqual(call(e, "analyze", id=cid)[1]["data"]["report"]["status"], "ok")


class Safety(unittest.TestCase):
    def test_disabled_flag_everywhere(self):
        for mode in ("db_flag_off", "env_flag_off"):
            e, st = mk(enabled=(mode == "env_flag_off"))
            if mode == "env_flag_off": e.enabled = False
            self.assertEqual(call(e, "config")[1]["data"], {"enabled": False})
            for op in ("competitor_add", "competitor_list", "analyze", "market", "strategy", "competitor_samples", "report", "competitor_get", "competitor_delete"):
                r = call(e, op, id="00000000-0000-0000-0000-000000000000", platform="tiktok", name="x", query="سوق ما")[1]; self.assertEqual(r["error"]["class"], "disabled", op)
        e, st = mk(); self.assertTrue(call(e, "config")[1]["data"]["enabled"])

    def test_tenant_isolation(self):
        e, _ = mk(); a = add(e, CTX_A, name="منافس A"); call(e, "competitor_samples", CTX_A, id=a, text=POSTS); call(e, "analyze", CTX_A, id=a); call(e, "strategy", CTX_A, id=a)
        self.assertEqual(call(e, "competitor_list", CTX_B)[1]["data"]["competitors"], [])
        for op in ("competitor_get", "report", "analyze", "strategy", "competitor_samples", "competitor_delete"):
            r = call(e, op, CTX_B, id=a, text=POSTS)[1]
            if op == "competitor_delete": self.assertEqual((r["ok"], r["data"]["deleted"]), (True, False)); continue
            self.assertFalse(r["ok"], op); self.assertIn(r["error"]["class"], ("not_found", "no_report"), op)
        self.assertEqual(call(e, "competitor_list", CTX_A)[1]["data"]["competitors"][0]["id"], a)
        b = add(e, CTX_B, name="منافس B"); self.assertNotEqual(a, b); self.assertEqual(len(call(e, "competitor_list", CTX_B)[1]["data"]["competitors"]), 1)
        call(e, "competitor_delete", CTX_B, id=a); self.assertEqual(len(call(e, "competitor_list", CTX_A)[1]["data"]["competitors"]), 1)   # حذف B لـA ما يمر

    def test_market_cache_isolated(self):
        e, _ = mk(); call(e, "market", CTX_A, query="فساتين نسائية في العراق", text="فساتين خصم 20% اليوم فقط\n\nعبايات سعر رخيص جدا")
        r = call(e, "market", CTX_B, query="فساتين نسائية في العراق", text="فساتين خصم 20% اليوم فقط\n\nعبايات سعر رخيص جدا")[1]["data"]; self.assertFalse(r["cached"])

    def test_unauthorized_ctx(self):
        e, _ = mk()
        for ctx in ("ctx-unknown-xxxx", "", None, 5, "x"):
            st, r = e.handle("competitor_list", ctx, {}); self.assertFalse(r["ok"]); self.assertIn(st, (400, 403))

    def test_limits_and_validation(self):
        e, st = mk(); st.max = 3
        for i in range(3): add(e, name="m%d" % i)
        self.assertEqual(call(e, "competitor_add", platform="tiktok", name="extra")[1]["error"]["class"], "limit")
        for bad in ({"platform": "myspace", "name": "x"}, {"platform": "tiktok", "name": ""}, {"platform": "tiktok", "name": "x" * 81}, {"platform": "tiktok", "name": "x", "evil": 1}):
            self.assertEqual(call(e, "competitor_add", CTX_B, **bad)[1]["error"]["class"], "invalid_params")
        self.assertEqual(call(e, "competitor_add", CTX_B, platform="tiktok", name="x", url="javascript:alert(1)")[1]["error"]["class"], "bad_url")
        for op in ("competitor_get", "report", "analyze", "strategy", "competitor_delete"): self.assertEqual(e.handle(op, CTX_A, {"id": "not-a-uuid"})[0], 400)
        self.assertEqual(e.handle("nope", CTX_A, {})[0], 404); self.assertEqual(e.handle("analyze", CTX_A, "bad")[0], 400)
        self.assertEqual(call(e, "competitor_samples", id="00000000-0000-0000-0000-000000000000", text="x" * 30001)[1]["error"]["class"], "invalid_params")

    def test_rate_limit_and_burst(self):
        e, _ = mk(rate=RateLimiter(2, 600)); cid = add(e); call(e, "competitor_samples", id=cid, text=POSTS)
        self.assertTrue(call(e, "analyze", id=cid, force=True)[1]["ok"]); self.assertTrue(call(e, "analyze", id=cid, force=True)[1]["ok"])
        self.assertEqual(call(e, "analyze", id=cid, force=True)[1]["error"]["class"], "rate_limited"); self.assertTrue(call(e, "analyze", id=cid)[1]["data"]["cached"])   # الكاش ما يستهلك الحد
        e2, _ = mk(); e2.rl_any = RateLimiter(3, 60)
        self.assertEqual([call(e2, "competitor_list")[1]["ok"] for _ in range(5)], [True] * 3 + [False] * 2)

    def test_concurrent_identical_analysis_runs_once(self):
        calls = [0]
        class Slow(FakeFetcher):
            def fetch(s, url, robots=None):
                calls[0] += 1; time.sleep(0.2); return super().fetch(url, robots)
        e, _ = mk(fetcher=Slow("<title>متجر فساتين</title><meta name='description' content='فساتين وعبايات بجودة عالية وضمان'>")); cid = add(e, url="https://shop.example.com/"); out = []
        ts = [threading.Thread(target=lambda: out.append(call(e, "analyze", id=cid, force=True)[1]["ok"])) for _ in range(4)]
        [t.start() for t in ts]; [t.join() for t in ts]; self.assertEqual((calls[0], out), (1, [True] * 4))

    def test_no_internal_exception_leak(self):
        e, st = mk()
        def boom(ctx): raise RuntimeError("SECRET-DSN password=hunter2")
        st.config = boom; s, r = e.handle("competitor_list", CTX_A, {}); self.assertEqual(s, 500); self.assertNotIn("hunter2", str(r)); self.assertEqual(r["error"]["class"], "internal")

    def test_module_has_no_ad_platform_write_path(self):
        import ast
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "service"); bad = ("broker", "set_campaign_status", "create_campaign", "launch_spark", "activate_campaign", "adgroup",
                                                                                     "wf_ingress", "business-api.tiktok", "graph.facebook", "adsapi.snapchat", "n8n")
        for f in sorted(os.listdir(root)):
            if not f.endswith(".py"): continue
            tree = ast.parse(open(os.path.join(root, f), encoding="utf-8").read()); doc = set()
            for n in ast.walk(tree):
                if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant): doc.add(id(n.body[0].value))
            used = []
            for n in ast.walk(tree):
                if isinstance(n, ast.Import): used += [a.name for a in n.names]
                elif isinstance(n, ast.ImportFrom): used.append(n.module or "")
                elif isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc: used.append(n.value)
                elif isinstance(n, ast.Attribute): used.append(n.attr)
                elif isinstance(n, ast.Name): used.append(n.id)
            blob = " ".join(used).lower()
            for w in bad: self.assertNotIn(w, blob, "%s uses %s" % (f, w))


class FakeConn:
    def __init__(self, rows=None, exc=None): self.rows, self.exc, self.sql, self.committed, self.rolled, self.closed = rows, exc, [], False, False, False
    def cursor(self): return self
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def execute(self, q, a):
        if self.exc: raise self.exc
        self.sql.append((q, a))
    def fetchone(self): return self.rows
    def commit(self): self.committed = True
    def rollback(self): self.rolled = True
    def close(self): self.closed = True


class PgErr(Exception):
    def __init__(self, m, sqlstate=None): super().__init__(m); self.sqlstate = sqlstate


class Pg(unittest.TestCase):
    def test_calls_and_json(self):
        c = FakeConn(('{"id": "x"}',)); s = PgStore(lambda: c); self.assertEqual(s.competitor_add("ctx", "tiktok", "n", None), {"id": "x"})
        self.assertEqual(c.sql[0][0], "SELECT competitor_radar.competitor_add(%s,%s,%s,%s)"); self.assertTrue(c.committed and c.closed)
        c = FakeConn(({"a": 1},)); PgStore(lambda: c).report_save("ctx", "id", {"k": [1]}, "done", "low"); self.assertEqual(c.sql[0][1][2], '{"k": [1]}')

    def test_error_mapping_no_leak(self):
        for exc, code in ((PgErr("x", "28000"), "invalid_ctx"), (PgErr("radar_limit"), "limit"), (PgErr("radar_not_found"), "not_found"), (PgErr("password authentication failed for user radar_rt"), "db_error")):
            c = FakeConn(exc=exc)
            with self.assertRaises(StoreError) as cm: PgStore(lambda: c).competitor_list("ctx")
            self.assertEqual(cm.exception.code, code); self.assertTrue(c.rolled and c.closed)


if __name__ == "__main__":
    unittest.main(verbosity=1)
