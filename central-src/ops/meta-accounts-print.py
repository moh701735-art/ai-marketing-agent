#!/usr/bin/env python3
"""قراءة فقط: يطبع كل الحسابات الإعلانية والصفحات اللي يشوفها توكن ميتا واحد (توكن مستخدم طويل أو System User).
الاستعمال (من /opt/central):  python3 ops/meta-accounts-print.py
التوكن يُكتب مخفياً بالطرفية (لا ينطبع ولا ينحفظ). ما يكتب بأي قاعدة ولا يغيّر شي بميتا.
آخر سطر = معرّفات الحسابات الفعّالة (ACTIVE) بعملة USD/IQD مفصولة بمسافة، جاهزة للصق بنموذج ops/link-meta-web.py.
"""
import getpass, json, os, re, sys, urllib.error, urllib.parse, urllib.request

GRAPH = os.environ.get("META_GRAPH", "https://graph.facebook.com/v21.0").rstrip("/")
NEED = ("ads_management", "ads_read", "business_management", "pages_show_list", "pages_read_engagement")
OK_CUR = ("USD", "IQD")
STATUS = {1: "ACTIVE", 2: "DISABLED", 3: "UNSETTLED", 7: "PENDING_RISK_REVIEW", 8: "PENDING_SETTLEMENT",
          9: "IN_GRACE_PERIOD", 100: "PENDING_CLOSURE", 101: "CLOSED", 201: "ANY_ACTIVE", 202: "ANY_CLOSED"}
MAX_PAGES = 40


def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read() or b"{}")
        except Exception:
            return {"error": {"message": "http %s" % e.code, "code": e.code}}
    except Exception as e:
        return {"error": {"message": type(e).__name__, "code": -1}}


def scrub(text, tok):
    text = str(text)
    if tok and len(tok) > 5:
        text = text.replace(tok, "***")
        text = text.replace(urllib.parse.quote(tok), "***")
    return re.sub(r"access_token=[^&\s\"']+", "access_token=***", text)[:300]


def fetch_all(path, fields, tok, get=http_get, limit=100):
    """كل صفحات قائمة Graph (paging.next). يرجع (rows, error_text_or_None)."""
    url = "%s/%s?%s" % (GRAPH, path, urllib.parse.urlencode({"fields": fields, "limit": limit, "access_token": tok}))
    rows, err = [], None
    for _ in range(MAX_PAGES):
        j = get(url)
        if not isinstance(j, dict):
            err = "bad response"
            break
        if j.get("error"):
            e = j["error"]
            err = scrub("%s (code %s)" % (e.get("message", "?"), e.get("code", "?")), tok)
            break
        rows.extend(j.get("data") or [])
        url = ((j.get("paging") or {}).get("next")) or ""
        if not url:
            break
    else:
        err = "too many pages (cut at %d)" % MAX_PAGES
    return rows, err


def norm_account(a):
    aid = re.sub(r"\D", "", str(a.get("account_id") or a.get("id") or ""))
    try:
        st = int(a.get("account_status"))
    except Exception:
        st = -1
    biz = a.get("business") or {}
    return {"id": aid, "name": str(a.get("name") or "")[:40], "cur": str(a.get("currency") or "").upper(),
            "st": st, "stname": STATUS.get(st, "UNKNOWN(%s)" % a.get("account_status")),
            "biz": str((biz.get("name") if isinstance(biz, dict) else "") or "")[:30]}


def usable(a):
    return bool(a["id"]) and a["st"] == 1 and a["cur"] in OK_CUR


def run(tok, get=http_get, out=print):
    me = get("%s/me?%s" % (GRAPH, urllib.parse.urlencode({"fields": "id,name", "access_token": tok})))
    if not isinstance(me, dict) or me.get("error") or not me.get("id"):
        e = (me or {}).get("error") or {}
        out("FAIL: token rejected by Meta: %s" % scrub("%s (code %s)" % (e.get("message", "?"), e.get("code", "?")), tok))
        return 2
    out("user: %s (id %s)" % (str(me.get("name") or "")[:40], str(me.get("id"))[:20]))
    perms, perr = fetch_all("me/permissions", "permission,status", tok, get)
    granted = {p.get("permission") for p in perms if p.get("status") == "granted"}
    if perr:
        out("permissions: could not read (%s)" % perr)
    else:
        for n in NEED:
            out("  %s %s" % ("OK  " if n in granted else "MISSING", n))
    raw, aerr = fetch_all("me/adaccounts", "account_id,name,currency,account_status,business{name}", tok, get)
    if aerr:
        out("ad accounts: read error after %d rows: %s" % (len(raw), aerr))
    accts, seen = [], set()
    for a in raw:
        n = norm_account(a)
        if n["id"] and n["id"] not in seen:
            seen.add(n["id"])
            accts.append(n)
    accts.sort(key=lambda x: (x["biz"].lower(), x["name"].lower()))
    out("")
    out("ad accounts seen by this token: %d" % len(accts))
    out("%-3s %-17s %-10s %-4s %-10s %s" % ("#", "id", "status", "cur", "business", "name"))
    for i, a in enumerate(accts, 1):
        flag = "" if usable(a) else "  <-- NOT usable (%s)" % (a["stname"] if a["st"] != 1 else "currency %s" % (a["cur"] or "?"))
        out("%-3d %-17s %-10s %-4s %-10s %s%s" % (i, a["id"], a["stname"][:10], a["cur"] or "-", a["biz"][:10] or "-", a["name"], flag))
    pages, perr2 = fetch_all("me/accounts", "id,name", tok, get)
    out("")
    out("pages seen by this token: %d%s" % (len(pages), "" if not perr2 else " (read error: %s)" % perr2))
    for p in pages[:60]:
        out("  %s  %s" % (str(p.get("id")), str(p.get("name") or "")[:40]))
    good = [a["id"] for a in accts if usable(a)]
    out("")
    out("usable (ACTIVE + USD/IQD): %d of %d" % (len(good), len(accts)))
    if len(good) > 30:
        out("NOTE: more than 30 usable accounts; link-meta-web.py (after p290) takes up to 30 per run: run it twice with the two lists below.")
    for k in range(0, len(good), 30):
        out("IDS: " + " ".join(good[k:k + 30]))
    if not good:
        out("IDS: (none)")
    return 0


def main():
    tok = getpass.getpass("Meta token (hidden, not stored): ").strip()
    if len(tok) < 20:
        sys.exit("token too short")
    sys.exit(run(tok))


if __name__ == "__main__":
    main()
