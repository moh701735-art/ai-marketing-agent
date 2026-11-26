import importlib.util, os, subprocess, sys, tempfile, unittest, re
H = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(H, "..", "..")
spec = importlib.util.spec_from_file_location("mp", os.path.join(ROOT, "ops", "meta-accounts-print.py"))
mp = importlib.util.module_from_spec(spec); spec.loader.exec_module(mp)
TOK = "EAAB" + "y" * 60
def A(i, st=1, cur="USD", biz=None):
    d = {"account_id": str(5000 + i), "name": "a%d" % i, "currency": cur, "account_status": st}
    if biz: d["business"] = {"name": biz}
    return d
def graph(me_accts, bizs, owned, client, err_biz=None):
    def get(url):
        assert "access_token" in url
        if "/me?" in url: return {"id": "1", "name": "Noor"}
        if "me/permissions" in url: return {"data": [{"permission": p, "status": "granted"} for p in mp.NEED]}
        if "me/accounts" in url: return {"data": []}
        if "me/adaccounts" in url: return {"data": me_accts}
        if "me/businesses" in url: return {"data": bizs}
        m = re.search(r"/v[\d.]+/(\d+)/(owned_ad_accounts|client_ad_accounts)\?", url)
        if m:
            bid, edge = m.groups()
            if bid == err_biz and edge == "client_ad_accounts": return {"error": {"message": "(#200) no permission " + TOK, "code": 200}}
            src = owned if edge == "owned_ad_accounts" else client
            return {"data": src.get(bid, [])}
        raise AssertionError(url)
    return get
def go(g):
    buf = []; rc = mp.run(TOK, get=g, out=buf.append); return rc, "\n".join(buf)

class T(unittest.TestCase):
    def test_business_accounts_found_and_deduped(self):
        g = graph([A(1)], [{"id": "11", "name": "Sidra"}, {"id": "12", "name": "Noor Med"}, {"id": "13", "name": "Empty"}],
                  {"11": [A(1), A(2)], "12": [A(3, cur="IQD")]}, {"12": [A(4, st=3)], "13": []})
        rc, o = go(g)
        self.assertEqual(rc, 0)
        self.assertIn("businesses seen by this token: 3", o)
        self.assertIn("ad accounts seen by this token: 4", o)
        self.assertEqual(sorted(re.search(r"IDS: (.*)", o).group(1).split()), ["5001", "5002", "5003"])
        self.assertIn("NOT usable (UNSETTLED)", o)
        self.assertIn("Sidra", o); self.assertIn("business 13  Empty: 0 ad accounts", o)
    def test_error_in_one_business_not_fatal_and_scrubbed(self):
        g = graph([], [{"id": "11", "name": "A"}, {"id": "12", "name": "B"}], {"11": [A(1)], "12": [A(2)]}, {}, err_biz="12")
        rc, o = go(g)
        self.assertEqual(rc, 0); self.assertIn("IDS: 5001 5002", o); self.assertIn("client_ad_accounts: (#200)", o); self.assertNotIn(TOK, o)
    def test_20_businesses_one_each(self):
        bizs = [{"id": str(100 + i), "name": "Biz%d" % i} for i in range(20)]
        owned = {str(100 + i): [A(i)] for i in range(20)}
        _, o = go(graph([], bizs, owned, {}))
        self.assertIn("ad accounts seen by this token: 20", o); self.assertIn("usable (ACTIVE + USD/IQD): 20 of 20", o)
    def test_no_businesses_falls_back_to_me(self):
        _, o = go(graph([A(1)], [], {}, {}))
        self.assertIn("businesses seen by this token: 0", o); self.assertIn("IDS: 5001", o)
    def test_business_list_error_reported(self):
        def g(url):
            if "me/businesses" in url: return {"error": {"message": "x " + TOK, "code": 10}}
            return graph([A(1)], [], {}, {})(url)
        _, o = go(g); self.assertIn("read error", o); self.assertNotIn(TOK, o); self.assertIn("IDS: 5001", o)

PATCH = os.path.join(ROOT, "ops", "p291-meta-printer.py.txt")
class P(unittest.TestCase):
    def run_patch(self, base):
        return subprocess.run([sys.executable, "-"], input=open(PATCH, encoding="utf-8").read(), text=True, capture_output=True, env=dict(os.environ, P291_BASE=base + "/"))
    def test_apply_backup_idempotent(self):
        d = tempfile.mkdtemp(); os.makedirs(d + "/ops"); old = "# old printer\n"; open(d + "/ops/meta-accounts-print.py", "w").write(old)
        r = self.run_patch(d); self.assertIn("APPLY291_OK", r.stdout, r.stderr)
        self.assertEqual(open(d + "/ops/meta-accounts-print.py.pre291").read(), old)
        self.assertIn("p291", open(d + "/ops/meta-accounts-print.py", encoding="utf-8").read())
        r2 = self.run_patch(d); self.assertIn("changed=0", r2.stdout)
    def test_fresh_install_without_old_file(self):
        d = tempfile.mkdtemp(); os.makedirs(d + "/ops"); r = self.run_patch(d); self.assertIn("APPLY291_OK", r.stdout, r.stderr)
    def test_no_ops_dir_fails_closed(self):
        r = self.run_patch(tempfile.mkdtemp()); self.assertIn("PATCH FAIL", r.stderr + r.stdout)
if __name__ == "__main__": unittest.main()
