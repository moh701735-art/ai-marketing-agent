#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WhatsApp Account Link Validator (قراءة فقط، لا حملة/صرف/تعديل): هل رقم واتساب معيّن مربوط فعلاً بحساب تيك توك، وهل له event set، وهل مؤهل للمحادثات.
عمليات الـBroker المسموحة: tiktok.read_* فقط (يُفرض بالكود). الأرقام مقنّعة دائماً. غير المعروف = N/A / UNKNOWN.
  SA_CHECK=07XXXXXXXXX SA_SLUG=mohm SA_ACCT=7593807340588253185 python3 ops/wa-link-validator.py"""
import importlib.util, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.environ.get("WA_ROOT", os.path.dirname(HERE))
WE = os.path.join(ROOT, "whatsapp_conversion_engine")
sys.path.insert(0, os.environ.get("WA_PREVIEW_DIR", os.path.join(WE, "campaign_builder"))); sys.path.insert(0, os.environ.get("WA_VALIDATOR_DIR", os.path.join(WE, "validator")))
import preview as pvm  # noqa: E402
import link_validator as lv  # noqa: E402

NA = "N/A"
READ_OP = re.compile(r"^tiktok\.read_[a-z_]+$")


def read_only(calls):
    for c in calls:
        if not READ_OP.match(c["op"]): raise SystemExit("REFUSED: non-read op " + c["op"])
    return calls


def load_wad():
    p = os.environ.get("WA_DIAG_PATH", os.path.join(HERE, "wa-diagnose.py"))
    if not os.path.exists(p): raise SystemExit("missing ops/wa-diagnose.py (p263) — install it first")
    s = importlib.util.spec_from_file_location("wad", p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def gather(wad, bk, target_e164):
    """قراءات فقط. → dict بكل الأدلة"""
    R = {"advertiser": {}, "errors": [], "adgroups": [], "sets_by_number": {}, "target_sets": [], "target_ok": False, "target_err": None, "campaigns": 0, "set_shapes": []}
    a = bk([{"label": "advertiser", "op": "tiktok.read_advertiser", "params": {}}])[0]
    if a["ok"]: R["advertiser"] = (wad.find_list(a.get("data")) or [{}])[0]
    else: R["errors"].append("read_advertiser: " + wad.errtxt(a.get("error")))
    c = bk([{"label": "campaigns", "op": "tiktok.read_campaigns", "params": {"page": 1, "page_size": 100}}])[0]
    camps = sorted((wad.find_list(c.get("data")) or []) if c["ok"] else [], key=lambda x: str(x.get("create_time") or ""), reverse=True)
    if not c["ok"]: R["errors"].append("read_campaigns: " + wad.errtxt(c.get("error")))
    R["campaigns"] = len(camps); ids = [str(x.get("campaign_id")) for x in camps[:40]]
    for i in range(0, len(ids), 10):
        g = bk([{"label": "adgroups", "op": "tiktok.read_adgroups", "params": {"campaign_ids": ids[i:i + 10], "page_size": 100}}])[0]
        if g["ok"]: R["adgroups"] += wad.find_list(g.get("data")) or []
        else: R["errors"].append("read_adgroups: " + wad.errtxt(g.get("error")))
    nums = lv.collect_numbers(R["adgroups"], lambda g: wad.classify_adgroup(g)[0] == "NATIVE_WHATSAPP"); R["numbers"] = nums
    for k, n in nums.items():
        e = bk([{"label": "es", "op": "tiktok.read_message_event_set", "params": {"messaging_app_type": "WHATSAPP", "messaging_app_account_id": n["raw_example"]}}])[0]
        R["sets_by_number"][k] = ((wad.find_list(e.get("data")) or []) if e["ok"] else [], e["ok"], None if e["ok"] else wad.errtxt(e.get("error")))
        if e["ok"] and len(R["set_shapes"]) < 1: R["set_shapes"].append(json.dumps(wad.shape(e.get("data")), ensure_ascii=False)[:200])
    if target_e164:
        t = lv.digits(target_e164)
        if t in R["sets_by_number"]: R["target_sets"], R["target_ok"], R["target_err"] = R["sets_by_number"][t]
        else:
            seen, errs, ok = [], [], False
            for form in ("+" + t, t):                                     # صيغة messaging_app_account_id غير مؤكدة: نجرّب الصيغتين (قراءة فقط)
                e = bk([{"label": "es_t", "op": "tiktok.read_message_event_set", "params": {"messaging_app_type": "WHATSAPP", "messaging_app_account_id": form}}])[0]
                ok = ok or e["ok"]
                if e["ok"]: seen += wad.find_list(e.get("data")) or []
                else: errs.append(wad.errtxt(e.get("error"))[:120])
            R["target_sets"], R["target_ok"], R["target_err"] = seen, ok, "; ".join(errs)[:200] or None
    return R


def report(R, target_raw):
    tgt = None; warn = None
    if target_raw:
        try: tgt = pvm.normalize_phone(target_raw)["e164"]
        except ValueError as e: warn = str(e)
    a = lv.assess(tgt, R["numbers"], R["target_sets"], R["target_ok"], R["target_err"]) if tgt else None
    L = ["== WhatsApp Account Link Validator (read-only; nothing created, no spend, DB/Broker/n8n untouched) =="]
    adv = R["advertiser"]; L.append("ACCOUNT: name=%s status=%s currency=%s country=%s" % (adv.get("name", NA), adv.get("status", NA), adv.get("currency", NA), adv.get("country", NA)))
    L.append("READ: campaigns=%d adgroups=%d native-WhatsApp numbers=%d" % (R["campaigns"], len(R["adgroups"]), len(R["numbers"])))
    for e in R["errors"]: L.append("  read error: " + e)
    L.append("\nNUMBERS LINKED (evidence: native adgroups TikTok accepted + read_message_event_set), masked:")
    for k, n in R["numbers"].items():
        sets, ok, err = R["sets_by_number"].get(k, ([], False, None))
        L.append("  %s | adgroups=%d status=%s | goals=%s | adgroup message_event_set_id=%s | event sets returned=%s%s" % (n["masked"], n["groups"], json.dumps(n["status"]), ",".join(sorted(n["goals"])), ",".join(sorted(n["set_ids"])) or NA, len(sets) if ok else "READ FAIL", ("" if ok else " " + str(err)[:100])))
        for x in sets[:3]: L.append("      set: " + json.dumps(lv.safe_set(x), ensure_ascii=False)[:300])
    if R["set_shapes"]: L.append("  event set response shape: " + R["set_shapes"][0])
    L += ["", "======== FINAL BLOCK (ASCII) ========", "CHECKED NUMBER: " + (lv.mask(tgt) if tgt else ("INVALID: " + str(warn) if warn else "none given (set SA_CHECK)"))]
    if a:
        linked_masked = [n["masked"] for n in R["numbers"].values()]
        L += ["LINK_STATUS: " + a["link_status"], "  evidence: " + "; ".join(a["link_evidence"]), "WHATSAPP_API_STATUS: %s  (TikTok has no API that says Business-API vs normal number; READY only if TikTok knows an event set for it AND accepted a native CONVERSATION adgroup)" % a["whatsapp_api_status"],
              "MESSAGE_EVENT_SET: %s %s" % (a["message_event_set"], ",".join(a["event_set_ids"])), "EVENT_SET_STATUS: " + a["event_set_status"], "CONVERSATION_ELIGIBILITY: " + a["conversation_eligibility"],
              "ROOT_CAUSE: " + lv.root_cause(a, linked_masked), "MINIMUM_REQUIRED_ACTION: " + lv.min_action(a)]
    L += ["MESSAGING PARTNER: required by TikTok docs for WhatsApp Business API numbers (partner connects the WhatsApp account and creates the event set); this tool cannot read which partner owns a set: N/A.",
          "EVENT DELIVERY: NOT VERIFIED (no TikTok read op for conversation events).", "NO CAMPAIGN CREATED. Broker ops used: read-only tiktok.read_* (code-enforced)."]
    return "\n".join(L)


def main():
    slug = os.environ.get("SA_SLUG", "mohm").strip(); acct = os.environ.get("SA_ACCT", "7593807340588253185").strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", slug) or not re.fullmatch(r"[0-9]{6,25}", acct): sys.exit("bad SA_SLUG / SA_ACCT")
    wad = load_wad(); env = wad.Env()
    tid = wad.psql(env, "select tenant_id from core.tenants where slug='%s'" % slug)
    ctxs = wad.psql(env, "select ctx from api.job_contexts_for_status(ARRAY['TESTING','NEEDS_REVIEW','READY'],100) where tenant_id='%s'" % tid[0]) if tid else []
    if not ctxs: sys.exit("tenant/ctx not found")
    raw = os.environ.get("SA_CHECK", "").strip(); tgt = None
    if raw:
        try: tgt = pvm.normalize_phone(raw)["e164"]
        except ValueError: pass
    R = gather(wad, lambda calls: wad.broker(env, ctxs[0], acct, read_only(calls)), tgt)
    print(report(R, raw))


if __name__ == "__main__":
    main()
