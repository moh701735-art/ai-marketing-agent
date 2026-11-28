#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""عامل ربط تيك توك لبوابة الويب (مثبّت كـ ops/web-linker.py، يشتغل على السيرفر نفسه كخدمة systemd؛ مو مكشوف للإنترنت).
يقرأ طلبات web.link_requests (رمز تفويض لمرة وحدة كتبه الموقع)، يبدّل الرمز بتوكن عند تيك توك، ويستعمل دوال الربط المجرّبة بـops/link-tiktok-agency.py (do_link: حفظ التوكن
بالخزنة + الاتصال + الحسابات + تفعيل تيك توك). الموقع ما يمسك توكن ولا مفتاح. التوكن ما ينطبع ولا ينكتب بأي مكان غير الخزنة.
قواعد الأمان: (1) ما يربط حساب مربوط أصلاً عند أي زبون (حماية الاستيلاء)، (2) ما يربط حساب عملته مختلفة عن عملة الزبون، (3) زبون عنده تيك توك مربوط ما يعيد الربط من الموقع (إعادة التفويض تبطل التوكنات القديمة)،
(4) فشل أي خطوة = طلب failed برسالة واضحة، بدون أي تغيير جزئي (do_link يلغي التوكن لو فشلت الكتابة)."""
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

ROOT = os.environ.get("WEB_LINKER_ROOT", "/opt/central")
API = os.environ.get("TIKTOK_API", "https://business-api.tiktok.com/open_api/v1.3").rstrip("/")
ENV_FILE = os.path.join(ROOT, "web_portal", "linker.env")
SWEEP_SQL = ("UPDATE web.link_requests SET status = 'failed', message = 'انتهت مهلة المعالجة، ارجع وابدأ الربط من جديد', auth_code = NULL, updated_at = now() WHERE status = 'processing' AND updated_at < now() - interval '5 minutes';\n"
             "UPDATE web.link_requests SET status = 'expired', message = 'انتهت المحاولة قبل ما تنعالج، ارجع وابدأ من جديد', auth_code = NULL, updated_at = now() WHERE status = 'pending' AND created_at < now() - interval '15 minutes';")
CLAIM_SQL = ("UPDATE web.link_requests r SET status = 'processing', updated_at = now() WHERE r.req_id = (SELECT q.req_id FROM web.link_requests q WHERE q.status = 'pending' ORDER BY q.created_at LIMIT 1 FOR UPDATE SKIP LOCKED) "
             "RETURNING r.req_id::text || '|' || r.tenant_id::text || '|' || coalesce(r.auth_code, '') || '|' || (SELECT t.slug || '|' || coalesce(t.currency, '') FROM core.tenants t WHERE t.tenant_id = r.tenant_id);")
FINISH_SQL = "UPDATE web.link_requests SET status = :'st', message = :'msg', result = :'res'::jsonb, auth_code = NULL, updated_at = now() WHERE req_id = :'rid'::uuid;"
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]{1,48}"); UUID_RE = re.compile(r"[0-9a-f-]{36}"); CODE_RE = re.compile(r"[A-Za-z0-9._~+/=-]{8,255}")


class Stop(Exception):
    pass


def scrub(text, *secrets_):
    text = str(text)
    for s in secrets_:
        if s and len(s) > 5: text = text.replace(s, "***")
    return re.sub(r"(?i)(token|secret|auth_code)[\"'=: ]+[A-Za-z0-9._~+/-]{12,}", r"\1=***", text)[:200]


def http(url, body=None, token=None, timeout=30):
    headers = {"Content-Type": "application/json"}
    if token: headers["Access-Token"] = token
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read() or b"{}")
        except Exception: return {"code": e.code, "message": "http %s" % e.code}
    except Exception as e:
        return {"code": -1, "message": type(e).__name__}


def exchange(app_id, secret, code, call=http):
    r = call(API + "/oauth2/access_token/", {"app_id": app_id, "secret": secret, "auth_code": code})
    d = r.get("data") or {}
    if r.get("code") != 0 or not d.get("access_token"):
        raise Stop("تيك توك رفض الرمز (code=%s): %s. الرمز يُستعمل مرة وحدة وينتهي بسرعة؛ ارجع وابدأ الربط من جديد." % (r.get("code"), scrub(r.get("message", ""), secret, code)[:100]))
    return d["access_token"], [str(x) for x in d.get("advertiser_ids", []) if re.fullmatch(r"[0-9]{5,24}", str(x))]


def account_info(token, ids, call=http):
    """{id: (name, currency)} للحسابات اللي يقدر التوكن يقرأها فعلاً (نفس شكل ops/link-tiktok-agency.py)."""
    out = {}
    for i in range(0, len(ids), 50):
        q = urllib.parse.urlencode({"advertiser_ids": json.dumps(ids[i:i + 50]), "fields": json.dumps(["advertiser_id", "name", "currency"])})
        r = call(API + "/advertiser/info/?" + q, None, token)
        if r.get("code") != 0: continue
        for a in (r.get("data") or {}).get("list", []) or []:
            out[str(a.get("advertiser_id"))] = (str(a.get("name") or "")[:80], str(a.get("currency") or "").upper()[:3])
    return out


class Live:
    """الاعتماد على أدوات الربط الحالية (نفس الدوال اللي تستعملها أنت يدوياً)."""
    def __init__(self):
        import importlib.util
        def load(name, f):
            spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "ops", f)); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
        self.lt = load("lt", "link-tiktok-agency.py"); self.lw = load("lw", "link-web.py"); self.at = self.lw.at; self.db = self.lw.DB
        if not hasattr(self.lt, "do_link"): raise SystemExit("link-tiktok-agency.py has no do_link (unexpected version)")

    def psql(self, sql, v=None): return self.at.psql(self.db, sql, v or {}, tx=False)

    def do_link(self, slug, tid, token, chosen, info):
        import contextlib, io
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf): self.lt.do_link(self.db, slug, tid, token, chosen, info)
        except SystemExit as e: raise Stop("فشل حفظ الربط (%s). ما انربط شي." % scrub(str(e) or buf.getvalue(), token)[:120])
        except Exception as e: raise Stop("فشل حفظ الربط (%s). ما انربط شي." % type(e).__name__)


def load_cfg(env=None):
    d = {}
    if os.path.exists(ENV_FILE):
        for l in open(ENV_FILE, encoding="utf-8").read().splitlines():
            if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); d[k] = v
    d.update({k: v for k, v in (env or {}).items() if v})
    if not re.fullmatch(r"[0-9]{5,25}", d.get("TIKTOK_APP_ID", "")) or len(d.get("TIKTOK_APP_SECRET", "")) < 8: raise SystemExit("linker.env needs TIKTOK_APP_ID and TIKTOK_APP_SECRET")
    return d


def process_one(deps, cfg, out=print, exch=exchange, info_fn=account_info):
    """يعالج طلباً واحداً. يرجّع True لو كان فيه طلب (حتى لو فشل)، False لو ما كو شي."""
    raw = deps.psql(CLAIM_SQL).strip()
    if not raw: return False
    row = raw.splitlines()[0]   # psql قد يضيف سطر «UPDATE 1» بعد الصف
    parts = row.split("|")
    if len(parts) < 5: out("claim: bad row shape"); return True
    rid, tid, code, slug, cur = parts[0], parts[1], parts[2], parts[3], parts[4]
    def done(status, msg, res=None):
        deps.psql(FINISH_SQL, {"st": status, "msg": msg, "res": json.dumps(res or {}, ensure_ascii=False), "rid": rid})
    token = None
    try:
        if not (UUID_RE.fullmatch(rid) and UUID_RE.fullmatch(tid) and SLUG_RE.fullmatch(slug) and CODE_RE.fullmatch(code)): raise Stop("طلب غير صالح.")
        already = deps.psql("SELECT count(*) FROM core.ad_accounts WHERE tenant_id = :'tid'::uuid AND platform = 'tiktok' AND unlinked_at IS NULL;", {"tid": tid}).strip()
        if already != "0": raise Stop("عندك حساب تيك توك مربوط أصلاً. لتغييره تواصل مع الإدارة (إعادة التفويض تبطل التوكن الحالي).")
        token, granted = exch(cfg["TIKTOK_APP_ID"], cfg["TIKTOK_APP_SECRET"], code)
        if not granted: raise Stop("ما وصلنا أي حساب إعلاني من تيك توك. ارجع وبالصفحة اختر حسابات وفعّل كل الصلاحيات.")
        info = info_fn(token, granted)
        readable = [a for a in granted if a in info]
        taken = set(deps.psql("SELECT external_id FROM core.ad_accounts WHERE platform = 'tiktok' AND unlinked_at IS NULL;").split())
        skipped_taken = [a for a in readable if a in taken]
        cand = [a for a in readable if a not in taken]
        chosen = [a for a in cand if info[a][1] == cur] if cur else []
        skipped_cur = [a for a in cand if a not in chosen]
        if not chosen:
            why = []
            if len(readable) < len(granted): why.append("%d حساب ما قدرنا نقرأه" % (len(granted) - len(readable)))
            if skipped_taken: why.append("%d حساب مربوط بحساب ثاني" % len(skipped_taken))
            if skipped_cur: why.append("%d حساب عملته غير %s" % (len(skipped_cur), cur or "المطلوبة"))
            raise Stop("ما انربط ولا حساب (%s)." % "، ".join(why or ["لا حسابات صالحة"]))
        deps.do_link(slug, tid, token, chosen, info)
        res = {"linked": [{"id": a, "name": info[a][0], "currency": info[a][1]} for a in chosen], "skipped_taken": len(skipped_taken), "skipped_currency": len(skipped_cur), "skipped_unreadable": len(granted) - len(readable)}
        note = "انربط %d حساب." % len(chosen) + (" (تخطّيت %d لأنها مربوطة بحساب ثاني)" % len(skipped_taken) if skipped_taken else "") + (" (تخطّيت %d لاختلاف العملة)" % len(skipped_cur) if skipped_cur else "")
        done("done", note + " حسابك يصير جاهزاً بعد الفحص الدوري (خلال ساعة).", res)
        out("linked req=%s tenant=%s accounts=%d" % (rid[:8], slug, len(chosen)))
    except Stop as e:
        done("failed", scrub(e, token, code, cfg.get("TIKTOK_APP_SECRET"))); out("failed req=%s: %s" % (rid[:8], scrub(e, token, code, cfg.get("TIKTOK_APP_SECRET"))))
    except Exception as e:
        done("failed", "خطأ غير متوقع، ما انربط شي. تواصل مع الإدارة."); out("error req=%s: %s" % (rid[:8], type(e).__name__))
    return True


def main():
    cfg = load_cfg(os.environ); deps = Live(); last_sweep = 0
    print("web-linker started", flush=True)
    while True:
        try:
            if time.time() - last_sweep > 60: deps.psql(SWEEP_SQL); last_sweep = time.time()
            busy = process_one(deps, cfg, out=lambda m: print(m, flush=True))
        except Exception as e:
            print("loop error: %s" % type(e).__name__, flush=True); busy = False
        if not busy: time.sleep(3)


if __name__ == "__main__":
    main()
