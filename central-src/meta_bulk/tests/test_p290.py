import importlib.util, os, subprocess, sys, tempfile, unittest, json
H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(H, "..", "..")
spec = importlib.util.spec_from_file_location("mp", os.path.join(ROOT, "ops", "meta-accounts-print.py"))
mp = importlib.util.module_from_spec(spec); spec.loader.exec_module(mp)
TOK = "EAAB" + "x" * 60
PATCH = os.path.join(ROOT, "ops", "p290-meta-bulk.py.txt")

def acct(i, st=1, cur="USD", biz="B%d"):
    return {"account_id": str(1000 + i), "id": "act_%d" % (1000 + i), "name": "acc%d" % i, "currency": cur, "account_status": st, "business": {"name": biz % i if "%d" in biz else biz}}

def fake(pages_accts, perms=None, page_list=None, me_ok=True):
    def get(url):
        assert TOK in url or "access_token" in url
        if "/me?" in url: return {"id": "99", "name": "Omar"} if me_ok else {"error": {"message": "Invalid OAuth access token " + TOK, "code": 190}}
        if "me/permissions" in url: return {"data": [{"permission": p, "status": "granted"} for p in (perms or mp.NEED)]}
        if "me/accounts" in url: return {"data": page_list or [{"id": "7", "name": "Pg"}]}
        if "me/adaccounts" in url:
            if "after=2" in url: return {"data": pages_accts[100:]}
            nxt = {"paging": {"next": url + "&after=2"}} if len(pages_accts) > 100 else {}
            return dict({"data": pages_accts[:100]}, **nxt)
        raise AssertionError(url)
    return get

def go(get):
    buf = []
    rc = mp.run(TOK, get=get, out=buf.append)
    return rc, "\n".join(buf)

class Helper(unittest.TestCase):
    def test_table_and_ids(self):
        a = [acct(1), acct(2, st=3), acct(3, cur="EUR"), acct(4, cur="IQD")]
        rc, o = go(fake(a))
        self.assertEqual(rc, 0)
        self.assertIn("IDS: 1001 1004", o)
        self.assertIn("NOT usable (UNSETTLED)", o); self.assertIn("NOT usable (currency EUR)", o)
        self.assertIn("usable (ACTIVE + USD/IQD): 2 of 4", o)
    def test_pagination_and_30_split(self):
        a = [acct(i) for i in range(130)]
        rc, o = go(fake(a))
        self.assertIn("ad accounts seen by this token: 130", o)
        ids = [l for l in o.split("\n") if l.startswith("IDS: ")]
        self.assertEqual(len(ids), 5)  # 130 -> 30+30+30+30+10
        self.assertEqual(len(ids[0].split()) - 1, 30)
        self.assertIn("NOTE: more than 30", o)
    def test_duplicates_deduped(self):
        a = [acct(1), acct(1)]
        _, o = go(fake(a)); self.assertIn("seen by this token: 1", o)
    def test_token_never_printed_and_bad_token(self):
        rc, o = go(fake([], me_ok=False))
        self.assertEqual(rc, 2); self.assertNotIn(TOK, o); self.assertIn("FAIL", o)
        _, o = go(fake([acct(1)])); self.assertNotIn(TOK, o)
    def test_missing_permission_marked(self):
        _, o = go(fake([acct(1)], perms=["ads_read"]))
        self.assertIn("MISSING pages_read_engagement", o); self.assertIn("OK   ads_read", o)
    def test_no_usable(self):
        _, o = go(fake([acct(1, st=2)])); self.assertIn("IDS: (none)", o)
    def test_error_midway_reported(self):
        calls = {"n": 0}
        def get(url):
            if "me/adaccounts" in url:
                calls["n"] += 1
                if calls["n"] == 1: return {"data": [acct(1)], "paging": {"next": url + "&x=1"}}
                return {"error": {"message": "rate limit " + TOK, "code": 17}}
            return fake([])(url)
        _, o = go(get)
        self.assertIn("read error after 1 rows", o); self.assertNotIn(TOK, o); self.assertIn("IDS: 1001", o)
    def test_scrub_url_encoded(self):
        self.assertNotIn("abc", mp.scrub("x access_token=abc&y", "zzzzzzz"))
    def test_ascii_only_output_lines_have_no_secret(self):
        _, o = go(fake([acct(1)]))
        self.assertNotIn("access_token", o)

SYN = '''import sys
def do_list(form):
    out = [a for a in form.get("acc","").split()]
    if len(out) > 5:
        return form_page("حتى 5 حسابات بالمرة الوحدة")
    pages = graph("/me/accounts?limit=25&fields=id,name")
    return out
'''
class Patch(unittest.TestCase):
    def run_patch(self, base, expect_ok=True):
        r = subprocess.run([sys.executable, "-"], input=open(PATCH, encoding="utf-8").read(), text=True, capture_output=True,
                           env=dict(os.environ, P290_BASE=base + "/"))
        return r
    def mk(self, text):
        d = tempfile.mkdtemp(); os.makedirs(d + "/ops")
        open(d + "/ops/link-meta-web.py", "w", encoding="utf-8").write(text); return d
    def test_apply_idempotent_backup(self):
        d = self.mk(SYN); r = self.run_patch(d)
        self.assertIn("APPLY290_OK link-meta-web", r.stdout, r.stderr)
        n = open(d + "/ops/link-meta-web.py", encoding="utf-8").read()
        self.assertIn("len(out) > 30", n); self.assertIn("limit=100", n); self.assertNotIn("limit=25", n)
        self.assertIn("حتى 30 حسابات", n); self.assertNotIn("> 5", n)
        self.assertEqual(open(d + "/ops/link-meta-web.py.pre290", encoding="utf-8").read(), SYN)
        self.assertTrue(os.path.exists(d + "/ops/meta-accounts-print.py"))
        compile(n, "x", "exec")
        r2 = self.run_patch(d); self.assertIn("changed=0", r2.stdout)
    def test_fail_closed_missing_anchor(self):
        d = self.mk(SYN.replace("len(out) > 5", "len(out) > 7")); before = open(d + "/ops/link-meta-web.py").read()
        r = self.run_patch(d)
        self.assertIn("PATCH FAIL (nothing written)", r.stderr + r.stdout)
        self.assertEqual(open(d + "/ops/link-meta-web.py").read(), before)
        self.assertFalse(os.path.exists(d + "/ops/link-meta-web.py.pre290")); self.assertFalse(os.path.exists(d + "/ops/meta-accounts-print.py"))
    def test_fail_closed_ambiguous_limit(self):
        d = self.mk(SYN + "x = 'me/accounts?limit=25'\n"); r = self.run_patch(d)
        self.assertIn("PATCH FAIL", r.stderr + r.stdout); self.assertIn("pages limit anchor count=2", r.stderr + r.stdout)
    def test_missing_file(self):
        d = tempfile.mkdtemp(); os.makedirs(d + "/ops"); r = self.run_patch(d); self.assertIn("PATCH FAIL", r.stderr + r.stdout)
    def test_one_liner_roundtrip(self):
        line = open(os.path.join(ROOT, "..", "out", "p290s.txt")).read()
        self.assertTrue(line.startswith("cd /opt/central && echo '")); self.assertEqual(line.count("\n"), 1)

if __name__ == "__main__":
    unittest.main()
