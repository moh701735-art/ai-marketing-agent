# -*- coding: utf-8 -*-
"""WhatsApp Account Link Validator — منطق نقي (بلا شبكة/كتابة). يقرّر من أدلة قراءة تيك توك فقط:
LINKED / WHATSAPP_API_STATUS / MESSAGE_EVENT_SET / EVENT_SET_STATUS / CONVERSATION_ELIGIBILITY.
ما في API من تيك توك يقول «هذا رقم Business API أم عادي»: الدليل الوحيد = وجود event set يعرفه تيك توك للرقم (ينشئه Messaging Partner/Events Manager) وحملة أصلية سبق قبلها تيك توك. غير ذلك = UNKNOWN، لا نخترع."""
import re

NA = "N/A"
SET_KEYS = ("message_event_set_id", "event_set_id", "id", "name", "status", "event_set_status", "create_time", "modify_time", "messaging_app_type", "messaging_app_account_id", "type", "event_set_type", "partner", "source")
OK_WORDS = re.compile(r"^(ENABLE|ENABLED|ACTIVE|NORMAL|AVAILABLE|VALID|OK)$", re.I)


def digits(s): return re.sub(r"\D", "", str(s or ""))


def mask(s):
    d = digits(s)
    return ("+%s...%s" % (d[:3], d[-3:])) if len(d) >= 7 else NA


def set_id(x):
    for k in ("message_event_set_id", "event_set_id", "id"):
        if x.get(k): return str(x[k])
    return None


def safe_set(x):
    out = {}
    for k in SET_KEYS:
        if k in x and x[k] not in (None, ""):
            v = x[k]; out[k] = mask(v) if k == "messaging_app_account_id" else (v if not isinstance(v, (dict, list)) else str(v)[:80])
    return out


def collect_numbers(adgroups, is_native):
    """{digits: {masked, groups:[...], goals:set, set_ids:set}} من adgroups أصلية (قراءة تيك توك)"""
    out = {}
    for g in adgroups:
        if not is_native(g): continue
        k = digits(g.get("messaging_app_account_id") or g.get("phone_number"))
        if not k: continue
        n = out.setdefault(k, {"masked": mask(k), "raw_example": g.get("messaging_app_account_id") or g.get("phone_number"), "groups": 0, "status": {}, "goals": set(), "set_ids": set()})
        n["groups"] += 1; st = str(g.get("operation_status") or NA); n["status"][st] = n["status"].get(st, 0) + 1
        n["goals"].add(str(g.get("optimization_goal") or g.get("optimize_goal") or NA))
        if g.get("message_event_set_id"): n["set_ids"].add(str(g["message_event_set_id"]))
    return out


def assess(target_e164, numbers, target_sets, target_read_ok, target_read_err=None):
    """target_e164: «+9647…» أو None. numbers: من collect_numbers. target_sets: صفوف event sets التي رجعها تيك توك لهذا الرقم."""
    t = digits(target_e164); hist = numbers.get(t)
    sets = [x for x in (target_sets or []) if set_id(x)]
    in_hist, has_sets = bool(hist), bool(sets)
    linked = "LINKED" if (in_hist or has_sets) else "NOT_LINKED"
    ev = []
    if in_hist: ev.append("number appears on %d native adgroup(s) TikTok accepted" % hist["groups"])
    if has_sets: ev.append("TikTok returned %d message event set(s) for it" % len(sets))
    if linked == "NOT_LINKED": ev.append("not in adgroup history and TikTok returned %s" % ("0 event sets" if target_read_ok else "error: %s" % (target_read_err or "unknown")))
    ids = sorted({set_id(x) for x in sets} | (hist["set_ids"] if hist else set()))
    statuses = sorted({str(x.get("status") or x.get("event_set_status")) for x in sets if x.get("status") or x.get("event_set_status")})
    accepted = bool(hist and any(g == "CONVERSATION" for g in hist["goals"]))
    if linked == "NOT_LINKED": elig = "NOT_READY"
    elif ids and accepted and (not statuses or all(OK_WORDS.match(s) for s in statuses)): elig = "READY"
    else: elig = "UNKNOWN"
    api = "READY" if (ids and accepted) else "UNKNOWN"          # NOT_READY ما نقدر نثبته من الـAPI
    return {"link_status": linked, "link_evidence": ev, "whatsapp_api_status": api, "message_event_set": "FOUND" if ids else "NOT_FOUND", "event_set_ids": ids,
            "event_set_status": ", ".join(statuses) if statuses else NA, "conversation_eligibility": elig, "in_history": in_hist}


def root_cause(a, linked_masked):
    if a["link_status"] == "NOT_LINKED":
        return ("the requested number is NOT among the numbers TikTok knows for this ad account (no accepted native adgroup, no message event set). Native WhatsApp conversations need a "
                "WhatsApp Business API number connected through a Messaging Partner, which creates the message event set; a normal number / wa.me link creates none. Numbers actually linked: " + (", ".join(linked_masked) or "N/A"))
    if a["conversation_eligibility"] == "READY": return "number is linked, has a message event set and TikTok already accepted a native CONVERSATION adgroup for it; nothing blocks it."
    return "number is linked only partially / evidence incomplete: " + "; ".join(a["link_evidence"])


def min_action(a):
    if a["link_status"] == "NOT_LINKED":
        return ("(1) use a number that is already linked (see list), or (2) convert the number to WhatsApp Business API and connect it to TikTok through a Messaging Partner (e.g. Pancake / Respond.io / Infobip; "
                "the partner creates the event set), then re-run this check. No conversation campaign is possible without it; falling back to Website/CLICK is forbidden because it spends without messages.")
    return "nothing to link; only verify event delivery manually in Events Manager."
