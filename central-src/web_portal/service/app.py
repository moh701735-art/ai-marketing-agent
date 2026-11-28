# -*- coding: utf-8 -*-
"""بوابة الزبائن (نسخة 1: دخول بدعوة + لوحة قراءة فقط). خادم HTTP صغير بدون مكتبات خارجية عدا psycopg.
متغيرات البيئة: WEB_DB_DSN (إلزامي)، WEB_PORT (8090)، WEB_COOKIE_SECURE (1). يشتغل خلف Caddy فقط (HTTPS يُنهى هناك)."""
import os, sys, time, urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import pages, security as sec

MAX_BODY = 8192
BAD_INVITE = {
    "used": ("الرابط انستعمل", "هذا الرابط انستعمل قبل. إذا نسيت كلمة السر اطلب دعوة جديدة."),
    "expired": ("الرابط انتهت صلاحيته", "اطلب دعوة جديدة من الإدارة."),
    "disabled": ("الحساب موقوف", "تواصل مع الإدارة."),
}


def log(msg):
    sys.stderr.write(msg + "\n"); sys.stderr.flush()   # بدون رموز ولا كلمات سر: فقط مرجع الهاش (أول 8 خانات) والحالة
SESSION_HOURS = 72
HEADERS = {
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
    "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store", "X-Frame-Options": "DENY",
    "Strict-Transport-Security": "max-age=31536000",
}


def make_handler(store, cookie_secure=True):
    flags = "; Path=/; HttpOnly; SameSite=Lax" + ("; Secure" if cookie_secure else "")

    class H(BaseHTTPRequestHandler):
        server_version = "portal"
        sys_version = ""
        timeout = 10

        def log_message(self, *a): pass

        # ---- أدوات ----
        def cookies(self):
            c = SimpleCookie()
            try: c.load(self.headers.get("Cookie", ""))
            except Exception: pass
            return {k: v.value for k, v in c.items()}

        def send(self, code, body="", ctype="text/html; charset=utf-8", cookies=(), location=None):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            for k, v in HEADERS.items(): self.send_header(k, v)
            self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(data)))
            if location: self.send_header("Location", location)
            for ck in cookies: self.send_header("Set-Cookie", ck)
            self.end_headers(); self.wfile.write(data)

        def csrf_cookie(self):
            """رمز CSRF: نفس القيمة بالكوكي وبالحقل المخفي. يُنشأ إن غاب."""
            v = self.cookies().get("csrf")
            if sec.valid_token(v): return v, []
            v = sec.new_token(); return v, ["csrf=%s%s" % (v, flags)]

        def form(self):
            try: n = int(self.headers.get("Content-Length", "0"))
            except ValueError: return None
            if n < 0 or n > MAX_BODY: return None
            raw = self.rfile.read(n).decode("utf-8", "replace")
            return {k: v[0] for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True, max_num_fields=10).items()}

        def session(self):
            sid = self.cookies().get("sid")
            if not sec.valid_token(sid): return None
            try: return store.session_get(sec.token_hash(sid))
            except Exception: return None


        def bad_invite(self, h):
            try: state = store.invite_state(h)
            except Exception: state = "error"
            log("invite_miss ref=%s state=%s" % (h[:8], state)); time.sleep(0.5)
            title, text = BAD_INVITE.get(state, ("الرابط غير صالح", "الرابط غلط أو ناقص (انسخه كامل من الإدارة). اطلب دعوة جديدة."))
            return self.send(404, pages.message_page(title, text))

        # ---- GET ----
        def do_GET(self):
            path = urllib.parse.urlsplit(self.path).path
            if path == "/healthz":
                try: ok = store.ping()
                except Exception: ok = False
                return self.send(200 if ok else 503, "ok" if ok else "db", "text/plain")
            if path == "/login":
                csrf, ck = self.csrf_cookie(); return self.send(200, pages.login_page(csrf), cookies=ck)
            if path == "/invite":
                qs = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                if "code" not in qs: return self.send(200, pages.invite_code_page())
                n = sec.norm_invite(qs["code"][0])
                if not n:
                    log("invite_miss ref=- state=malformed len=%d" % len(qs["code"][0])); time.sleep(0.5)
                    return self.send(400, pages.invite_code_page("الرمز لازم يكون 12 حرف/رقم (مثل 7k3m-q9xp-4tn2). تأكد منه وأعد الكتابة."))
                return self.send(302, "", location="/invite/" + n)
            if path.startswith("/invite/"):
                tok = path[len("/invite/"):]; h = sec.invite_hash(tok)
                if h is None:
                    log("invite_miss ref=- state=malformed len=%d" % len(tok)); time.sleep(0.5)
                    return self.send(404, pages.invite_code_page("الرابط ناقص أو غلط. اكتب رمز الدعوة (12 خانة) هنا بدل الرابط."))
                try: info = store.invite_peek(h)
                except Exception: return self.send(503, pages.message_page("خطأ مؤقت", "حاول بعد قليل."))
                if not info: return self.bad_invite(h)
                csrf, ck = self.csrf_cookie(); return self.send(200, pages.invite_page(csrf, tok, info.get("email"), ""), cookies=ck)
            if path == "/":
                who = self.session()
                if not who: return self.send(302, "", location="/login")
                csrf, ck = self.csrf_cookie()
                try: dash = store.dashboard(who["user_id"])
                except Exception: dash = None; note = "تعذّر جلب البيانات حالياً، حاول بعد قليل."
                else: note = "" if dash else "حسابك غير متاح حالياً."
                accts, camps = dash if dash else ([], [])
                return self.send(200, pages.dashboard_page(csrf, who, accts, camps, note), cookies=ck)
            return self.send(404, pages.message_page("غير موجود", "هذي الصفحة غير موجودة."))

        # ---- POST ----
        def do_POST(self):
            path = urllib.parse.urlsplit(self.path).path
            f = self.form()
            if f is None: return self.send(413, "too large", "text/plain")
            if not sec.csrf_ok(self.cookies().get("csrf"), f.get("csrf")):
                return self.send(403, pages.message_page("انتهت الجلسة", "حدّث الصفحة وحاول من جديد."))
            if path == "/login": return self.login(f)
            if path == "/logout":
                sid = self.cookies().get("sid")
                if sec.valid_token(sid):
                    try: store.session_delete(sec.token_hash(sid))
                    except Exception: pass
                return self.send(302, "", location="/login", cookies=["sid=; Max-Age=0" + flags])
            if path.startswith("/invite/"): return self.invite(path[len("/invite/"):], f)
            return self.send(404, pages.message_page("غير موجود", "هذي الصفحة غير موجودة."))

        def login(self, f):
            email, pwd = str(f.get("email", ""))[:120], str(f.get("password", ""))[:sec.MAX_PWD]
            csrf = self.cookies().get("csrf")
            bad = lambda: self.send(401, pages.login_page(csrf, "البريد أو كلمة السر غلط، أو الحساب مقفل مؤقتاً."))
            try: info = store.login_lookup(email)
            except Exception: return self.send(503, pages.login_page(csrf, "خطأ مؤقت، حاول بعد قليل."))
            if not info or not info.get("active") or info.get("locked") or not info.get("pwd"):
                sec.dummy_verify(pwd); return bad()
            if not sec.verify_password(pwd, info["pwd"]):
                try: store.login_fail(info["user_id"])
                except Exception: pass
                time.sleep(0.3); return bad()
            sid = sec.new_token()
            try:
                store.login_ok(info["user_id"]); store.session_create(info["user_id"], sec.token_hash(sid), SESSION_HOURS)
            except Exception: return self.send(503, pages.login_page(csrf, "خطأ مؤقت، حاول بعد قليل."))
            return self.send(302, "", location="/", cookies=["sid=%s%s; Max-Age=%d" % (sid, flags, SESSION_HOURS * 3600)])

        def invite(self, tok, f):
            csrf = self.cookies().get("csrf")
            h = sec.invite_hash(tok)
            if h is None: return self.send(404, pages.message_page("الرابط غير صالح", "الرابط ناقص أو غلط. اطلب دعوة جديدة."))
            try: info = store.invite_peek(h)
            except Exception: return self.send(503, pages.message_page("خطأ مؤقت", "حاول بعد قليل."))
            if not info: return self.bad_invite(h)
            pwd, conf = str(f.get("password", "")), str(f.get("confirm", ""))
            problem = sec.password_problem(pwd, conf)
            if problem: return self.send(400, pages.invite_page(csrf, tok, info.get("email"), problem))
            try: store.invite_accept(h, sec.hash_password(pwd))
            except Exception: return self.send(400, pages.message_page("ما انحفظ", "الدعوة انتهت أو انستعملت. اطلب دعوة جديدة."))
            return self.send(200, pages.login_page(csrf, "", "انحفظت كلمة السر. سجّل دخولك الآن."))

    return H


def main():
    dsn = os.environ.get("WEB_DB_DSN", "")
    if not dsn: sys.exit("WEB_DB_DSN missing")
    from .store import Store
    port = int(os.environ.get("WEB_PORT", "8090"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), make_handler(Store(dsn), os.environ.get("WEB_COOKIE_SECURE", "1") != "0"))
    srv.daemon_threads = True
    srv.serve_forever()


if __name__ == "__main__":
    main()
