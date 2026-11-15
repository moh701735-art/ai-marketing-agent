#!/usr/bin/env python3
"""ربط سناب شات (قراءة فقط): صفحة HTTPS مؤقتة بنفس نمط link-meta-web.py (الخادم والشهادة والتوكن السري من link-web.py).
لا شي من الأسرار يمر بالمحادثة: Client ID/Secret ورابط الإرجاع يُلصقان بالنموذج. التشغيل: cd /opt/central && python3 ops/link-snapchat-web.py
"""
import html, importlib.util, json, os, re, secrets, sys, time, unicodedata, urllib.error, urllib.parse, urllib.request
from pathlib import Path

spec = importlib.util.spec_from_file_location("lw", Path(__file__).resolve().parent / "link-web.py")
lw = importlib.util.module_from_spec(spec); spec.loader.exec_module(lw)
at, page = lw.at, lw.page

REDIRECT = "https://agent.mohammedai.tech/snap-cb"
TOKEN_URL = "https://accounts.snapchat.com/login/oauth2/access_token"
API = os.environ.get("SNAP_API", "https://adsapi.snapchat.com/v1")


def http(url, data=None, token=None):
    hdr = {"Accept": "application/json"}
    if data is not None: hdr["Content-Type"] = "application/x-www-form-urlencoded"
    if token: hdr["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, headers=hdr)
    try:
        return 200, json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except Exception: return e.code, {"error": "HTTP %d" % e.code}
    except Exception as e:
        return 0, {"error": type(e).__name__}


def emsg(j):
    if not isinstance(j, dict): return "?"
    parts = [str(j.get(k))[:160] for k in ("error", "error_description", "debug_message", "display_message", "request_status") if j.get(k)]
    return " | ".join(parts)[:400] or "?"


def form_page(err=""):
    e = '<div class="e">%s</div>' % html.escape(err) if err else ""
    return page('<h1>ربط سناب شات (قراءة فقط)</h1>' + e +
        '<form method="post" action="list" autocomplete="off">'
        '<label>1) Client ID (من تطبيق OAuth بـ Snap Business)</label><input type="text" name="cid"/>'
        '<label>2) Client Secret (حقل مخفي؛ لا ترسله بأي مكان ثاني)</label><input type="password" name="sec" autocomplete="new-password"/>'
        '<label>3) الرابط الكامل بعد الموافقة (يبدأ بـ agent.mohammedai.tech/snap-cb?code=... وممكن تطلع صفحة 404، عادي)</label><textarea name="link"></textarea>'
        '<label>4) اسم العميل (slug مثل mohm)</label><input type="text" name="slug" value="mohm"/>'
        '<button type="submit">عرض الحسابات</button></form>')


def clean(s):
    """ينظّف القيمة الملصوقة: يشيل المسافات والرموز المخفية (اتجاه RTL وغيره)، ولو انلصق معها نص مثل «المفتاح السري: xxx» ياخذ الي بعد آخر نقطتين."""
    s = unicodedata.normalize("NFKC", s or "")
    s = "".join(ch for ch in s if unicodedata.category(ch) not in ("Cf", "Cc", "Zs", "Zl", "Zp"))
    if ":" in s: s = s.rsplit(":", 1)[1]
    return s


def why(s):
    bad = sum(1 for ch in s if not re.match(r"[0-9A-Za-z_\-]", ch))
    return "طوله %d حرف، رموز غير مسموحة: %d" % (len(s), bad)


def parse_code(s):
    s = (s or "").strip()
    m = re.search(r"[?&#]code=([0-9A-Za-z_\-\.~%]{10,2000})", s)
    c = urllib.parse.unquote(m.group(1)) if m else urllib.parse.unquote(s.split("&")[0].strip())
    return c if re.fullmatch(r"[0-9A-Za-z_\-\.~]{10,2000}", c) else ""


def snap_get(path, tok):
    return http(API + path, token=tok)


def do_list(form):
    cid = clean(form.get("cid", ""))
    sec = clean(form.get("sec", ""))
    slug = form.get("slug", "").strip()
    code = parse_code(form.get("link", ""))
    if not re.fullmatch(r"[0-9A-Za-z\-]{8,80}", cid): return form_page("Client ID غير صالح (%s). انسخه من صفحة التطبيق بدون مسافات." % why(cid))
    if not re.fullmatch(r"[0-9A-Za-z_\-]{8,200}", sec): return form_page("Client Secret غير صالح (%s). انسخه بزر مفتاح النسخ، المفتاح الصحيح حروف وأرقام فقط." % why(sec))
    if not code: return form_page("ما لقيت code بالرابط الملصوق. الصق الرابط الكامل من شريط العنوان بعد الموافقة.")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", slug): return form_page("اسم العميل (slug) غير صالح.")
    tid = at.psql(lw.DB, "SELECT tenant_id FROM core.tenants WHERE slug = :'slug'", {"slug": slug}, tx=False).strip()
    if not tid: return form_page("ما لقيت عميل بهذا الاسم.")
    st, j = http(TOKEN_URL, data=urllib.parse.urlencode({"grant_type": "authorization_code", "code": code,
                 "redirect_uri": REDIRECT, "client_id": cid, "client_secret": sec}).encode())
    if st != 200 or not j.get("access_token") or not j.get("refresh_token"):
        return form_page("سناب رفض التفويض (R01): %s. الكود يُستعمل مرة وحدة وينتهي بسرعة؛ أعد الموافقة وانسخ رابطاً جديداً." % emsg(j))
    tok = {"a": j["access_token"], "r": j["refresh_token"], "e": time.time() + int(j.get("expires_in") or 1800), "c": cid, "s": sec}
    st, me = snap_get("/me", tok["a"])
    uid = str(((me or {}).get("me") or {}).get("id") or "")
    if st != 200 or not uid: return form_page("تعذّر قراءة حساب سناب (R02): %s" % emsg(me))
    st, og = snap_get("/me/organizations?with_ad_accounts=true", tok["a"])
    if st != 200: return form_page("تعذّر قراءة المنظمات (R03): %s" % emsg(og))
    accts = []
    for o in (og.get("organizations") or []):
        org = (o or {}).get("organization") or {}
        oid, oname = str(org.get("id") or ""), str(org.get("name") or "")
        lst = org.get("ad_accounts")
        if lst is None and oid:
            s2, aj = snap_get("/organizations/%s/adaccounts" % urllib.parse.quote(oid), tok["a"])
            lst = [(x or {}).get("adaccount") or {} for x in (aj.get("adaccounts") or [])] if s2 == 200 else []
        for a in (lst or []):
            if a.get("id"):
                accts.append({"id": str(a["id"]), "name": str(a.get("name") or "")[:80], "cur": str(a.get("currency") or "").upper(),
                              "st": str(a.get("status") or ""), "org": oname[:60]})
    if not accts: return form_page("ما لقيت حسابات إعلانية بهذا الحساب (R04). تأكد إن الحساب Organization Admin وإن الحسابات تابعة للمنظمة.")
    taken = set(at.psql(lw.DB, "SELECT external_id FROM core.ad_accounts WHERE platform = 'snapchat' AND unlinked_at IS NULL", {}, tx=False).split())
    sid = secrets.token_hex(16)
    with lw.LOCK:
        lw.purge_sessions()
        lw.SESSIONS[sid] = {"tok": tok, "uid": uid, "accts": accts, "taken": taken, "slug": slug, "tid": tid, "ts": time.time()}
    rows = []
    for i, a in enumerate(accts):
        if a["id"] in taken:
            rows.append('<tr><td></td><td>%s</td><td>%s</td><td class="t">مربوط</td></tr>' % (html.escape(a["name"] or "-"), html.escape(a["cur"] or "-")))
        else:
            rows.append('<tr><td><input type="checkbox" name="acc" value="%s"/></td><td>%s (%s)</td><td>%s</td><td class="t">%s</td></tr>' % (
                html.escape(a["id"]), html.escape(a["name"] or "-"), html.escape(a["org"] or "-"), html.escape(a["cur"] or "-"), html.escape(a["st"] or "")))
    return page('<h1>اختر الحسابات الإعلانية</h1><div class="m">سناب حساب %s | %d حساب إعلاني. اختر الحسابات الي تريدها فقط.</div>'
                '<form method="post" action="link"><input type="hidden" name="sid" value="%s"/><table>%s</table>'
                '<button type="submit">ربط المختار</button></form>' % (html.escape(uid[:12]), len(accts), sid, "".join(rows)))


def do_link(multi):
    sid = (multi.get("sid") or [""])[0]
    with lw.LOCK:
        lw.purge_sessions()
        s = lw.SESSIONS.pop(sid, None)
    if not s: return form_page("انتهت الجلسة (10 دقايق). ابدأ من جديد.")
    pick = set(multi.get("acc", []))
    chosen = [a for a in s["accts"] if a["id"] in pick and a["id"] not in s["taken"]]
    if not chosen: return form_page("ما انختار أي حساب جديد.")
    ref = "snap-" + secrets.token_hex(12)
    try:
        at.vault([{"tenant_id": s["tid"], "kind": "snap_oauth", "secret_ref": ref, "value": json.dumps(s["tok"])}])
    except Exception as e:
        msg = str(e)
        for v in list(s["tok"].values()) + [json.dumps(s["tok"])]:
            if isinstance(v, str) and len(v) > 6: msg = msg.replace(v, "***")
        print("VAULT ERROR:", msg[:500])
        return form_page("فشل حفظ التوكن بالخزنة (R05): %s. التفاصيل مكتوبة بالتيرمنال." % type(e).__name__)
    vars_ = {"tid": s["tid"], "user": "snap_" + s["uid"][:60], "ref": ref}
    stmts = ["BEGIN;",
             "INSERT INTO core.platform_connections (tenant_id, platform, auth_mode, external_user_id, secret_ref) "
             "VALUES (:'tid', 'snapchat', 'oauth_user', :'user', :'ref') "
             "ON CONFLICT (tenant_id, platform, external_user_id) DO UPDATE SET secret_ref = EXCLUDED.secret_ref, status = 'active';"]
    for i, a in enumerate(chosen):
        vars_.update({"acct%d" % i: a["id"], "aname%d" % i: a["name"] or ("Snap " + a["id"][:8]), "cur%d" % i: a["cur"] if re.fullmatch(r"[A-Z]{3}", a["cur"]) else ""})
        stmts.append("INSERT INTO core.ad_accounts (tenant_id, platform, external_id, name, connection_id, currency) "
                     "SELECT :'tid', 'snapchat', :'acct%d', :'aname%d', connection_id, nullif(:'cur%d','')::char(3) FROM core.platform_connections WHERE secret_ref = :'ref' "
                     "ON CONFLICT (tenant_id, platform, external_id) DO UPDATE SET connection_id = EXCLUDED.connection_id, name = EXCLUDED.name, "
                     "currency = EXCLUDED.currency, enabled = true, unlinked_at = NULL;" % (i, i, i))
    stmts += ["UPDATE core.tenants SET features = features || '{\"snapchat\": true}'::jsonb WHERE tenant_id = :'tid';", "COMMIT;"]
    try:
        at.psql(lw.DB, "\n".join(stmts), vars_, tx=False)
    except Exception as e:
        print("DB insert failed:", type(e).__name__)
        return form_page("فشل التسجيل بالقاعدة (R06). التوكن انحفظ بالخزنة بدون استعمال (ما يضر). صوّر لي الشاشة.")
    lw.STATE["done"] = True
    names = ", ".join(a["id"] for a in chosen)
    print("OK: %d ad account(s) linked to %s: %s" % (len(chosen), s["slug"], names))
    return page('<h1>تم الربط</h1><div class="ok">ربطنا %d حساب إعلاني بسناب للعميل %s.</div>'
                '<div class="m">ارجع للتيرمنال (يغلق الرابط تلقائياً). المرحلة الأولى قراءة فقط: ما ينشئ حملات ولا يوقف شي.</div>' % (len(chosen), html.escape(s["slug"])))


lw.form_page, lw.do_list, lw.do_link = form_page, do_list, do_link
if __name__ == "__main__":
    lw.main()
