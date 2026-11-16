# -*- coding: utf-8 -*-
"""سناب شات — إنشاء مسودة حملة (p195a). عملية مركّبة `snapchat.launch_draft` على نمط metaflow.launch_whatsapp:
  1) قراءة الحساب الإعلاني (snapchat.adaccount): لازم ACTIVE، ونأخذ العملة والتوقيت.
  2) إنشاء حملة **متوقفة** (snapchat.create_campaign).  3) إنشاء مجموعة إعلانية **متوقفة** بالاستهداف (snapchat.create_adsquad).
لا يُنشأ إعلان/كرييتيف هنا (يحتاج رفع وسائط). الحالة PAUSED تُفرض بالـBroker نفسه مهما أرسل المتصل. لا نجاح وهمي: كل مرحلة تُبلَّغ باسمها.
أسماء حقول سناب مكتوبة من الذاكرة (التوثيق محجوب): كلها بقواميس ثابتة بأعلى الملف حتى يسهل تصحيحها من رد سناب الحقيقي."""
import datetime, json, re

CAMPAIGN_FIELDS = {"objective_key": None}            # سناب v1: الحملة بدون هدف؛ الهدف يُحدَّد بمجموعة الإعلان (optimization_goal)
GOALS = {"trf": "SWIPES"}                            # المرحلة الحالية: زيارات فقط (بقية الأهداف تحتاج بكسل/نموذج عملاء/رسائل)
AGE_GROUPS = ("18-20", "21-24", "25-34", "35+")
GENDERS = {"m": "MALE", "f": "FEMALE"}
LANGS = ("ar", "en", "ku")
ACCT_RE = re.compile(r"[0-9a-fA-F\-]{8,64}")
MAX_BUDGET_UNITS = 1_000_000
SLC_RE = re.compile(r"SLC_[0-9]{1,6}")


def _bad(msg: str):
    return 400, {"ok": False, "error": {"class": "invalid_params", "message": msg, "retryable": False}}


def _fail(stage: str, msg: str, cls: str = "invalid_params", data: dict = None):
    d = dict(data or {}); d["stage"] = stage
    return 200, {"ok": False, "error": {"class": cls, "message": str(msg)[:400], "retryable": False}, "data": d}


async def _call(svc, ctx, op, prm, key, stage):
    st, env = await svc.call(ctx, "snapchat", op, "", prm, key, internal=True)
    if st == 200 and env.get("ok"):
        return env.get("data") or {}, None
    err = dict(env.get("error") or {"class": "internal", "message": "فشل"})
    return None, _fail(stage, err.get("message") or "", err.get("class") or "internal")


def clean(params: dict):
    """يتحقق من مدخلات launch_draft ويرجع (p, خطأ)."""
    if not isinstance(params, dict): return None, "params لازم يكون كائن"
    extra = set(params) - {"name", "objective", "budget", "days", "regions", "ages", "gender", "lang", "interests", "landing_url", "start_at"}
    if extra: return None, "حقول غير مسموحة: " + ",".join(sorted(extra))[:100]
    p = {}
    nm = params.get("name"); 
    if not isinstance(nm, str) or not (1 <= len(nm.strip()) <= 200) or re.search(r"[\x00-\x1f]", nm): return None, "name مطلوب (1..200)"
    p["name"] = nm.strip()
    obj = params.get("objective", "trf")
    if obj not in GOALS: return None, "الهدف غير مدعوم حالياً (المتاح: زيارات)"
    p["objective"] = obj
    b = params.get("budget")
    if isinstance(b, bool) or not isinstance(b, (int, float)) or not (0 < b <= MAX_BUDGET_UNITS): return None, "budget مطلوب (أكبر من صفر)"
    p["budget"] = float(b)
    d = params.get("days", 1)
    if isinstance(d, bool) or not isinstance(d, int) or not (1 <= d <= 90): return None, "days (1..90)"
    p["days"] = d
    r = params.get("regions", [])
    if not isinstance(r, list) or len(r) > 25 or not all(isinstance(x, (str, int)) and re.fullmatch(r"[0-9]{1,12}", str(x)) for x in r): return None, "regions: أرقام معرفات المحافظات"
    p["regions"] = [str(x) for x in r]
    a = params.get("ages", [])
    if not isinstance(a, list) or not all(x in AGE_GROUPS for x in a): return None, "ages غير صالحة"
    p["ages"] = list(dict.fromkeys(a))
    g = params.get("gender", "a")
    if g not in ("a", "m", "f"): return None, "gender: a|m|f"
    p["gender"] = g
    l = params.get("lang", "")
    if l not in ("",) + LANGS: return None, "lang غير مدعومة"
    p["lang"] = l
    it = params.get("interests", [])
    if not isinstance(it, list) or len(it) > 10 or not all(isinstance(x, str) and SLC_RE.fullmatch(x) for x in it): return None, "interests: SLC_<رقم> حتى 10"
    p["interests"] = list(dict.fromkeys(it))
    u = params.get("landing_url")
    if not isinstance(u, str) or not re.fullmatch(r"https://[^\s\x00-\x1f<>\"']{4,500}", u): return None, "landing_url رابط https مطلوب"
    p["landing_url"] = u
    sa = params.get("start_at")
    if sa is not None and (not isinstance(sa, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.*", sa)): return None, "start_at ISO"
    p["start_at"] = sa
    return p, None


def targeting(p: dict) -> dict:
    geo = {"country_code": "iq"}
    if p["regions"]: geo["region_id"] = list(p["regions"])
    t = {"geos": [geo]}
    demo = {}
    if p["ages"]: demo["age_groups"] = list(p["ages"])
    if p["gender"] in GENDERS: demo["gender"] = GENDERS[p["gender"]]
    if p["lang"]: demo["languages"] = [p["lang"]]
    if demo: t["demographics"] = [demo]
    if p["interests"]: t["interests"] = [{"category_id": list(p["interests"])}]
    return t


def iso_times(tz_offset: str, days: int, start_at=None, now=None):
    """بداية = start_at أو الآن + 15 دقيقة؛ النهاية = البداية + days. الصيغة ISO بالتوقيت المعطى (+03:00 مثلاً)."""
    m = re.fullmatch(r"([+-])(\d{2}):(\d{2})", tz_offset or "+00:00") or re.fullmatch(r"([+-])(\d{2}):(\d{2})", "+00:00")
    sign = 1 if m.group(1) == "+" else -1
    tz = datetime.timezone(sign * datetime.timedelta(hours=int(m.group(2)), minutes=int(m.group(3))))
    if start_at:
        s = datetime.datetime.fromisoformat(start_at[:19]).replace(tzinfo=tz)
    else:
        s = (now or datetime.datetime.now(tz)).astimezone(tz).replace(microsecond=0) + datetime.timedelta(minutes=15)
    e = s + datetime.timedelta(days=days)
    f = lambda x: x.strftime("%Y-%m-%dT%H:%M:%S.000") + (m.group(1) + m.group(2) + ":" + m.group(3))
    return f(s), f(e)


def tz_offset_of(tzname: str) -> str:
    try:
        import zoneinfo
        off = datetime.datetime.now(zoneinfo.ZoneInfo(tzname)).utcoffset()
        mins = int(off.total_seconds() // 60); sign = "+" if mins >= 0 else "-"; mins = abs(mins)
        return "%s%02d:%02d" % (sign, mins // 60, mins % 60)
    except Exception:
        return "+00:00"


def body(op_name: str, p: dict, account_id: str = "") -> dict:
    """يحوّل params المسطّحة المتحقَّق منها إلى جسم سناب. يُستدعى من service._build."""
    if op_name == "snapchat.create_campaign":
        c = {"name": p["name"], "ad_account_id": p.get("account_id") or account_id, "status": "PAUSED", "start_time": p["start_time"]}
        if p.get("end_time"): c["end_time"] = p["end_time"]
        return {"campaigns": [c]}
    if op_name == "snapchat.create_adsquad":
        s = {"name": p["name"], "campaign_id": p.get("campaign_id"), "status": "PAUSED", "type": "SNAP_ADS", "placement_v2": {"config": "AUTOMATIC"},
             "optimization_goal": p.get("goal") or "SWIPES", "billing_event": "IMPRESSION", "bid_strategy": "AUTO_BID",
             "start_time": p["start_time"], "targeting": json.loads(p["targeting_json"])}
        if p.get("end_time"): s["end_time"] = p["end_time"]
        s["daily_budget_micro" if p.get("budget_kind") == "daily" else "lifetime_budget_micro"] = int(p["budget_micro"])
        return {"adsquads": [s]}
    raise ValueError(op_name)


def first_result(data: dict, listkey: str, itemkey: str):
    """يقرأ رد سناب {request_status, <list>:[{sub_request_status, <item>:{id}}]} → (id, رسالة خطأ)"""
    if not isinstance(data, dict): return None, "رد غير مفهوم"
    arr = data.get(listkey) or []
    if not arr: return None, str(data.get("display_message") or data.get("debug_message") or "رد فاضي من سناب")[:300]
    x = arr[0] or {}
    if str(x.get("sub_request_status", "SUCCESS")).upper() != "SUCCESS":
        return None, str(x.get("display_message") or x.get("debug_message") or x.get("sub_request_status"))[:300]
    i = (x.get(itemkey) or {}).get("id")
    return (str(i), None) if i else (None, "ما رجع id")


async def launch_draft(svc, ctx: str, ad_account, params: dict, idem: str):
    if not (isinstance(idem, str) and 16 <= len(idem) <= 100): return _bad("idempotency_key (16..100 حرف) مطلوب")
    acct = str(params.get("account_id") or ad_account or "") if isinstance(params, dict) else ""
    if not ACCT_RE.fullmatch(acct): return _bad("account_id (معرّف حساب سناب) مطلوب")
    p, err = clean({k: v for k, v in params.items() if k != "account_id"})
    if err: return _bad(err)
    made = {"account_id": acct, "objective": p["objective"], "status": "PAUSED"}
    info, f = await _call(svc, ctx, "snapchat.adaccount", {"oid": acct}, idem + "-a", "account")
    if f: return f
    ad = (((info.get("adaccounts") or [{}])[0]) or {}).get("adaccount") or {}
    if str(ad.get("status", "")).upper() != "ACTIVE": made["account_status"] = str(ad.get("status")); return _fail("account", "account_not_active", "invalid_params", made)
    made["currency"] = str(ad.get("currency") or "")
    st, en = iso_times(tz_offset_of(ad.get("timezone") or ""), p["days"], p["start_at"])
    made["start_time"], made["end_time"] = st, en
    camp, f = await _call(svc, ctx, "snapchat.create_campaign", {"oid": acct, "account_id": acct, "name": p["name"], "status": "PAUSED", "start_time": st, "end_time": en}, idem + "-c", "campaign")
    if f: return f
    cid, e = first_result(camp, "campaigns", "campaign")
    if not cid: return _fail("campaign", e or "no_campaign_id_returned", "bad_response", made)
    made["campaign_id"] = cid
    tj = json.dumps(targeting(p), ensure_ascii=False, separators=(",", ":"))
    sq, f = await _call(svc, ctx, "snapchat.create_adsquad", {"oid": cid, "campaign_id": cid, "name": p["name"], "status": "PAUSED", "start_time": st, "end_time": en, "goal": GOALS[p["objective"]],
                                                              "budget_micro": int(round(p["budget"] * 1_000_000)), "targeting_json": tj}, idem + "-s", "adsquad")
    if f:
        f[1].setdefault("data", {}).update(made)          # الحملة انعملت لكن المجموعة فشلت: نقول ذلك ونعطي معرّف الحملة
        return f
    sid, e = first_result(sq, "adsquads", "adsquad")
    if not sid: return _fail("adsquad", e or "no_adsquad_id_returned", "bad_response", made)
    made["adsquad_id"] = sid; made["creative"] = "missing"; made["stage"] = "adsquad"
    return 200, {"ok": True, "data": made}


async def run(svc, op_name: str, ctx: str, ad_account, params: dict, idem: str):
    if op_name == "snapchat.launch_draft": return await launch_draft(svc, ctx, ad_account, params or {}, idem)
    return _bad("unknown composite op")
