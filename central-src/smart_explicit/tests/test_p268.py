# -*- coding: utf-8 -*-
import importlib.util, os, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); P = os.path.join(H, "..", "..", "ops", "p268-smart-explicit.py.txt")
SPARK = '''def validate(params, allowed_countries=None):
    if params.get("smart") is not None and not isinstance(params.get("smart"), bool): return None, "smart must be bool"
    if params.get("smart") and params["objective"] != "whatsapp": return None, "smart only for whatsapp"
    params = {**params, "smart": False}  # p207: manual only (owner request 18-11)
    cs = params.get("countries")
    if params.get("smart") and cs != ["IQ"]: return None, "smart: Iraq only"
    return params, None
'''
rd = lambda p: open(p, encoding="utf-8").read()
def mk(src=SPARK):
    d = tempfile.mkdtemp(); os.makedirs(d + "/broker/app"); open(d + "/broker/app/spark.py", "w", encoding="utf-8").write(src); return d
def apply(d): return subprocess.run([sys.executable, P], env={**os.environ, "P268_BASE": d + "/"}, capture_output=True, text=True)
def load(d):
    s = importlib.util.spec_from_file_location("sp%d" % id(d), d + "/broker/app/spark.py"); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = mk(); r = apply(cls.d); assert "APPLY268_OK" in r.stdout, r.stdout + r.stderr; cls.sp = load(cls.d); cls.old = load(mk())

    def test_before_always_manual(self):
        self.assertFalse(self.old.validate({"objective": "whatsapp", "smart": True})[0]["smart"])

    def test_explicit_smart_whatsapp(self):
        p, e = self.sp.validate({"objective": "whatsapp", "smart": True, "countries": ["IQ"]}); self.assertIsNone(e); self.assertIs(p["smart"], True)

    def test_default_manual(self):
        for q in ({"objective": "whatsapp"}, {"objective": "whatsapp", "smart": False}, {"objective": "sales"}, {"objective": "traffic", "smart": False}):
            p, e = self.sp.validate(dict(q)); self.assertIsNone(e); self.assertIs(p["smart"], False, q)

    def test_smart_other_objective_still_rejected(self):
        self.assertIn("only for whatsapp", self.sp.validate({"objective": "sales", "smart": True})[1])

    def test_non_bool_never_smart(self):
        self.assertIn("bool", self.sp.validate({"objective": "whatsapp", "smart": "yes"})[1])

    def test_smart_limits_return(self):                                     # قيود Smart+ الأصلية (العراق فقط) تشتغل ثانية
        self.assertIn("Iraq only", self.sp.validate({"objective": "whatsapp", "smart": True, "countries": ["IQ", "SA"]})[1])

    def test_idempotent_and_only_that_line(self):
        r = apply(self.d); self.assertIn("changed=0", r.stdout)
        a, b = rd(self.d + "/broker/app/spark.py.pre268").split("\n"), rd(self.d + "/broker/app/spark.py").split("\n")
        self.assertEqual(len(a), len(b)); self.assertEqual(sum(1 for x, y in zip(a, b) if x != y), 1)

    def test_fail_closed(self):
        for src in ("x = 1\n", SPARK + SPARK, SPARK.replace('"smart": False', '"smart": None')):
            d = mk(src); before = rd(d + "/broker/app/spark.py"); r = apply(d)
            self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertEqual(rd(d + "/broker/app/spark.py"), before); self.assertFalse(os.path.exists(d + "/broker/app/spark.py.pre268"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
