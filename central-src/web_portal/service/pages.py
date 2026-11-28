# -*- coding: utf-8 -*-
"""صفحات HTML عربية (RTL) بسيطة. كل نص متغيّر يمر عبر esc()."""
import html

esc = lambda v: html.escape(str(v if v is not None else ""), quote=True)
CSS = ("body{font-family:system-ui,-apple-system,'Segoe UI',Tahoma,sans-serif;background:#f4f6f8;color:#1b2430;margin:0}"
       ".w{max-width:880px;margin:0 auto;padding:16px}.c{background:#fff;border-radius:12px;padding:18px;margin:14px 0;box-shadow:0 1px 3px #0001}"
       "h1{font-size:1.3rem;margin:.2rem 0 .8rem}h2{font-size:1.05rem;margin:0 0 .6rem}label{display:block;margin:.7rem 0 .25rem;font-weight:600}"
       "input{width:100%;box-sizing:border-box;padding:11px;border:1px solid #c9d1d9;border-radius:8px;font-size:1rem}"
       "button{background:#0b7a75;color:#fff;border:0;border-radius:8px;padding:11px 18px;font-size:1rem;margin-top:14px;cursor:pointer}"
       "button.g{background:#e6eaee;color:#1b2430}table{width:100%;border-collapse:collapse;font-size:.92rem}th,td{padding:8px;border-bottom:1px solid #eef1f4;text-align:right}"
       ".e{background:#fdecea;color:#8a1f17;padding:10px;border-radius:8px}.o{background:#e7f6ee;color:#14532d;padding:10px;border-radius:8px}.m{color:#5b6775;font-size:.85rem}"
       ".t{display:inline-block;padding:2px 8px;border-radius:99px;background:#eef1f4;font-size:.8rem}")


def page(title, body, nav=""):
    return ("<!doctype html><html lang=\"ar\" dir=\"rtl\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<meta name=\"robots\" content=\"noindex,nofollow\"><title>%s</title><style>%s</style></head><body><div class=\"w\">%s%s</div></body></html>" % (esc(title), CSS, nav, body))


def msg(kind, text):
    return "<div class=\"%s\">%s</div>" % ("e" if kind == "e" else "o", esc(text)) if text else ""


def login_page(csrf, error="", ok=""):
    return page("تسجيل الدخول", "<div class=\"c\"><h1>تسجيل الدخول</h1>%s%s<form method=\"post\" action=\"/login\" autocomplete=\"on\">"
                "<input type=\"hidden\" name=\"csrf\" value=\"%s\"><label>البريد الإلكتروني</label><input name=\"email\" type=\"email\" required autocomplete=\"username\">"
                "<label>كلمة السر</label><input name=\"password\" type=\"password\" required autocomplete=\"current-password\"><button>دخول</button></form>"
                "<p class=\"m\">الدخول بدعوة من الإدارة فقط. إذا ما عندك دعوة تواصل معنا.</p></div>" % (msg("e", error), msg("o", ok), esc(csrf)))


def invite_page(csrf, token, email, error=""):
    return page("تعيين كلمة السر", "<div class=\"c\"><h1>أهلاً بك</h1><p>حسابك: <b dir=\"ltr\">%s</b></p>%s<form method=\"post\" action=\"/invite/%s\">"
                "<input type=\"hidden\" name=\"csrf\" value=\"%s\"><label>كلمة السر الجديدة (6 خانات فأكثر، أرقام وحروف إنكليزية، لازم فيها حرف ورقم)</label><input name=\"password\" type=\"password\" required minlength=\"6\" maxlength=\"64\" autocomplete=\"new-password\" dir=\"ltr\">"
                "<label>أعد كتابتها</label><input name=\"confirm\" type=\"password\" required minlength=\"6\" maxlength=\"64\" autocomplete=\"new-password\" dir=\"ltr\"><button>حفظ</button></form></div>" % (esc(email), msg("e", error), esc(token), esc(csrf)))


def invite_code_page(error=""):
    return page("رمز الدعوة", "<div class=\"c\"><h1>رمز الدعوة</h1>%s<form method=\"get\" action=\"/invite\"><label>اكتب الرمز (12 خانة، مثل 7k3m-q9xp-4tn2)</label>"
                "<input name=\"code\" required maxlength=\"40\" autocomplete=\"off\" autocapitalize=\"none\" spellcheck=\"false\" dir=\"ltr\"><button>متابعة</button></form></div>" % msg("e", error))


LINK_STATUS = {"pending": "بالانتظار", "processing": "جاري الربط", "done": "تم الربط", "failed": "فشل الربط", "expired": "انتهت المحاولة"}


def link_page(csrf, last, can_start, enabled, note=""):
    """last: آخر طلب ربط {status,message,result} أو None. can_start: يقدر يبدأ ربطاً جديداً. enabled: الربط مفعّل بالإعدادات."""
    body = "<div class=\"c\"><h1>ربط حساب تيك توك</h1>%s" % msg("e", note)
    refresh = ""
    if last:
        stt = last.get("status")
        refresh = "<meta http-equiv=\"refresh\" content=\"4\">" if stt in ("pending", "processing") else ""
        body += "<p>آخر محاولة: <span class=\"t\">%s</span></p>" % esc(LINK_STATUS.get(stt, stt))
        if last.get("message"): body += "<p class=\"%s\">%s</p>" % ("o" if stt == "done" else "m", esc(last.get("message")))
        res = last.get("result") or {}
        rows = "".join("<tr><td dir=\"ltr\">%s</td><td>%s</td><td>%s</td></tr>" % (esc(a.get("id")), esc(a.get("name") or "-"), esc(a.get("currency") or "-")) for a in (res.get("linked") or []))
        if rows: body += "<table><tr><th>الرقم</th><th>الاسم</th><th>العملة</th></tr>%s</table>" % rows
    if can_start and enabled:
        body += ("<p class=\"m\">راح تروح لصفحة تيك توك الرسمية، وتختار حساباتك الإعلانية وتوافق، ونرجع بك. ما نشوف كلمة سرك ولا نخزنها.</p>"
                 "<form method=\"get\" action=\"/link/tiktok\"><button>اربط تيك توك</button></form>")
    elif not enabled:
        body += "<p class=\"m\">الربط من الموقع غير مفعّل بعد. تواصل مع الإدارة.</p>"
    body += "<p><a href=\"/\">رجوع للوحة</a></p></div>"
    return page("ربط تيك توك", body).replace("<title>", refresh + "<title>", 1)


def message_page(title, text):
    return page(title, "<div class=\"c\"><h1>%s</h1><p>%s</p><p><a href=\"/login\">تسجيل الدخول</a></p></div>" % (esc(title), esc(text)))


PLAT = {"tiktok": "تيك توك", "meta": "فيسبوك/إنستغرام", "snapchat": "سناب شات"}
STAT = {"READY": "جاهز", "NEEDS_REVIEW": "يحتاج مراجعة", "TESTING": "قيد الإعداد", "CONFIGURATION_REQUIRED": "قيد الإعداد", "SUSPENDED": "موقوف"}


def dashboard_page(csrf, who, accounts, campaigns, note=""):
    nav = ("<div class=\"c\" style=\"display:flex;justify-content:space-between;align-items:center\"><div><b>%s</b><div class=\"m\" dir=\"ltr\">%s</div></div>"
           "<form method=\"post\" action=\"/logout\"><input type=\"hidden\" name=\"csrf\" value=\"%s\"><button class=\"g\" style=\"margin:0\">خروج</button></form></div>" % (esc(who.get("name")), esc(who.get("email")), esc(csrf)))
    st = who.get("status")
    scard = ""
    if st:
        hint = "" if st == "READY" else "<p class=\"m\">حسابك قيد الإعداد: يصير جاهزاً بعد ربط حساب إعلاني ونجاح الفحوصات (الربط من الموقع يجي بالمرحلة الجاية).</p>" if st in ("TESTING", "CONFIGURATION_REQUIRED") else "<p class=\"m\">تواصل مع الإدارة.</p>"
        scard = "<div class=\"c\"><h2>حالة الحساب: <span class=\"t\">%s</span></h2>%s</div>" % (esc(STAT.get(st, st)), hint)
    lcard = "" if any(a.get("platform") == "tiktok" for a in accounts) else "<div class=\"c\"><h2>ربط الحسابات</h2><p class=\"m\">ما عندك حساب تيك توك مربوط.</p><a href=\"/link\"><button>اربط تيك توك</button></a></div>"
    rows = "".join("<tr><td>%s</td><td>%s</td><td dir=\"ltr\">%s</td><td>%s</td><td>%s</td></tr>" % (esc(PLAT.get(a.get("platform"), a.get("platform"))), esc(a.get("name") or "-"), esc(a.get("external_id")), esc(a.get("currency") or "-"),
                   "مفعّل" if a.get("enabled") else "موقوف") for a in accounts) or "<tr><td colspan=\"5\" class=\"m\">ما كو حسابات مربوطة بعد.</td></tr>"
    crow = "".join("<tr><td>%s</td><td dir=\"ltr\">%s</td><td>%s</td><td dir=\"ltr\">%s</td></tr>" % (esc(c.get("name") or "-"), esc(c.get("external_id") or "-"), esc(c.get("status") or "-"), esc(str(c.get("created_at") or "")[:16])) for c in campaigns) \
        or "<tr><td colspan=\"4\" class=\"m\">ما كو حملات بعد.</td></tr>"
    body = ("%s%s%s%s"
            "<div class=\"c\"><h2>الحسابات الإعلانية</h2><table><tr><th>المنصة</th><th>الاسم</th><th>الرقم</th><th>العملة</th><th>الحالة</th></tr>%s</table></div>"
            "<div class=\"c\"><h2>آخر الحملات</h2><table><tr><th>الاسم</th><th>الرقم</th><th>الحالة</th><th>التاريخ</th></tr>%s</table></div>"
            "<p class=\"m\">هذي نسخة تجريبية للعرض فقط. رفع الحملات وربط الحسابات يجي بالمراحل الجاية.</p>" % (nav, ('<div class="c">%s</div>' % msg("e", note)) if note else '', scard, lcard, rows, crow))
    return page("لوحة التحكم", body)
