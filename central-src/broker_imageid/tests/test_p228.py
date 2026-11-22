import os, re, subprocess, sys, tempfile, unittest
PATCH = os.path.join(os.path.dirname(__file__), "..", "..", "ops", "p228-tt-image-id-chars.py.txt")
CAT = '''
import re
class P:
    def __init__(self, kind, **k): self.kind = kind
class Bad(ValueError): pass
def _check(name, spec, v):
    if spec.kind == "safelist":
        if not isinstance(v, (list, tuple)) or len(v) > 40 or any(not isinstance(x, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,60}", x) for x in v):
            raise Bad(f"{name}: list of identifiers not valid")
    return v
'''
def apply(d): return subprocess.run([sys.executable, "-"], input=open(PATCH, encoding="utf-8").read(), text=True, capture_output=True, env=dict(os.environ, P228_BASE=d + "/"))
class T(unittest.TestCase):
    def setUp(self): self.d = tempfile.mkdtemp(); os.makedirs(self.d + "/broker/app"); open(self.d + "/broker/app/catalog.py", "w", encoding="utf-8").write(CAT)
    def mod(self):
        ns = {}; exec(open(self.d + "/broker/app/catalog.py", encoding="utf-8").read(), ns); return ns
    def ok(self, ns, name, v):
        try: ns["_check"](name, ns["P"]("safelist"), v); return True
        except ns["Bad"]: return False
    def test_01_before_patch_slash_id_rejected_after_accepted(self):
        TID = "ad-site-i18n-sg/20261122abcdef0123456789abcdef01"
        self.assertFalse(self.ok(self.mod(), "image_ids", [TID]))
        r = apply(self.d); self.assertIn("APPLY228_OK", r.stdout, r.stderr); ns = self.mod(); self.assertTrue(self.ok(ns, "image_ids", [TID]))
    def test_02_other_lists_still_reject_slash(self):
        apply(self.d); ns = self.mod(); self.assertFalse(self.ok(ns, "video_ids", ["a/b"])); self.assertTrue(self.ok(ns, "video_ids", ["v10033g50000c1abc"]))
    def test_03_dotdot_non_str_long_and_too_many_rejected_for_image_ids(self):
        apply(self.d); ns = self.mod()
        for bad in (["a/../b"], [123], ["x" * 121], ["ok"] * 41, ["bad id"], ["a;b"], ["a\\b"], [""]): self.assertFalse(self.ok(ns, "image_ids", bad), bad)
        for good in (["a-b_c.d/e1"], ["ad-site-i18n-sg/" + "f" * 60]): self.assertTrue(self.ok(ns, "image_ids", good), good)
    def test_04_idempotent_backup_marker(self):
        apply(self.d); self.assertTrue(os.path.exists(self.d + "/broker/app/catalog.py.pre228")); self.assertIn("changed=0", apply(self.d).stdout)
        self.assertEqual(sum(1 for l in open(self.d + "/broker/app/catalog.py", encoding="utf-8") if "p228" in l), 1)
    def test_06_regex_class_variants_all_patched_preserving_original_class(self):
        for cls in (r"[A-Za-z0-9_.-]", r"[A-Za-z0-9_.\\-]", r"[A-Za-z0-9_.]"):
            self.setUp(); open(self.d + "/broker/app/catalog.py", "w", encoding="utf-8").write(CAT.replace(r"[A-Za-z0-9_.-]", cls)); r = apply(self.d); self.assertIn("APPLY228_OK", r.stdout, (cls, r.stderr)); ns = self.mod()
            self.assertTrue(self.ok(ns, "image_ids", ["ad-site-i18n-sg/abc123"]), cls); self.assertFalse(self.ok(ns, "video_ids", ["a/b"]), cls); self.assertTrue(self.ok(ns, "video_ids", ["abc_1.2"]), cls)
    def test_05_missing_or_duplicate_anchor_writes_nothing(self):
        for src in ("x = 1\n", CAT + CAT.split("def _check")[1]):
            open(self.d + "/broker/app/catalog.py", "w", encoding="utf-8").write(src); r = apply(self.d); self.assertIn("PATCH FAIL (nothing written)", r.stderr); self.assertEqual(open(self.d + "/broker/app/catalog.py", encoding="utf-8").read(), src)
if __name__ == "__main__": unittest.main(verbosity=1)
