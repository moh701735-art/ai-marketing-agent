import os, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(H, "..")
subprocess.run([sys.executable, os.path.join(R, "deploy", "build_install.py")], check=True, capture_output=True)
PATCH = os.path.join(R, "..", "ops", "p251-radar-install-files.py.txt")
def apply(d): return subprocess.run([sys.executable, PATCH], env={**os.environ, "P251_BASE": d + "/"}, capture_output=True, text=True)
def tree(d): return sorted(os.path.relpath(os.path.join(a, f), d) for a, _, fs in os.walk(d) for f in fs)

class T(unittest.TestCase):
    def test_writes_only_new_paths_and_files_match_source(self):
        d = tempfile.mkdtemp(); os.makedirs(d + "/ops"); open(d + "/ops/existing.py", "w").write("keep"); os.makedirs(d + "/n8n"); open(d + "/n8n/wf_ingress.py", "w").write("old")
        r = apply(d); self.assertIn("APPLY251_OK", r.stdout, r.stderr)
        t = tree(d); self.assertTrue(all(p.startswith(("competitor_radar/", "ops/competitor-radar.py", "ops/existing.py", "n8n/wf_ingress.py")) for p in t), t)
        self.assertEqual(open(d + "/n8n/wf_ingress.py").read(), "old"); self.assertEqual(open(d + "/ops/existing.py").read(), "keep")
        for f in os.listdir(os.path.join(R, "service")):
            if f.endswith(".py"): self.assertEqual(open(d + "/competitor_radar/service/" + f, encoding="utf-8").read(), open(os.path.join(R, "service", f), encoding="utf-8").read())
        self.assertEqual(open(d + "/competitor_radar/db/80_competitor_radar.sql", encoding="utf-8").read(), open(os.path.join(R, "db", "80_competitor_radar.sql"), encoding="utf-8").read())
        self.assertTrue(os.access(d + "/ops/competitor-radar.py", os.X_OK)); self.assertFalse(any(p.endswith(".pre251") for p in t))

    def test_idempotent_and_backup_on_change(self):
        d = tempfile.mkdtemp(); apply(d); r = apply(d); self.assertIn("changed=0", r.stdout)
        open(d + "/competitor_radar/service/engine.py", "w").write("# local edit"); r = apply(d); self.assertIn("changed=1", r.stdout); self.assertEqual(open(d + "/competitor_radar/service/engine.py.pre251").read(), "# local edit")

    def test_installed_service_imports_and_runs_from_the_installed_tree(self):
        d = tempfile.mkdtemp(); apply(d)
        code = "import sys; sys.path.insert(0, %r); " % d + "import competitor_radar.service.engine as E, competitor_radar.service.app as A; from competitor_radar.service.store import MemoryStore; e = E.Engine(MemoryStore({'ctx-aaaaaaaa': 't'})); print(e.handle('config', 'ctx-aaaaaaaa', {})[1]['data']['enabled'])"
        r = subprocess.run([sys.executable, "-I", "-c", code], cwd=d + "/", capture_output=True, text=True); self.assertEqual((r.returncode, r.stdout.strip()), (0, "True"), r.stderr)

    def test_installed_ctl_is_the_tested_tool(self):
        d = tempfile.mkdtemp(); apply(d); self.assertEqual(open(d + "/ops/competitor-radar.py", encoding="utf-8").read(), open(os.path.join(R, "deploy", "competitor_radar_ctl.py"), encoding="utf-8").read())
        r = subprocess.run([sys.executable, d + "/ops/competitor-radar.py", "wipe"], capture_output=True, text=True); self.assertEqual(r.returncode, 2)

if __name__ == "__main__":
    unittest.main(verbosity=1)
