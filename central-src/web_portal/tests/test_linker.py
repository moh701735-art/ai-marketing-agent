import importlib.util, json, os, unittest
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..")
spec = importlib.util.spec_from_file_location("wl", os.path.join(ROOT, "linker", "web_linker.py")); wl = importlib.util.module_from_spec(spec); spec.loader.exec_module(wl)
TID, RID = "11111111-2222-3333-4444-555555555555", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
CFG = {"TIKTOK_APP_ID": "7688235455380193301", "TIKTOK_APP_SECRET": "supersecretvalue123"}
CODE = "AUTHcode1234567890abc"
TOKEN = "TOKEN_abcdefghijklmnopqrstuv"


class Deps:
    def __init__(self, claim=None, already="0", taken=""):
        self.claim = claim if claim is not None else "%s|%s|%s|web-demo|IQD" % (RID, TID, CODE); self.already = already; self.taken = taken; self.log = []; self.linked = None; self.fail_link = None
    def psql(self, sql, v=None):
        self.log.append((sql, dict(v or {})))
        if sql.startswith("UPDATE web.link_requests r SET status = 'processing'"): return self.claim
        if "count(*) FROM core.ad_accounts" in sql: return self.already + "\n"
        if "SELECT external_id FROM core.ad_accounts" in sql: return self.taken
        return ""
    def do_link(self, slug, tid, token, chosen, info):
        if self.fail_link: raise self.fail_link
        self.linked = (slug, tid, token, list(chosen), dict(info))
    def finish(self):
        return [(v["st"], v["msg"], json.loads(v["res"])) for s, v in self.log if s.startswith("UPDATE web.link_requests SET status = :'st'")]


def run(deps, granted=("7001", "7002"), info=None, exch_err=None, code=CODE):
    ids = ["70010000001", "70010000002"] if granted == ("7001", "7002") else list(granted)
    info = info if info is not None else {ids[0]: ("Acme 1", "IQD"), ids[-1]: ("Acme 2", "IQD")}
    def exch(a, s, c):
        if exch_err: raise wl.Stop(exch_err)
        assert (a, s, c) == (CFG["TIKTOK_APP_ID"], CFG["TIKTOK_APP_SECRET"], CODE); return TOKEN, ids
    out = []; r = wl.process_one(deps, CFG, out.append, exch, lambda t, i: info)
    return r, out, ids


class T(unittest.TestCase):
    def test_01_success_links_all_matching_currency(self):
        d = Deps(); r, out, ids = run(d); self.assertTrue(r); st, msg, res = d.finish()[0]; self.assertEqual(st, "done"); self.assertEqual([a["id"] for a in res["linked"]], ids)
        self.assertEqual(d.linked[:2], ("web-demo", TID)); self.assertEqual(d.linked[3], ids); self.assertIn("خلال ساعة", msg)
        self.assertNotIn(TOKEN, json.dumps(d.log, ensure_ascii=False)); self.assertNotIn(CFG["TIKTOK_APP_SECRET"], json.dumps(d.log)); self.assertTrue(all(TOKEN not in o and CODE not in o for o in out))

    def test_02_no_work(self):
        d = Deps(claim=""); self.assertFalse(wl.process_one(d, CFG, lambda m: None)); self.assertEqual(d.finish(), [])

    def test_03_claim_with_command_tag_line(self):
        d = Deps(claim="%s|%s|%s|web-demo|IQD\nUPDATE 1" % (RID, TID, CODE)); r, out, ids = run(d); self.assertEqual(d.finish()[0][0], "done")

    def test_04_already_linked_blocks_and_never_calls_tiktok(self):
        d = Deps(already="2"); called = []; r = wl.process_one(d, CFG, lambda m: None, lambda *a: called.append(1) or (TOKEN, []), lambda t, i: {})
        st, msg, _ = d.finish()[0]; self.assertEqual(st, "failed"); self.assertIn("مربوط أصلاً", msg); self.assertEqual(called, []); self.assertIsNone(d.linked)

    def test_05_taken_accounts_are_skipped_never_linked(self):
        d = Deps(taken="70010000001\n99999\n"); r, out, ids = run(d); st, msg, res = d.finish()[0]; self.assertEqual(st, "done"); self.assertEqual(d.linked[3], [ids[1]]); self.assertEqual(res["skipped_taken"], 1); self.assertIn("مربوطة بحساب ثاني", msg)

    def test_06_all_taken_fails_without_linking(self):
        d = Deps(taken="70010000001 70010000002"); r, out, ids = run(d); st, msg, res = d.finish()[0]; self.assertEqual(st, "failed"); self.assertIsNone(d.linked); self.assertIn("مربوط بحساب ثاني", msg)

    def test_07_currency_mismatch_skipped(self):
        d = Deps(); info = {"70010000001": ("A", "USD"), "70010000002": ("B", "IQD")}; r, out, ids = run(d, info=info); st, msg, res = d.finish()[0]; self.assertEqual(d.linked[3], ["70010000002"]); self.assertEqual(res["skipped_currency"], 1)
        d2 = Deps(); r, out, ids = run(d2, info={"70010000001": ("A", "USD"), "70010000002": ("B", "USD")}); self.assertEqual(d2.finish()[0][0], "failed"); self.assertIsNone(d2.linked); self.assertIn("عملته غير IQD", d2.finish()[0][1])

    def test_08_empty_tenant_currency_never_links(self):
        d = Deps(claim="%s|%s|%s|web-demo|" % (RID, TID, CODE)); r, out, ids = run(d); self.assertEqual(d.finish()[0][0], "failed"); self.assertIsNone(d.linked)

    def test_09_exchange_failure_message_has_no_secrets(self):
        d = Deps(); r, out, ids = run(d, exch_err="تيك توك رفض الرمز (code=40002): bad %s and %s" % (CODE, CFG["TIKTOK_APP_SECRET"])); st, msg, _ = d.finish()[0]; self.assertEqual(st, "failed"); self.assertNotIn(CODE, msg); self.assertNotIn(CFG["TIKTOK_APP_SECRET"], msg); self.assertIsNone(d.linked)

    def test_10_no_granted_accounts(self):
        d = Deps(); r, out, ids = run(d, granted=(), info={}); self.assertEqual(d.finish()[0][0], "failed"); self.assertIn("ما وصلنا أي حساب", d.finish()[0][1])

    def test_11_unreadable_accounts_not_linked(self):
        d = Deps(); r, out, ids = run(d, info={"70010000002": ("B", "IQD")}); res = d.finish()[0][2]; self.assertEqual(d.linked[3], ["70010000002"]); self.assertEqual(res["skipped_unreadable"], 1)

    def test_12_link_failure_reports_nothing_linked(self):
        d = Deps(); d.fail_link = wl.Stop("فشل حفظ الربط (x). ما انربط شي."); r, out, ids = run(d); st, msg, _ = d.finish()[0]; self.assertEqual(st, "failed"); self.assertIn("ما انربط شي", msg)

    def test_13_bad_rows_rejected_before_any_call(self):
        for claim in ("%s|%s|%s|Bad Slug|IQD" % (RID, TID, CODE), "%s|%s|bad code!|web-demo|IQD" % (RID, TID), "%s|not-a-uuid|%s|web-demo|IQD" % (RID, CODE)):
            d = Deps(claim=claim); called = []; wl.process_one(d, CFG, lambda m: None, lambda *a: called.append(1), lambda *a: {}); self.assertEqual(called, [], claim); self.assertEqual(d.finish()[0][0], "failed")

    def test_14_unexpected_exception_is_contained_and_code_cleared(self):
        d = Deps(); out = []
        def boom(*a): raise ZeroDivisionError("x " + CODE)
        wl.process_one(d, CFG, out.append, boom, lambda *a: {}); st, msg, _ = d.finish()[0]; self.assertEqual(st, "failed"); self.assertNotIn(CODE, msg); self.assertTrue(all(CODE not in o for o in out))
        self.assertIn("auth_code = NULL", wl.FINISH_SQL)

    def test_15_sweep_and_load_cfg(self):
        self.assertIn("auth_code = NULL", wl.SWEEP_SQL); self.assertIn("interval '5 minutes'", wl.SWEEP_SQL); self.assertIn("interval '15 minutes'", wl.SWEEP_SQL)
        self.assertEqual(wl.load_cfg(CFG)["TIKTOK_APP_ID"], CFG["TIKTOK_APP_ID"])
        with self.assertRaises(SystemExit): wl.load_cfg({"TIKTOK_APP_ID": "abc", "TIKTOK_APP_SECRET": "x"})

    def test_16_account_info_and_exchange_shapes(self):
        calls = []
        def fake(url, body=None, token=None):
            calls.append((url, body, token))
            if "oauth2/access_token" in url: return {"code": 0, "data": {"access_token": "T" * 30, "advertiser_ids": [7001, "7002x", "700300000001"]}}
            return {"code": 0, "data": {"list": [{"advertiser_id": 111, "name": "N" * 100, "currency": "iqd"}]}}
        tok, ids = wl.exchange("1" * 10, "secret1234", "CODE12345", fake); self.assertEqual((tok, ids), ("T" * 30, ["700300000001"])); self.assertEqual(calls[0][1], {"app_id": "1" * 10, "secret": "secret1234", "auth_code": "CODE12345"})
        info = wl.account_info(tok, ["111"], fake); self.assertEqual(info, {"111": ("N" * 80, "IQD")}); self.assertEqual(calls[1][2], tok)
        with self.assertRaises(wl.Stop): wl.exchange("1" * 10, "secret1234", "CODE12345", lambda *a, **k: {"code": 40002, "message": "bad"})
if __name__ == "__main__": unittest.main()
