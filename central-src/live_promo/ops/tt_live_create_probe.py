#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""المرحلة B1 لـ«ترويج البث المباشر» (v2 / p278): يقرأ من تيك توك نفسه قائمة `objective_type` المسموحة — **بدون إنشاء أي حملة**: يرسل قيمة هدف غير صالحة عمداً (PROBE_INVALID_*)،
فيرفضها تيك توك برسالة 40002 فيها «allowed: …». الكود يرفض أي قيمة هدف غير هذا البادئة (حتى لا تنشأ حملة بالغلط). لا مجموعة، لا إعلان، لا صرف.
v2: محلّل مرن (أي تنسيق: أقواس/اقتباسات/أسطر) + يطبع كل قيمة بسطر مستقل وبحروف مفرّقة (E N G A G E M E N T) حتى لا تغيّرها ترجمة المتصفح.
يتطلب p277 (عملية Broker معزولة tiktok.probe_campaign). غير المعروف = N/A.
  SA_SLUG=mohm SA_ACCT=7593807340588253185 python3 ops/tt-live-create-probe.py"""
import importlib.util, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
NA = "N/A"
INVALID = "PROBE_INVALID_OBJECTIVE"
OP = "tiktok.probe_campaign"
TOKEN = re.compile(r"[A-Z][A-Z0-9_]{2,}")


def fold(s): return re.sub(r"[^ -~]", "?", str(s))


def spaced(s): return " ".join(str(s))


def load_wad():
    p = os.environ.get("WA_DIAG_PATH", os.path.join(HERE, "wa-diagnose.py"))
    if not os.path.exists(p): raise SystemExit("missing ops/wa-diagnose.py (p263) - install it first")
    s = importlib.util.spec_from_file_location("wad", p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def build_call(objective=INVALID):
    """يرفض أي هدف لا يبدأ بـPROBE_INVALID (ضمان: هذه الأداة لا تنشئ حملة)"""
    if not str(objective).startswith("PROBE_INVALID"): raise SystemExit("REFUSED: this tool only sends an invalid objective on purpose")
    return {"label": "probe", "op": OP, "params": {"campaign_name": "PROBE-INVALID-DELETE-ME", "objective_type": objective, "budget_mode": "BUDGET_MODE_INFINITE"}}


def tokens_after_allowed(msg):
    """كل رموز UPPER_SNAKE بعد كلمة allowed (بأي تنسيق)؛ بدونها = كل الرموز بعد أول «:» ؛ بدون تكرار وبالترتيب، بدون PROBE_INVALID_*"""
    s = str(msg or "")
    m = re.search(r"allowed", s, re.I)
    tail = s[m.end():] if m else ""
    out, seen = [], set()
    for t in TOKEN.findall(tail):
        if t.startswith("PROBE_INVALID") or t in seen: continue
        seen.add(t); out.append(t)
    return out


def parse(res):
    """→ dict: created(bool), allowed(list), message(str), cls, code"""
    err = res.get("error") or {}
    msg = str(err.get("message") or "")
    allowed = tokens_after_allowed(msg)
    allmsg = []
    for t in TOKEN.findall(msg):
        if not t.startswith("PROBE_INVALID") and t not in allmsg: allmsg.append(t)
    return {"created": bool(res.get("ok")), "allowed": allowed, "all_tokens": allmsg, "message": msg, "cls": str(err.get("class") or NA), "code": str(err.get("platform_code") or NA)}


def report(r):
    L = ["== TikTok LIVE probe B1 v2 (objective list from TikTok itself; invalid value on purpose; NO campaign is created) =="]
    if r["created"]: L.append("WARNING: TikTok ACCEPTED the probe value and a campaign may exist (name PROBE-INVALID-DELETE-ME); check Ads Manager and delete it.")
    L += ["TikTok answer class=%s platform_code=%s" % (r["cls"], r["code"]), "TikTok message length=%d" % len(r["message"]), "TikTok message (verbatim, ASCII): " + fold(r["message"])[:3000], "",
          "======== FINAL BLOCK (ASCII) ========", "OBJECTIVE VALUES ALLOWED BY TIKTOK (%d), one per line, plain | letter-spaced:" % len(r["allowed"])]
    for i, a in enumerate(r["allowed"], 1): L.append("%02d %s | %s" % (i, a, spaced(a)))
    if not r["allowed"]:
        L.append(NA)
        L.append("ALL UPPER-CASE TOKENS FOUND ANYWHERE IN THE MESSAGE (%d): %s" % (len(r.get("all_tokens", [])), ", ".join(r.get("all_tokens", [])) or NA))
    live = [a for a in r["allowed"] if re.search(r"live|stream|communit|engag|interact", a, re.I)]
    L += ["LIVE/ENGAGEMENT-LIKE OBJECTIVES: " + (", ".join(live) or "NONE FOUND"), "LIVE/ENGAGEMENT-LIKE letter-spaced: " + (" ; ".join(spaced(a) for a in live) or NA),
          "NO CAMPAIGN CREATED (unless the WARNING line above appears). No ad group, no ad, no spend."]
    return "\n".join(L)


def main():
    slug = os.environ.get("SA_SLUG", "mohm").strip(); acct = os.environ.get("SA_ACCT", "7593807340588253185").strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", slug) or not re.fullmatch(r"[0-9]{6,25}", acct): sys.exit("bad SA_SLUG / SA_ACCT")
    wad = load_wad(); env = wad.Env()
    tid = wad.psql(env, "select tenant_id from core.tenants where slug='%s'" % slug)
    ctxs = wad.psql(env, "select ctx from api.job_contexts_for_status(ARRAY['TESTING','NEEDS_REVIEW','READY'],100) where tenant_id='%s'" % tid[0]) if tid else []
    if not ctxs: sys.exit("tenant/ctx not found")
    res = wad.broker(env, ctxs[0], acct, [build_call()])[0]
    print(report(parse(res)))


if __name__ == "__main__":
    main()
