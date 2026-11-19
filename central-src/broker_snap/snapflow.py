# -*- coding: utf-8 -*-
"""سناب شات — إنشاء مسودة حملة (p195a). عملية مركّبة `snapchat.launch_draft` على نمط metaflow.launch_whatsapp:
  1) قراءة الحساب الإعلاني (snapchat.adaccount): لازم ACTIVE، ونأخذ العملة والتوقيت.
  2) إنشاء حملة **متوقفة** (snapchat.create_campaign).  3) إنشاء مجموعة إعلانية **متوقفة** بالاستهداف (snapchat.create_adsquad).
لا يُنشأ إعلان/كرييتيف هنا (يحتاج رفع وسائط). الحالة PAUSED تُفرض بالـBroker نفسه مهما أرسل المتصل. لا نجاح وهمي: كل مرحلة تُبلَّغ باسمها.
أسماء حقول سناب مكتوبة من الذاكرة (التوثيق محجوب): كلها بقواميس ثابتة بأعلى الملف حتى يسهل تصحيحها من رد سناب الحقيقي."""
import datetime, json, re

CAMPAIGN_FIELDS = {"objective_key": None}            # سناب v1: الحملة بدون هدف؛ الهدف يُحدَّد بمجموعة الإعلان (optimization_goal)
GOALS = {"trf": "SWIPES", "vid": "VIDEO_VIEWS", "sal": "PIXEL_PURCHASE"}   # زيارات، مشاهدات، مبيعات (بكسل). العملاء المحتملون لاحقاً (يحتاج نموذج)
CTAS = ("MORE", "LEARN_MORE", "SHOP_NOW", "ORDER_NOW", "SIGN_UP", "BOOK_NOW", "WATCH", "VIEW", "VISIT")
UUID_RE = re.compile(r"[0-9a-fA-F\-]{8,64}")
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
    extra = set(params) - {"name", "objective", "budget", "days", "regions", "ages", "gender", "lang", "interests", "landing_url", "start_at", "pixel_id", "media_id", "file_id", "headline", "brand_name", "cta", "profile_id", "min_age", "max_age"}
    if extra: return None, "حقول غير مسموحة: " + ",".join(sorted(extra))[:100]
    p = {}
    nm = params.get("name"); 
    if not isinstance(nm, str) or not (1 <= len(nm.strip()) <= 200) or re.search(r"[\x00-\x1f]", nm): return None, "name مطلوب (1..200)"
    p["name"] = nm.strip()
    obj = params.get("objective", "trf")
    if obj not in GOALS: return None, "الهدف غير مدعوم حالياً (المتاح: زيارات، مشاهدات، مبيعات)"
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
    mn, mx = params.get("min_age"), params.get("max_age")
    for v in (mn, mx):
        if v is not None and (isinstance(v, bool) or not isinstance(v, int) or not (13 <= v <= 50)): return None, "min_age/max_age أرقام 13..50"
    if mn is not None and mx is not None and mx < mn: return None, "max_age أصغر من min_age"
    if (mn is not None or mx is not None) and p["ages"]: return None, "ages أو min_age/max_age (مو الاثنين)"
    p["min_age"], p["max_age"] = mn, mx
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
    if u is None and p["objective"] == "vid": p["landing_url"] = ""
    elif not isinstance(u, str) or not re.fullmatch(r"https://[^\s\x00-\x1f<>\"']{4,500}", u): return None, "landing_url رابط https مطلوب"
    else: p["landing_url"] = u
    px = params.get("pixel_id")
    if p["objective"] == "sal" and not (isinstance(px, str) and UUID_RE.fullmatch(px)): return None, "pixel_id مطلوب لهدف المبيعات"
    if px not in (None, "") and not (isinstance(px, str) and UUID_RE.fullmatch(px)): return None, "pixel_id غير صالح"
    p["pixel_id"] = px or ""
    for k, mx in (("headline", 34), ("brand_name", 25)):
        v = params.get(k, "")
        if not isinstance(v, str) or len(v.strip()) > mx or re.search(r"[\x00-\x1f<>]", v): return None, "%s حتى %d حرف" % (k, mx)
        p[k] = v.strip()
    c = params.get("cta", "MORE")
    if c not in CTAS: return None, "cta غير مدعوم"
    p["cta"] = c
    mid, fid = params.get("media_id"), params.get("file_id")
    if mid is not None and not (isinstance(mid, str) and UUID_RE.fullmatch(mid)): return None, "media_id غير صالح"
    if fid is not None and not (isinstance(fid, str) and re.fullmatch(r"[A-Za-z0-9_\-]{10,200}", fid)): return None, "file_id غير صالح"
    if mid and fid: return None, "media_id أو file_id (مو الاثنين)"
    p["media_id"], p["file_id"] = mid or "", fid or ""
    pf = params.get("profile_id", "")
    if pf and not (isinstance(pf, str) and UUID_RE.fullmatch(pf)): return None, "profile_id غير صالح"
    p["profile_id"] = pf
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
    if p.get("min_age") is not None: demo["min_age"] = str(p["min_age"])      # عمر من → إلى (سناب: نصوص). بدون max_age = بدون حد أعلى
    if p.get("max_age") is not None: demo["max_age"] = str(p["max_age"])
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
        if p.get("pixel_id"): s["pixel_id"] = p["pixel_id"]
        if str(s["optimization_goal"]).startswith("PIXEL_"): s["conversion_window"] = p.get("conversion_window") or "SWIPE_28DAY_VIEW_1DAY"   # p197f: E3017 «…ineligible for PIXEL_PURCHASE null» = ما أرسلنا نافذة التحويل
        return {"adsquads": [s]}
    if op_name == "snapchat.create_media":
        return {"media": [{"name": p["name"], "type": "VIDEO", "ad_account_id": p.get("account_id") or account_id}]}
    if op_name == "snapchat.create_creative":
        c = json.loads(p["payload_json"]); c["ad_account_id"] = p.get("account_id") or account_id; return {"creatives": [c]}
    if op_name == "snapchat.create_ad":
        a = json.loads(p["payload_json"]); a["status"] = "PAUSED"; return {"ads": [a]}
    raise ValueError(op_name)


def snap_reason(x: dict) -> str:
    """سبب رفض سناب لعنصر فرعي: sub_request_error_reason أولاً (p197e) ثم الرسائل المعتادة."""
    for k in ("sub_request_error_reason", "display_message", "debug_message", "error_description", "message"):
        v = x.get(k) if isinstance(x, dict) else None
        if isinstance(v, str) and v.strip(): return v.strip()
    return str((x or {}).get("sub_request_status") or "error")


def first_result(data: dict, listkey: str, itemkey: str):
    """يقرأ رد سناب {request_status, <list>:[{sub_request_status, <item>:{id}}]} → (id, رسالة خطأ)"""
    if not isinstance(data, dict): return None, "رد غير مفهوم"
    arr = data.get(listkey) or []
    if not arr: return None, str(data.get("display_message") or data.get("debug_message") or "رد فاضي من سناب")[:300]
    x = arr[0] or {}
    if str(x.get("sub_request_status", "SUCCESS")).upper() != "SUCCESS":
        return None, snap_reason(x)[:300]
    i = (x.get(itemkey) or {}).get("id")
    return (str(i), None) if i else (None, "ما رجع id")


def creative_body(p: dict, acct: str, media_id: str, profile_id: str) -> dict:
    web = bool(p.get("landing_url"))
    c = {"name": p["name"][:100], "type": "WEB_VIEW" if web else "SNAP_AD", "top_snap_media_id": media_id, "top_snap_crop_position": "MIDDLE",
         "brand_name": (p.get("brand_name") or p["name"])[:25], "headline": (p.get("headline") or p["name"])[:34], "shareable": True,
         "profile_properties": {"profile_id": profile_id}}
    if web:
        c["web_view_properties"] = {"url": p["landing_url"], "allow_snap_javascript_sdk": False, "use_immersive_mode": False, "deep_link_urls": []}
        c["call_to_action"] = p.get("cta") or "MORE"
    return c


def ad_body(p: dict, squad_id: str, creative_id: str) -> dict:
    return {"ad_squad_id": squad_id, "creative_id": creative_id, "name": p["name"][:100], "type": "REMOTE_WEBPAGE" if p.get("landing_url") else "SNAP_AD", "status": "PAUSED"}


async def _snap_token_for(svc, ctx):
    az = await svc.central.authorize(ctx, "snapchat", None, "write")
    _, _, raw = await svc.store.open_latest(az["tenant_id"], az["secret_ref"])
    return await svc._snap_token(az["tenant_id"], az["secret_ref"], raw)


async def upload_video(svc, ctx, media_id: str, file_id: str):
    """ينزّل الفيديو من تلغرام (svc._tg_download، حد 20MB) ويرفعه لسناب multipart ثم ينتظر READY. يرجع (None, خطأ-مرحلة) عند الفشل."""
    blob, name = await svc._tg_download(ctx, file_id)
    if blob is None: return "upload", (name or {}).get("message") or "telegram_download_failed"
    try:
        tok = await _snap_token_for(svc, ctx)
        base = svc.s.base_urls["snapchat"].rstrip("/")
        r = await svc.client.post(base + "/media/" + media_id + "/upload", headers={"Authorization": "Bearer " + tok},
                                  files={"file": ((name or "video.mp4"), blob, "video/mp4")}, timeout=180.0)
    except Exception as e:
        return "upload", "snapchat_upload_failed:" + type(e).__name__
    if r.status_code != 200: return "upload", ("snapchat_upload_http_%d: %s" % (r.status_code, (r.text or "")[:300]))
    import asyncio
    for _ in range(24):                      # حتى دقيقتين
        st, env = await svc.call(ctx, "snapchat", "snapchat.media_get", "", {"oid": media_id}, None, internal=True)
        m = (((env.get("data") or {}).get("media") or [{}])[0] or {}).get("media") or {}
        if str(m.get("media_status", "")).upper() == "READY": return None, None
        if str(m.get("media_status", "")).upper() in ("ERROR", "FAILED"): return "upload", "snapchat_media_status_" + str(m.get("media_status"))
        await asyncio.sleep(5)
    return "upload", "snapchat_media_not_ready_in_time"


async def attach_ad(svc, ctx, acct, p, squad_id, idem, made, org_id=None):
    """وسائط (موجودة أو ترفع من تلغرام) ← creative ← ad (متوقف). يرجع (None, None) عند النجاح أو (200,{ok:False}) فشل مرحلة."""
    media_id = p["media_id"]
    if not media_id:
        d, f = await _call(svc, ctx, "snapchat.create_media", {"oid": acct, "account_id": acct, "name": (p["name"] + " video")[:100]}, idem + "-m", "media")
        if f: return f
        media_id, e = first_result(d, "media", "media")
        if not media_id: return _fail("media", e or "no_media_id_returned", "bad_response", made)
        made["media_id"] = media_id
        stg, msg = await upload_video(svc, ctx, media_id, p["file_id"])
        if stg: return _fail(stg, msg, "bad_response", made)
    else:
        made["media_id"] = media_id
    pid = p["profile_id"]
    if not pid:
        last = ""
        d, f = await _call(svc, ctx, "snapchat.creatives_list", {"oid": acct, "limit": 100}, idem + "-q", "profile")     # أضمن مسار: بروفايل مستعمل بتصميم سابق بنفس الحساب
        if not f:
            for x in ((d or {}).get("creatives") or []):
                v = str((((x or {}).get("creative") or {}).get("profile_properties") or {}).get("profile_id") or "")
                if UUID_RE.fullmatch(v): pid = v; break
        for op_name, oid in (() if pid else (("snapchat.profiles_org", org_id), ("snapchat.profiles_acct", acct))):   # من المنظمة أولاً ثم من الحساب الإعلاني
            if not oid: continue
            d, f = await _call(svc, ctx, op_name, {"oid": oid}, idem + "-p", "profile")
            if f: last = f[1]["error"]["message"]; continue
            arr = (d or {}).get("profiles") or []
            pid = str((((arr[0] or {}).get("profile")) or {}).get("id") or "") if arr else ""
            if pid: break
        if not pid: return _fail("profile", "ما لقيت Public Profile بحساب سناب (مطلوب للإعلانات)" + (" — " + last if last else "") + ". أنشئه من Snap Ads Manager أو مرّر profile_id", "invalid_params", made)
    made["profile_id"] = pid
    cb = creative_body(p, acct, media_id, pid)
    d, f = await _call(svc, ctx, "snapchat.create_creative", {"oid": acct, "account_id": acct, "payload_json": json.dumps(cb, ensure_ascii=False, separators=(",", ":"))}, idem + "-r", "creative")
    if f: return f
    crid, e = first_result(d, "creatives", "creative")
    if not crid: return _fail("creative", e or "no_creative_id_returned", "bad_response", made)
    made["creative_id"] = crid
    ab = ad_body(p, squad_id, crid)
    d, f = await _call(svc, ctx, "snapchat.create_ad", {"oid": squad_id, "payload_json": json.dumps(ab, ensure_ascii=False, separators=(",", ":"))}, idem + "-d", "ad")
    if f: return f
    adid, e = first_result(d, "ads", "ad")
    if not adid: return _fail("ad", e or "no_ad_id_returned", "bad_response", made)
    made["ad_id"] = adid; made["creative"] = "created"
    return None


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
                                                              "budget_micro": int(round(p["budget"] * 1_000_000)), "targeting_json": tj, **({"pixel_id": p["pixel_id"]} if p["pixel_id"] else {})}, idem + "-s", "adsquad")
    if f:
        f[1].setdefault("data", {}).update(made)          # الحملة انعملت لكن المجموعة فشلت: نقول ذلك ونعطي معرّف الحملة
        return f
    sid, e = first_result(sq, "adsquads", "adsquad")
    if not sid: return _fail("adsquad", e or "no_adsquad_id_returned", "bad_response", made)
    made["adsquad_id"] = sid; made["creative"] = "missing"; made["stage"] = "adsquad"
    if p["media_id"] or p["file_id"]:
        f = await attach_ad(svc, ctx, acct, p, sid, idem, made, str(ad.get("organization_id") or ""))
        if f:                                    # الحملة والمجموعة انعملت (متوقفة) لكن الإعلان فشل: نبلّغ بمرحلته ونعطي المعرّفات
            d = f[1].setdefault("data", {}); stg = d.get("stage"); d.update({k: v for k, v in made.items() if k not in d}); d["stage"] = stg
            return f
        made["stage"] = "ad"
    return 200, {"ok": True, "data": made}


async def run(svc, op_name: str, ctx: str, ad_account, params: dict, idem: str):
    if op_name == "snapchat.launch_draft": return await launch_draft(svc, ctx, ad_account, params or {}, idem)
    return _bad("unknown composite op")
