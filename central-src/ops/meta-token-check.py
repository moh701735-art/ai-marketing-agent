#!/usr/bin/env python3
"""قراءة فقط: يفحص توكن ميتا قبل ما تدخله بالنظام: طويل (شهرين) لو قصير (ساعة)؟ + الصلاحيات الست.
الاستعمال (من /opt/central):  python3 ops/meta-token-check.py
التوكن يُكتب مخفياً (لا ينطبع ولا ينحفظ). ما يكتب بأي قاعدة. آخر سطر: VERDICT=OK أو VERDICT=REFUSE أو VERDICT=UNKNOWN.
"""
# p301
import datetime, getpass, json, os, re, sys, urllib.error, urllib.parse, urllib.request

GRAPH = os.environ.get("META_GRAPH", "https://graph.facebook.com/v21.0").rstrip("/")
NEED = ("ads_management", "ads_read", "business_management", "pages_show_list", "pages_read_engagement", "pages_manage_ads")
MIN_DAYS = 30


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
        text = text.replace(tok, "***").replace(urllib.parse.quote(tok), "***")
    return re.sub(r"access_token=[^&\s\"']+", "access_token=***", text)[:300]


def run(tok, get=http_get, out=print, now=None):
    now = now if now is not None else datetime.datetime.now(datetime.timezone.utc).timestamp()
    url = "%s/debug_token?%s" % (GRAPH, urllib.parse.urlencode({"input_token": tok, "access_token": tok}))
    j = get(url)
    if not isinstance(j, dict) or j.get("error") or not isinstance(j.get("data"), dict):
        e = (j or {}).get("error") or {}
        out("could_not_read_token_info: %s" % scrub("%s (code %s)" % (e.get("message", "bad response"), e.get("code", "?")), tok))
        me = get("%s/me?%s" % (GRAPH, urllib.parse.urlencode({"fields": "id,name", "access_token": tok})))
        if isinstance(me, dict) and me.get("id"):
            out("token_works_for_user=%s but its expiry cannot be read here" % str(me.get("id"))[:20])
        else:
            out("token_rejected_by_meta")
            out("VERDICT=REFUSE")
            return 2
        out("VERDICT=UNKNOWN")
        return 3
    d = j["data"]
    if not d.get("is_valid"):
        out("token_not_valid: %s" % scrub((d.get("error") or {}).get("message", "invalid"), tok))
        out("VERDICT=REFUSE")
        return 2
    exp = d.get("expires_at")
    try:
        exp = int(exp)
    except Exception:
        exp = None
    scopes = [str(s) for s in (d.get("scopes") or [])]
    out("token_type=%s app_id=%s" % (str(d.get("type"))[:12], str(d.get("app_id"))[:20]))
    for n in NEED:
        out("  %s %s" % ("OK     " if n in scopes else "MISSING", n))
    missing = [n for n in NEED if n not in scopes]
    dae = d.get("data_access_expires_at")
    if dae:
        try:
            out("data_access_expires=%s" % datetime.datetime.fromtimestamp(int(dae), datetime.timezone.utc).strftime("%Y-%m-%d"))
        except Exception:
            pass
    if exp == 0:
        out("expires=never (non-expiring token)")
        days = None
        ok_len = True
    elif exp:
        secs = exp - now
        days = secs / 86400.0
        out("expires=%s (in %s)" % (datetime.datetime.fromtimestamp(exp, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                                  ("%.1f days" % days) if days >= 1 else ("%.1f hours" % (secs / 3600.0))))
        ok_len = days >= MIN_DAYS
    else:
        out("expires=unknown")
        out("VERDICT=UNKNOWN")
        return 3
    if not ok_len:
        out("SHORT_LIVED_TOKEN: press Extend Access Token in the Access Token Debugger and copy the NEW token shown under that button")
        out("VERDICT=REFUSE")
        return 2
    if missing:
        out("MISSING_PERMISSIONS: %s (redo the Explorer consent and tick them)" % ",".join(missing))
        out("VERDICT=REFUSE")
        return 2
    out("VERDICT=OK")
    return 0


def main():
    tok = getpass.getpass("Meta token (hidden, not stored): ").strip()
    if len(tok) < 20:
        sys.exit("token too short")
    sys.exit(run(tok))


if __name__ == "__main__":
    main()
