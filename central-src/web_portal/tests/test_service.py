import http.client, os, re, sys, threading, time, unittest, urllib.parse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from http.server import ThreadingHTTPServer
from web_portal.service import app, pages, security as sec


class FakeStore:
    def __init__(self):
        self.users = {}; self.invites = {}; self.sessions = {}; self.calls = []; self.down = False
    def ping(self): return not self.down
    def _chk(self):
        if self.down: raise RuntimeError("db down")
    def add_user(self, email, pwd=None, active=True):
        uid = "u-" + email; self.users[email.lower()] = {"user_id": uid, "email": email.lower(), "pwd": pwd, "active": active, "failed": 0, "locked": False, "name": "Acme <b>X</b>", "status": "READY"}; return uid
    def invite_peek(self, h): self._chk(); i = self.invites.get(h); return {"email": i["email"]} if i and not i.get("used") else None
    def invite_accept(self, h, pwd):
        self._chk(); i = self.invites.get(h)
        if not i or i.get("used"): raise RuntimeError("invite_invalid")
        i["used"] = True; u = self.users[i["email"]]; u["pwd"] = pwd; u["active"] = True
    def login_lookup(self, email): self._chk(); u = self.users.get(email.strip().lower()); return {"user_id": u["user_id"], "pwd": u["pwd"], "locked": u["locked"], "active": u["active"]} if u else None
    def login_fail(self, uid):
        self.calls.append(("fail", uid)); u = [x for x in self.users.values() if x["user_id"] == uid][0]; u["failed"] += 1
        if u["failed"] >= 5: u["locked"] = True
    def login_ok(self, uid): self.calls.append(("ok", uid))
    def session_create(self, uid, h, ttl): self.sessions[h] = uid
    def session_get(self, h):
        uid = self.sessions.get(h)
        if not uid: return None
        u = [x for x in self.users.values() if x["user_id"] == uid][0]; return {"user_id": uid, "email": u["email"], "name": u["name"], "status": u["status"], "slug": "acme", "tenant_id": "t"}
    def session_delete(self, h): self.sessions.pop(h, None)
    def dashboard(self, uid):
        if self.down: raise RuntimeError("down")
        return ([{"platform": "tiktok", "external_id": "111", "name": "<script>alert(1)</script>", "currency": "USD", "enabled": True}], [{"name": "حملة \"x\"", "external_id": "9", "status": "ACTIVE", "created_at": "2026-11-28T10:00:00"}])


class Client:
    def __init__(self, port): self.port = port; self.jar = {}
    def req(self, method, path, data=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10); h = dict(headers or {})
        if self.jar: h["Cookie"] = "; ".join("%s=%s" % kv for kv in self.jar.items())
        body = None
        if data is not None: body = urllib.parse.urlencode(data); h["Content-Type"] = "application/x-www-form-urlencoded"
        c.request(method, path, body, h); r = c.getresponse(); b = r.read().decode("utf-8", "replace")
        for k, v in r.getheaders():
            if k.lower() == "set-cookie":
                nv = v.split(";")[0]; name, val = nv.split("=", 1)
                if "Max-Age=0" in v: self.jar.pop(name, None)
                else: self.jar[name] = val
        return r.status, b, dict((k.lower(), v) for k, v in r.getheaders())
    def csrf(self, path="/login"):
        s, b, _ = self.req("GET", path); m = re.search(r'name="csrf" value="([^"]+)"', b); return m.group(1) if m else None


class T(unittest.TestCase):
    def setUp(self):
        self.st = FakeStore(); self.srv = ThreadingHTTPServer(("127.0.0.1", 0), app.make_handler(self.st, cookie_secure=True)); self.srv.daemon_threads = True
        threading.Thread(target=self.srv.serve_forever, daemon=True).start(); self.port = self.srv.server_address[1]; self.cl = Client(self.port)
        self.st.add_user("Client@Acme.com", sec.hash_password("correct-horse-9"))
    def tearDown(self): self.srv.shutdown(); self.srv.server_close()
    def login(self, cl=None, email="client@acme.com", pwd="correct-horse-9"):
        cl = cl or self.cl; t = cl.csrf(); return cl.req("POST", "/login", {"csrf": t, "email": email, "password": pwd})

    def test_01_security_headers_and_health(self):
        s, b, h = self.cl.req("GET", "/healthz"); self.assertEqual((s, b), (200, "ok"))
        s, b, h = self.cl.req("GET", "/login"); self.assertEqual(s, 200)
        for k in ("content-security-policy", "x-content-type-options", "referrer-policy", "cache-control", "x-frame-options", "strict-transport-security"): self.assertIn(k, h)
        self.assertIn("frame-ancestors 'none'", h["content-security-policy"]); self.assertEqual(h["cache-control"], "no-store"); self.assertIn('dir="rtl"', b)
        self.st.down = True; self.assertEqual(self.cl.req("GET", "/healthz")[0], 503)

    def test_02_login_success_cookie_flags_and_dashboard(self):
        s, b, h = self.login(); self.assertEqual((s, h["location"]), (302, "/")); sc = h["set-cookie"]
        for flag in ("HttpOnly", "SameSite=Lax", "Secure", "Max-Age="): self.assertIn(flag, sc)
        self.assertIn("sid", self.cl.jar); self.assertNotIn(self.cl.jar["sid"], str(self.st.sessions))   # الجلسة تُخزَّن كهاش
        s, b, _ = self.cl.req("GET", "/"); self.assertEqual(s, 200); self.assertIn("111", b)
        self.assertNotIn("<script>alert(1)</script>", b); self.assertIn("&lt;script&gt;", b); self.assertNotIn("<b>X</b>", b)

    def test_03_wrong_password_and_unknown_user_same_message(self):
        a = self.login(pwd="wrong-password-1")[:2]; b = self.login(email="nobody@x.co")[:2]; c = self.login(email="client@acme.com", pwd="x")[:2]
        self.assertEqual(a[0], 401); self.assertEqual(a[1], b[1]); self.assertEqual(a[1], c[1]); self.assertNotIn("sid", self.cl.jar)

    def test_04_lockout_calls_and_locked_rejects_good_password(self):
        for _ in range(5): self.login(pwd="wrong-password-1")
        self.assertEqual(len([c for c in self.st.calls if c[0] == "fail"]), 5); s, b, _ = self.login(); self.assertEqual(s, 401); self.assertNotIn("sid", self.cl.jar)

    def test_05_csrf_required_everywhere(self):
        self.cl.csrf(); self.assertEqual(self.cl.req("POST", "/login", {"email": "client@acme.com", "password": "correct-horse-9"})[0], 403)
        self.assertEqual(self.cl.req("POST", "/login", {"csrf": "x" * 40, "email": "client@acme.com", "password": "correct-horse-9"})[0], 403)
        other = Client(self.port); t2 = other.csrf(); self.assertEqual(self.cl.req("POST", "/login", {"csrf": t2, "email": "client@acme.com", "password": "correct-horse-9"})[0], 403)
        self.login(); self.assertEqual(self.cl.req("POST", "/logout", {})[0], 403)

    def test_06_dashboard_needs_session_and_logout_kills_it(self):
        self.assertEqual(self.cl.req("GET", "/")[:1], (302,)); self.login(); self.assertEqual(self.cl.req("GET", "/")[0], 200)
        t = self.cl.csrf("/"); s, b, h = self.cl.req("POST", "/logout", {"csrf": t}); self.assertEqual((s, h["location"]), (302, "/login")); self.assertEqual(self.cl.req("GET", "/")[0], 302); self.assertEqual(self.st.sessions, {})
        self.cl.jar["sid"] = "A" * 43; self.assertEqual(self.cl.req("GET", "/")[0], 302)

    def test_07_disabled_user_cannot_login(self):
        self.st.users["client@acme.com"]["active"] = False; self.assertEqual(self.login()[0], 401)

    def test_08_invite_flow(self):
        tok = sec.new_token(); self.st.add_user("new@acme.com", None, False); self.st.invites[sec.token_hash(tok)] = {"email": "new@acme.com"}
        s, b, _ = self.cl.req("GET", "/invite/" + tok); self.assertEqual(s, 200); self.assertIn("new@acme.com", b)
        t = self.cl.csrf("/invite/" + tok)
        s, b, _ = self.cl.req("POST", "/invite/" + tok, {"csrf": t, "password": "short", "confirm": "short"}); self.assertEqual(s, 400); self.assertIn("10 أحرف", b)
        s, b, _ = self.cl.req("POST", "/invite/" + tok, {"csrf": t, "password": "long-enough-pass", "confirm": "different-pass-x"}); self.assertEqual(s, 400); self.assertIn("غير متطابقتين", b)
        s, b, _ = self.cl.req("POST", "/invite/" + tok, {"csrf": t, "password": "long-enough-pass", "confirm": "long-enough-pass"}); self.assertEqual(s, 200); self.assertIn("انحفظت", b)
        self.assertTrue(sec.verify_password("long-enough-pass", self.st.users["new@acme.com"]["pwd"])); self.assertEqual(self.cl.req("GET", "/invite/" + tok)[0], 404)
        self.assertEqual(self.login(email="new@acme.com", pwd="long-enough-pass")[0], 302)

    def test_09_bad_invite_tokens(self):
        for t in ("short", "x" * 70, "a" * 43 + "!", "../../etc"): self.assertEqual(self.cl.req("GET", "/invite/" + t)[0], 404)
        self.assertEqual(self.cl.req("GET", "/invite/" + "A" * 43)[0], 404)

    def test_10_body_limit_and_unknown_paths(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5); c.request("POST", "/login", "x" * 20000, {"Content-Type": "application/x-www-form-urlencoded", "Content-Length": "20000"}); self.assertEqual(c.getresponse().status, 413)
        self.assertEqual(self.cl.req("GET", "/admin")[0], 404); self.assertEqual(self.cl.req("GET", "/etc/passwd")[0], 404)

    def test_11_db_down_is_graceful(self):
        self.login(); self.st.down = True; s, b, _ = self.cl.req("GET", "/"); self.assertIn(s, (200, 302)); self.assertNotIn("Traceback", b)
        c2 = Client(self.port); t = c2.csrf(); self.assertEqual(c2.req("POST", "/login", {"csrf": t, "email": "client@acme.com", "password": "x"})[0], 503)


class Sec(unittest.TestCase):
    def test_hash_verify(self):
        h = sec.hash_password("a-long-password-1"); self.assertTrue(h.startswith("scrypt$15$8$1$")); self.assertTrue(sec.verify_password("a-long-password-1", h)); self.assertFalse(sec.verify_password("a-long-password-2", h))
        self.assertNotEqual(h, sec.hash_password("a-long-password-1")); self.assertFalse(sec.verify_password("x", None)); self.assertFalse(sec.verify_password("x", "scrypt$99$8$1$aa$bb")); self.assertFalse(sec.verify_password("x", "garbage"))
    def test_db_regex_accepts_our_hash(self):
        self.assertTrue(re.fullmatch(r"scrypt[$][0-9]{1,2}[$][0-9]{1,2}[$][0-9]{1,2}[$][A-Za-z0-9+/=_-]{8,64}[$][A-Za-z0-9+/=_-]{32,128}", sec.hash_password("a-long-password-1")))
    def test_tokens_and_policy(self):
        t = sec.new_token(); self.assertTrue(sec.valid_token(t)); self.assertEqual(len(sec.token_hash(t)), 64); self.assertFalse(sec.valid_token("short")); self.assertTrue(sec.csrf_ok(t, t)); self.assertFalse(sec.csrf_ok(t, t[::-1])); self.assertFalse(sec.csrf_ok(None, t))
        self.assertIsNone(sec.password_problem("long-enough-pass", "long-enough-pass")); self.assertIsNotNone(sec.password_problem("short", "short")); self.assertIsNotNone(sec.password_problem("aaaaaaaaaaaa", "aaaaaaaaaaaa"))

class Pages(unittest.TestCase):
    def test_escape_everywhere(self):
        s = pages.dashboard_page("c", {"name": "<i>n</i>", "email": "a@b.co\"><x>", "status": "READY"}, [{"platform": "tiktok", "name": "<x>", "external_id": "1", "currency": "<c>", "enabled": True}], [{"name": "<y>", "external_id": "<z>", "status": "<s>", "created_at": "<d>"}], "<note>")
        for bad in ("<i>", "<x>", "<c>", "<y>", "<z>", "<s>", "<d>", "<note>", '"><x>'): self.assertNotIn(bad, s)

if __name__ == "__main__": unittest.main()
