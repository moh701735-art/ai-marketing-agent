# -*- coding: utf-8 -*-
import importlib.util, os, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); MOD = os.path.dirname(H); ROOT = os.path.dirname(os.path.dirname(MOD)); P = os.path.join(os.path.dirname(MOD), "ops", "p283-live-probe-ad.py.txt")
def load(name, p):
    s = importlib.util.spec_from_file_location(name, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
tool = load("b2v4", os.path.join(MOD, "ops", "tt_live_b2.py")); t80 = load("t80b", os.path.join(H, "test_p280.py")); t81 = load("t81b", os.path.join(H, "test_p281.py"))
rd = lambda p: open(p, encoding="utf-8").read()
SP = {**t81.SP, "tiktok.probe_ad": {"write": True, "params": {k: "safe" for k in ("adgroup_id", "ad_name", "ad_format", "identity_id", "identity_type", "tiktok_item_id", "ad_text", "call_to_action")}}}
CAT = '''
import dataclasses
class P:
    def __init__(self, kind, **k): self.kind = kind; self.k = k
@dataclasses.dataclass(frozen=@@F@@)
class Op:
    name: str
    platform: str = "tiktok"
    write: bool = False
    params: dict = dataclasses.field(default_factory=dict)
OPS = {}
@@EXTRA@@
OPS["tiktok.create_ad"] = Op("tiktok.create_ad", write=True, params={"adgroup_id": P("safe"), "ad_name": P("text"), "ad_format": P("enum", values=("SINGLE_VIDEO",)), "call_to_action": P("enum", values=("LEARN_MORE",)), "identity_type": P("enum", values=("AUTH_CODE",)), "ad_text": P("text")})
# p277 marker
'''
def mk(frozen=False, p277=True, create_ad=True):
    d = tempfile.mkdtemp(); os.makedirs(d + "/broker/app"); os.makedirs(d + "/ops"); open(d + "/ops/wa-diagnose.py", "w").write("x=1\n")
    c = CAT.replace("@@F@@", str(frozen)).replace("@@EXTRA@@", "")
    if not p277: c = c.replace("# p277 marker", "")
    if not create_ad: c = c.replace('OPS["tiktok.create_ad"] =', '_x =')
    open(d + "/broker/app/catalog.py", "w").write(c); open(d + "/ops/tt-live-b2.py", "w").write("OLD\n"); return d
def apply(d): return subprocess.run([sys.executable, P], env={**os.environ, "P283_BASE": d + "/"}, capture_output=True, text=True)


class Cat(unittest.TestCase):
    def check(self, frozen):
        d = mk(frozen); r = apply(d); self.assertIn("APPLY283_OK", r.stdout, r.stdout + r.stderr)
        cat = load("c%d" % id(d), d + "/broker/app/catalog.py"); pa = cat.OPS["tiktok.probe_ad"]
        self.assertEqual(pa.params["ad_format"].kind, "safe"); self.assertEqual(pa.params["call_to_action"].kind, "safe"); self.assertEqual(pa.params["ad_text"].kind, "text"); self.assertEqual(pa.name, "tiktok.probe_ad"); self.assertTrue(pa.write)
        self.assertEqual(cat.OPS["tiktok.create_ad"].params["ad_format"].kind, "enum"); self.assertEqual(cat.OPS["tiktok.create_ad"].name, "tiktok.create_ad")
        self.assertTrue(os.path.exists(d + "/broker/app/catalog.py.pre283")); self.assertEqual(rd(d + "/ops/tt-live-b2.py.pre283"), "OLD\n")
    def test_mutable_and_frozen(self): self.check(False); self.check(True)
    def test_idempotent(self): d = mk(); apply(d); self.assertIn("changed=0", apply(d).stdout)
    def test_missing_create_ad_is_harmless(self):
        d = mk(create_ad=False); apply(d); cat = load("cx", d + "/broker/app/catalog.py"); self.assertNotIn("tiktok.probe_ad", cat.OPS)
    def test_fail_closed(self):
        d = mk(p277=False); before = rd(d + "/broker/app/catalog.py"); r = apply(d); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertEqual(rd(d + "/broker/app/catalog.py"), before)
    def test_oneliners(self):
        s = rd(os.path.join(ROOT, "out", "p283s.txt")); self.assertEqual(s.count("\n"), 1); self.assertIn("bash deploy/update.sh", s)
        r = rd(os.path.join(ROOT, "out", "p283r.txt")); self.assertIn("LB_ONLY=promotion_type,ad_format python3 ops/tt-live-b2.py", r)


class Adv(t80.FakeWad):
    def broker(self, env, ctx, acct, calls):
        c = calls[0]
        if c["op"] == "tiktok.probe_ad":
            self.calls.append((c["op"], c["params"]))
            for k in ("identity_id", "tiktok_item_id"):
                if k not in c["params"]: return [t80.err("missing param: " + k, "invalid_params", None)]
            return [t80.err("ad_format: not valid; allowed: SINGLE_IMAGE, SINGLE_VIDEO, LIVE_CONTENT, CAROUSEL, PRB_BA")]
        if c["op"] == "tiktok.probe_adgroup":
            self.calls.append((c["op"], c["params"])); return [t80.err("promotion_type: not valid; allowed: LIVE_SHOPPING, LIVE, WEBSITE")]
        return super().broker(env, ctx, acct, calls)


class Tool(unittest.TestCase):
    def go(self, w, **kw):
        out = []; tool.run(w, None, "c", "7593807340588253185", out=out.append, **kw); return "\n".join(out)
    def test_ad_probe_has_sentinel_and_fake_adgroup_and_autofill(self):
        w = Adv(specs=SP); o = self.go(w)
        ads = [p for op, p in w.calls if op == "tiktok.probe_ad"]; self.assertTrue(ads)
        for p in ads: self.assertEqual(p["ad_format"], "PRB_BAD"); self.assertEqual(p["adgroup_id"], tool.FAKE_AG)
        self.assertIn("autofilled required params: identity_id, tiktok_item_id", o); self.assertIn("F|ad_format|03|x_LIVE_CONTENT_x", o); self.assertIn("VALUES WITH LIVE OR STREAM IN THE NAME", o)
        self.assertFalse(any(l.startswith("WARNING") for l in o.split("\n"))); self.assertTrue(all(ord(c) < 128 for c in o))
    def test_only_filter(self):
        w = Adv(specs=SP); o = self.go(w, only=["promotion_type"])
        self.assertEqual({p.get("promotion_type") for op, p in w.calls if op == "tiktok.probe_adgroup"}, {"PRB_BAD"}); self.assertEqual(sum(1 for op, _ in w.calls if op == "tiktok.probe_adgroup"), 1)
        self.assertNotIn("tiktok.probe_ad", [c[0] for c in w.calls]); self.assertIn("F|promotion_type|01|x_LIVE_SHOPPING_x", o); self.assertNotIn("F|optimization_goal", o)
    def test_only_both(self):
        w = Adv(specs=SP); o = self.go(w, only=["promotion_type", "ad_format"]); self.assertIn("tiktok.probe_ad", [c[0] for c in w.calls]); self.assertIn("F|ad_format|01|x_SINGLE_IMAGE_x", o)
    def test_missing_probe_ad_noted(self):
        o = self.go(Adv(specs=t81.SP)); self.assertIn("tiktok.probe_ad NOT IN CATALOG", o)
    def test_ad_probe_guards(self):
        c = tool.ad_call(SP["tiktok.probe_ad"]); self.assertEqual(c["params"]["ad_format"], "PRB_BAD"); self.assertEqual(c["params"]["adgroup_id"], tool.FAKE_AG)
        with self.assertRaises(SystemExit): tool.ad_call({"params": {"adgroup_id": "x"}})                          # ad_format غير موجود بالكتالوج => رفض
    def test_ad_accepted_warns(self):
        class A2(Adv):
            def broker(s, env, ctx, acct, calls):
                if calls[0]["op"] == "tiktok.probe_ad": return [{"ok": True, "data": {"ad_ids": ["1"]}}]
                return super().broker(env, ctx, acct, calls)
        self.assertIn("WARNING: TikTok ACCEPTED the ad probe", self.go(A2(specs=SP)))
    def test_source_forbidden_ops(self):
        s = rd(os.path.join(MOD, "ops", "tt_live_b2.py")); self.assertNotIn("tiktok.create_", s.replace("tiktok.probe_", "")); self.assertEqual(s.count('"tiktok.set_campaign_status"'), 1); self.assertIn("v4 / p283", s)


if __name__ == "__main__":
    unittest.main(verbosity=1)
