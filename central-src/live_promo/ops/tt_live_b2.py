#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""المرحلة B2 لـ«ترويج البث المباشر» (v3 / p282؛ بموافقة المالك 25-11): حملة اختبار واحدة PROBE-LIVE-DELETE-ME بهدف ENGAGEMENT (متوقفة، ميزانية INFINITE = بلا مجموعة/إعلان لا صرف)،
ثم مجموعات إعلانية **بقيمة غلط عمداً** (PRB_BAD) حتى يرجّع تيك توك قوائم allowed لـpromotion_type/optimization_goal/... — لا تُنشأ مجموعة ولا إعلان.
الحراسات بالكود: الهدف فقط ENGAGEMENT أو RF_ENGAGEMENT؛ كل نداء مجموعة لازم يحمل PRB_BAD؛ العملية الوحيدة غير القراءة الأخرى = set_campaign_status DISABLE.
الإخراج ASCII (القيم مكتوبة عادية + بحروف مفرّقة حتى لا تغيّرها ترجمة المتصفح). يتطلب p277 + p263. غير المعروف = N/A.
  SA_SLUG=mohm SA_ACCT=7593807340588253185 python3 ops/tt-live-b2.py        (LB_OBJ=ENGAGEMENT افتراضي، LB_CID=<id> لتخطي الإنشاء)"""
import importlib.util, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
NA = "N/A"
NAME = "PROBE-LIVE-DELETE-ME"
SENT = "PRB_BAD"
OBJ_OK = ("ENGAGEMENT", "RF_ENGAGEMENT")
FIELDS = ("promotion_type", "optimization_goal", "billing_event", "bid_type", "promotion_target_type", "optimization_event", "schedule_type", "messaging_app_type", "promotion_website_type")
TOKEN = re.compile(r"[A-Z][A-Z0-9_]{2,}")
def dummies():
    """قيم تعبئة آمنة للمعاملات الإلزامية على جهة Broker (أي مجموعة بقيمة PRB_BAD ترفضها تيك توك دائماً فلا تنشأ مجموعة)"""
    import datetime
    t0 = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) + datetime.timedelta(days=1); t1 = t0 + datetime.timedelta(days=1); f = "%Y-%m-%d %H:%M:%S"
    return {"location_ids": ["99237"], "budget": 50, "budget_mode": "BUDGET_MODE_TOTAL", "schedule_type": "SCHEDULE_START_END", "schedule_start_time": t0.strftime(f), "schedule_end_time": t1.strftime(f),
            "gender": "GENDER_UNLIMITED", "age_groups": ["AGE_18_24"], "placement_type": "PLACEMENT_TYPE_NORMAL", "placements": ["PLACEMENT_TIKTOK"], "pacing": "PACING_MODE_SMOOTH", "operation_status": "DISABLE", "languages": ["ar"]}


MISS = re.compile(r"missing param:? ([a-z_]+)|([a-z_]{3,}) (?:is )?(?:required|missing)", re.I)
LIVE_RX = re.compile(r"live|stream|room|follow|view|engag|interact|communit", re.I)


def fold(s): return re.sub(r"[^ -~]", "?", str(s))
def spaced(s): return " ".join(str(s))
def wrap(t): return "x_%s_x" % t          # كلمة واحدة بشرطات سفلية: ترجمة المتصفح ما تغيّرها (الأحرف المفرّقة كانت تتحول إلى «أنا»)


def load_wad():
    p = os.environ.get("WA_DIAG_PATH", os.path.join(HERE, "wa-diagnose.py"))
    if not os.path.exists(p): raise SystemExit("missing ops/wa-diagnose.py (p263) - install it first")
    s = importlib.util.spec_from_file_location("wad", p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def keep(spec, want):
    p = (spec or {}).get("params")
    return {k: v for k, v in want.items() if p is None or k in p}


def campaign_call(obj, spec=None):
    if obj not in OBJ_OK: raise SystemExit("REFUSED: objective must be one of " + ", ".join(OBJ_OK))
    return {"label": "create_campaign", "op": "tiktok.probe_campaign", "params": keep(spec, {"campaign_name": NAME, "objective_type": obj, "budget_mode": "BUDGET_MODE_INFINITE"})}


def adgroup_call(cid, fields, spec=None):
    """مجموعة بقيم غلط عمداً: يرفض الكود أي نداء بدون PRB_BAD بحقل enum معروف (حتى لا تنشأ مجموعة بالغلط)"""
    if not re.fullmatch(r"[0-9]{6,25}", str(cid)): raise SystemExit("REFUSED: bad campaign id")
    fields = [f for f in fields if f in FIELDS]
    want = {"campaign_id": str(cid), "adgroup_name": NAME}
    for f in fields: want[f] = SENT
    params = keep(spec, want)
    if not any(params.get(f) == SENT for f in FIELDS): raise SystemExit("REFUSED: adgroup probe without an invalid value")
    return {"label": "adgroup_" + ("all" if len(fields) > 1 else (fields[0] if fields else "none")), "op": "tiktok.probe_adgroup", "params": params}


def status_call(cid):
    if not re.fullmatch(r"[0-9]{6,25}", str(cid)): raise SystemExit("REFUSED: bad campaign id")
    return {"label": "pause", "op": "tiktok.set_campaign_status", "params": {"campaign_ids": [str(cid)], "operation_status": "DISABLE"}}


def tokens(msg):
    out = []
    for t in TOKEN.findall(str(msg or "")):
        if t.startswith("PRB_") or SENT.startswith(t) or t in out: continue
        out.append(t)
    return out


def find_list(d):
    if isinstance(d, dict):
        if isinstance(d.get("list"), list): return d["list"]
        for v in d.values():
            r = find_list(v)
            if r is not None: return r
    return None


def err_of(r): return (r or {}).get("error") or {}


def probe(wad, env, ctx, acct, call, spec, L, maxfill=14):
    """ينادي؛ إن رفض الـBroker بـ«missing param: X» وX بجدول التعبئة والكتالوج → يضيفه ويعيد (بحد أقصى). ما يلمس PRB_BAD: يبقى بالنداء دائماً."""
    D = dummies(); filled = []
    for _ in range(maxfill + 1):
        r = wad.broker(env, ctx, acct, [call])[0]
        e = err_of(r); m = MISS.search(str(e.get("message") or ""))
        name = (m.group(1) or m.group(2)) if m and str(e.get("class")) == "invalid_params" else None
        if not name or name in call["params"] or name not in D or name not in (spec or {}).get("params", {}): break
        call = {**call, "params": {**call["params"], name: D[name]}}; filled.append(name)
        if not any(call["params"].get(f) == SENT for f in FIELDS): raise SystemExit("REFUSED: probe lost its invalid value")
    if filled: L.append("   autofilled required params: " + ", ".join(filled))
    return r


def show_err(L, label, r):
    e = err_of(r); m = str(e.get("message") or ""); tk = tokens(m)
    L.append("[%s] ok=%s class=%s code=%s len=%d%s" % (label, bool(r.get("ok")), e.get("class", NA), e.get("platform_code", NA), len(m), " CUT-AT-300(list may be incomplete)" if len(m) == 300 else ""))
    L.append("   msg: " + fold(m)[:300])
    if len(m) >= 200 or (not tk and len(m) > 60):
        for i in range(0, min(len(m), 400), 40): L.append("   M%02d %s" % (i // 40 + 1, spaced(fold(m)[i:i + 40])))
    return tk


def run(wad, env, ctx, acct, obj="ENGAGEMENT", cid=None, out=print):
    L = []
    specs = wad.introspect(env); sp = lambda n: specs.get(n)
    for n in ("tiktok.probe_campaign", "tiktok.probe_adgroup"):
        s = sp(n)
        L.append("%s: %s" % (n, ("write=%s params=%s" % (s.get("write"), ",".join(sorted(s["params"])))) if s else "NOT IN CATALOG (apply p277 + rebuild Broker)"))
    if not sp("tiktok.probe_campaign") or not sp("tiktok.probe_adgroup"): out("\n".join(L)); return
    # 1) إيجاد/إنشاء الحملة
    st = "existing (LB_CID)" if cid else ""
    if not cid:
        rr = wad.broker(env, ctx, acct, [{"label": "list", "op": "tiktok.read_campaigns", "params": keep(sp("tiktok.read_campaigns"), {"page": 1, "page_size": 100})}])[0]
        for c in (find_list(rr.get("data")) or []) if rr.get("ok") else []:
            if str(c.get("campaign_name")) == NAME: cid = str(c.get("campaign_id")); st = "reused existing campaign with the probe name"; break
    if not cid:
        r = wad.broker(env, ctx, acct, [campaign_call(obj, sp("tiktok.probe_campaign"))])[0]
        if not r.get("ok"):
            L.append("CAMPAIGN NOT CREATED (TikTok/Broker refused):"); show_err(L, "create_campaign", r); L.append("NO CAMPAIGN CREATED."); out("\n".join(L)); return
        d = r.get("data") or {}; cid = str(d.get("campaign_id") or "")
        st = "CREATED just now (objective %s)" % obj
        if not re.fullmatch(r"[0-9]{6,25}", cid): L.append("created but campaign_id not found in response: " + fold(json.dumps(d))[:200]); out("\n".join(L)); return
    L.append("campaign %s : %s" % (cid, st))
    # 2) قراءة الحالة + إيقاف إن لزم
    def status():
        rr = wad.broker(env, ctx, acct, [{"label": "read", "op": "tiktok.read_campaigns", "params": keep(sp("tiktok.read_campaigns"), {"campaign_ids": [cid], "page_size": 10})}])[0]
        for c in (find_list(rr.get("data")) or []) if rr.get("ok") else []:
            if str(c.get("campaign_id")) == cid: return c
        return {}
    c = status(); ops = str(c.get("operation_status") or NA)
    L.append("read-back: objective_type=%s operation_status=%s budget_mode=%s" % (c.get("objective_type", NA), ops, c.get("budget_mode", NA)))
    if ops != "DISABLE":
        rp = wad.broker(env, ctx, acct, [status_call(cid)])[0]; c = status(); ops = str(c.get("operation_status") or NA)
        L.append("pause sent (ok=%s) -> operation_status now %s" % (rp.get("ok"), ops))
    if ops != "DISABLE": L.append("WARNING: campaign not confirmed PAUSED - pause it in Ads Manager now. (No ad group/ad exists, so no spend is possible.)")
    # 3) مجموعات بقيم غلط عمداً: كل الحقول معاً ثم حقل حقل
    res = {}
    cands = [f for f in FIELDS if f in (sp("tiktok.probe_adgroup") or {}).get("params", {})]
    L.append("adgroup fields available in catalog op: " + (", ".join(cands) or NA))
    need = sorted(k for k, v in (sp("tiktok.probe_adgroup") or {}).get("params", {}).items() if str(v).endswith("*"))
    L.append("required params of the op (Broker side): " + (", ".join(need) or "none"))
    calls = ([adgroup_call(cid, cands, sp("tiktok.probe_adgroup"))] if len(cands) > 1 else []) + [adgroup_call(cid, [f], sp("tiktok.probe_adgroup")) for f in cands]
    for call in calls:
        L.append("-- probe " + call["label"])
        r = probe(wad, env, ctx, acct, call, sp("tiktok.probe_adgroup"), L)
        if r.get("ok"): L.append("WARNING: TikTok ACCEPTED %s (an ad group may exist inside the paused campaign - delete it in Ads Manager)" % call["label"])
        tk = show_err(L, call["label"], r); res[call["label"]] = tk
    L += ["", "======== FINAL BLOCK (ASCII) ========", "campaign=%s status=%s objective=%s" % (cid, ops, c.get("objective_type", obj))]
    for k, tk in res.items():
        L.append("%s (%d values, one per line below as F|field|NN|x_TOKEN_x)" % (k, len(tk)))
        for i, t in enumerate(tk, 1): L.append("F|%s|%02d|%s" % (k.replace("adgroup_", ""), i, wrap(t)))
    live = sorted({t for tk in res.values() for t in tk if LIVE_RX.search(t)})
    named = sorted({t for tk in res.values() for t in tk if re.search(r"live|stream", t, re.I)})
    L += ["VALUES WITH LIVE OR STREAM IN THE NAME: " + (", ".join(wrap(t) for t in named) or "NONE FOUND"), "LIVE/VIEWER-LIKE VALUES: " + (", ".join(wrap(t) for t in live) or "NONE FOUND"),
          "No ad group and no ad were created (unless a line starting with WARNING: appears). The probe campaign stays PAUSED; delete it later in Ads Manager (name %s)." % NAME]
    out("\n".join(L))


def main():
    slug = os.environ.get("SA_SLUG", "mohm").strip(); acct = os.environ.get("SA_ACCT", "7593807340588253185").strip(); obj = os.environ.get("LB_OBJ", "ENGAGEMENT").strip(); cid = os.environ.get("LB_CID", "").strip() or None
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", slug) or not re.fullmatch(r"[0-9]{6,25}", acct) or (cid and not re.fullmatch(r"[0-9]{6,25}", cid)): sys.exit("bad SA_SLUG / SA_ACCT / LB_CID")
    if obj not in OBJ_OK: sys.exit("LB_OBJ must be one of " + ", ".join(OBJ_OK))
    wad = load_wad(); env = wad.Env()
    tid = wad.psql(env, "select tenant_id from core.tenants where slug='%s'" % slug)
    ctxs = wad.psql(env, "select ctx from api.job_contexts_for_status(ARRAY['TESTING','NEEDS_REVIEW','READY'],100) where tenant_id='%s'" % tid[0]) if tid else []
    if not ctxs: sys.exit("tenant/ctx not found")
    run(wad, env, ctxs[0], acct, obj, cid)


if __name__ == "__main__":
    main()
