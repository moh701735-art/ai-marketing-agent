"""يشغّل اختبارات الواجهة (node) على العقد الحقيقية. python3 -m unittest discover -s smart_audience/tests -p 'test_*.py'"""
import pathlib, shutil, subprocess, sys, unittest

HERE = pathlib.Path(__file__).resolve().parent


@unittest.skipUnless(shutil.which("node"), "node required")
class SmartAudience(unittest.TestCase):
    def test_nodes(self):
        subprocess.run([sys.executable, str(HERE / "dump.py")], check=True, capture_output=True)
        r = subprocess.run(["node", str(HERE / "test_sa.cjs")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("passed", r.stdout)


if __name__ == "__main__":
    unittest.main()
