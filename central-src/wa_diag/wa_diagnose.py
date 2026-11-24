#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تشخيص قراءة فقط لحساب تيك توك واحد (افتراضي mohm / 7593807340588253185): هل مسار واتساب الأصلي (محادثات) يشتغل، ولماذا «صرف بدون رسائل».
لا ينشئ ولا يعدّل أي شي: فقط عمليات قراءة عبر الـBroker (adgroups/campaigns/report/event sets/advertiser) + استعلامات SELECT على DB.
لا يطبع أي توكن/مفتاح؛ يطبع حقولاً مسموحة فقط، والأرقام والروابط مقنّعة. غير المعروف = N/A.
  SA_SLUG=mohm SA_ACCT=7593807340588253185 python3 ops/wa-diagnose.py   (اختياري: SA_CAMPS=id1,id2 لتحديد حملات؛ SA_DAYS=30)"""
import datetime, json, os, re, subprocess, sys

NA = "N/A"
ADG_KEYS = re.compile(r"^(adgroup_id|adgroup_name|campaign_id|operation_status|secondary_status|promotion_type|promotion_target_type|optimization_goal|optimization_event|optimize_goal|billing_event|bid_type|bid_price|conversion_bid_price|"
                      r"messaging_app_type|messaging_app_account_id|message_event_set_id|messaging_app_id|phone_region_code|phone_region_calling_code|phone_number|pixel_id|optimization_event|deep_bid_type|schedule_type|budget_mode|budget|placement_type|"
                      r"shopping_ads_type|identity_type|app_download_url|landing_page_url|promotion_website_type|dsa_.*|conversion_window|click_attribution_window|view_attribution_window|campaign_automation_type)$")
ADG_BRIEF = re.compile(r"^(adgroup_id|operation_status|promotion_type|messaging_app_type|optimization_goal|optimization_event|billing_event|bid_type|budget|budget_mode|message_event_set_id|messaging_app_account_id|phone_region_calling_code|landing_page_url|pixel_id|promotion_target_type)$")
AD_KEYS = re.compile(r"^(ad_id|ad_name|adgroup_id|operation_status|secondary_status|call_to_action|call_to_action_id|landing_page_url|ad_format|identity_type|tiktok_item_id|creative_type|display_name|ad_text|deeplink|fallback_type|page_id|promotion_type)$", re.I)
REP_BASE = ["spend", "impressions", "clicks", "ctr", "cpc", "cpm", "conversion", "cost_per_conversion"]
REP_EXTRA = ["result", "cost_per_result", "result_rate"]   # قد ترفضها بعض الحسابات: تُطلب منفصلة حتى ما تُسقط الأساس


def mask_phone(s):
    d = re.sub(r"\D", "", str(s))
    return (str(s)[:4] + "…" + d[-3:]) if len(d) >= 7 else str(s)


def mask_url(u):
    u = str(u or "")
    if not u: return NA
    m = re.match(r"^(https?://)([^/\s?#]+)([^?#\s]*)", u)
    if not m: return "(غير URL)"
    host, path = m.group(2).lower(), m.group(3)
    kind = "WHATSAPP_LINK" if re.search(r"(^|\.)wa\.me$|whatsapp\.com$", host) else ("TIKTOK" if "tiktok" in host else "OTHER")
    tail = re.sub(r"\d{7,}", lambda x: mask_phone(x.group(0)), path)[:30]
    return "%s %s%s%s" % (kind, m.group(1), host, tail)


def safe(k, v):
    k = str(k).lower()
    if ("phone" in k and "region" not in k) or k.endswith("app_account_id"): return mask_phone(v)
    if "url" in k or "link" in k: return mask_url(v)
    if isinstance(v, (dict, list)): return json.dumps(v, ensure_ascii=False)[:200]
    return v


def pick(row, rx):
    return {k: safe(k, v) for k, v in sorted(row.items()) if rx.match(k)}


def find_list(d):
    if isinstance(d, dict):
        if isinstance(d.get("list"), list): return d["list"]
        for v in d.values():
            r = find_list(v)
            if r is not None: return r
    return None


def classify_adgroup(g, camp=None):
    """يصنّف مسار الإنشاء من حقول المجموعة كما قرأها تيك توك (دليل، مو تخمين). → (path, notes)"""
    pt, goal, app, es = g.get("promotion_type"), g.get("optimization_goal") or g.get("optimize_goal"), g.get("messaging_app_type"), g.get("message_event_set_id")
    url = str(g.get("landing_page_url") or "") + " " + str((camp or {}).get("landing_page_url") or "")
    notes = []
    if pt == "LEAD_GEN_CLICK_TO_SOCIAL_MEDIA_APP_MESSAGE" and app == "WHATSAPP":
        notes.append("native WhatsApp messaging destination")
        if goal != "CONVERSATION": notes.append("optimization_goal=%s (ليس CONVERSATION)" % goal)
        if g.get("optimization_event") not in (None, "MESSAGE"): notes.append("optimization_event=%s" % g.get("optimization_event"))
        if not es: notes.append("message_event_set_id مفقود بقراءة تيك توك")
        return "NATIVE_WHATSAPP", notes
    if pt == "LEAD_GEN_CLICK_TO_TT_DIRECT_MESSAGE": return "TIKTOK_DM", notes
    obj = str((camp or {}).get("objective_type") or "")
    wa = "wa.me" in url.lower() or "whatsapp.com" in url.lower()
    if obj == "WEB_CONVERSIONS" or goal in ("CONVERT", "SHOP"):
        return ("SALES_WEB_CONVERSIONS_WA_LINK" if wa else "SALES_WEB_CONVERSIONS"), notes + (["رابط واتساب كوجهة موقع"] if wa else [])
    if obj == "TRAFFIC" or goal == "CLICK":
        return ("TRAFFIC_CLICK_WA_LINK" if wa else "TRAFFIC_CLICK"), notes + (["رابط واتساب كوجهة موقع"] if wa else [])
    if obj == "LEAD_GENERATION": return "LEAD_FORM_OR_OTHER", notes
    return "UNKNOWN", notes


def eligibility(sets_ok, sets, native_ok, native_fail_classes):
    """مستوى الأهلية من الأدلة فقط. sets_ok: قراءة event sets نجحت؛ native_ok: عدد إنشاءات واتساب أصلية ناجحة تاريخياً."""
    if native_ok > 0 and sets: return "WHATSAPP_CONVERSATION_READY", "عندنا حملات واتساب أصلية بتيك توك (CONVERSATION) + مجموعة أحداث"
    if sets and not native_ok: return "UNKNOWN_READY_TO_TEST", "مجموعة أحداث موجودة لكن ما في حملة أصلية سابقة بهذا الحساب"
    if sets_ok and not sets: return "NOT_READY_NO_EVENT_SET", "ما في message event set بهذا الحساب"
    return "UNKNOWN", "تعذّرت القراءة: " + ", ".join(native_fail_classes[:3]) if native_fail_classes else "N/A"


def mask_ctx(s): return "REDACTED"


PY = r'''
import base64, hmac, hashlib, json, secrets, sys, time, urllib.request, urllib.error
job = json.loads(sys.stdin.read())
S = json.load(open("/s.json")); key = base64.b64decode(S["hmac_keys"]["n8n-runtime"]["key"])
def call(c):
    body = json.dumps({"ctx": job["ctx"], "platform": "tiktok", "op": c["op"], "ad_account": job["acct"], "params": c["params"], "idempotency_key": "wadiag-" + secrets.token_hex(12)}).encode()
    ts, n = int(time.time()), secrets.token_hex(12)
    sig = hmac.new(key, ("%d.%s." % (ts, n)).encode() + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request("http://%s:8080/v1/call" % job["host"], data=body, method="POST", headers={"content-type": "application/json", "x-key-id": "n8n-runtime", "x-timestamp": str(ts), "x-nonce": n, "x-signature": sig})
    try: return json.loads(urllib.request.urlopen(req, timeout=40).read())
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read() or b"{}")
        except Exception: return {"ok": False, "error": {"message": "http %s" % e.code}}
    except Exception as e: return {"ok": False, "error": {"message": str(e)[:160]}}
out = []
for c in job["calls"]:
    r = call(c); out.append({"label": c["label"], "op": c["op"], "ok": bool(r.get("ok")), "data": r.get("data"), "error": r.get("error")})
print(json.dumps(out, ensure_ascii=False))
'''
INTRO = r'''
import json, sys, re
for root in ("/app", "/srv", "/opt", "/"):
    sys.path.insert(0, root)
try:
    from app import catalog
except Exception:
    try: from broker.app import catalog
    except Exception as e:
        print(json.dumps({"error": "catalog import failed: %s" % type(e).__name__})); sys.exit(0)
rx = re.compile(r"message|event|identity|report|adgroup|campaign|^tiktok\.read_ad|advertiser|instant|pixel|whatsapp|bc_|business", re.I)
out = {}
for n, o in sorted(catalog.OPS.items()):
    if n.startswith("tiktok.") and rx.search(n):
        ps = getattr(o, "params", {}) or {}
        out[n] = {"write": bool(getattr(o, "write", False)), "path": getattr(o, "path", None), "params": {k: (getattr(v, "kind", str(v)) + ("*" if getattr(v, "required", False) else "")) for k, v in ps.items()}}
print(json.dumps(out, ensure_ascii=False))
'''


class Env:
    def __init__(self):
        self.net = os.environ.get("BROKER_NETWORK", "central-stg_backend"); self.img = os.environ.get("BROKER_IMAGE", "central-broker:prod")
        self.host = os.environ.get("BROKER_HOST", "central-stg-broker"); self.secrets = os.environ.get("SA_SECRETS", os.path.abspath("deploy/.secrets/broker_secrets.json"))
        self.pg = os.environ.get("PG_CONTAINER", "central-stg-pg")


def sh(cmd, inp=None):
    return subprocess.run(cmd, input=inp, capture_output=True, text=True)


def psql(env, sql):
    r = sh(["docker", "exec", env.pg, "psql", "-U", "postgres", "-d", "central", "-At", "-c", sql])
    if r.returncode: raise SystemExit("psql failed: " + r.stderr.strip()[-200:])
    return [l for l in r.stdout.splitlines() if l]


def broker(env, ctx, acct, calls):
    r = sh(["docker", "run", "--rm", "-i", "--network", env.net, "-v", env.secrets + ":/s.json:ro", "--entrypoint", "python", env.img, "-c", PY], json.dumps({"host": env.host, "ctx": ctx, "acct": acct, "calls": calls}))
    if r.returncode or not r.stdout.strip(): raise SystemExit("broker call failed: " + (r.stderr or r.stdout)[-300:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def introspect(env):
    r = sh(["docker", "run", "--rm", "--entrypoint", "python", env.img, "-c", INTRO])
    try: return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception: return {"error": "introspection failed"}


def errtxt(e): return json.dumps(e, ensure_ascii=False)[:260] if e else NA


def build_params(spec, want):
    """يمرّر فقط المعاملات الموجودة بمواصفة الـBroker (ما نخترع)"""
    p = (spec or {}).get("params")
    return {k: v for k, v in want.items() if p is None or k in p}


def main():
    slug = os.environ.get("SA_SLUG", "mohm").strip(); acct = os.environ.get("SA_ACCT", "7593807340588253185").strip(); days = int(os.environ.get("SA_DAYS", "30"))
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", slug) or not re.fullmatch(r"[0-9]{6,25}", acct): sys.exit("bad SA_SLUG / SA_ACCT")
    env = Env()
    tid = psql(env, "select tenant_id from core.tenants where slug='%s'" % slug)
    if not tid: sys.exit("tenant not found")
    ctx = psql(env, "select ctx from api.job_contexts_for_status(ARRAY['TESTING','NEEDS_REVIEW','READY'],100) where tenant_id='%s'" % tid[0])
    if not ctx: sys.exit("no context")
    ctx = ctx[0]
    print("== تشخيص واتساب (قراءة فقط) | العميل %s | الحساب %s | ctx %s ==" % (slug, acct, mask_ctx(ctx)))
    specs = introspect(env)
    if os.environ.get("SA_CATALOG"):
        print("\n[0] عمليات الـBroker (من الكتالوج الحي):")
        for n, s in sorted(specs.items()):
            if n != "error": print("  %s %s params=%s" % ("W" if s["write"] else "r", n, ",".join(sorted(s["params"])) or "-"))
    if "error" in specs: print("  (%s)" % specs["error"])
    rd = lambda n: specs.get(n)
    calls = [{"label": "advertiser", "op": "tiktok.read_advertiser", "params": {}}]
    calls.append({"label": "campaigns", "op": "tiktok.read_campaigns", "params": {"page": 1, "page_size": 100}})
    res = {t["label"]: t for t in broker(env, ctx, acct, calls)}
    # [1] المعلنة
    t = res["advertiser"]; adv = (find_list(t.get("data")) or [{}])[0] if t["ok"] else {}
    print("\n[1] الحساب (read_advertiser): " + ("OK" if t["ok"] else "FAIL " + errtxt(t.get("error"))))
    for k in ("name", "status", "currency", "country", "timezone", "role", "company", "industry", "description"): 
        if k in adv: print("  %s = %s" % (k, adv[k] if k != "description" else str(adv[k])[:60]))
    # [2] event sets
    # [3] campaigns + adgroups
    t = res["campaigns"]; camps = (find_list(t.get("data")) or []) if t["ok"] else []
    print("\n[3] الحملات (read_campaigns): " + ("OK n=%d" % len(camps) if t["ok"] else "FAIL " + errtxt(t.get("error"))))
    want = [c for c in os.environ.get("SA_CAMPS", "").replace(" ", "").split(",") if re.fullmatch(r"[0-9]{6,25}", c)]
    camps = sorted(camps, key=lambda c: str(c.get("create_time") or c.get("modify_time") or ""), reverse=True)
    sel = [c for c in camps if str(c.get("campaign_id")) in want] if want else camps[:12]
    byid = {str(c.get("campaign_id")): c for c in sel}
    ag = {}
    if sel:
        ids = [str(c.get("campaign_id")) for c in sel]
        r2 = broker(env, ctx, acct, [{"label": "adgroups", "op": "tiktok.read_adgroups", "params": build_params(rd("tiktok.read_adgroups"), {"campaign_ids": ids, "page_size": 100})}])[0]
        print("  read_adgroups: " + ("OK" if r2["ok"] else "FAIL " + errtxt(r2.get("error"))))
        for g in (find_list(r2.get("data")) or []): ag.setdefault(str(g.get("campaign_id")), []).append(g)
    summary = {}
    for c in sel:
        cid = str(c.get("campaign_id")); print("\n  ▸ حملة %s | %s | objective=%s | status=%s | automation=%s" % (cid, str(c.get("campaign_name"))[:40], c.get("objective_type", NA), c.get("operation_status", NA), c.get("campaign_automation_type", NA)))
        for g in ag.get(cid, [])[:3]:
            path, notes = classify_adgroup(g, c); summary[path] = summary.get(path, 0) + 1
            print("    مجموعة → PATH=%s %s" % (path, ("(" + "; ".join(notes) + ")") if notes else ""))
            print("    " + json.dumps(pick(g, ADG_KEYS if os.environ.get("SA_FULL") else ADG_BRIEF), ensure_ascii=False)[:900])
        if not ag.get(cid): print("    (ما انقرأت مجموعات: N/A)")
    print("\n  ملخص المسارات: " + (json.dumps(summary, ensure_ascii=False) if summary else NA))
    accts_msg = sorted({str(g.get("messaging_app_account_id")) for gl in ag.values() for g in gl if g.get("messaging_app_type") == "WHATSAPP" and g.get("messaging_app_account_id")})[:3]
    sets, sets_ok = [], False
    print("\n[2] Message Event Sets (read_message_event_set لكل رقم واتساب مستعمل بالحملات؛ المعاملات إلزامية messaging_app_type + messaging_app_account_id):")
    if not accts_msg: print("  N/A (ما في مجموعات واتساب أصلية بين الحملات المقروءة)")
    for ma in accts_msg:
        r5 = broker(env, ctx, acct, [{"label": "event_sets", "op": "tiktok.read_message_event_set", "params": build_params(rd("tiktok.read_message_event_set"), {"messaging_app_type": "WHATSAPP", "messaging_app_account_id": ma})}])[0]
        got = (find_list(r5.get("data")) or []) if r5["ok"] else []
        print("  رقم %s: %s" % (mask_phone(ma), ("OK n=%d" % len(got)) if r5["ok"] else "FAIL " + errtxt(r5.get("error"))))
        sets_ok = sets_ok or r5["ok"]; sets += got
        for x in got[:5]: print("    " + json.dumps({k: safe(k, v) for k, v in x.items() if not re.search(r"token|secret|key", k, re.I)}, ensure_ascii=False)[:420])
    # [4] إعلانات + نتائج
    if sel and (rd("tiktok.read_ads") or rd("tiktok.read_ad")):
        op = "tiktok.read_ads" if rd("tiktok.read_ads") else "tiktok.read_ad"
        r3 = broker(env, ctx, acct, [{"label": "ads", "op": op, "params": build_params(rd(op), {"campaign_ids": [str(c.get("campaign_id")) for c in sel[:6]], "page_size": 50})}])[0]
        print("\n[4] الإعلانات (%s): %s" % (op, "OK" if r3["ok"] else "FAIL " + errtxt(r3.get("error"))))
        for a in (find_list(r3.get("data")) or [])[:8]: print("  " + json.dumps(pick(a, AD_KEYS), ensure_ascii=False)[:520])
    else:
        print("\n[4] الإعلانات: N/A (لا توجد عملية قراءة إعلانات بالكتالوج أو لا توجد حملات)")
    end = datetime.date.today(); start = end - datetime.timedelta(days=days)
    if sel and rd("tiktok.read_report"):
        base = {"report_type": "BASIC", "data_level": "AUCTION_CAMPAIGN", "dimensions": ["campaign_id"], "start_date": str(start), "end_date": str(end), "page_size": 100, "page": 1}
        outs = broker(env, ctx, acct, [{"label": "rep_base", "op": "tiktok.read_report", "params": build_params(rd("tiktok.read_report"), {**base, "metrics": REP_BASE})},
                                       {"label": "rep_extra", "op": "tiktok.read_report", "params": build_params(rd("tiktok.read_report"), {**base, "metrics": REP_EXTRA})}])
        rows = {}
        for o in outs:
            print("\n[5%s] نتائج آخر %d يوم (%s): %s" % ("a" if o["label"] == "rep_base" else "b", days, o["label"], "OK" if o["ok"] else "FAIL " + errtxt(o.get("error"))))
            for row in (find_list(o.get("data")) or [])[:12]:
                m, d = row.get("metrics", {}), row.get("dimensions", {}); rows.setdefault(d.get("campaign_id", NA), {}).update(m)
        for cid, m in list(rows.items())[:12]: print("  campaign %s: %s" % (cid, json.dumps({k: m[k] for k in REP_BASE + REP_EXTRA if k in m}, ensure_ascii=False)))
    else:
        print("\n[5] النتائج: N/A (read_report غير موجودة بالكتالوج أو لا حملات)")
    # [6] تاريخ المحاولات من api_call_log (بدون payload)
    rows = psql(env, "select endpoint||'|'||coalesce(error_code,'ok')||'|'||count(*) from vault.api_call_log where tenant_id='%s' and platform::text='tiktok' and at > now() - interval '%d days' and (endpoint ilike '%%adgroup%%' or endpoint ilike '%%campaign%%' or endpoint ilike '%%message%%' or endpoint ilike '%%event%%') group by 1 order by 1" % (tid[0], days))
    print("\n[6] سجل استدعاءات الـBroker (endpoint|error_code|count آخر %d يوم؛ بدون محتوى):" % days)
    native_ok = 0; fails = []
    for r in rows[:40]:
        print("  " + r)
        ep, ec, cnt = (r.split("|") + ["", "", "0"])[:3]
        if "create_adgroup" in ep and ec == "ok": native_ok += int(cnt or 0)
        if ec != "ok": fails.append(ec)
    # [7] التقييم
    level, why = eligibility(sets_ok, sets, summary.get("NATIVE_WHATSAPP", 0) + native_ok, fails)
    print("\n[7] تقييم الأهلية من الأدلة: %s — %s" % (level, why))
    print("    التوصيف الرسمي المطلوب: LEAD_GENERATION + promotion_type=LEAD_GEN_CLICK_TO_SOCIAL_MEDIA_APP_MESSAGE + messaging_app_type=WHATSAPP + optimization_goal=CONVERSATION (+event MESSAGE) + message_event_set_id")
    print("    Messaging Partner / Message Events / Conversations بـEvents Manager: " + ("N/A (لا توجد عملية قراءة لهذي بالكتالوج)" if not any("event" in n and n != "tiktok.read_message_event_set" for n in specs) else "انظر العمليات بقسم [0]"))


if __name__ == "__main__":
    main()
