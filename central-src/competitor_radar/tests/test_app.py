import http.client, json, os, sys, threading, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from competitor_radar.service import app as APP
from competitor_radar.service.engine import Engine
from competitor_radar.service.store import MemoryStore

KEY = "k" * 40
CTX = "ctx-tenant-A-0001"


class Srv(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = [1_000_000.0]
        cls.auth = APP.Auth(KEY, clock=lambda: cls.t[0])
        cls.eng = Engine(MemoryStore({CTX: "A"}))
        cls.srv = APP.ThreadingHTTPServer(("127.0.0.1", 0), APP.make_handler(cls.eng, cls.auth)); cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls): cls.srv.shutdown()

    def req(self, path, body, ts=None, sig=None, method="POST", raw=None):
        raw = raw if raw is not None else json.dumps(body).encode()
        if ts is None: self.t[0] += 1   # توقيع جديد لكل طلب (منع الإعادة يرفض نفس التوقيع)
        ts = str(int(self.t[0])) if ts is None else str(ts)
        h ={"content-type": "application/json", "x-radar-ts": ts, "x-radar-sig": sig if sig is not None else self.auth.sign(ts, path, raw)}
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5); c.request(method, path, body=raw if method == "POST" else None, headers=h)
        r = c.getresponse(); b = r.read(); c.close()
        return r.status, json.loads(b.decode()) if b else {}

    def test_health_open_and_minimal(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5); c.request("GET", "/healthz"); r = c.getresponse(); self.assertEqual((r.status, json.loads(r.read())), (200, {"ok": True}))
        c.request("GET", "/v1/config"); r = c.getresponse(); r.read(); self.assertEqual(r.status, 404)

    def test_signed_call_works_and_ctx_is_popped(self):
        st, r = self.req("/v1/config", {"ctx": CTX}); self.assertEqual((st, r["ok"], r["data"]["enabled"]), (200, True, True))
        st, r = self.req("/v1/competitor_add", {"ctx": CTX, "platform": "tiktok", "name": "x1"}); self.assertEqual((st, r["ok"]), (200, True))

    def test_bad_signature_and_missing(self):
        self.assertEqual(self.req("/v1/config", {"ctx": CTX}, sig="0" * 64)[0], 401)
        self.assertEqual(self.req("/v1/config", {"ctx": CTX}, sig="")[0], 401)
        body = json.dumps({"ctx": CTX}).encode(); other = APP.Auth("z" * 40, clock=lambda: self.t[0]).sign(str(int(self.t[0])), "/v1/config", body)
        self.assertEqual(self.req("/v1/config", None, raw=body, sig=other, ts=int(self.t[0]))[0], 401)

    def test_signature_binds_path_and_body(self):
        body = json.dumps({"ctx": CTX}).encode(); ts = str(int(self.t[0])); sig = self.auth.sign(ts, "/v1/config", body)
        self.assertEqual(self.req("/v1/competitor_list", None, raw=body, sig=sig, ts=ts)[0], 401)
        self.assertEqual(self.req("/v1/config", None, raw=json.dumps({"ctx": CTX, "x": 1}).encode(), sig=sig, ts=ts)[0], 401)

    def test_replay_and_skew(self):
        body = json.dumps({"ctx": CTX}).encode(); ts = str(int(self.t[0])); sig = self.auth.sign(ts, "/v1/config", body)
        self.assertEqual(self.req("/v1/config", None, raw=body, sig=sig, ts=ts)[0], 200); self.assertEqual(self.req("/v1/config", None, raw=body, sig=sig, ts=ts)[0], 401)
        old = int(self.t[0]) - 500; self.assertEqual(self.req("/v1/config", {"ctx": CTX}, ts=old)[0], 401)
        self.assertEqual(self.req("/v1/config", {"ctx": CTX}, ts="abc", sig="x")[0], 401)

    def test_size_unknown_and_malformed(self):
        self.assertEqual(self.req("/v1/config", None, raw=b"x" * 70000)[0], 413)
        self.assertEqual(self.req("/v1/nope", {"ctx": CTX})[0], 404); self.assertEqual(self.req("/v2/config", {"ctx": CTX})[0], 404)
        self.assertEqual(self.req("/v1/config", None, raw=b"{not json")[0], 400); self.assertEqual(self.req("/v1/config", None, raw=b"[1,2]")[0], 400)

    def test_invalid_ctx_forbidden_and_no_leak(self):
        st, r = self.req("/v1/competitor_list", {"ctx": "ctx-unknown-xxxxxx"}); self.assertEqual(st, 403); self.assertNotIn("tenant", json.dumps(r).lower().replace("tenant_", ""))
        st, r = self.req("/v1/competitor_list", {"ctx": 5}); self.assertEqual(st, 400)

    def test_key_length_enforced(self):
        os.environ["RADAR_HMAC_KEY"] = "short"
        with self.assertRaises(SystemExit): APP.main()
        os.environ.pop("RADAR_HMAC_KEY")


if __name__ == "__main__":
    unittest.main(verbosity=1)
