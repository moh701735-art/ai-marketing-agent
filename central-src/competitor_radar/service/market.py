# -*- coding: utf-8 -*-
"""🌎 رادار السوق v1: بدون سحب من أي منصة. يجمع تقارير منافسي العميل (المحللة) + عينات سوق يلصقها المستخدم. أي شي من معرفة النموذج العامة
يُعلَّم 🔴 «معرفة عامة وليست بيانات حية». المخرجات فرص/فرضيات وليست حقائق."""
from . import confidence as C
from .analyze import validate
from .classify import classify
from .lexicon import ANGLES, ANGLE_ORDER
from .llm import LLMUnavailable

NOTE = "استنتاجات وتوصيات وليست حقائق إلا إذا كانت مدعومة بالبيانات المعروضة."


def analyze_market(query, reports, pasted_samples, llm=None):
    q = " ".join(str(query or "").split())
    if not (3 <= len(q) <= 120): return {"status": "invalid", "message": "اكتب وصفاً للسوق (3–120 حرف) مثل: فساتين نسائية في العراق."}
    s, _ = validate(pasted_samples or [])
    rep = [r for r in (reports or []) if isinstance(r, dict) and r.get("status") == "ok"]
    n_src = len(rep) + (1 if len(s) >= 2 else 0)
    prods, angs, offers = {}, {k: 0 for k in ANGLE_ORDER}, 0
    for r in rep:
        for p in r.get("products", []): prods[p["name"]] = prods.get(p["name"], 0) + 1
        for m in r.get("messages", []):
            if m["level"] in (C.HIGH, C.MEDIUM): angs[m["key"]] += 1
        offers += 1 if r.get("offers") else 0
    if len(s) >= 2:
        cl = classify(s)
        for p in cl["products"]: prods[p["name"]] = prods.get(p["name"], 0) + 1
        for k, v in cl["angles"].items():
            if v["level"] in (C.HIGH, C.MEDIUM): angs[k] += 1
        offers += 1 if cl["offers"] else 0
    out = {"status": "ok", "query": q, "sources": {"competitor_reports": len(rep), "pasted_samples": len(s)}, "note": NOTE, "opportunities": [], "frequent_products": [], "frequent_angles": [], "model_knowledge": []}
    if n_src:
        out["frequent_products"] = [{"name": k, "sources": v, "level": C.pattern(v, n_src)} for k, v in sorted(prods.items(), key=lambda x: -x[1])[:6]]
        out["frequent_angles"] = [{"label": ANGLES[k][0], "sources": v, "level": C.pattern(v, n_src)} for k, v in sorted(angs.items(), key=lambda x: -x[1]) if v][:6]
        busy = [k for k, v in angs.items() if v >= max(2, n_src // 2)]
        idle = [k for k in ("quality", "guarantee", "trust", "social_proof", "delivery") if angs[k] == 0]
        if busy and idle:
            out["opportunities"].append({"text": "الزوايا المتكررة بالبيانات المتاحة: %s. زاوية أقل استخداماً قد تستحق اختباراً: %s." % ("، ".join(ANGLES[k][0] for k in busy[:3]), "، ".join(ANGLES[k][0] for k in idle[:2])),
                                         "level": C.MEDIUM if n_src >= 3 else C.LOW, "kind": "recommendation", "tag": "💡 فرصة محتملة"})
        if offers and n_src >= 2:
            out["opportunities"].append({"text": "عروض ظاهرة عند %d من %d مصادر؛ نوع عرض مختلف (باقة/هدية/ضمان) قد يكون قابلاً للاختبار." % (offers, n_src), "level": C.LOW, "kind": "recommendation", "tag": "💡 فرصة محتملة"})
    if llm is not None:
        try:
            o = llm.complete_json("أنت محلل أسواق. أجب JSON فقط: {\"opportunities\": [\"...\"]} (حد أقصى 3، فرضيات قابلة للاختبار بالعربية، بدون ادعاء حقائق أو أرقام).",
                                  "السوق: " + q, 700)
            for t in (o.get("opportunities") or [])[:3]:
                if isinstance(t, str) and t.strip():
                    out["model_knowledge"].append({"text": t.strip()[:300], "level": C.LOW, "kind": "model_knowledge", "tag": "🔴 معرفة عامة وليست بيانات حية"})
        except LLMUnavailable:
            pass
    if not out["opportunities"] and not out["model_knowledge"] and not out["frequent_products"]:
        return {**out, "status": "insufficient", "message": "⚠️ بيانات غير كافية للتحليل. حلّل منافسين أولاً أو الصق عينات من السوق."}
    out["confidence"] = C.LOW if n_src < 3 else C.MEDIUM
    return out
