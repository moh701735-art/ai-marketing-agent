# -*- coding: utf-8 -*-
"""🥊 خطة المنافسة: تحويل التقرير إلى استراتيجية أصلية (زاوية، Hook، فكرة، CTA، جمهور، 3 اختبارات، ميزانية توصية). ما تنسخ المنافس:
فحص تطابق صارم (n-gram) ضد نصوص المنافس قبل الإرجاع. الخطة توصية فقط: لا تنشئ/تشغّل/تعدّل أي حملة."""
import re
from . import confidence as C
from .lexicon import ANGLES, norm
from .llm import LLMUnavailable

PREF = ["quality", "guarantee", "trust", "social_proof", "delivery", "problem_solution", "offer"]
HOOK = {
    "quality": "ليش {p} الجيد يفرق؟ جرّبه مرة وتعرف الفرق بنفسك.",
    "guarantee": "اطلب {p} وانت مرتاح: عدنا ضمان واضح لو ما عجبك.",
    "trust": "زبائننا وصلهم {p} وراجعونا مرة ثانية. شوف ليش.",
    "social_proof": "شوف شنو يكولون ناس جربوا {p} عدنا.",
    "delivery": "{p} يوصلك لباب البيت، وانت بس اختار.",
    "problem_solution": "تعبت من نفس المشكلة؟ {p} جاي يحلها بخطوة بسيطة.",
    "offer": "عرض محدود على {p}: اطلب هسه قبل ما يخلص.",
}
IDEA = {
    "quality": "فيديو قصير يعرض {p} عن قرب (خامة/تفصيل/استخدام حقيقي) مع مقارنة هادئة بدون ذكر منافس.",
    "guarantee": "فيديو يشرح خطوات الضمان/الاسترجاع بوضوح ويعرض المنتج وهو يُسلَّم للزبون.",
    "trust": "فيديو من وراء الكواليس: تجهيز الطلب وتغليفه وتوصيله، مع تعليق صوتي بسيط.",
    "social_proof": "تجميع رسائل/تقييمات حقيقية من زبائن (بإذنهم) مع لقطات المنتج.",
    "delivery": "فيديو يتتبّع رحلة الطلب من الاستلام للتوصيل بسرعة وبساطة.",
    "problem_solution": "مشهد قبل/بعد: المشكلة ثم استخدام {p} ثم النتيجة.",
    "offer": "فيديو قصير يعرض العرض وشروطه بشكل واضح مع عد تنازلي للمدة.",
}
AUD = {"فساتين": "نساء 18–44", "عبايات": "نساء 20–50", "ملابس نسائية": "نساء 18–44", "مكياج وعناية": "نساء 18–40", "عطور": "رجال ونساء 20–45", "ملابس رجالية": "رجال 18–45",
       "ملابس أطفال": "أمهات 22–40", "مطاعم وأكل": "الجميع 18–45 قرب منطقة المطعم", "أثاث وديكور": "أرباب بيوت 25–50"}


def _tok(s):
    return re.findall(r"[\w؀-ۿ]+", norm(s))


def _shingles(t, n=5):
    return {tuple(t[i:i + n]) for i in range(max(0, len(t) - n + 1))}


def overlap(text, samples):
    """→ {max_overlap, run, passed}: containment لـ5-gram + أطول مقطع متطابق بالكلمات"""
    t = _tok(text)
    if not t: return {"max_overlap": 0.0, "run": 0, "passed": True}
    sh, best, run = _shingles(t), 0.0, 0
    for s in samples:
        st = _tok(s["text"])
        if sh: best = max(best, len(sh & _shingles(st)) / len(sh))
        for n in range(min(len(t), len(st), 12), 5, -1):   # مقطع ≥6 كلمات متطابق
            if _shingles(t, n) & _shingles(st, n):
                run = max(run, n); break
    return {"max_overlap": round(best, 3), "run": run, "passed": best < 0.15 and run < 6}


def _rules(report):
    msgs = {m["key"]: m["count"] for m in report.get("messages", [])}
    ang = sorted(PREF, key=lambda k: (msgs.get(k, 0), PREF.index(k)))
    p = (report.get("products") or [{}])[0].get("name") or (report.get("business") or {}).get("domain") or "منتجك"
    dom = (report.get("business") or {}).get("domain")
    top = ang[0]
    tests = [{"angle": ANGLES[k][0], "hook": HOOK[k].format(p=p), "idea": IDEA[k].format(p=p)} for k in ang[:3]]
    why = "لم تظهر عند المنافس بالعينات" if msgs.get(top, 0) == 0 else "ظهرت عند المنافس بدرجة أقل من غيرها"
    return {"angle": {"key": top, "label": ANGLES[top][0], "why": why + " (توصية وليست حقيقة)"}, "hook": tests[0]["hook"], "ad_idea": tests[0]["idea"],
            "cta": "اضغط على زر واتساب واطلب هسه.", "audience": (AUD.get(dom) or "حدّد حسب منتجك وعمر زبائنك الفعليين") + " — توصية مبدئية قابلة للتعديل", "tests": tests,
            "budget": "توصية فقط: جرّب كل فكرة بميزانية صغيرة (مثلاً 5–10$) لمدة 2–3 أيام ثم قارن سعر النتيجة. لا يتم أي إطلاق تلقائي.", "source": "rules"}


def _llm_plan(report, llm):
    sysm = ("أنت خبير إعلانات. أنشئ خطة منافسة أصلية بالعربية (لهجة عراقية بسيطة) من الملخص. ممنوع نسخ أي نص من المنافس أو ذكر اسم علامته. أجب JSON فقط: "
            '{"angle": "...", "hook": "...", "ad_idea": "...", "cta": "...", "audience": "...", "tests": [{"angle": "...", "hook": "...", "idea": "..."}], "budget": "..."} '
            "tests = 3 عناصر بالضبط. كل نص ≤220 حرف.")
    brief = {"domain": (report.get("business") or {}).get("domain"), "products": [p["name"] for p in report.get("products", [])[:4]],
             "competitor_angles": [m["label"] for m in report.get("messages", [])[:4]], "platform": report.get("platform")}
    o = llm.complete_json(sysm, "ملخص (بدون نصوص المنافس الأصلية): %s" % brief, 1200)
    g = lambda k: o.get(k).strip()[:220] if isinstance(o.get(k), str) and o.get(k).strip() else None
    tests = [{"angle": (t.get("angle") or "")[:60], "hook": (t.get("hook") or "")[:220], "idea": (t.get("idea") or "")[:220]} for t in (o.get("tests") or [])[:3] if isinstance(t, dict)]
    if not all(g(k) for k in ("angle", "hook", "ad_idea", "cta", "audience", "budget")) or len(tests) != 3 or not all(t["hook"] and t["idea"] for t in tests): return None
    return {"angle": {"key": "ai", "label": g("angle"), "why": "اقتراح AI (توصية)"}, "hook": g("hook"), "ad_idea": g("ad_idea"), "cta": g("cta"), "audience": g("audience"), "tests": tests, "budget": g("budget"), "source": "ai"}


def build_strategy(report, samples, llm=None):
    if report.get("status") != "ok":
        return {"status": "insufficient", "message": "⚠️ بيانات غير كافية لبناء خطة؛ حلّل منافساً ببيانات أكثر أولاً."}
    plan, note = None, ""
    if llm is not None:
        try: plan = _llm_plan(report, llm)
        except LLMUnavailable as e: note = "llm_skipped:%s" % e
    if plan is not None:
        text = " ".join([plan["hook"], plan["ad_idea"], plan["cta"]] + [t["hook"] + " " + t["idea"] for t in plan["tests"]])
        if not overlap(text, samples)["passed"]: plan, note = None, "ai_rejected_copy_risk"
    if plan is None: plan = _rules(report)
    text = " ".join([plan["hook"], plan["ad_idea"], plan["cta"]] + [t["hook"] + " " + t["idea"] for t in plan["tests"]])
    ov = overlap(text, samples)
    if not ov["passed"]:   # حتى القوالب الحتمية: نمنع أي تطابق
        return {"status": "blocked", "message": "تعذّر إنشاء خطة أصلية (احتمال تطابق مع نص المنافس). عدّل العينات وأعد المحاولة.", "originality": ov}
    return {"status": "ok", **plan, "originality": {**ov, "method": "5-gram containment <0.15 + no 6-word run"}, "confidence": C.LOW if report.get("overall_confidence") == C.LOW else C.MEDIUM,
            "note": note, "disclaimer": "توصية فقط وليست حقيقة مؤكدة؛ لا تُنفَّذ أي حملة تلقائياً."}
