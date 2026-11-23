# -*- coding: utf-8 -*-
"""تصنيف حتمي (بدون LLM) للعينات: المنتجات، زوايا الرسالة، العروض، إشارات المحتوى (Hook/CTA/فيديو/أسلوب/تكرار). كل نتيجة تحمل معرّفات الأدلة."""
import re
from . import confidence as C
from .lexicon import ANGLES, ANGLE_ORDER, CTAS, HOOKS, PRODUCTS, STYLES, VIDEO, norm

_SPLIT = re.compile(r"(?<=[.!؟?\n])\s+|\n+")


def _sentences(text):
    return [s.strip() for s in _SPLIT.split(text) if len(s.strip()) >= 6]


def _hit(nt: str, words) -> bool:
    return any(w in nt for w in words)


def _quote(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()[:140]


def classify(samples):
    total = len(samples)
    prod, ang, offers, ctas, hooks, vid, styles, rep = {}, {k: {"ev": [], "q": []} for k in ANGLE_ORDER}, [], {}, [], 0, {}, {}
    sent_seen = {}
    for s in samples:
        nt = norm(s["text"])
        sents = _sentences(s["text"]) or [s["text"]]
        for name, words in PRODUCTS.items():
            if _hit(nt, [norm(w) for w in words]):
                p = prod.setdefault(name, {"ev": []})
                if s["id"] not in p["ev"]: p["ev"].append(s["id"])
        for k in ANGLE_ORDER:
            ws = [norm(w) for w in ANGLES[k][1]]
            for sn in sents:
                if _hit(norm(sn), ws):
                    a = ang[k]
                    if s["id"] not in a["ev"]: a["ev"].append(s["id"])
                    if len(a["q"]) < 3 and _quote(sn) not in a["q"]: a["q"].append(_quote(sn))
                    break
        for sn in sents:
            ns = norm(sn)
            if re.search(r"\d+\s*%|1\s*\+\s*1|اشتري\s*\d|خصم\s*\d|عرض", ns) and len(offers) < 5 and _quote(sn) not in [o["quote"] for o in offers]:
                offers.append({"quote": _quote(sn), "evidence": [s["id"]]})
            if len(ns) >= 14:
                sent_seen.setdefault(ns, {"ids": set(), "raw": _quote(sn)})["ids"].add(s["id"])
        for w in CTAS:
            if norm(w) in nt:
                c = ctas.setdefault(w, {"ev": [], "q": _quote(next((x for x in sents if norm(w) in norm(x)), s["text"]))})
                if s["id"] not in c["ev"]: c["ev"].append(s["id"])
        first = sents[0] if sents else s["text"]
        if any(re.search(h, norm(first)) or re.search(h, first) for h in HOOKS):
            hooks.append({"quote": _quote(first), "evidence": [s["id"]]})
        if _hit(nt, [norm(v) for v in VIDEO]): vid += 1
        for st, ws in STYLES.items():
            if ws and _hit(nt, [norm(w) for w in ws]): styles.setdefault(st, []).append(s["id"])
        if len(re.findall(r"[\U0001F300-\U0001FAFF☀-➿]", s["text"])) >= 3: styles.setdefault("emoji_heavy", []).append(s["id"])
    products = sorted(({"name": n, "count": len(v["ev"]), "evidence": v["ev"], "level": C.fact(len(v["ev"]))} for n, v in prod.items()), key=lambda x: -x["count"])
    angles = {k: {"label": ANGLES[k][0], "count": len(v["ev"]), "evidence": v["ev"], "quotes": v["q"], "level": C.pattern(len(v["ev"]), total)} for k, v in ang.items() if v["ev"]}
    repeated = sorted(({"phrase": v["raw"], "count": len(v["ids"]), "evidence": sorted(v["ids"])} for v in sent_seen.values() if len(v["ids"]) >= 2), key=lambda x: -x["count"])[:5]
    return {
        "total": total, "products": products[:8], "angles": angles, "offers": offers,
        "content": {"hooks": hooks[:5], "ctas": [{"phrase": k, "quote": v["q"], "evidence": v["ev"], "level": C.fact(len(v["ev"]))} for k, v in list(ctas.items())[:5]],
                    "video_mentions": vid, "styles": {k: {"evidence": v, "level": C.pattern(len(v), total)} for k, v in styles.items()}, "repeated": repeated},
    }
