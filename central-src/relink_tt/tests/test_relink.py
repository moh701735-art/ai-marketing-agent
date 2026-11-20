import importlib.util, io, json, os, sys, unittest, contextlib
P = os.path.join(os.path.dirname(__file__), "..", "..", "ops", "relink-tiktok-token.py")
spec = importlib.util.spec_from_file_location("rtt", P); rtt = importlib.util.module_from_spec(spec); spec.loader.exec_module(rtt)
ACC = ["7709944497303732244", "7709945775719235636", "7709946626143567878"]
TOKEN = "TOK_SECRET_ABCDEF"; SECRET = "APPSECRET_123456"; CODE = "AUTHCODE_999999"


class FakeAt:
    def __init__(self, conns=None, accts=None, tid="t-1"):
        self.conns = conns if conns is not None else ["c-1|tt_agency_57c3e0e4|ref-ammar-tt-5de"]
        self.accts = ACC if accts is None else accts; self.tid = tid; self.vaults = []; self.writes = []; self.sqls = []
    def psql(self, db, sql, vars_=None, tx=True):
        self.sqls.append(sql)
        if sql.startswith("SELECT tenant_id"): return self.tid + "\n"
        if "FROM core.platform_connections" in sql: return "\n".join(self.conns) + "\n"
        if "FROM core.ad_accounts" in sql: return "\n".join(self.accts) + "\n"
        if sql.startswith("UPDATE"): self.writes.append((sql, vars_)); return ""
        raise AssertionError("unexpected sql: " + sql)
    def vault(self, items): self.vaults.append(items)


def mkcall(adv_ids=ACC, readable=ACC, code_ok=True, info_ok=True):
    calls = []
    def call(url, body=None, token=None, timeout=30):
        calls.append((url, body, token))
        if "oauth2/access_token" in url:
            if not code_ok: return {"code": 40002, "message": "invalid auth_code " + CODE}
            return {"code": 0, "data": {"access_token": TOKEN, "advertiser_ids": adv_ids}}
        if "advertiser/info" in url:
            if not info_ok: return {"code": 40001, "message": "no permission"}
            return {"code": 0, "data": {"list": [{"advertiser_id": a, "name": "n" + a[-3:], "currency": "IQD", "status": "STATUS_ENABLE"} for a in readable]}}
        raise AssertionError(url)
    call.calls = calls
    return call


def run(at=None, call=None, apply=False, new_ref=False, slug="ammar-mohmaed", app_id="7000000000001"):
    at = at or FakeAt(); call = call or mkcall(); buf = []
    try: r = rtt.run(slug, app_id, SECRET, CODE, apply, new_ref, at, "central", call, buf.append); err = None
    except rtt.Stop as e: r = None; err = str(e)
    return at, call, r, err, "\n".join(buf)


class T(unittest.TestCase):
    def test_01_dry_run_writes_nothing(self):
        at, call, r, err, out = run()
        self.assertIsNone(err); self.assertFalse(r["written"]); self.assertEqual(at.vaults, []); self.assertEqual(at.writes, []); self.assertIn("dry-run", out)
    def test_02_apply_same_ref_one_vault_put(self):
        at, call, r, err, out = run(apply=True)
        self.assertIsNone(err); self.assertTrue(r["written"]); self.assertEqual(len(at.vaults), 1)
        v = at.vaults[0][0]; self.assertEqual(v["secret_ref"], "ref-ammar-tt-5de"); self.assertEqual(v["kind"], "tiktok_token"); self.assertEqual(v["value"], TOKEN); self.assertEqual(v["tenant_id"], "t-1")
        self.assertEqual(at.writes, [])   # no DB writes: connection/accounts untouched
    def test_03_missing_account_stops_without_write(self):
        at, call, r, err, out = run(call=mkcall(adv_ids=ACC[:2], readable=ACC[:2]), apply=True)
        self.assertIn("ما يغطي", err); self.assertEqual(at.vaults, []); self.assertEqual(at.writes, [])
    def test_04_unreadable_account_stops(self):
        at, call, r, err, out = run(call=mkcall(readable=ACC[:1]), apply=True)
        self.assertIn("ما يغطي", err); self.assertEqual(at.vaults, [])
    def test_05_info_failure_stops(self):
        at, call, r, err, out = run(call=mkcall(info_ok=False), apply=True)
        self.assertIsNotNone(err); self.assertEqual(at.vaults, [])
    def test_06_bad_code_message_without_secrets(self):
        at, call, r, err, out = run(call=mkcall(code_ok=False), apply=True)
        self.assertIn("رفض الكود", err); self.assertNotIn(CODE, err); self.assertEqual(at.vaults, [])
    def test_07_two_or_zero_active_connections_die(self):
        for conns in (["a|x|r1", "b|y|r2"], []):
            at, call, r, err, out = run(at=FakeAt(conns=conns), apply=True)
            self.assertIn("**واحد**", err); self.assertEqual(at.vaults, []); self.assertEqual(call.calls, [])   # no TikTok call before DB sanity
    def test_08_no_accounts_die(self):
        at, call, r, err, out = run(at=FakeAt(accts=[]), apply=True); self.assertIn("حسابات", err); self.assertEqual(at.vaults, [])
    def test_09_unknown_tenant_die(self):
        at, call, r, err, out = run(at=FakeAt(tid=""), apply=True); self.assertIn("ما لقيت عميل", err)
    def test_10_new_ref_updates_connection_only(self):
        at, call, r, err, out = run(apply=True, new_ref=True)
        self.assertIsNone(err); ref = at.vaults[0][0]["secret_ref"]; self.assertTrue(ref.startswith("ref-ammar-mohmaed-tt-")); self.assertNotEqual(ref, "ref-ammar-tt-5de")
        self.assertEqual(len(at.writes), 1); sql, vars_ = at.writes[0]; self.assertIn("UPDATE core.platform_connections SET secret_ref", sql); self.assertEqual(vars_["nref"], ref); self.assertEqual(vars_["cid"], "c-1")
        self.assertNotIn("ad_accounts", sql)
    def test_11_secrets_never_printed(self):
        for apply in (False, True):
            at, call, r, err, out = run(apply=apply); blob = out + (err or "")
            for s in (TOKEN, SECRET, CODE): self.assertNotIn(s, blob)
    def test_12_input_validation(self):
        self.assertIn("slug", run(slug="Bad Slug!")[3]); self.assertIn("App ID", run(app_id="abc")[3])
    def test_13_token_goes_only_in_header_and_exchange_body(self):
        at, call, r, err, out = run(apply=True)
        for url, body, token in call.calls:
            if "oauth2" in url: self.assertEqual(body["auth_code"], CODE)
            else: self.assertEqual(token, TOKEN); self.assertNotIn(TOKEN, url)
    def test_14_extra_advertisers_in_token_do_not_matter(self):
        at, call, r, err, out = run(call=mkcall(adv_ids=ACC + ["7700000000000000001"]), apply=True); self.assertIsNone(err); self.assertEqual(len(at.vaults), 1)
    def test_15_main_scrubs_secrets_from_error(self):
        # main() path: Stop message containing the secret is scrubbed
        self.assertNotIn(CODE, rtt.scrub("x " + CODE + " y", SECRET, CODE)); self.assertIn("***", rtt.scrub("x " + CODE, CODE))





class TAsk(unittest.TestCase):
    def test_16_ask_reprompts_on_empty_and_bad(self):
        vals = iter(["", "  ", "Bad Slug!", "ammar-mohmaed"]); out = []
        with contextlib.redirect_stdout(io.StringIO()):
            v = rtt.ask(lambda p: next(vals), "p", rtt.SLUG_RE)
        self.assertEqual(v, "ammar-mohmaed")
    def test_17_ask_gives_up_without_writing(self):
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit): rtt.ask(lambda p: "", "p", rtt.SLUG_RE, tries=3)
    def test_18_main_with_stray_blank_line_still_runs(self):
        # simulate main()'s prompts through ask(): first blank line (stray Enter from pasting) then real values
        seq = iter(["", "ammar-mohmaed", "7688235455380193301"]); sec = iter(["", SECRET, CODE])
        with contextlib.redirect_stdout(io.StringIO()):
            slug = rtt.ask(lambda p: next(seq), "s", rtt.SLUG_RE); app = rtt.ask(lambda p: next(seq), "a", __import__("re").compile(r"[0-9]{5,24}"))
            s = rtt.ask(lambda p: next(sec), "x", __import__("re").compile(r"\S{8,200}")); c = rtt.ask(lambda p: next(sec), "y", __import__("re").compile(r"\S{8,400}"))
        self.assertEqual((slug, app, s, c), ("ammar-mohmaed", "7688235455380193301", SECRET, CODE))


if __name__ == "__main__": unittest.main(verbosity=1)
