"""حماية الانحدار (المرحلة 1): كل تغيير بالمستودع مقابل HEAD لازم يكون داخل central-src/competitor_radar/ (أو توثيق out/ و CLAUDE.md الاختياري).
أي ملف قديم تغيّر = فشل. يتخطى نفسه خارج git."""
import os, subprocess, unittest

ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__))).stdout.strip()
ALLOWED = ("central-src/competitor_radar/", "out/ops/", "out/central-knowledge.md", "central-src/ops/p250-", "central-src/ops/p251-", "out/p250s.txt", "out/p251s.txt")


@unittest.skipUnless(ROOT, "git required")
class Untouched(unittest.TestCase):
    def changed(self):
        a = subprocess.run(["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.split()
        b = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], capture_output=True, text=True, cwd=ROOT).stdout.split()
        return sorted(set(a + b))

    def test_only_new_feature_files_changed(self):
        bad = [p for p in self.changed() if not p.startswith(ALLOWED)]
        self.assertEqual(bad, [], "ملفات قديمة تغيّرت: %s" % bad)

    def test_no_old_file_modified_or_deleted(self):
        r = subprocess.run(["git", "diff", "--name-status", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.splitlines()
        bad = [l for l in r if not l.split("\t", 1)[1].startswith(ALLOWED)]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
