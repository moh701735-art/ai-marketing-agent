"""يطبّق p217 على نسخة اصطناعية من معالج llm.* (حزمة app حقيقية) ويشغّله بعملية فرعية. بدون شبكة."""
import json, os, shutil, subprocess, sys, tempfile, textwrap, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATCH = os.path.join(ROOT, "ops", "p217-cmdparse.py.txt"); P216 = os.path.join(ROOT, "ops", "p216-llm-retry.py.txt")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import test_cmdparse as TC
sys.path.insert(0, os.path.join(ROOT, "broker_llm", "tests")); import test_p216 as T16
SYN = T16.SYN.replace("async def llm_call(self, tenant, op, params):", "async def llm_call(self, tenant, op, params):\n        self.store = self.__dict__.get('store')").replace("        ms = int((time.monotonic() - t0) * 1000)\n        return status, cls, result", "        ms = int((time.monotonic() - t0) * 1000)\n        return status, cls, result")
DRIVER = '''
import asyncio, json, sys
sys.path.insert(0, sys.argv[1])
from app import service
class Store:
    def __init__(self): self.rows = []
    def log_call(self, *a): self.rows.append(list(a))
class R:
    def __init__(self, status, content): self.status_code, self.content = status, content
class Client:
    def __init__(self): self.calls = 0
    async def post(self, url, headers=None, json=None, timeout=None):
        self.calls += 1
        return R(200, b'{"candidates":[{"content":{"parts":[{"text":"{\\\\"intent\\\\": \\\\"unknown\\\\"}"}]}}]}')
s = service.Svc(); s.client = Client(); s.llm_bucket_ok = True; s.store = Store()
case = json.loads(sys.argv[2])
if case.get("ci") == "add": service.llm.clean_intent = staticmethod(lambda d: {**d, "_clean": True})
if case.get("ci") == "none": service.llm.clean_intent = staticmethod(lambda d: None)
if case.get("ci") == "boom": service.llm.clean_intent = staticmethod(lambda d: 1 / 0)
out = asyncio.run(s.llm_call("tenantX", case["op"], {"text": case["text"]}))
print(json.dumps({"out": list(out), "client_calls": s.client.calls, "log": s.store.rows}, ensure_ascii=False, default=str))
'''
class T(unittest.TestCase):
    PRE216 = False
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(); os.makedirs(cls.tmp + "/broker/app"); open(cls.tmp + "/broker/app/__init__.py", "w").write("")
        open(cls.tmp + "/broker/app/service.py", "w", encoding="utf-8").write(SYN)
        if cls.PRE216: r = subprocess.run([sys.executable, P216], env=dict(os.environ, P216_BASE=cls.tmp + "/"), capture_output=True, text=True); assert "APPLY216_OK" in r.stdout, r.stdout + r.stderr
        r = subprocess.run([sys.executable, PATCH], env=dict(os.environ, P217_BASE=cls.tmp + "/"), capture_output=True, text=True); assert "APPLY217_OK" in r.stdout, r.stdout + r.stderr
        open(cls.tmp + "/driver.py", "w").write(DRIVER)
    @classmethod
    def tearDownClass(cls): shutil.rmtree(cls.tmp, ignore_errors=True)
    def run_case(self, op, text, ci=None):
        r = subprocess.run([sys.executable, self.tmp + "/driver.py", self.tmp + "/broker", json.dumps({"op": op, "text": text, "ci": ci}, ensure_ascii=False)], capture_output=True, text=True); self.assertEqual(r.returncode, 0, r.stderr[-400:]); return json.loads(r.stdout.strip().splitlines()[-1])
    def test_template_message_is_read_by_code_without_calling_the_llm(self):
        o = self.run_case("llm.parse_command", TC.PUBG); self.assertEqual(o["client_calls"], 0); self.assertEqual(o["out"][0], 200); self.assertTrue(o["out"][1]["ok"])
        d = o["out"][1]["data"]; self.assertEqual(d["objective"], "TRAFFIC"); self.assertEqual(d["budget"], 20); self.assertEqual(d["account"], "غزل وزينب")
        self.assertEqual(o["log"][0][:3], ["tenantX", "llm", "llm.parse_command"])
    def test_same_sanitizer_as_llm_path_is_applied_when_present(self):
        o = self.run_case("llm.parse_command", TC.PUBG, ci="add"); self.assertTrue(o["out"][1]["data"]["_clean"]); self.assertEqual(o["client_calls"], 0)
    def test_sanitizer_rejecting_or_crashing_falls_back_to_the_llm(self):
        self.assertEqual(self.run_case("llm.parse_command", TC.PUBG, ci="none")["client_calls"], 1); self.assertEqual(self.run_case("llm.parse_command", TC.PUBG, ci="boom")["client_calls"], 1)
    def test_other_messages_still_go_to_the_llm(self):
        o = self.run_case("llm.parse_command", "شنو رصيدي"); self.assertEqual(o["client_calls"], 1)
    def test_chat_op_is_not_intercepted(self):
        o = self.run_case("llm.chat", TC.PUBG); self.assertEqual(o["client_calls"], 1)
    def test_incomplete_template_falls_back_to_the_llm(self):
        o = self.run_case("llm.parse_command", TC.mod(TC.PUBG, "20 دولار", "")); self.assertEqual(o["client_calls"], 1)
    def test_idempotent_and_files_and_backup(self):
        r = subprocess.run([sys.executable, PATCH], env=dict(os.environ, P217_BASE=self.tmp + "/"), capture_output=True, text=True); self.assertIn("changed=0", r.stdout)
        self.assertTrue(os.path.exists(self.tmp + "/broker/app/cmdparse.py")); self.assertTrue(os.path.exists(self.tmp + "/broker/app/service.py.pre217"))
class WithP216(T):
    PRE216 = True
class Robustness(unittest.TestCase):
    def test_unknown_variable_names_never_break_the_llm_path(self):
        tmp = tempfile.mkdtemp(); os.makedirs(tmp + "/broker/app"); open(tmp + "/broker/app/__init__.py", "w").write("")
        src = SYN.replace("async def llm_call(self, tenant, op, params):", "async def llm_call(self, tenant, operation, params):").replace('if op == "llm.chat":', 'if operation == "llm.chat":')
        open(tmp + "/broker/app/service.py", "w", encoding="utf-8").write(src)
        r = subprocess.run([sys.executable, PATCH], env=dict(os.environ, P217_BASE=tmp + "/"), capture_output=True, text=True); self.assertIn("APPLY217_OK", r.stdout)
        open(tmp + "/driver.py", "w").write(DRIVER)
        r = subprocess.run([sys.executable, tmp + "/driver.py", tmp + "/broker", json.dumps({"op": "llm.parse_command", "text": TC.PUBG}, ensure_ascii=False)], capture_output=True, text=True); self.assertEqual(r.returncode, 0, r.stderr[-400:])
        o = json.loads(r.stdout.strip().splitlines()[-1]); self.assertEqual(o["client_calls"], 1); shutil.rmtree(tmp)   # الخطأ داخل try => نفس مسار الـLLM القديم
    def test_anchor_mismatch_writes_nothing(self):
        tmp = tempfile.mkdtemp(); os.makedirs(tmp + "/broker/app"); src = SYN.replace("t0 = time.monotonic()", "t_start = time.monotonic()"); open(tmp + "/broker/app/service.py", "w", encoding="utf-8").write(src)
        r = subprocess.run([sys.executable, PATCH], env=dict(os.environ, P217_BASE=tmp + "/"), capture_output=True, text=True); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr)
        self.assertEqual(open(tmp + "/broker/app/service.py", encoding="utf-8").read(), src); self.assertFalse(os.path.exists(tmp + "/broker/app/cmdparse.py")); shutil.rmtree(tmp)
if __name__ == "__main__": unittest.main()
