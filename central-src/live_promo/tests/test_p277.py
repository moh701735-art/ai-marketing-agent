# -*- coding: utf-8 -*-
import dataclasses, importlib.util, os, re, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); MOD = os.path.dirname(H); P = os.path.join(os.path.dirname(MOD), "ops", "p277-live-probe-op.py.txt")
def load(name, p):
    s = importlib.util.spec_from_file_location(name, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
tool = load("cprobe", os.path.join(MOD, "ops", "tt_live_create_probe.py"))
rd = lambda p: open(p, encoding="utf-8").read()
CAT = '''
import dataclasses
class P:
    def __init__(self, kind, **k): self.kind = kind; self.k = k
@dataclasses.dataclass(frozen=@@FROZEN@@)
class Op:
    name: str
    platform: str = "tiktok"
    write: bool = False
    params: dict = dataclasses.field(default_factory=dict)
OPS = {}
def _add(o): OPS[o.name] = o
_add(Op("tiktok.create_campaign", write=True, params={"campaign_name": P("text"), "objective_type": P("enum", values=("TRAFFIC", "LEAD_GENERATION")), "budget_mode": P("enum", values=("BUDGET_MODE_TOTAL",)), "budget": P("num")}))
_add(Op("tiktok.create_adgroup", write=True, params={"promotion_type": P("enum", values=("WEBSITE",)), "optimization_goal": P("enum", values=("CLICK",)), "budget": P("num")}))
@@EXTRA@@
'''
def mk(frozen=False, extra=""):
    d = tempfile.mkdtemp(); os.makedirs(d + "/broker/app"); os.makedirs(d + "/ops"); open(d + "/ops/wa-diagnose.py", "w").write("x=1\n")
    open(d + "/broker/app/catalog.py", "w", encoding="utf-8").write(CAT.replace("@@FROZEN@@", str(frozen)).replace("@@EXTRA@@", extra)); return d
def apply(d): return subprocess.run([sys.executable, P], env={**os.environ, "P277_BASE": d + "/"}, capture_output=True, text=True)


class Patch(unittest.TestCase):
    def check(self, frozen):
        d = mk(frozen); r = apply(d); self.assertIn("APPLY277_OK", r.stdout, r.stdout + r.stderr)
        cat = load("cat%d" % id(d), d + "/broker/app/catalog.py")
        pc, pa = cat.OPS["tiktok.probe_campaign"], cat.OPS["tiktok.probe_adgroup"]
        self.assertEqual(pc.params["objective_type"].kind, "safe"); self.assertEqual(pc.params["budget"].kind, "num"); self.assertTrue(pc.write); self.assertEqual(pc.name, "tiktok.probe_campaign")
        self.assertEqual(pa.params["promotion_type"].kind, "safe"); self.assertEqual(pa.params["optimization_goal"].kind, "safe")
        oc = cat.OPS["tiktok.create_campaign"]; self.assertEqual(oc.params["objective_type"].kind, "enum"); self.assertEqual(oc.name, "tiktok.create_campaign")        # الأصل ما تغيّر
        self.assertEqual(sorted(cat.OPS), ["tiktok.create_adgroup", "tiktok.create_campaign", "tiktok.probe_adgroup", "tiktok.probe_campaign"])
        self.assertTrue(os.path.exists(d + "/broker/app/catalog.py.pre277")); self.assertTrue(os.path.exists(d + "/ops/tt-live-create-probe.py"))

    def test_mutable_and_frozen_dataclass_ops(self): self.check(False); self.check(True)

    def test_idempotent(self):
        d = mk(); apply(d); self.assertIn("changed=0", apply(d).stdout); self.assertGreaterEqual(rd(d + "/broker/app/catalog.py").count("p277"), 1)

    def test_missing_base_op_does_not_break_import(self):
        d = mk(); s = rd(d + "/broker/app/catalog.py").replace('_add(Op("tiktok.create_campaign"', '_x = (Op("tiktok.create_campaign"'); open(d + "/broker/app/catalog.py", "w", encoding="utf-8").write(s)
        apply(d); cat = load("catx", d + "/broker/app/catalog.py"); self.assertNotIn("tiktok.probe_campaign", cat.OPS); self.assertIn("tiktok.probe_adgroup", cat.OPS)

    def test_broken_ops_structure_never_crashes_the_module(self):
        d = mk(); s = rd(d + "/broker/app/catalog.py").replace("OPS = {}", "OPS = []").replace("OPS[o.name] = o", "OPS.append(o)"); open(d + "/broker/app/catalog.py", "w", encoding="utf-8").write(s)
        apply(d); load("caty", d + "/broker/app/catalog.py")                       # لا استثناء عند الاستيراد

    def test_fail_closed_without_wa_diagnose_or_syntax(self):
        d = mk(); os.remove(d + "/ops/wa-diagnose.py"); before = rd(d + "/broker/app/catalog.py"); r = apply(d)
        self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertEqual(rd(d + "/broker/app/catalog.py"), before)
        d = mk(); open(d + "/broker/app/catalog.py", "w", encoding="utf-8").write("def broken(:\n"); r = apply(d); self.assertIn("PATCH FAIL", r.stdout + r.stderr)


class Tool(unittest.TestCase):
    def test_build_call_only_invalid_objectives(self):
        c = tool.build_call(); self.assertEqual(c["op"], "tiktok.probe_campaign"); self.assertEqual(c["params"]["objective_type"], "PROBE_INVALID_OBJECTIVE")
        for bad in ("TRAFFIC", "LIVE", "ENGAGEMENT", ""):
            with self.assertRaises(SystemExit): tool.build_call(bad)

    def test_parse_allowed_list_from_tiktok_message(self):
        r = tool.parse({"ok": False, "error": {"class": "bad_request", "platform_code": 40002, "message": "[bad_request] platform_code 40002: objective_type: not a valid value; allowed: TRAFFIC, LEAD_GENERATION, ENGAGEMENT, LIVE_SHOPPING"}})
        self.assertEqual(r["allowed"], ["TRAFFIC", "LEAD_GENERATION", "ENGAGEMENT", "LIVE_SHOPPING"]); self.assertFalse(r["created"])
        out = tool.report(r); self.assertIn("ENGAGEMENT", out.split("LIVE/ENGAGEMENT-LIKE OBJECTIVES:")[1]); self.assertIn("LIVE_SHOPPING", out); self.assertFalse(any(l.startswith("WARNING:") for l in out.split("\n")))

    def test_unparsable_and_accepted_cases(self):
        r = tool.parse({"ok": False, "error": {"message": "something else"}}); self.assertEqual(r["allowed"], []); self.assertIn("N/A", tool.report(r))
        r = tool.parse({"ok": True, "data": {}}); self.assertIn("WARNING: TikTok ACCEPTED", tool.report(r))

    def test_ascii_and_no_secrets(self):
        out = tool.report(tool.parse({"ok": False, "error": {"class": "bad_request", "message": "خطأ allowed: A_B, C_D"}})); self.assertTrue(all(ord(c) < 128 for c in out))
        src = rd(os.path.join(MOD, "ops", "tt_live_create_probe.py"))
        for bad in ("access_token", "getpass", "INSERT", "ad_group", "tiktok.create_"): self.assertNotIn(bad, src.replace("tiktok.probe_campaign", ""))


if __name__ == "__main__":
    unittest.main(verbosity=1)
