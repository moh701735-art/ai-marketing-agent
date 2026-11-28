import base64, lzma, os, re, shutil, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..")
subprocess.run([sys.executable, os.path.join(ROOT, "build_p305.py")], check=True, capture_output=True)
PATCH = os.path.join(ROOT, "..", "ops", "p305-web-portal-package.py.txt"); rd = lambda p: open(p, encoding="utf-8").read()
def tree():
    d = tempfile.mkdtemp(); [os.makedirs(d + "/" + x) for x in ("ops", "deploy")]; return d
def ap(d, body=None): return subprocess.run([sys.executable], input=body or rd(PATCH), env={**os.environ, "P305_BASE": d + "/"}, capture_output=True, text=True)
class T(unittest.TestCase):
    def test_01_writes_files_idempotent_backup(self):
        d = tree(); r = ap(d); self.assertIn("APPLY305_OK changed=15", r.stdout, r.stdout + r.stderr)
        for f in ("web_portal/Dockerfile", "web_portal/service/app.py", "web_portal/db/81_web_portal.sql", "ops/web-portal.py"): self.assertTrue(os.path.exists(d + "/" + f), f)
        self.assertTrue(os.access(d + "/ops/web-portal.py", os.X_OK)); self.assertIn("changed=0", ap(d).stdout)
        open(d + "/web_portal/service/app.py", "a").write("# local edit"); r = ap(d); self.assertIn("changed=1", r.stdout); self.assertTrue(os.path.exists(d + "/web_portal/service/app.py.pre305"))
    def test_02_refuses_wrong_tree_and_nothing_written(self):
        d = tempfile.mkdtemp(); r = ap(d); self.assertNotEqual(r.returncode, 0); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertEqual(os.listdir(d), [])
    def test_03_package_imports_and_ctl_runs(self):
        d = tree(); ap(d); r = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, %r); import web_portal.service.app as a; print(a.SESSION_HOURS)" % d], capture_output=True, text=True); self.assertEqual(r.stdout.strip(), "72", r.stderr)
        r = subprocess.run([sys.executable, d + "/ops/web-portal.py", "--help"], capture_output=True, text=True); self.assertIn("install", r.stdout)
    def test_04_oneliner_matches_and_files_equal_sources(self):
        s = rd(os.path.join(ROOT, "..", "..", "out", "p305s.txt")); self.assertEqual(s.count("\n"), 1); self.assertIn("python3 ops/web-portal.py --help", s); self.assertNotIn("install\n", s.split("--help")[1])
        body = lzma.decompress(base64.b64decode(re.search(r"echo '([^']+)'", s).group(1))).decode(); self.assertEqual(body, rd(PATCH))
        d = tree(); ap(d, body); self.assertEqual(rd(d + "/web_portal/service/security.py"), rd(os.path.join(ROOT, "service", "security.py"))); self.assertEqual(rd(d + "/ops/web-portal.py"), rd(os.path.join(ROOT, "deploy", "web_portal_ctl.py")))
    def test_05_no_secrets_in_package(self):
        t = rd(PATCH); self.assertNotRegex(t, r"postgresql://web_rt:[^@{%]{8,}@"); self.assertNotIn("BEGIN PRIVATE", t)
if __name__ == "__main__": unittest.main()
