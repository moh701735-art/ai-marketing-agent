"""p217: قارئ مباشر (بدون ذكاء اصطناعي) لرسائل إطلاق الحملات ذات القالب المنظّم (أسطر بعناوين مثل «هدف الحملة:» و«الدول المستهدفة:»).
يرجّع نفس عقد llm.parse_command (intent/platform/account/budget/days/objective/budget_kind/landing_page/activate_now/name)
أو None إذا الرسالة مو قالب واضح أو ناقص فيه (الحساب/الميزانية/المدة) أو فيه تعارض — وقتها يكمل المسار القديم (الذكاء الاصطناعي). ما يخمّن فلوس أبداً."""
import re, math

_DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_STRIP = re.compile("[‎‏‪-‮ً-ْـ]")


def _norm(s):
    return _STRIP.sub("", str(s or "").translate(_DIG))


def _k(s):
    s = _norm(s).lower()
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ة", "ه"), ("ى", "ي")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


LABELS = {
    "time": ("وقت الحمله", "مده الحمله", "مده"), "objective": ("هدف الحمله",), "opt": ("هدف التحسين",),
    "cta": ("زر الدعوه للاجراء", "زر الدعوه"), "placement": ("مكان ظهور الاعلان", "مكان ظهور الاعلانات", "مكان الظهور"),
    "countries": ("الدول المستهدفه", "الدول"), "age": ("العمر",), "gender": ("الجنس",), "lang": ("اللغه",),
    "expansion": ("audience expansion",), "device": ("نظام الجهاز", "الجهاز"), "interests": ("الاهتمامات",),
    "budget": ("الميزانيه", "ميزانيه"), "account": ("الحساب", "حساب"), "name": ("الاسم", "اسم الحمله"),
}
_REV = {v: k for k, vs in LABELS.items() for v in vs}
_LINE = re.compile(r"^\s*([^:：\n]{2,40}?)\s*[:：]\s*(.*)$")
_TEMPLATE_KEYS = ("time", "objective", "opt", "cta", "placement", "countries", "age", "gender", "lang", "expansion", "device", "interests")
OBJ = (("LEAD_GENERATION", ("عميل محتمل", "عملاء محتملين", "ليدز", "lead")), ("VIDEO_VIEWS", ("مشاهدات", "video views", "views")),
       ("CONVERSIONS", ("تحويلات", "مبيعات", "conversion", "sales")), ("ENGAGEMENT", ("تفاعل", "engagement")),
       ("FOLLOWERS", ("متابعين", "متابعه", "followers")), ("REACH", ("وصول", "انتشار", "reach")), ("TRAFFIC", ("زيارات", "زياره", "ترافيك", "traffic", "نقرات", "نقر")))
_NUMW = {"واحد": 1, "واحده": 1, "اثنين": 2, "اثنان": 2, "ثنين": 2, "ثلاث": 3, "ثلاثه": 3, "اربع": 4, "اربعه": 4, "خمس": 5, "خمسه": 5,
         "ست": 6, "سته": 6, "سبع": 7, "سبعه": 7, "ثمان": 8, "ثمانيه": 8, "تسع": 9, "تسعه": 9, "عشر": 10, "عشره": 10}
_DAYS_LINE = re.compile(r"^(?:(يوم واحد|يوم|يومين|اسبوع|اسبوعين)|(\d{1,3})\s*(?:يوم|ايام)|(" + "|".join(_NUMW) + r")\s*(?:ايام|يوم))\s*[.!]?$")
_HOURS = re.compile(r"(\d{1,3})\s*ساعه|ساعات")
_BUDGET_LINE = re.compile(r"^(?:(?:ب)?ميزانيه\s*)?(\d{1,3}(?:,\d{3})+|\d+(?:[.,]\d+)?)\s*(الف|الاف|مليون|k)?\s*(دولار|\$|usd|دينار|iqd|د\.ع)?\s*(يوميا|يوميه|لكل يوم|كل يوم|اجمالي|بالكامل|للحمله)?\s*[.!]?$")
_URL = re.compile(r"https?://[^\s<>\"']+")
_ACCT = re.compile(r"(?:^|\s)(?:ب|ل)?حساب(?:ي)?\s+(?!:)(.+)$")
_ID = re.compile(r"\b\d{15,20}\b")
_ACT = re.compile(r"(?:فعل|شغل)(?:ها|ه)\s*(?:فورا|الان|هسه|مباشره)|(?:فعل|شغل)\s+الحمله\s*(?:فورا|الان|هسه)|activate now")


def _num(s):
    s = s.strip()
    if re.fullmatch(r"\d{1,3}(,\d{3})+", s):
        return float(s.replace(",", ""))
    return float(s.replace(",", "."))


def parse(text):
    raw = _norm(text)
    if not raw.strip() or len(raw) > 4000:
        return None
    lines = [l for l in raw.split("\n")]
    labelled, free = {}, []
    for l in lines:
        m = _LINE.match(l)
        key = _REV.get(_k(m.group(1))) if m else None
        if key:
            labelled.setdefault(key, []).append(m.group(2).strip())
        elif l.strip():
            free.append(l.strip())
    if "objective" not in labelled or sum(1 for k in _TEMPLATE_KEYS if k in labelled) < 4:
        return None                                   # مو قالب حملة منظّم: يكمل الذكاء الاصطناعي
    out = {"intent": "create_campaign"}
    # الهدف
    ov = _k(" ".join(labelled["objective"]))
    obj = [o for o, ks in OBJ if any(_k(k) in ov for k in ks)]
    if len(obj) != 1:
        return None
    out["objective"] = obj[0]
    # المنصة
    pv = _k(" ".join(labelled.get("placement", [])))
    if "tiktok" in pv or "تيك توك" in pv:
        if any(w in pv for w in ("facebook", "فيسبوك", "instagram", "انستغرام", "ميتا", "snap", "سناب")):
            return None
        out["platform"] = "tiktok"
    elif pv:
        return None
    # الحساب
    acct = ""
    for v in labelled.get("account", []):
        acct = v.strip()
    if not acct:
        for l in free:
            m = _ACCT.search(l)
            if m:
                acct = m.group(1).strip()
                break
    if not acct:
        ids = _ID.findall(raw)
        acct = ids[0] if len(set(ids)) == 1 else ""
    acct = re.sub(r"[\s.،,]+$", "", acct)
    if not acct or len(acct) > 60 or acct.count("\n"):
        return None
    out["account"] = acct
    # المدة
    days = set()
    for v in labelled.get("time", []):
        k = _k(v)
        mh = re.search(r"(\d{1,3})\s*ساعه", k)
        if mh:
            days.add(max(1, math.ceil(int(mh.group(1)) / 24)))
        md = re.search(r"(\d{1,3})\s*(?:يوم|ايام)", k)
        if md:
            days.add(int(md.group(1)))
        if re.search(r"يوم واحد|^يوم$", k):
            days.add(1)
        if "اسبوعين" in k:
            days.add(14)
        elif "اسبوع" in k:
            days.add(7)
    for l in free:
        m = _DAYS_LINE.match(_k(l))
        if m:
            g = m.group(1)
            days.add({"يوم واحد": 1, "يوم": 1, "يومين": 2, "اسبوع": 7, "اسبوعين": 14}[g] if g else int(m.group(2)) if m.group(2) else _NUMW[m.group(3)])
    if len(days) != 1:
        return None                                   # ناقصة أو متضاربة: ما نخمّن
    d = days.pop()
    if not 1 <= d <= 90:
        return None
    out["days"] = d
    # الميزانية
    cands = []
    for v in labelled.get("budget", []):
        mm = _BUDGET_LINE.match(_k(v))
        if mm:
            cands.append(mm)
    for l in free:
        mm = _BUDGET_LINE.match(_k(l))
        if mm:
            cands.append(mm)
    if len(cands) != 1:
        return None
    mm = cands[0]
    b = _num(mm.group(1)) * (1000 if mm.group(2) in ("الف", "الاف", "k") else 1_000_000 if mm.group(2) == "مليون" else 1)
    if not b > 0:
        return None
    out["budget"] = int(b) if b == int(b) else b
    k = _k(raw)
    out["budget_kind"] = "daily" if (mm.group(4) in ("يوميا", "يوميه", "لكل يوم", "كل يوم") or re.search(r"(?:ميزانيه|ميزانية)\s+يوميه|ميزانيه يوميا|per day|daily", k)) else "total"
    u = _URL.search(raw)
    if u:
        out["landing_page"] = u.group(0).rstrip(".,،)")
    nm = [v for v in labelled.get("name", []) if v]
    if nm:
        out["name"] = nm[-1][:80]
    else:
        for l in free:
            m = re.search(r"(?:سميها|اسمها)\s+(.+)$", _norm(l))
            if m:
                out["name"] = m.group(1).strip()[:80]
                break
    out["activate_now"] = bool(_ACT.search(k))
    return out
