# -*- coding: utf-8 -*-
"""صفحات HTML عربية (RTL) بسيطة. كل نص متغيّر يمر عبر esc()."""
import html

esc = lambda v: html.escape(str(v if v is not None else ""), quote=True)
CSS = """
:root{--pink:#ff3d8b;--pink2:#ff7ab6;--blue:#1747c9;--navy:#050b2e;--ink:#eef2ff;--mut:#a9b6e8}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;color:var(--ink);font-family:system-ui,-apple-system,'Segoe UI',Tahoma,sans-serif;line-height:1.6;
background:linear-gradient(125deg,#050b2e,#0b1f6b 35%,#1747c9 65%,#4a2bd0 85%,#8a2be2);background-size:260% 260%;background-attachment:fixed;animation:drift 32s ease-in-out infinite}
.bg{position:fixed;inset:0;overflow:hidden;pointer-events:none;z-index:0}
.bg span{position:absolute;border-radius:50%;filter:blur(80px);opacity:.45;animation:float 26s ease-in-out infinite}
.bg span:nth-child(1){width:380px;height:380px;background:var(--pink);top:-90px;right:-80px}
.bg span:nth-child(2){width:460px;height:460px;background:#2b6bff;bottom:-140px;left:-120px;animation-duration:32s;animation-delay:-8s}
.bg span:nth-child(3){width:280px;height:280px;background:#c026d3;top:42%;left:38%;opacity:.28;animation-duration:38s;animation-delay:-15s}
.w{position:relative;z-index:1;max-width:980px;margin:0 auto;padding:18px 16px 40px}
.c{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.16);border-radius:18px;padding:20px;margin:16px 0;backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);box-shadow:0 18px 50px -20px #000a;animation:rise .9s cubic-bezier(.2,.7,.2,1) both}
h1{font-size:1.45rem;margin:.2rem 0 .8rem}h2{font-size:1.1rem;margin:0 0 .6rem}
label{display:block;margin:.8rem 0 .3rem;font-weight:600}
input[type=text],input[type=password],input[type=email],input:not([type]){width:100%;padding:12px 14px;border:1px solid rgba(255,255,255,.28);border-radius:12px;font-size:1rem;color:#fff;background:rgba(5,11,46,.45);outline:0;transition:border-color .5s,box-shadow .5s}
input:focus{border-color:var(--pink);box-shadow:0 0 0 4px #ff3d8b33}
button,a.b{display:inline-block;background:linear-gradient(90deg,var(--pink),#c026d3 70%,#7c3aed);background-size:180% 100%;color:#fff;border:0;border-radius:12px;padding:12px 22px;font-size:1rem;margin-top:14px;cursor:pointer;text-decoration:none;font-weight:600;box-shadow:0 10px 28px -10px #ff3d8bcc;transition:transform .6s cubic-bezier(.2,.7,.2,1),box-shadow .6s,background-position 1s}
button:hover,a.b:hover{transform:translateY(-2px);background-position:100% 0;box-shadow:0 16px 34px -10px #ff3d8bf0}
button.g{background:rgba(255,255,255,.12);box-shadow:none;border:1px solid rgba(255,255,255,.24)}
a{color:var(--pink2)}
table{width:100%;border-collapse:collapse;font-size:.92rem}th,td{padding:9px 8px;border-bottom:1px solid rgba(255,255,255,.12);text-align:right}
.e{background:#ff3d8b26;border:1px solid #ff3d8b66;color:#ffd3e6;padding:11px 13px;border-radius:12px}
.o{background:#22c55e22;border:1px solid #22c55e66;color:#c6f6d5;padding:11px 13px;border-radius:12px}
.m{color:var(--mut);font-size:.88rem}
.t{display:inline-block;padding:3px 12px;border-radius:99px;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.2);font-size:.82rem}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.top .who{display:flex;align-items:center;gap:12px}
.av{width:46px;height:46px;border-radius:14px;display:grid;place-items:center;font-weight:700;font-size:1.2rem;background:linear-gradient(135deg,var(--pink),#7c3aed);box-shadow:0 8px 22px -8px var(--pink)}
.hero{padding:6px 2px 2px;animation:rise 1s cubic-bezier(.2,.7,.2,1) both}
.hero h1{font-size:1.7rem;margin:.1rem 0}
.hero h1 span{background:linear-gradient(90deg,var(--pink2),#fff 55%,#9fc0ff);-webkit-background-clip:text;background-clip:text;color:transparent}
.r{position:absolute;opacity:0;pointer-events:none}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin:18px 0}
.tile{position:relative;display:flex;flex-direction:column;align-items:center;gap:8px;padding:20px 10px 16px;margin:0;border-radius:20px;cursor:pointer;text-align:center;font-weight:600;
background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.16);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
transition:transform .7s cubic-bezier(.2,.7,.2,1),box-shadow .7s,background .7s,border-color .7s;animation:rise .9s cubic-bezier(.2,.7,.2,1) both;animation-delay:calc(var(--i)*110ms)}
.tile:hover{transform:translateY(-6px);box-shadow:0 22px 40px -18px #ff3d8b99;border-color:#ff7ab688}
.tile svg{width:50px;height:50px;filter:drop-shadow(0 6px 14px #0007);transition:transform .8s cubic-bezier(.2,.7,.2,1)}
.tile:hover svg{transform:scale(1.1) rotate(-4deg)}
.tile b{font-size:1.9rem;line-height:1;font-weight:700}
.tile small{color:var(--mut);font-weight:500}
#t-all:checked~.tiles [for=t-all],#t-meta:checked~.tiles [for=t-meta],#t-tt:checked~.tiles [for=t-tt],#t-camp:checked~.tiles [for=t-camp]{
background:linear-gradient(160deg,#ff3d8b40,#1747c966);border-color:#ff7ab6;box-shadow:0 0 0 1px #ff7ab6aa,0 20px 44px -16px #ff3d8bcc;animation:rise .9s cubic-bezier(.2,.7,.2,1) both,glow 6s ease-in-out infinite;animation-delay:calc(var(--i)*110ms),0s}
#t-all:focus-visible~.tiles [for=t-all],#t-meta:focus-visible~.tiles [for=t-meta],#t-tt:focus-visible~.tiles [for=t-tt],#t-camp:focus-visible~.tiles [for=t-camp]{outline:3px solid #fff}
.panel{display:none}
#t-all:checked~.panels .p-all,#t-meta:checked~.panels .p-meta,#t-tt:checked~.panels .p-tt,#t-camp:checked~.panels .p-camp{display:block;animation:swap .9s cubic-bezier(.2,.7,.2,1) both}
.row{display:flex;align-items:center;gap:14px;padding:13px 14px;margin:9px 0;border-radius:16px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);
transition:transform .6s cubic-bezier(.2,.7,.2,1),background .6s,border-color .6s;animation:rise .8s cubic-bezier(.2,.7,.2,1) both;animation-delay:calc(var(--i)*55ms)}
.row:hover{transform:translateX(-5px);background:rgba(255,255,255,.12);border-color:#ff7ab655}
.row svg{width:34px;height:34px;flex:none}
.nm{flex:1;min-width:0}.nm b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.nm small{color:var(--mut);direction:ltr;display:block;unicode-bidi:plaintext;text-align:right}
.chip{padding:3px 11px;border-radius:99px;font-size:.78rem;font-weight:600;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.18);white-space:nowrap}
.chip.ok{background:#22c55e26;border-color:#22c55e77;color:#bbf7d0}.chip.off{background:#ff3d8b26;border-color:#ff3d8b77;color:#ffc2dc}
.empty{padding:26px;text-align:center;color:var(--mut)}
.foot{color:var(--mut);font-size:.82rem;text-align:center;margin-top:26px}
@keyframes drift{0%,100%{background-position:0% 40%}50%{background-position:100% 60%}}
@keyframes float{0%,100%{transform:translate(0,0) scale(1)}33%{transform:translate(-50px,40px) scale(1.12)}66%{transform:translate(40px,-30px) scale(.94)}}
@keyframes rise{from{opacity:0;transform:translateY(18px)}to{opacity:1;transform:none}}
@keyframes swap{from{opacity:0;transform:translateY(12px) scale(.985)}to{opacity:1;transform:none}}
@keyframes glow{0%,100%{box-shadow:0 0 0 1px #ff7ab6aa,0 20px 44px -16px #ff3d8bcc}50%{box-shadow:0 0 0 1px #ff7ab6,0 24px 56px -12px #4f7dff}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
@media(max-width:560px){.hero h1{font-size:1.4rem}.row{flex-wrap:wrap}.nm{flex:1 1 calc(100% - 60px)}.row .chip:first-of-type{margin-right:48px}.tile b{font-size:1.6rem}}
"""


def page(title, body, nav=""):
    return ("<!doctype html><html lang=\"ar\" dir=\"rtl\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<meta name=\"robots\" content=\"noindex,nofollow\"><title>%s</title><style>%s</style></head><body><div class=\"bg\"><span></span><span></span><span></span></div><div class=\"w\">%s%s</div></body></html>" % (esc(title), CSS, nav, body))


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
                 "<a class=\"b\" href=\"/link/tiktok\">اربط تيك توك</a>")
    elif not enabled:
        body += "<p class=\"m\">الربط من الموقع غير مفعّل بعد. تواصل مع الإدارة.</p>"
    body += "<p><a href=\"/\">رجوع للوحة</a></p></div>"
    return page("ربط تيك توك", body).replace("<title>", refresh + "<title>", 1)


def message_page(title, text):
    return page(title, "<div class=\"c\"><h1>%s</h1><p>%s</p><p><a href=\"/login\">تسجيل الدخول</a></p></div>" % (esc(title), esc(text)))


PLAT = {"tiktok": "تيك توك", "meta": "فيسبوك/إنستغرام", "snapchat": "سناب شات"}
STAT = {"READY": "جاهز", "NEEDS_REVIEW": "يحتاج مراجعة", "TESTING": "قيد الإعداد", "CONFIGURATION_REQUIRED": "قيد الإعداد", "SUSPENDED": "موقوف"}


# شعارات المنصات: SVG مضمّن (ما فيه طلبات خارجية؛ الـCSP يمنعها). فيسبوك: دائرة زرقاء وحرف f أبيض. تيك توك: مربع أسود بنوتة بثلاث طبقات (سماوي/وردي/أبيض).
_TT = "M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z"
LOGO = {
    "meta": "<svg viewBox=\"0 0 24 24\" role=\"img\" aria-label=\"Facebook\"><circle cx=\"12\" cy=\"12\" r=\"12\" fill=\"#1877F2\"/><path fill=\"#fff\" d=\"M16.671 15.469 17.203 12h-3.329V9.75c0-.949.465-1.875 1.956-1.875h1.513V4.922s-1.373-.234-2.686-.234c-2.741 0-4.533 1.66-4.533 4.668V12H7.078v3.469h3.047v8.385a12.1 12.1 0 0 0 3.75 0V15.469z\"/></svg>",
    "tiktok": "<svg viewBox=\"0 0 24 24\" role=\"img\" aria-label=\"TikTok\"><rect width=\"24\" height=\"24\" rx=\"6\" fill=\"#010101\"/><g transform=\"translate(4.6 4.2) scale(.62)\"><path d=\"" + _TT + "\" fill=\"#25F4EE\" transform=\"translate(-.9 -.7)\"/><path d=\"" + _TT + "\" fill=\"#FE2C55\" transform=\"translate(.9 .7)\"/><path d=\"" + _TT + "\" fill=\"#fff\"/></g></svg>",
    "snapchat": "<svg viewBox=\"0 0 24 24\" role=\"img\" aria-label=\"Snapchat\"><rect width=\"24\" height=\"24\" rx=\"6\" fill=\"#FFFC00\"/><path d=\"M12 4.5c-2.3 0-3.6 1.7-3.6 3.8v1.6c-.5-.1-.9-.2-1.1.1-.3.4.1.8.7 1-.1.9-1.2 2.1-2.1 2.4.1.5 1 .6 1.5.8.1.4.1.8.5.9.6.1 1.3-.4 2.1.3.6.6 1.2 1.1 2 1.1s1.4-.5 2-1.1c.8-.7 1.5-.2 2.1-.3.4-.1.4-.5.5-.9.5-.2 1.4-.3 1.5-.8-.9-.3-2-1.5-2.1-2.4.6-.2 1-.6.7-1-.2-.3-.6-.2-1.1-.1V8.3c0-2.1-1.3-3.8-3.6-3.8z\" fill=\"#fff\" stroke=\"#111\" stroke-width=\".9\" stroke-linejoin=\"round\"/></svg>",
    "all": "<svg viewBox=\"0 0 24 24\" role=\"img\" aria-label=\"\"><rect width=\"24\" height=\"24\" rx=\"7\" fill=\"url(#gA)\"/><defs><linearGradient id=\"gA\" x1=\"0\" y1=\"0\" x2=\"1\" y2=\"1\"><stop offset=\"0\" stop-color=\"#ff3d8b\"/><stop offset=\"1\" stop-color=\"#4f7dff\"/></linearGradient></defs><g fill=\"#fff\"><rect x=\"5\" y=\"5\" width=\"6\" height=\"6\" rx=\"1.6\"/><rect x=\"13\" y=\"5\" width=\"6\" height=\"6\" rx=\"1.6\" opacity=\".75\"/><rect x=\"5\" y=\"13\" width=\"6\" height=\"6\" rx=\"1.6\" opacity=\".75\"/><rect x=\"13\" y=\"13\" width=\"6\" height=\"6\" rx=\"1.6\"/></g></svg>",
    "camp": "<svg viewBox=\"0 0 24 24\" role=\"img\" aria-label=\"\"><rect width=\"24\" height=\"24\" rx=\"7\" fill=\"url(#gC)\"/><defs><linearGradient id=\"gC\" x1=\"0\" y1=\"1\" x2=\"1\" y2=\"0\"><stop offset=\"0\" stop-color=\"#7c3aed\"/><stop offset=\"1\" stop-color=\"#ff3d8b\"/></linearGradient></defs><g fill=\"#fff\"><rect x=\"5\" y=\"12\" width=\"3.4\" height=\"7\" rx=\"1.2\"/><rect x=\"10.3\" y=\"8\" width=\"3.4\" height=\"11\" rx=\"1.2\"/><rect x=\"15.6\" y=\"5\" width=\"3.4\" height=\"14\" rx=\"1.2\"/></g></svg>",
}


def _acct_rows(accts):
    if not accts: return "<div class=\"empty\">ما كو حسابات هنا بعد.</div>"
    out = []
    for i, a in enumerate(accts):
        pl = a.get("platform")
        out.append("<div class=\"row\" style=\"--i:%d\">%s<div class=\"nm\"><b>%s</b><small>%s</small></div><span class=\"chip\">%s</span><span class=\"chip %s\">%s</span></div>" % (
            min(i, 14), LOGO.get(pl, LOGO["all"]), esc(a.get("name") or PLAT.get(pl, pl)), esc(a.get("external_id")), esc(a.get("currency") or "-"),
            "ok" if a.get("enabled") else "off", "مفعّل" if a.get("enabled") else "موقوف"))
    return "".join(out)


def dashboard_page(csrf, who, accounts, campaigns, note=""):
    name = who.get("name") or ""
    nav = ("<div class=\"c top\"><div class=\"who\"><div class=\"av\">%s</div><div><b>%s</b><div class=\"m\" dir=\"ltr\">%s</div></div></div>"
           "<form method=\"post\" action=\"/logout\"><input type=\"hidden\" name=\"csrf\" value=\"%s\"><button class=\"g\" style=\"margin:0\">خروج</button></form></div>" % (esc(name[:1].upper() or "؟"), esc(name), esc(who.get("email")), esc(csrf)))
    st = who.get("status")
    chip = ""
    if st:
        chip = "<span class=\"chip %s\">حالة الحساب: %s</span>" % ("ok" if st == "READY" else "off", esc(STAT.get(st, st)))
    hint = ""
    if st and st != "READY":
        hint = "<div class=\"c\"><p class=\"m\" style=\"margin:0\">%s</p></div>" % (
            "حسابك قيد الإعداد: يصير جاهزاً بعد ربط حساب إعلاني ونجاح الفحوصات (الربط من الموقع يجي بالمرحلة الجاية)." if st in ("TESTING", "CONFIGURATION_REQUIRED") else "تواصل مع الإدارة.")
    hero = "<div class=\"hero\"><h1>أهلاً، <span>%s</span></h1><div>%s</div></div>" % (esc(name), chip)
    fb = [a for a in accounts if a.get("platform") == "meta"]; tt = [a for a in accounts if a.get("platform") == "tiktok"]
    lcard = "" if tt else "<div class=\"c\"><h2>ربط الحسابات</h2><p class=\"m\">ما عندك حساب تيك توك مربوط.</p><a class=\"b\" href=\"/link\">اربط تيك توك</a></div>"
    def tile(i, tid, key, label, n):
        return "<label class=\"tile\" for=\"%s\" style=\"--i:%d\">%s<b>%d</b><small>%s</small></label>" % (tid, i, LOGO[key], n, label)
    tiles = tile(0, "t-all", "all", "الحسابات الإعلانية", len(accounts)) + tile(1, "t-meta", "meta", "فيسبوك", len(fb)) + tile(2, "t-tt", "tiktok", "تيك توك", len(tt)) + tile(3, "t-camp", "camp", "الحملات", len(campaigns))
    camp = "".join("<div class=\"row\" style=\"--i:%d\">%s<div class=\"nm\"><b>%s</b><small>%s</small></div><span class=\"chip\">%s</span><span class=\"chip\" dir=\"ltr\">%s</span></div>" % (
        min(i, 14), LOGO["camp"], esc(c.get("name") or "-"), esc(c.get("external_id") or "-"), esc(c.get("status") or "-"), esc(str(c.get("created_at") or "")[:16])) for i, c in enumerate(campaigns)) \
        or "<div class=\"empty\">ما كو حملات بعد.</div>"
    panels = ("<div class=\"panels\"><div class=\"panel p-all c\"><h2>الحسابات الإعلانية</h2>%s</div><div class=\"panel p-meta c\"><h2>فيسبوك وإنستغرام</h2>%s</div>"
              "<div class=\"panel p-tt c\"><h2>تيك توك</h2>%s</div><div class=\"panel p-camp c\"><h2>آخر الحملات</h2>%s</div></div>" % (_acct_rows(accounts), _acct_rows(fb), _acct_rows(tt), camp))
    radios = "<input class=\"r\" type=\"radio\" name=\"tab\" id=\"t-all\" checked><input class=\"r\" type=\"radio\" name=\"tab\" id=\"t-meta\"><input class=\"r\" type=\"radio\" name=\"tab\" id=\"t-tt\"><input class=\"r\" type=\"radio\" name=\"tab\" id=\"t-camp\">"
    body = (nav + hero + (("<div class=\"c\">%s</div>" % msg("e", note)) if note else "") + hint + lcard + radios + "<div class=\"tiles\">" + tiles + "</div>" + panels +
            "<p class=\"foot\">هذي نسخة تجريبية للعرض فقط. رفع الحملات وربط الحسابات يجي بالمراحل الجاية.</p>")
    return page("لوحة التحكم", body)
