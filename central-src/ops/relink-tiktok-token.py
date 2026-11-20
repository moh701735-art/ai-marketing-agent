#!/usr/bin/env python3
"""تجديد توكن تيك توك لعميل موجود (بدون إنشاء اتصال جديد وبدون لمس الحسابات).
الاستعمال (من /opt/central):  python3 ops/relink-tiktok-token.py [--apply] [--new-ref]
  بدون --apply = فحص فقط (ما يكتب شي). الأسرار (App Secret و auth_code) تنكتب مخفية بالطرفية ولا تنطبع.
الفحص: يبدّل الكود بتوكن، ثم يتأكد أن التوكن يشمل **كل** حسابات العميل المربوطة بالاتصال النشط، وإلا يتوقف بدون كتابة.
الكتابة (--apply): نسخة جديدة بالخزنة تحت نفس المرجع (أو مرجع جديد مع --new-ref ويحدّث الاتصال)."""
import getpass, json, os, re, secrets, sys, urllib.error, urllib.parse, urllib.request

API = os.environ.get("TIKTOK_API", "https://business-api.tiktok.com/open_api/v1.3").rstrip("/")
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]{1,48}")


class Stop(Exception):
    pass


def http(url, body=None, token=None, timeout=30):
    headers = {"Content-Type": "application/json"}
    if token: headers["Access-Token"] = token
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers,
                                 method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read() or b"{}")
        except Exception: return {"code": e.code, "message": "http %s" % e.code}
    except Exception as e:
        return {"code": -1, "message": type(e).__name__}


def scrub(text, *secrets_):
    text = str(text)
    for s in secrets_:
        if s and len(s) > 5: text = text.replace(s, "***")
    return text[:300]


def clean_code(raw):
    """يقبل auth_code لحاله أو الرابط كامل (…?auth_code=XXX&state=…) ويرجع القيمة فقط."""
    raw = str(raw or "").strip().strip("'\"")
    m = re.search(r"(?:^|[?&#\s])(?:auth_code|code)=([^&\s#]+)", raw)
    v = urllib.parse.unquote(m.group(1)) if m else raw
    return v.strip()


def shape(v):
    """وصف غير سري للقيمة: الطول ونوع الأحرف (بدون أي حرف منها)."""
    v = str(v or "")
    kind = "hex" if re.fullmatch(r"[0-9a-fA-F]+", v) else "alnum" if re.fullmatch(r"[0-9A-Za-z]+", v) else "alnum+رموز"
    return "طول %d، نوع %s" % (len(v), kind)


def code_variants(code):
    """الكود كما هو، ثم نسخة بدون رموز بالأطراف (علامات اقتباس/نقطة/شرطة مايلة من النسخ)."""
    out = [code]
    t = re.sub(r"^[^0-9A-Za-z]+|[^0-9A-Za-z]+$", "", code)
    if t and t not in out: out.append(t)
    return out


def exchange(app_id, secret, code, call=http):
    code = clean_code(code)
    r = {}
    for c in code_variants(code):
        r = call(API + "/oauth2/access_token/", {"app_id": app_id, "secret": secret, "auth_code": c})
        if r.get("code") == 0 and (r.get("data") or {}).get("access_token"): break
    d = r.get("data") or {}
    if r.get("code") != 0 or not d.get("access_token"):
        raise Stop("تيك توك رفض الكود (code=%s): %s. [شكل الكود: %s | شكل السر: %s]. الكود يُستعمل مرة وحدة وينتهي بسرعة؛ خذ كود جديد والصقه مباشرة." % (r.get("code"), scrub(r.get("message", ""), secret, code), shape(code), shape(secret)))
    ids = [str(x) for x in d.get("advertiser_ids", []) if re.fullmatch(r"[0-9]{5,24}", str(x))]
    return d["access_token"], ids


def account_info(token, ids, call=http):
    """يرجع {id: (name, currency, status)} للحسابات اللي يقدر التوكن يقرأها فعلاً."""
    out = {}
    for i in range(0, len(ids), 50):
        part = ids[i:i + 50]
        q = urllib.parse.urlencode({"advertiser_ids": json.dumps(part), "fields": json.dumps(["advertiser_id", "name", "currency", "status"])})
        r = call(API + "/advertiser/info/?" + q, None, token)
        if r.get("code") != 0: continue
        for a in (r.get("data") or {}).get("list", []):
            out[str(a.get("advertiser_id"))] = (str(a.get("name", ""))[:60], str(a.get("currency", "")).upper()[:3], str(a.get("status", "")))
    return out


def db_state(at, db, slug):
    tid = at.psql(db, "SELECT tenant_id FROM core.tenants WHERE slug = :'slug'", {"slug": slug}, tx=False).strip()
    if not tid: raise Stop("ما لقيت عميل بهذا الاسم (%s)." % slug)
    rows = [l for l in at.psql(db, "SELECT connection_id::text || '|' || external_user_id || '|' || secret_ref FROM core.platform_connections "
                                   "WHERE tenant_id = :'tid' AND platform = 'tiktok' AND status = 'active' ORDER BY created_at", {"tid": tid}, tx=False).splitlines() if l.strip()]
    if len(rows) != 1:
        raise Stop("لازم يكون عند العميل اتصال تيك توك نشط **واحد** بالضبط، لقيت %d. ما أكتب شي. (%s)" % (len(rows), "; ".join(r.split("|")[1] for r in rows)[:200] or "لا شي"))
    cid, ext, ref = rows[0].split("|")
    accts = [l.strip() for l in at.psql(db, "SELECT external_id FROM core.ad_accounts WHERE tenant_id = :'tid' AND platform = 'tiktok' AND enabled AND unlinked_at IS NULL "
                                            "AND connection_id::text = :'cid' ORDER BY external_id", {"tid": tid, "cid": cid}, tx=False).splitlines() if l.strip()]
    if not accts: raise Stop("الاتصال النشط ما عنده حسابات مفعّلة. ما أكتب شي.")
    return tid, cid, ext, ref, accts


def run(slug, app_id, secret, code, apply, new_ref, at, db, call=http, out=print):
    if not SLUG_RE.fullmatch(slug): raise Stop("slug غير صالح.")
    if not re.fullmatch(r"[0-9]{5,24}", app_id): raise Stop("App ID غير صالح (أرقام فقط).")
    tid, cid, ext, ref, accts = db_state(at, db, slug)
    out("العميل: %s | الاتصال النشط: %s | عدد حساباته المفعّلة: %d" % (slug, ext, len(accts)))
    out("الكود المستلم: %s | App ID: %s" % (shape(clean_code(code)), shape(app_id)))
    token, adv_ids = exchange(app_id, secret, code, call)
    info = account_info(token, accts, call)
    missing = [a for a in accts if a not in adv_ids]
    unreadable = [a for a in accts if a not in info]
    for a in accts:
        n = info.get(a)
        out("  %s %s %s" % ("✅" if a in adv_ids and n else "❌", a, ("%s | %s | حالة %s" % n) if n else "(التوكن الجديد ما يقدر يقرأه)"))
    if missing or unreadable:
        raise Stop("التوكن الجديد **ما يغطي** كل الحسابات (ناقص بالتفويض: %d، ما ينقرأ: %d). ما كتبت شي. أعد التفويض واختر كل الحسابات الثلاثة وكل الصلاحيات." % (len(missing), len(unreadable)))
    out("التوكن الجديد يغطي كل الحسابات (%d من %d بالتفويض)." % (len(accts), len(adv_ids)))
    if not apply:
        out("فحص فقط (dry-run): ما كتبت شي. للكتابة أعد نفس الأمر مع --apply")
        return {"written": False}
    if new_ref:
        nref = "ref-%s-tt-%s" % (slug, secrets.token_hex(4))
        at.vault([{"tenant_id": tid, "kind": "tiktok_token", "secret_ref": nref, "value": token}])
        at.psql(db, "UPDATE core.platform_connections SET secret_ref = :'nref' WHERE connection_id::text = :'cid' AND tenant_id = :'tid'",
                {"nref": nref, "cid": cid, "tid": tid}, tx=False)
        out("✅ انحفظ التوكن بمرجع جديد وانربط بالاتصال %s" % ext)
        return {"written": True, "ref": nref}
    at.vault([{"tenant_id": tid, "kind": "tiktok_token", "secret_ref": ref, "value": token}])
    out("✅ انحفظ التوكن الجديد بالخزنة (نسخة جديدة تحت نفس المرجع). الاتصال والحسابات ما تغيّروا.")
    return {"written": True, "ref": ref}


def ask(read, prompt, rx, tries=6):
    """يعيد السؤال لين تنكتب قيمة صالحة (سطر فاضي من لصق الأمر ما يخرّب الجلسة)."""
    for _ in range(tries):
        v = read(prompt).strip()
        if rx.fullmatch(v): return v
        print("  ⚠️ القيمة فاضية أو غير صالحة، أعد الكتابة.")
    print("⛔ توقفت بعد محاولات كثيرة. ما انكتب شي."); sys.exit(1)


def main(argv=None, inp=input, hidden=getpass.getpass):
    argv = list(sys.argv[1:] if argv is None else argv)
    apply, new_ref = "--apply" in argv, "--new-ref" in argv
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("lw", Path(__file__).resolve().parent / "link-web.py")
    lw = importlib.util.module_from_spec(spec); spec.loader.exec_module(lw)
    at = lw.at
    slug = ask(inp, "slug العميل بالإنجليزي (مثال ammar-mohmaed): ", SLUG_RE)
    app_id = ask(inp, "TikTok App ID (أرقام): ", re.compile(r"[0-9]{5,24}"))
    secret = ask(hidden, "TikTok App Secret (مخفي، الصقه ثم Enter): ", re.compile(r"\S{8,200}"))
    code = ask(hidden, "auth_code (مخفي، الصقه ثم Enter): ", re.compile(r"\S{8,400}"))
    try:
        run(slug, app_id, secret, code, apply, new_ref, at, lw.DB)
    except Stop as e:
        print("⛔ " + scrub(e, secret, code)); return 1
    except Exception as e:
        print("⛔ خطأ غير متوقع: %s. ما انكتب شي بعد نقطة الفحص." % type(e).__name__); return 1
    if apply: print("الخطوة الجاية: bash deploy/run-readiness.sh (مرتين) ثم جرّب البوت: /start و/accounts و/balance")
    return 0


if __name__ == "__main__":
    sys.exit(main())
