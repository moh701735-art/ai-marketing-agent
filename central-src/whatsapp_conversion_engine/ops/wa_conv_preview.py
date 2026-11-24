#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""إثبات صغير (قراءة فقط، لا حملة، لا صرف): يبيّن المسار الحقيقي «مبيعات/زيارات + رابط واتساب» مقابل «محادثات واتساب» الأصلي.
  [A] من الكود الحي داخل صورة الـBroker (بدون شبكة): spark.OBJECTIVES + نصوص adgroup_params/validate/_launch_spark المفلترة + محاولة استدعاء الدوال النقية
  [B] أسطر wf_ingress.py (تحويل النص لهدف) — ASCII فقط
  [C] WhatsAppConversationPreview (من قراءة حية read-only لحملة واتساب أصلية، أو من المسجّل لو SA_OFFLINE=1)
  [D] مقارنة الحالي vs واتساب،  [E] EVENT DELIVERY NOT VERIFIED
عمليات الـBroker الوحيدة المسموحة: tiktok.read_* (يُفرض بالكود). لا create/set/update/launch.
  SA_SLUG=mohm SA_ACCT=7593807340588253185 python3 ops/wa-conv-preview.py     (SA_OFFLINE=1 بدون قراءات تيك توك؛ SA_PHONE=… رقم اختياري)"""
import importlib.util, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("WA_ROOT", os.path.dirname(HERE))
sys.path.insert(0, os.environ.get("WA_PREVIEW_DIR", os.path.join(ROOT, "whatsapp_conversion_engine", "campaign_builder")))
import preview as pvm  # noqa: E402

NA = "N/A"
KEYWORDS = r"whatsapp|event_set|phone|promotion|objective|landing|call_to_action|optimization|billing|OBJECTIVES|messaging|bid_type|budget_mode|pixel|CONVERT|CONVERSATION|WEBSITE|CLICK"
INGRESS_RX = r"WEB_CONVERSIONS|LEAD_GENERATION|TRAFFIC|objective|landing_url|wa\.me|whatsapp|sales\b"

INSPECT = r'''
import sys, os, re, json, inspect
roots = os.environ.get("WA_INSPECT_ROOTS", "/app:/srv:/opt:/").split(":")
for r in roots: sys.path.insert(0, r)
KW = re.compile(os.environ.get("WA_KW"), re.I)
out = {"sections": {}, "calls": {}}
try:
    from app import spark
except Exception:
    try:
        from broker.app import spark
    except Exception as e:
        print(json.dumps({"error": "spark import failed: %s" % type(e).__name__})); sys.exit(0)
base = os.path.dirname(spark.__file__)
def fn_text(path, name):
    try: t = open(os.path.join(base, path), encoding="utf-8").read()
    except Exception as e: return None
    m = re.search(r"^([ ]*)(?:async )?def %s\b" % re.escape(name), t, re.M)
    if not m: return None
    ind = len(m.group(1)); lines = t[m.start():].splitlines(); keep = [lines[0]]
    for l in lines[1:]:
        if l.strip() and (len(l) - len(l.lstrip())) <= ind and not l.lstrip().startswith(("#", ")", "]", "}")): break
        keep.append(l)
    first = t[:m.start()].count("\n") + 1
    return first, keep
def sect(label, path, name, full_max=0):
    r = fn_text(path, name)
    if not r: out["sections"][label] = ["(function not found: %s in %s)" % (name, path)]; return
    first, keep = r; sel = [(first + i, l) for i, l in enumerate(keep)]
    if not (full_max and len(keep) <= full_max): sel = [(n, l) for n, l in sel if KW.search(l)]
    out["sections"][label] = ["%d: %s" % (n, l.strip()[:170]) for n, l in sel[:130]]
out["objectives"] = repr(getattr(spark, "OBJECTIVES", None))[:400]
for nm in ("adgroup_params", "validate"):
    try: out[nm + "_sig"] = str(inspect.signature(getattr(spark, nm)))
    except Exception as e: out[nm + "_sig"] = "N/A (%s)" % type(e).__name__
sect("spark.adgroup_params", "spark.py", "adgroup_params", 140)
sect("spark.validate (filtered)", "spark.py", "validate")
sect("service._launch_spark (filtered)", "service.py", "_launch_spark")
sect("service._launch_smart (filtered)", "service.py", "_launch_smart")
BASE = {"budget": 5, "days": 1, "name": "PREVIEW-DELETE-ME", "product": "x", "ad_text": "x", "page_name": "x"}
SYN = {"sales": {"objective": "sales"}, "traffic": {"objective": "traffic", "landing_url": "https://example.com/p"},
       "whatsapp": {"objective": "whatsapp", "phone_number": "+9647000000000"}, "leads": {"objective": "leads"}}
for k, extra in SYN.items():
    p = dict(BASE); p.update(extra); rec = {}
    try:
        v = spark.validate(dict(p)); rec["validate"] = repr(v)[:260]
        q = v if isinstance(v, dict) else p
    except Exception as e:
        rec["validate"] = "EXC %s: %s" % (type(e).__name__, str(e)[:200]); q = p
    try:
        sig = inspect.signature(spark.adgroup_params); args = []
        for n, prm in sig.parameters.items():
            if prm.default is not inspect._empty: continue
            args.append(q if n in ("p", "params", "prm", "launch") else ("1" if "id" in n else None))
        r = spark.adgroup_params(*args); rec["adgroup_params"] = r if isinstance(r, dict) else repr(r)[:300]
    except Exception as e:
        rec["adgroup_params"] = "EXC %s: %s" % (type(e).__name__, str(e)[:200])
    out["calls"][k] = rec
print(json.dumps(out, ensure_ascii=False, default=str))
'''


def sh(cmd, inp=None):
    return subprocess.run(cmd, input=inp, capture_output=True, text=True)


def run_inspector(img, runner=sh):
    """يشغّل المفتش داخل صورة الـBroker بلا شبكة (--network none) — لا يقدر يتصل بأي شي."""
    try: r = runner(["docker", "run", "--rm", "--network", "none", "-e", "WA_KW=" + KEYWORDS, "--entrypoint", "python", img, "-c", INSPECT])
    except OSError as e: return {"error": "inspector failed: docker unavailable (%s)" % type(e).__name__}
    try: return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception: return {"error": "inspector failed: " + (r.stderr or r.stdout or "").strip()[-200:]}


def ascii_fold(s): return re.sub(r"[^ -~]", "?", s)


def grep_ingress(path, rx=INGRESS_RX, cap=60):
    if not os.path.exists(path): return ["(ingress file not found: N/A)"]
    out = []
    for i, l in enumerate(open(path, encoding="utf-8", errors="replace").read().splitlines(), 1):
        if re.search(rx, l, re.I): out.append("%d: %s" % (i, ascii_fold(re.sub(r"\s+", " ", l).strip())[:190]))
    return out[:cap] + (["... (%d more)" % (len(out) - cap)] if len(out) > cap else [])


READ_OP = re.compile(r"^tiktok\.read_[a-z_]+$")


def read_only(calls):
    """حارس كود: أي عملية غير tiktok.read_* ترفع خطأ قبل أي استدعاء"""
    for c in calls:
        if not READ_OP.match(c["op"]): raise SystemExit("REFUSED: non-read op " + c["op"])
    return calls


def load_wad():
    p = os.environ.get("WA_DIAG_PATH", os.path.join(HERE, "wa-diagnose.py"))
    if not os.path.exists(p): raise SystemExit("missing ops/wa-diagnose.py (p263) — install it first")
    s = importlib.util.spec_from_file_location("wad", p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def live_reference(wad, env, ctx, acct, bk=None):
    """قراءة فقط: أحدث adgroup واتساب أصلي + event sets لرقمه + مؤشر conversion (غير مباشر). → dict"""
    bk = bk or (lambda calls: wad.broker(env, ctx, acct, read_only(calls)))
    r = {"adgroup": None, "campaign": None, "event_sets": [], "sets_shape": NA, "conversion": NA, "errors": []}
    c = bk([{"label": "campaigns", "op": "tiktok.read_campaigns", "params": {"page": 1, "page_size": 100}}])[0]
    camps = sorted((wad.find_list(c.get("data")) or []) if c["ok"] else [], key=lambda x: str(x.get("create_time") or ""), reverse=True)
    if not c["ok"]: r["errors"].append("read_campaigns: " + wad.errtxt(c.get("error")))
    ids = [str(x.get("campaign_id")) for x in camps[:12]]
    if ids:
        g = bk([{"label": "adgroups", "op": "tiktok.read_adgroups", "params": {"campaign_ids": ids, "page_size": 100}}])[0]
        if not g["ok"]: r["errors"].append("read_adgroups: " + wad.errtxt(g.get("error")))
        byc = {str(x.get("campaign_id")): x for x in camps}
        for a in (wad.find_list(g.get("data")) or []) if g["ok"] else []:
            if wad.classify_adgroup(a, byc.get(str(a.get("campaign_id"))))[0] == "NATIVE_WHATSAPP":
                r["adgroup"], r["campaign"] = a, byc.get(str(a.get("campaign_id"))); break
    ma = (r["adgroup"] or {}).get("messaging_app_account_id")
    if ma:
        e = bk([{"label": "event_sets", "op": "tiktok.read_message_event_set", "params": {"messaging_app_type": "WHATSAPP", "messaging_app_account_id": ma}}])[0]
        r["event_sets"] = (wad.find_list(e.get("data")) or []) if e["ok"] else []
        r["sets_shape"] = json.dumps(wad.shape(e.get("data")), ensure_ascii=False)[:200] if e["ok"] else "FAIL " + wad.errtxt(e.get("error"))
    if r["campaign"]:
        import datetime
        end = datetime.date.today(); start = end - datetime.timedelta(days=30)
        p = {"report_type": "BASIC", "data_level": "AUCTION_CAMPAIGN", "dimensions": ["campaign_id"], "start_date": str(start), "end_date": str(end), "page_size": 100, "page": 1, "metrics": ["spend", "conversion"]}
        rp = bk([{"label": "rep", "op": "tiktok.read_report", "params": p}])[0]
        for row in (wad.find_list(rp.get("data")) or []) if rp["ok"] else []:
            if str((row.get("dimensions") or {}).get("campaign_id")) == str(r["campaign"].get("campaign_id")): r["conversion"] = (row.get("metrics") or {}).get("conversion", NA)
    return r


def current_payloads(insp):
    """payload الحالي لكل هدف: من استدعاء الكود الحي لو نجح، وإلا من المسجّل (يُذكر المصدر بوضوح)"""
    cur, src = {}, {}
    objs = insp.get("objectives", "")
    for k in ("sales", "traffic"):
        call = (insp.get("calls") or {}).get(k, {}).get("adgroup_params")
        if isinstance(call, dict) and call:
            d = {kk: v for kk, v in call.items() if kk in pvm.COMPARE_FIELDS}
            m = re.search(r"['\"]%s['\"]\s*:\s*['\"]([A-Z_]+)['\"]" % k, objs)
            if m: d["objective_type"] = m.group(1)
            cur[k], src[k] = d, "LIVE code (spark.adgroup_params, offline call)"
        else:
            cur[k], src[k] = dict(pvm.RECORDED_CURRENT[k]), "RECORDED p152/p176 (live call unavailable: %s)" % str((insp.get("calls") or {}).get(k, {}).get("adgroup_params", NA))[:90]
    return cur, src


def final_block(ref, pv, cur, src):
    """كتلة نهائية ASCII فقط (ما تتخرب بترجمة المتصفح): محاكاة Sales + WhatsApp + تحقق payload + الحكم"""
    sim = pvm.simulate_request(os.environ.get("SA_SIMULATE", "sales+whatsapp"))
    obj = sim["objective"] if sim["objective"] in cur else "sales"
    val = pvm.validate_payload(pv); v = pvm.verdict(sim, pv, val, obj, cur.get(obj), src.get(obj, "recorded"))
    L = ["", "======== FINAL BLOCK (ASCII, read-only, nothing created, no spend) ========",
         "SIMULATED REQUEST : %s (preview only; ingress/Broker/DB untouched)" % v["request"],
         "LIVE REFERENCE    : %s" % ("yes (read-only TikTok reads, newest native WhatsApp adgroup)" if ref["adgroup"] else "NO (recorded values only)"),
         "CURRENT PATH      : " + v["current_path"],
         "PROPOSED PATH     : " + v["proposed_path"], "PROPOSED PAYLOAD (phone masked):"]
    for k in pvm.FIELDS:
        f = pv["fields"][k]; L.append("  %-27s = %-45s [%s]" % (k, ascii_fold(str(f["value"])), ascii_fold(f["source"])))
    L += ["PAYLOAD VALIDATION : " + v["payload_validation"],
          "  confirmed live   : " + (", ".join(v["confirmed_live"]) or "none"),
          "  UNCONFIRMED (=N/A, not invented): " + (", ".join(v["unconfirmed_as_NA"]) or "none"),
          "  MISSING (N/A)    : " + (", ".join(v["missing_NA"]) or "none"),
          "EVENT DELIVERY STATUS: " + v["event_delivery_status"] + "  (message_event_set_id and the `conversion` metric = indirect evidence only; conversion metric for the reference campaign, 30d = %s)" % ref["conversion"],
          "NO CAMPAIGN CREATED. Broker ops used: read-only tiktok.read_* (code-enforced)."]
    print("\n".join(L))


def main():
    slug = os.environ.get("SA_SLUG", "mohm").strip(); acct = os.environ.get("SA_ACCT", "7593807340588253185").strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", slug) or not re.fullmatch(r"[0-9]{6,25}", acct): sys.exit("bad SA_SLUG / SA_ACCT")
    print("== إثبات صغير: مبيعات/زيارات+رابط واتساب مقابل محادثات واتساب | قراءة فقط، بلا حملة ولا صرف ==")
    img = os.environ.get("BROKER_IMAGE", "central-broker:prod")
    insp = run_inspector(img)
    print("\n[A] الكود الحي داخل صورة الـBroker (بلا شبكة):")
    if insp.get("error"): print("  " + insp["error"])
    else:
        print("  spark.OBJECTIVES = " + str(insp.get("objectives"))); print("  validate%s | adgroup_params%s" % (insp.get("validate_sig"), insp.get("adgroup_params_sig")))
        for k, lines in insp["sections"].items():
            print("\n  --- %s ---" % k)
            for l in lines: print("   " + l)
        print("\n  --- استدعاءات نقية بمعاملات وهمية (بلا شبكة) ---")
        for k, rec in insp["calls"].items(): print("   %s: validate=%s\n        adgroup_params=%s" % (k, rec.get("validate"), json.dumps(rec.get("adgroup_params"), ensure_ascii=False)[:420]))
    print("\n[B] wf_ingress.py (ASCII فقط):")
    for l in grep_ingress(os.path.join(ROOT, "n8n", "wf_ingress.py")): print("   " + l)
    ref = {"adgroup": None, "event_sets": [], "conversion": NA, "errors": [], "campaign": None, "sets_shape": NA}
    if not os.environ.get("SA_OFFLINE"):
        wad = load_wad(); env = wad.Env()
        tid = wad.psql(env, "select tenant_id from core.tenants where slug='%s'" % slug)
        ctxs = wad.psql(env, "select ctx from api.job_contexts_for_status(ARRAY['TESTING','NEEDS_REVIEW','READY'],100) where tenant_id='%s'" % tid[0]) if tid else []
        if not ctxs: sys.exit("tenant/ctx not found")
        ref = live_reference(wad, env, ctxs[0], acct)
    print("\n[C] " + ("مرجع حي (قراءة): أحدث حملة واتساب أصلية" if ref["adgroup"] else "لا مرجع حي — يُستعمل المسجّل (p152) ويُوسَم بذلك"))
    for e in ref["errors"]: print("   read error: " + e)
    pv = pvm.WhatsAppConversationPreview(ref["adgroup"], ref["event_sets"]).build(os.environ.get("SA_PHONE"))
    print(pvm.WhatsAppConversationPreview.render(pv))
    print("   event set read shape: " + str(ref["sets_shape"]))
    cur, src = current_payloads(insp if not insp.get("error") else {})
    print("\n[D] المقارنة:")
    for k in ("sales", "traffic"): print(pvm.render_compare(k, pvm.compare(cur[k], pv), src[k]))
    print("\n[E] " + pvm.EVENT_DELIVERY)
    print("   مؤشر غير مباشر فقط (مو إثبات): metric conversion للحملة المرجعية آخر 30 يوم = %s" % ref["conversion"])
    print("   ما في عملية قراءة لأحداث المحادثات/أنواعها بالكتالوج → التحقق يدوي: Events Manager > Data sources > Messaging.")
    final_block(ref, pv, cur, src)


if __name__ == "__main__":
    main()
