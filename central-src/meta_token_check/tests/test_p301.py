import importlib.util, os, subprocess, sys, tempfile, unittest, re, base64, lzma
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..", "..")
subprocess.run([sys.executable, os.path.join(ROOT, "meta_token_check", "build_p301.py")], check=True)
spec = importlib.util.spec_from_file_location("mtc", os.path.join(ROOT, "ops", "meta-token-check.py")); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
NOW = 1_800_000_000
TOK = "EAAXSECRETTOKEN1234567890"
ALL = list(m.NEED)
def dbg(exp, scopes=None, valid=True, extra=None):
    return {"data": {"is_valid": valid, "type": "USER", "app_id": "1960985577901430", "expires_at": exp, "scopes": ALL if scopes is None else scopes, "data_access_expires_at": NOW + 90 * 86400, **(extra or {})}}
def go(resp, me=None):
    lines = []
    def get(url):
        if "debug_token" in url: return resp
        return me if me is not None else {"error": {"message": "x", "code": 190}}
    rc = m.run(TOK, get=get, out=lines.append, now=NOW); return rc, "\n".join(lines)
class T(unittest.TestCase):
    def test_long_ok(self):
        rc, o = go(dbg(NOW + 60 * 86400)); self.assertEqual(rc, 0); self.assertIn("VERDICT=OK", o); self.assertIn("60.0 days", o)
    def test_short_refused(self):
        rc, o = go(dbg(NOW + 5400)); self.assertEqual(rc, 2); self.assertIn("VERDICT=REFUSE", o); self.assertIn("SHORT_LIVED_TOKEN", o); self.assertIn("1.5 hours", o)
    def test_29_days_refused_30_ok(self):
        self.assertEqual(go(dbg(NOW + 29 * 86400))[0], 2); self.assertEqual(go(dbg(NOW + 30 * 86400))[0], 0)
    def test_never_expires(self):
        rc, o = go(dbg(0)); self.assertEqual(rc, 0); self.assertIn("never", o)
    def test_missing_scopes_refused(self):
        rc, o = go(dbg(NOW + 60 * 86400, scopes=["ads_read"])); self.assertEqual(rc, 2); self.assertIn("MISSING_PERMISSIONS", o); self.assertIn("MISSING pages_manage_ads", o)
    def test_invalid(self):
        rc, o = go(dbg(0, valid=False)); self.assertEqual(rc, 2); self.assertIn("VERDICT=REFUSE", o)
    def test_debug_error_but_token_works_unknown(self):
        rc, o = go({"error": {"message": "no access " + TOK, "code": 100}}, me={"id": "123", "name": "x"}); self.assertEqual(rc, 3); self.assertIn("VERDICT=UNKNOWN", o)
    def test_rejected(self):
        rc, o = go({"error": {"message": "bad", "code": 190}}); self.assertEqual(rc, 2); self.assertIn("token_rejected_by_meta", o)
    def test_unknown_expiry(self):
        rc, o = go(dbg(None)); self.assertEqual(rc, 3)
    def test_token_never_printed(self):
        for resp in (dbg(NOW + 60 * 86400), dbg(NOW + 100), {"error": {"message": "bad " + TOK + " access_token=" + TOK, "code": 1}}):
            self.assertNotIn(TOK, go(resp, me={"id": "1"})[1])
    def test_installer(self):
        d = tempfile.mkdtemp(); os.makedirs(d + "/ops")
        s = open(os.path.join(ROOT, "..", "out", "p301s.txt")).read(); self.assertEqual(s.count("\n"), 1)
        body = lzma.decompress(base64.b64decode(re.search(r"echo '([^']+)'", s).group(1))).decode()
        run = lambda: subprocess.run([sys.executable], input=body, env={**os.environ, "P301_BASE": d + "/"}, capture_output=True, text=True)
        r = run(); self.assertIn("APPLY301_OK ops/meta-token-check.py installed", r.stdout, r.stderr); self.assertIn("changed=0", run().stdout)
        self.assertEqual(open(d + "/ops/meta-token-check.py").read(), open(os.path.join(ROOT, "ops", "meta-token-check.py")).read())
        e = tempfile.mkdtemp(); r = subprocess.run([sys.executable], input=body, env={**os.environ, "P301_BASE": e + "/"}, capture_output=True, text=True); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr)
if __name__ == "__main__": unittest.main()
