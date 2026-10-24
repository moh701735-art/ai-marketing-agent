import logging, io, os, sys, unittest, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cryptography.exceptions import InvalidTag
import envelope, redact, hmac_auth

TG = "123456789:AAH_fake-telegram-token_abcdefghijklmnop12345"
META = "EAAGm0PX4ZCpsBO" + "x" * 40
TT = "0123456789abcdef0123456789abcdef01234567"


class Envelope(unittest.TestCase):
    def setUp(self):
        self.kek = os.urandom(32)
        self.s = envelope.seal(b"secret-A", self.kek, "t1", "tiktok", 1, "ref1")

    def test_roundtrip(self):
        self.assertEqual(envelope.open_(self.s, self.kek, "t1", "tiktok", 1, "ref1"), b"secret-A")

    def test_cross_tenant_fails(self):       # نسخ سر عميل لصف عميل آخر
        with self.assertRaises(InvalidTag):
            envelope.open_(self.s, self.kek, "t2", "tiktok", 1, "ref1")

    def test_wrong_kind_version_ref_fail(self):
        for args in [("t1", "meta", 1, "ref1"), ("t1", "tiktok", 2, "ref1")]:
            with self.assertRaises(InvalidTag):
                envelope.open_(self.s, self.kek, *args)
        with self.assertRaises(InvalidTag):
            envelope.open_(self.s, self.kek, "t1", "tiktok", 1, "ref2")

    def test_tamper_ciphertext(self):
        ct = bytearray(self.s.ciphertext); ct[-1] ^= 1
        with self.assertRaises(InvalidTag):
            envelope.open_(envelope.Sealed(bytes(ct), self.s.dek_wrapped), self.kek, "t1", "tiktok", 1, "ref1")

    def test_tamper_wrapped_dek(self):
        w = bytearray(self.s.dek_wrapped); w[-1] ^= 1
        with self.assertRaises(InvalidTag):
            envelope.open_(envelope.Sealed(self.s.ciphertext, bytes(w)), self.kek, "t1", "tiktok", 1, "ref1")

    def test_wrong_kek(self):
        with self.assertRaises(InvalidTag):
            envelope.open_(self.s, os.urandom(32), "t1", "tiktok", 1, "ref1")

    def test_unique_nonce_dek(self):
        s2 = envelope.seal(b"secret-A", self.kek, "t1", "tiktok", 1, "ref1")
        self.assertNotEqual(self.s.ciphertext, s2.ciphertext)
        self.assertNotEqual(self.s.dek_wrapped, s2.dek_wrapped)

    def test_plaintext_not_in_ciphertext(self):
        self.assertNotIn(b"secret-A", self.s.ciphertext + self.s.dek_wrapped)

    def test_rotation_rewrap_keeps_ciphertext(self):
        new = os.urandom(32)
        r = envelope.rewrap(self.s, self.kek, new, "ref1")
        self.assertEqual(r.ciphertext, self.s.ciphertext)
        self.assertEqual(envelope.open_(r, new, "t1", "tiktok", 1, "ref1"), b"secret-A")
        with self.assertRaises(InvalidTag):
            envelope.open_(r, self.kek, "t1", "tiktok", 1, "ref1")

    def test_bad_kek_length_and_aad_delimiter(self):
        with self.assertRaises(ValueError):
            envelope.load_kek("AAAA")
        with self.assertRaises(ValueError):
            envelope.seal(b"x", self.kek, "t1|x", "k", 1, "r")


class Redaction(unittest.TestCase):
    def test_patterns(self):
        for s in [TG, META, TT, f"https://api.telegram.org/bot{TG}/sendMessage", "Authorization: Bearer abcdefghijklmnop1234",
                  "https://x/cb?code=SUPERSECRETCODE&state=1", "Access-Token: " + TT, "client_secret=abc123xyz"]:
            out = redact.redact_text(f"err {s} end")
            for leak in [TG, META, TT, "SUPERSECRETCODE", "abcdefghijklmnop1234", "abc123xyz"]:
                self.assertNotIn(leak, out)

    def test_nested(self):
        o = redact.redact({"a": {"access_token": "zzz", "list": [{"Authorization": "Bearer q"}, f"x {TG}"]}, "ok": 1})
        txt = json.dumps(o)
        self.assertNotIn("zzz", txt); self.assertNotIn(TG, txt); self.assertEqual(o["ok"], 1)

    def test_known_secret_exact_match(self):
        redact.KNOWN.add("weird-format-secret-value")
        self.assertNotIn("weird-format-secret-value", redact.redact_text("boom weird-format-secret-value!"))

    def test_exception(self):
        self.assertNotIn(TG, redact.redact(RuntimeError(f"failed {TG}")))

    def test_logging_filter_msg_args_traceback(self):
        buf = io.StringIO(); h = logging.StreamHandler(buf); h.addFilter(redact.RedactingFilter())
        lg = logging.getLogger("t_redact"); lg.handlers = [h]; lg.propagate = False; lg.setLevel(logging.DEBUG)
        lg.info("token %s", TG)
        try:
            raise ValueError(f"url https://graph.facebook.com/?access_token={META}")
        except ValueError:
            lg.exception("fail")
        out = buf.getvalue()
        self.assertNotIn(TG, out); self.assertNotIn(META, out); self.assertIn("[REDACTED]", out)

    def test_no_false_positive_on_normal_text(self):
        self.assertEqual(redact.redact_text("campaign 123 created ok"), "campaign 123 created ok")


class Hmac(unittest.TestCase):
    def setUp(self):
        self.t = [1000.0]
        self.key = os.urandom(32)
        self.v = hmac_auth.Verifier(self.key, 60, clock=lambda: self.t[0])
        self.body = b'{"a":1}'; self.n = "n" * 16

    def sig(self, body=None, ts=1000, nonce=None):
        return hmac_auth.sign(self.key, body or self.body, ts, nonce or self.n)

    def test_valid(self):
        self.assertTrue(self.v.verify(self.body, 1000, self.n, self.sig()))

    def test_replay_rejected(self):
        self.assertTrue(self.v.verify(self.body, 1000, self.n, self.sig()))
        self.assertFalse(self.v.verify(self.body, 1000, self.n, self.sig()))

    def test_body_tamper(self):
        self.assertFalse(self.v.verify(b'{"a":2}', 1000, self.n, self.sig()))

    def test_expired_and_future(self):
        self.assertFalse(self.v.verify(self.body, 900, self.n, self.sig(ts=900)))
        self.assertFalse(self.v.verify(self.body, 1100, self.n, self.sig(ts=1100)))

    def test_wrong_key_short_nonce(self):
        bad = hmac_auth.sign(os.urandom(32), self.body, 1000, self.n)
        self.assertFalse(self.v.verify(self.body, 1000, self.n, bad))
        self.assertFalse(self.v.verify(self.body, 1000, "short", hmac_auth.sign(self.key, self.body, 1000, "short")))

    def test_nonce_swap_tamper(self):
        self.assertFalse(self.v.verify(self.body, 1000, "m" * 16, self.sig()))


if __name__ == "__main__":
    unittest.main(verbosity=1)
