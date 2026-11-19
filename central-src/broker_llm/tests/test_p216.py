"""يطبّق p216 على نسخة اصطناعية من معالج llm.* بـservice.py (بنية مستنتجة من النسخة المكبّرة) ويختبر إعادة المحاولة. بدون شبكة."""
import asyncio, contextlib, importlib.util, io, json, os, shutil, subprocess, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATCH = os.path.join(ROOT, "ops", "p216-llm-retry.py.txt")
SYN = '''
import json, time

class httpx:
    class HTTPError(Exception): pass

class llm:
    @staticmethod
    def build_request(text, model):
        return {"contents": [{"role": "user", "parts": [{"text": text}]}], "generationConfig": {"temperature": 0, "maxOutputTokens": 1500}}
    @staticmethod
    def parse_response(content):
        try:
            d = json.loads(content); return json.loads(d["candidates"][0]["content"]["parts"][0]["text"])
        except Exception:
            return None

class S:
    llm_base_url = "https://g.example/v1beta/"; llm_model = "m"; llm_key = "k"

class Svc:
    s = S()
    async def sleep(self, x): return None
    async def llm_call(self, tenant, op, params):
        if not self.llm_bucket_ok: return 429, "rate_limited_local", None
        t0 = time.monotonic()
        url = self.s.llm_base_url.rstrip("/") + f"/models/{self.s.llm_model}:generateContent"
        status, cls, result = None, None, None
        for attempt in (1, 2):
            try:
                if op == "llm.chat":
                    body = {"chat": True}
                else:
                    body = llm.build_request(params["text"], self.s.llm_model)
                r = await self.client.post(url, headers={"x-goog-api-key": self.s.llm_key}, json=body, timeout=20.0)
            except httpx.HTTPError:
                cls = "transient"
                status = None
                await self.sleep(0.4)
                continue
            status = r.status_code
            if status == 200:
                if op == "llm.chat":
                    result = {"reply": "x"}
                else:
                    result = llm.parse_response(r.content)
                cls = "bad_response" if result is None else None
                break
            cls = "auth_expired" if status in (400, 401, 403) else "rate_limited" if status == 429 else "transient"
            if cls in ("rate_limited", "bad_response"):  # p190
                break
            await self.sleep(0.4)
        ms = int((time.monotonic() - t0) * 1000)
        return status, cls, result
'''
def gem(text, finish="STOP", toks=120):
    return json.dumps({"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": finish}], "usageMetadata": {"candidatesTokenCount": toks}}).encode()
GOOD = gem(json.dumps({"intent": "launch", "budget": 20}))
TRUNC = gem('{"intent": "launch", "name": "' + "x" * 50, finish="MAX_TOKENS", toks=1500)
class R:
    def __init__(self, status, content=b""): self.status_code, self.content = status, content
class Client:
    def __init__(self, script): self.script, self.calls = list(script), []
    async def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append(json); x = self.script.pop(0)
        if isinstance(x, Exception): raise x
        return x
class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(); os.makedirs(cls.tmp + "/broker/app"); open(cls.tmp + "/broker/app/service.py", "w", encoding="utf-8").write(SYN)
        r = subprocess.run([sys.executable, PATCH], env=dict(os.environ, P216_BASE=cls.tmp + "/"), capture_output=True, text=True); assert "APPLY216_OK" in r.stdout, r.stdout + r.stderr
        spec = importlib.util.spec_from_file_location("svc216", cls.tmp + "/broker/app/service.py"); cls.m = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.m)
    @classmethod
    def tearDownClass(cls): shutil.rmtree(cls.tmp, ignore_errors=True)
    def run_op(self, script, op="llm.parse_command", bucket=True):
        s = self.m.Svc(); s.client = Client(script); s.llm_bucket_ok = bucket; buf = io.StringIO()
        with contextlib.redirect_stdout(buf): out = asyncio.run(s.llm_call("t", op, {"text": "hello"}))
        return out, s.client, buf.getvalue()
    def test_good_first_reply_no_retry_no_temperature_change(self):
        (st, cls, res), c, log = self.run_op([R(200, GOOD)]); self.assertEqual((st, cls), (200, None)); self.assertEqual(res["intent"], "launch"); self.assertEqual(len(c.calls), 1); self.assertEqual(c.calls[0]["generationConfig"]["temperature"], 0); self.assertEqual(log, "")
    def test_truncated_then_good_succeeds_with_higher_temperature(self):
        (st, cls, res), c, log = self.run_op([R(200, TRUNC), R(200, GOOD)]); self.assertIsNone(cls); self.assertEqual(res["budget"], 20); self.assertEqual(len(c.calls), 2)
        self.assertEqual(c.calls[0]["generationConfig"]["temperature"], 0); self.assertEqual(c.calls[1]["generationConfig"]["temperature"], 0.4); self.assertEqual(c.calls[1]["generationConfig"]["maxOutputTokens"], 1500)
        self.assertIn("p216 llm bad_response finish=MAX_TOKENS out_tokens=1500 retry=False", log)
    def test_two_failures_still_bad_response_never_invents_fields(self):
        (st, cls, res), c, log = self.run_op([R(200, TRUNC), R(200, TRUNC)]); self.assertEqual(cls, "bad_response"); self.assertIsNone(res); self.assertEqual(len(c.calls), 2); self.assertEqual(log.count("p216 llm bad_response"), 2); self.assertIn("retry=True", log)
    def test_log_has_no_user_text(self):
        _, _, log = self.run_op([R(200, gem("not json at all hello", "MAX_TOKENS", 1500)), R(200, GOOD)]); self.assertNotIn("hello", log); self.assertNotIn("not json", log)
    def test_http_error_path_unchanged(self):
        (st, cls, res), c, log = self.run_op([self.m.httpx.HTTPError("net"), R(200, GOOD)]); self.assertIsNone(cls); self.assertEqual(len(c.calls), 2); self.assertEqual(c.calls[1]["generationConfig"]["temperature"], 0)
    def test_rate_limit_still_breaks_without_retry(self):
        (st, cls, res), c, log = self.run_op([R(429)]); self.assertEqual(cls, "rate_limited"); self.assertEqual(len(c.calls), 1)
    def test_auth_error_unchanged(self):
        (st, cls, res), c, _ = self.run_op([R(401), R(401)]); self.assertEqual(cls, "auth_expired")
    def test_chat_op_untouched(self):
        (st, cls, res), c, log = self.run_op([R(200, GOOD)], op="llm.chat"); self.assertEqual(res, {"reply": "x"}); self.assertEqual(len(c.calls), 1)
    def test_garbage_non_json_response_body_does_not_crash_logging(self):
        (st, cls, res), c, log = self.run_op([R(200, b"<html>oops</html>"), R(200, GOOD)]); self.assertIsNone(cls); self.assertEqual(len(c.calls), 2)
    def test_idempotent_and_backup(self):
        r = subprocess.run([sys.executable, PATCH], env=dict(os.environ, P216_BASE=self.tmp + "/"), capture_output=True, text=True); self.assertIn("changed=0", r.stdout); self.assertTrue(os.path.exists(self.tmp + "/broker/app/service.py.pre216"))
    def test_anchor_mismatch_writes_nothing_and_prints_raw_lines(self):
        tmp = tempfile.mkdtemp(); os.makedirs(tmp + "/broker/app"); src = SYN.replace('cls = "bad_response" if result is None else None', 'cls = "x" if result is None else None')
        open(tmp + "/broker/app/service.py", "w", encoding="utf-8").write(src)
        r = subprocess.run([sys.executable, PATCH], env=dict(os.environ, P216_BASE=tmp + "/"), capture_output=True, text=True); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertIn("RAW", r.stdout + r.stderr)
        self.assertEqual(open(tmp + "/broker/app/service.py", encoding="utf-8").read(), src); shutil.rmtree(tmp)
if __name__ == "__main__": unittest.main()
