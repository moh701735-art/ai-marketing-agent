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


def make_handler(store, cookie_secure=True, cfg=None):
    cfg = cfg or {}
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

        def link_routes(self, path):
            who = self.session()
            if not who: return self.send(302, "", location="/login")
            uid = who["user_id"]; app_id = cfg.get("app_id") or ""; base = (cfg.get("base_url") or "").rstrip("/")
            enabled = bool(app_id and base and sec.APP_ID_RE.fullmatch(app_id))
            if path == "/link":
                csrf, ck = self.csrf_cookie()
                try: last = store.link_status(uid); dash = store.dashboard(uid)
                except Exception as e:
                    log("link_error %s: %s" % (type(e).__name__, str(e).replace("\n", " ")[:200])); return self.send(503, pages.link_page(csrf, None, False, enabled, "خطأ مؤقت، حاول بعد قليل."), cookies=ck)
                linked = bool(dash and any(a.get("platform") == "tiktok" for a in (dash.get("accounts") or [])))
                busy = bool(last and last.get("status") in ("pending", "processing"))
                note = "عندك حساب تيك توك مربوط. لتغييره تواصل مع الإدارة." if linked else ""
                return self.send(200, pages.link_page(csrf, last, not linked and not busy, enabled, note), cookies=ck)
            if not enabled: return self.send(503, pages.message_page("غير مفعّل", "الربط من الموقع غير مفعّل بعد."))
            if path == "/link/tiktok":
                state = sec.new_state()
                try: store.link_state_new(uid, sec.token_hash(state))
                except Exception as e:
                    log("link_state_error %s" % type(e).__name__); return self.send(503, pages.message_page("خطأ مؤقت", "حاول بعد قليل."))
                redirect = cfg.get("redirect_uri") or (base + "/tiktok/callback")   # مع الجسر: الرابط المسجّل عند تيك توك (agent…/tiktok-code)
                url = "https://business-api.tiktok.com/portal/auth?" + urllib.parse.urlencode({"app_id": app_id, "state": state, "redirect_uri": redirect}, quote_via=urllib.parse.quote)
                return self.send(302, "", location=url)
            qs = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query, max_num_fields=12)
            code = (qs.get("auth_code") or qs.get("code") or [""])[0]; state = (qs.get("state") or [""])[0]
            if not sec.valid_state(state) or not sec.AUTH_CODE_RE.fullmatch(code):
                log("link_callback_bad state=%s code=%s" % (bool(sec.valid_state(state)), bool(sec.AUTH_CODE_RE.fullmatch(code))))
                return self.send(400, pages.message_page("ما اكتمل الربط", "ما وصل رمز تفويض صالح من تيك توك (أو الرابط انتهى). ارجع وابدأ الربط من جديد."))
            try: store.link_begin(uid, sec.token_hash(state), code)
            except Exception as e:
                msg = str(e)
                log("link_begin_error %s" % ("state" if "state_invalid" in msg else "busy" if "request_in_progress" in msg else type(e).__name__))
                if "request_in_progress" in msg: return self.send(302, "", location="/link")
                return self.send(400, pages.message_page("ما اكتمل الربط", "انتهت صلاحية المحاولة أو انستعملت. ارجع وابدأ الربط من جديد."))
            return self.send(302, "", location="/link")

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
            if path in ("/link", "/link/tiktok", "/tiktok/callback"):
                return self.link_routes(path)
            if path == "/":
                who = self.session()
                if not who: return self.send(302, "", location="/login")
                csrf, ck = self.csrf_cookie()
                try: dash = store.dashboard(who["user_id"])
                except Exception as e:
                    dash = None; note = "تعذّر جلب البيانات حالياً، حاول بعد قليل."; log("dashboard_error %s: %s" % (type(e).__name__, str(e).replace("\n", " ")[:200]))
                else: note = "" if dash else "حسابك غير متاح حالياً."
                accts, camps, status = (dash.get("accounts") or [], dash.get("campaigns") or [], dash.get("status")) if dash else ([], [], None)
                who = {**who, "status": status}
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
    cfg = {"app_id": os.environ.get("TIKTOK_APP_ID", ""), "base_url": os.environ.get("WEB_BASE_URL", ""), "redirect_uri": os.environ.get("TIKTOK_REDIRECT", "")}
    srv = ThreadingHTTPServer(("0.0.0.0", port), make_handler(Store(dsn), os.environ.get("WEB_COOKIE_SECURE", "1") != "0", cfg))
    srv.daemon_threads = True
    srv.serve_forever()


if __name__ == "__main__":
    main()
