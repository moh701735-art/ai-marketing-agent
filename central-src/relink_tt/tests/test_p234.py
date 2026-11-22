import importlib.util, os, unittest
H = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("trl", os.path.join(H, "test_relink.py")); trl = importlib.util.module_from_spec(spec); spec.loader.exec_module(trl)
RT = "REFRESH_SECRET_XYZ_123456"


def call_with(extra):
    base = trl.mkcall()
    def call(url, body=None, token=None, timeout=30):
        r = base(url, body, token, timeout)
        if "oauth2/access_token" in url: r["data"].update(extra)
        return r
    call.calls = base.calls
    return call


class T(unittest.TestCase):
    def test_01_reports_expiry_fields_without_secrets(self):
        at, call, r, err, out = trl.run(call=call_with({"expires_in": 86400, "refresh_token": RT, "refresh_token_expires_in": 31536000, "scope": [1, 2, 3], "token_type": "Bearer"}))
        self.assertIsNone(err); self.assertIn("expires_in=86400", out); self.assertIn("refresh_token_expires_in=31536000", out); self.assertIn("scope=[1, 2, 3]", out)
        self.assertIn("refresh_token(str, طول %d)" % len(RT), out); self.assertIn("access_token(str, طول %d)" % len(trl.TOKEN), out); self.assertIn("advertiser_ids(3)", out)
        for secret in (RT, trl.TOKEN, trl.SECRET, trl.CODE): self.assertNotIn(secret, out)
    def test_02_plain_response_lists_only_the_two_known_fields(self):
        at, call, r, err, out = trl.run(); self.assertIn("حقول رد تيك توك (بدون أسرار): access_token(str, طول", out); self.assertNotIn("expires_in", out)
    def test_03_long_strings_and_odd_types_never_printed(self):
        s = trl.rtt.meta_summary({"note": "x" * 50, "obj": {"a": 1}, "flag": True, "token_type": "Bearer", "code_x": "short", "ids": [1, "a"]})
        self.assertNotIn("x" * 20, s); self.assertIn("flag=True", s); self.assertIn("token_type(str", s); self.assertIn("code_x(str", s); self.assertIn("ids(list", s); self.assertIn("obj(dict", s)
    def test_04_apply_behaviour_unchanged(self):
        at, call, r, err, out = trl.run(apply=True); self.assertTrue(r["written"]); self.assertEqual(len(at.vaults), 1); self.assertEqual(at.vaults[0][0]["value"], trl.TOKEN)


if __name__ == "__main__":
    unittest.main(verbosity=2)
