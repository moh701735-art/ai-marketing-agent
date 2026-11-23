# -*- coding: utf-8 -*-
"""واجهة HTTP الداخلية للرادار (شبكة docker فقط، ما تُنشر خارجياً). POST /v1/<op> بجسم JSON {ctx, ...}.
توقيع: X-Radar-Ts (epoch ثواني) + X-Radar-Sig = HMAC-SHA256(RADAR_HMAC_KEY, "<ts>.<path>.<body>")، انحراف ≤120 ث، ومنع إعادة الإرسال.
متغيرات البيئة (كلها جديدة): COMPETITOR_RADAR_ENABLED, RADAR_HMAC_KEY, RADAR_DB_DSN, RADAR_LLM_PROVIDER/API_KEY/MODEL, RADAR_PORT."""
import hashlib, hmac, json, os, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .engine import OPS, Engine

MAX_BODY = 65536
SKEW = 120


class Auth:
    def __init__(self, key: str, clock=time.time):
        self.key, self.clock, self.seen, self.lock = key.encode(), clock, {}, threading.Lock()

    def sign(self, ts: str, path: str, body: bytes) -> str:
        return hmac.new(self.key, ts.encode() + b"." + path.encode() + b"." + body, hashlib.sha256).hexdigest()

    def check(self, ts, sig, path, body) -> bool:
        try: t = int(ts)
        except (TypeError, ValueError): return False
        now = self.clock()
        if abs(now - t) > SKEW or not isinstance(sig, str): return False
        if not hmac.compare_digest(self.sign(str(t), path, body), sig): return False
        with self.lock:
            for k in [k for k, v in self.seen.items() if v < now]: self.seen.pop(k)
            if sig in self.seen: return False
            self.seen[sig] = now + SKEW * 2
        return True


def make_handler(engine: Engine, auth: Auth):
    class H(BaseHTTPRequestHandler):
        server_version = "radar"
        sys_version = ""

        def log_message(self, *a): pass   # لا نسجّل مضمون الطلبات

        def _send(self, st, obj):
            b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(st); self.send_header("content-type", "application/json; charset=utf-8"); self.send_header("content-length", str(len(b))); self.end_headers(); self.wfile.write(b)

        def do_GET(self):
            self._send(200, {"ok": True}) if self.path == "/healthz" else self._send(404, {"ok": False})

        def do_POST(self):
            try:
                n = int(self.headers.get("content-length") or 0)
                if n <= 0 or n > MAX_BODY: return self._send(413, {"ok": False, "error": {"class": "too_large"}})
                body = self.rfile.read(n)
                if not auth.check(self.headers.get("x-radar-ts"), self.headers.get("x-radar-sig"), self.path, body): return self._send(401, {"ok": False, "error": {"class": "unauthorized"}})
                if not self.path.startswith("/v1/") or self.path[4:] not in OPS: return self._send(404, {"ok": False, "error": {"class": "unknown_op"}})
                try: d = json.loads(body.decode("utf-8"))
                except ValueError: return self._send(400, {"ok": False, "error": {"class": "invalid_params"}})
                if not isinstance(d, dict): return self._send(400, {"ok": False, "error": {"class": "invalid_params"}})
                ctx = d.pop("ctx", None)
                st, out = engine.handle(self.path[4:], ctx, d)
                self._send(st, out)
            except Exception:
                self._send(500, {"ok": False, "error": {"class": "internal"}})
    return H


def build_engine(env=os.environ):
    from .llm import GeminiLLM, LLMUnavailable, NullLLM
    from .store import PgStore
    import psycopg   # فقط داخل الحاوية (requirements)
    dsn = env["RADAR_DB_DSN"]
    llm = NullLLM()
    if (env.get("RADAR_LLM_PROVIDER") or "").lower() == "gemini":
        try: llm = GeminiLLM(env.get("RADAR_LLM_API_KEY", ""), env.get("RADAR_LLM_MODEL") or "gemini-2.5-flash")
        except LLMUnavailable: llm = NullLLM()
    return Engine(PgStore(lambda: psycopg.connect(dsn, connect_timeout=5)), llm=llm, enabled=(env.get("COMPETITOR_RADAR_ENABLED", "false").lower() == "true"))


def main():
    key = os.environ.get("RADAR_HMAC_KEY", "")
    if len(key) < 32: sys.exit("RADAR_HMAC_KEY must be >= 32 chars")
    eng = build_engine()
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("RADAR_PORT", "8088"))), make_handler(eng, Auth(key))).serve_forever()


if __name__ == "__main__":
    main()
