# -*- coding: utf-8 -*-
"""WhatsAppConversationPreview — محوّل معزول (دالة نقية): يعرض فقط payload «محادثات واتساب» الأصلي كما سيُرسل لتيك توك.
لا شبكة، لا كتابة، لا يستدعي الـBroker ولا يعدّل أي ملف قديم. لا ينشئ حملة. المدخلات = قراءة حية (adgroup أصلي + event sets) تُمرَّر له.
كل حقل يحمل مصدره: «live read-back» (قرأه تيك توك فعلاً) | «recorded p152» (كما سجّلنا من الكود الحي، غير مقروء الآن) | «derived» (مشتق محلياً من الرقم، غير مُثبَت) | N/A.
EVENT DELIVERY NOT VERIFIED: وجود message_event_set_id لا يثبت وصول أحداث المحادثات (ما في API قراءة لأحداثها)."""
import re

NA = "N/A"
EVENT_DELIVERY = "EVENT DELIVERY NOT VERIFIED"
FIELDS = ("promotion_type", "messaging_app_type", "messaging_app_account_id", "phone_region_code", "phone_region_calling_code", "phone_number",
          "optimization_goal", "optimization_event", "message_event_set_id", "billing_event", "bid_type", "budget_mode")
SRC_LIVE, SRC_REC, SRC_DER = "live read-back", "recorded p152 (not read now)", "derived locally (UNVERIFIED by TikTok)"
RECORDED = {"promotion_type": "LEAD_GEN_CLICK_TO_SOCIAL_MEDIA_APP_MESSAGE", "messaging_app_type": "WHATSAPP", "optimization_goal": "CONVERSATION",
            "optimization_event": "MESSAGE", "billing_event": "OCPM", "bid_type": "BID_TYPE_NO_BID", "budget_mode": "BUDGET_MODE_TOTAL"}
# مسارات «الحالي» كما سُجّلت من patches/knowledge (p152/p176/p186) — تُستعمل فقط لو ما توفّر ناتج الكود الحي
RECORDED_CURRENT = {
    "sales": {"objective_type": "WEB_CONVERSIONS", "promotion_type": "WEBSITE", "optimization_goal": "CONVERT", "billing_event": "OCPM", "bid_type": "BID_TYPE_NO_BID",
              "budget_mode": "BUDGET_MODE_TOTAL", "promotion_target_type": "TIKTOK_NATIVE_PAGE"},
    "traffic": {"objective_type": "TRAFFIC", "promotion_type": "WEBSITE", "optimization_goal": "CLICK", "billing_event": "CPC", "bid_type": "BID_TYPE_NO_BID",
                "budget_mode": "BUDGET_MODE_TOTAL", "landing_page_url": "(external https landing_url on the AD)"},
}
WA_EXTRA = {"objective_type": "LEAD_GENERATION", "promotion_target_type": NA, "landing_page_url": NA}
COMPARE_FIELDS = ("objective_type",) + FIELDS + ("promotion_target_type", "landing_page_url")
CALLING = {"964": "IQ", "966": "SA", "965": "KW", "971": "AE", "974": "QA", "973": "BH", "968": "OM"}
ALIASES = {"optimization_goal": ("optimization_goal", "optimize_goal")}


def normalize_phone(raw):
    """→ {e164, calling_code, region, assumed}. يرفع ValueError برسالة واضحة. العراق + دول الخليج المعروفة فقط (غير ذلك = ما نخمّن)."""
    s = re.sub(r"[\s\-().]", "", str(raw or ""))
    if not re.fullmatch(r"\+?\d{7,16}", s or ""): raise ValueError("WHATSAPP_NUMBER_INVALID: not a phone number")
    assumed = ""
    if s.startswith("+"): d = s[1:]
    elif s.startswith("00"): d = s[2:]
    elif re.fullmatch(r"07\d{9}", s): d = "964" + s[1:]
    elif re.fullmatch(r"7\d{9}", s): d, assumed = "964" + s, "assumed Iraq (no leading 0)"
    else: d = s
    cc = next((c for c in CALLING if d.startswith(c)), None)
    if not cc: raise ValueError("UNSUPPORTED_REGION: calling code not in %s" % ",".join("+" + c for c in sorted(CALLING)))
    nat = d[len(cc):]
    if cc == "964" and not re.fullmatch(r"7\d{9}", nat): raise ValueError("WHATSAPP_NUMBER_INVALID: Iraqi mobile must be 7XXXXXXXXX after +964")
    if not 7 <= len(nat) <= 11: raise ValueError("WHATSAPP_NUMBER_INVALID: bad length")
    return {"e164": "+" + d, "calling_code": "+" + cc, "region": CALLING[cc], "assumed": assumed}


def mask_phone(s):
    d = re.sub(r"\D", "", str(s or ""))
    if len(d) < 7: return str(s or NA)
    cc = next((c for c in CALLING if d.startswith(c)), d[:3])
    return "+%s…%s" % (cc, d[-3:])


def _digits(s): return re.sub(r"\D", "", str(s or ""))


def _es_id(x):
    for k in ("message_event_set_id", "event_set_id", "id"):
        if x.get(k): return str(x[k])
    return None


class WhatsAppConversationPreview:
    def __init__(self, reference_adgroup=None, event_sets=None, currency=None):
        self.ref = dict(reference_adgroup or {}); self.sets = list(event_sets or []); self.currency = currency

    def _pick(self, name):
        for k in ALIASES.get(name, (name,)):
            if self.ref.get(k) not in (None, ""): return self.ref[k], SRC_LIVE, ""
        if name in RECORDED: return RECORDED[name], SRC_REC, ""
        return NA, NA, ""

    def build(self, phone=None):
        F, warn = {}, []
        for n in ("promotion_type", "messaging_app_type", "optimization_goal", "optimization_event", "billing_event", "bid_type", "budget_mode"):
            v, s, note = self._pick(n); F[n] = {"value": v, "source": s, "note": note}
        num = None; src_num = phone or self.ref.get("phone_number") or self.ref.get("messaging_app_account_id")
        if src_num:
            try: num = normalize_phone(src_num)
            except ValueError as e: warn.append(str(e))
        F["phone_number"] = ({"value": mask_phone(num["e164"] if num else src_num), "source": (SRC_LIVE if (not phone and self.ref.get("phone_number")) else SRC_DER),
                              "note": (num or {}).get("assumed", "") or "masked; full number never printed"} if src_num else {"value": NA, "source": NA, "note": "no number given and none in reference"})
        cc = self.ref.get("phone_region_calling_code")
        F["phone_region_calling_code"] = ({"value": cc, "source": SRC_LIVE, "note": ""} if cc else ({"value": num["calling_code"], "source": SRC_DER, "note": ""} if num else {"value": NA, "source": NA, "note": ""}))
        rc = self.ref.get("phone_region_code")
        F["phone_region_code"] = ({"value": rc, "source": SRC_LIVE, "note": ""} if rc else ({"value": num["region"], "source": SRC_DER, "note": "live read-back did not show this field; whether TikTok needs/accepts it: LIVE-CHECK"} if num else {"value": NA, "source": NA, "note": ""}))
        ma = self.ref.get("messaging_app_account_id")
        F["messaging_app_account_id"] = {"value": mask_phone(ma), "source": SRC_LIVE, "note": "masked"} if ma else {"value": NA, "source": NA, "note": "comes from TikTok (read_message_event_set shape); not derivable offline"}
        es = self.ref.get("message_event_set_id")
        if es: F["message_event_set_id"] = {"value": str(es), "source": SRC_LIVE, "note": ""}
        else:
            ids = [i for i in (_es_id(x) for x in self.sets) if i]
            hit = [x for x in self.sets if num and _digits(x.get("messaging_app_account_id")) == _digits(num["e164"]) and _es_id(x)]
            if len(hit) == 1: F["message_event_set_id"] = {"value": _es_id(hit[0]), "source": "live read-back (event set matched by number)", "note": ""}
            elif len(ids) == 1: F["message_event_set_id"] = {"value": ids[0], "source": "live read-back (only set returned)", "note": ""}
            else: F["message_event_set_id"] = {"value": NA, "source": NA, "note": "none returned" if not ids else "ambiguous (%d sets, no number match)" % len(ids)}
        return {"fields": {k: F[k] for k in FIELDS}, "event_delivery": EVENT_DELIVERY, "warnings": warn, "no_campaign_created": True}

    @staticmethod
    def render(pv):
        out = ["WhatsAppConversationPreview (لا ينشئ حملة — عرض فقط):"]
        for k in FIELDS:
            f = pv["fields"][k]; out.append("  %-27s = %-46s [%s]%s" % (k, f["value"], f["source"], (" — " + f["note"]) if f["note"] else ""))
        out += ["  warnings: " + ("; ".join(pv["warnings"]) if pv["warnings"] else "none"), "  " + pv["event_delivery"] + ": message_event_set_id لا يثبت وصول أحداث المحادثات؛ ما في API قراءة لأحداثها هنا (تحقق يدوي: Events Manager > Data sources > Messaging)."]
        return "\n".join(out)


def compare(current, pv):
    """فرق حقل-بحقل بين payload الحالي (dict) وpayload واتساب. → [{field, current, whatsapp, verdict}]"""
    rows = []
    for k in COMPARE_FIELDS:
        c = current.get(k, NA); w = pv["fields"][k]["value"] if k in pv["fields"] else WA_EXTRA.get(k, NA)
        if c == NA and w == NA: v = "—"
        elif c == NA: v = "ONLY_WHATSAPP"
        elif w == NA: v = "ONLY_CURRENT"
        else: v = "SAME" if str(c) == str(w) else "DIFF"
        rows.append({"field": k, "current": c, "whatsapp": w, "verdict": v})
    return rows


def render_compare(name, rows, src):
    out = ["مقارنة [%s]  (الحالي من: %s)" % (name, src), "  %-27s %-34s %-46s %s" % ("field", "CURRENT", "WHATSAPP CONVERSATIONS", "verdict")]
    out += ["  %-27s %-34s %-46s %s" % (r["field"], str(r["current"])[:34], str(r["whatsapp"])[:46], r["verdict"]) for r in rows]
    return "\n".join(out)
