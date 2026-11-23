import importlib.util, os, shutil, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..", "..")
PATCH = os.path.join(ROOT, "ops", "p236-sp-toggle-param.py.txt")
FIX = open(os.path.join(H, "sp_fixture.txt"), encoding="utf-8").read()
HEAD = '''OPS = {}
def P(kind, **kw): return {"kind": kind, **kw}
class Op:
    def __init__(self, name, platform, method, path, **kw): OPS[name] = {"method": method, "path": path, **kw}
CATALOG = [
    Op("tiktok.read_adgroups", "tiktok", "GET", "/adgroup/get/", params={"campaign_ids": P("idlist", required=True)}),
'''
TAIL = ''']
'''
CAT = HEAD + FIX + TAIL


def mk(text=CAT):
    d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "broker/app")); os.makedirs(os.path.join(d, "ops"))
    open(os.path.join(d, "broker/app/catalog.py"), "w", encoding="utf-8").write(text); return d


def apply(d): return subprocess.run([sys.executable, PATCH], env={**os.environ, "P236_BASE": d + "/"}, capture_output=True, text=True)


def load_ops(path):
    ns = {}; exec(compile(open(path, encoding="utf-8").read(), "catalog", "exec"), ns); return ns["OPS"]


class T(unittest.TestCase):
    def test_01_fixture_is_valid_and_has_both_ops(self):
        ops = load_ops(os.path.join(mk(), "broker/app/catalog.py")); self.assertIn("tiktok.sp_create_campaign", ops); self.assertIn("tiktok.sp_create_adgroup", ops)
    def test_02_apply_adds_optional_enum_to_both_ops_only(self):
        d = mk(); before = load_ops(os.path.join(d, "broker/app/catalog.py")); r = apply(d); self.assertIn("APPLY236_OK", r.stdout, r.stdout + r.stderr)
        after = load_ops(os.path.join(d, "broker/app/catalog.py"))
        for name in ("tiktok.sp_create_campaign", "tiktok.sp_create_adgroup"):
            added = set(after[name]["params"]) - set(before[name]["params"]); self.assertEqual(added, {"budget_auto_adjust_strategy"})
            p = after[name]["params"]["budget_auto_adjust_strategy"]; self.assertEqual(p["values"], ("AUTO_BUDGET_INCREASE", "UNSET")); self.assertFalse(p.get("required", False))
            self.assertEqual(after[name]["forced"], before[name]["forced"])
            for k, v in before[name]["params"].items(): self.assertEqual(after[name]["params"][k], v)
        self.assertEqual(after["tiktok.read_adgroups"], before["tiktok.read_adgroups"])
        self.assertTrue(os.path.exists(os.path.join(d, "broker/app/catalog.py.pre236")))
        self.assertTrue(os.path.exists(os.path.join(d, "ops/tt-smart-toggle-test.py")))
    def test_03_idempotent(self):
        d = mk(); apply(d); self.assertIn("changed=0", apply(d).stdout)
    def test_04_anchor_failures_write_nothing(self):
        for name, txt in {"no budget_mode": CAT.replace('"BUDGET_MODE_DYNAMIC_DAILY"', '"X"'), "no phone_number": CAT.replace('"phone_number": P("id", required=True)', '"phone": P("id", required=True)'), "no campaign op": CAT.replace("tiktok.sp_create_campaign", "tiktok.zzz")}.items():
            d = mk(txt); before = open(os.path.join(d, "broker/app/catalog.py"), encoding="utf-8").read(); r = apply(d)
            self.assertNotEqual(r.returncode, 0, name); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr, name)
            self.assertEqual(open(os.path.join(d, "broker/app/catalog.py"), encoding="utf-8").read(), before, name); self.assertFalse(os.path.exists(os.path.join(d, "broker/app/catalog.py.pre236")), name)
    def test_05_embedded_test_script_is_the_repo_file(self):
        d = mk(); apply(d); self.assertEqual(open(os.path.join(d, "ops/tt-smart-toggle-test.py"), encoding="utf-8").read(), open(os.path.join(ROOT, "ops", "tt-smart-toggle-test.py"), encoding="utf-8").read())
    def test_06_script_helpers_and_write_scope(self):
        spec = importlib.util.spec_from_file_location("tst", os.path.join(ROOT, "ops", "tt-smart-toggle-test.py")); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        self.assertEqual((m.default_budget("IQD"), m.default_budget("usd"), m.default_budget(None)), (10000, 10, 10))
        self.assertEqual(m.build_params(10000), {"campaign_name": "PROBE-SMART-TOGGLE-DELETE-ME", "budget": 10000, "budget_mode": "BUDGET_MODE_DYNAMIC_DAILY", "budget_auto_adjust_strategy": "AUTO_BUDGET_INCREASE"})
        src = open(os.path.join(ROOT, "ops", "tt-smart-toggle-test.py"), encoding="utf-8").read(); compile(m.PY, "PY", "exec")
        for op in ("tiktok.sp_create_campaign", "tiktok.sp_read_campaigns"): self.assertIn(op, src)
        for bad in ("set_campaign_status", "sp_create_adgroup", "sp_create_ad", "operation_status\": \"ENABLE"): self.assertNotIn(bad, src)
        self.assertEqual(bytes.fromhex(m.hexs("AUTO_BUDGET_INCREASE")).decode(), "AUTO_BUDGET_INCREASE")
        out = "\n".join(m.summarize({"campaign_id": "1", "budget_auto_adjust_strategy": "AUTO_BUDGET_INCREASE", "budget": 10000})); self.assertIn("HEX budget_auto_adjust_strategy = ", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
