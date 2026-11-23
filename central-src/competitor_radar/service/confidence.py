# -*- coding: utf-8 -*-
"""مستوى الثقة يُحسب بالكود (مو بالـLLM): 🟢 عالي = حقيقة مقتبسة من النص المجموع/الملصوق؛ 🟡 متوسط = استنتاج مدعوم بعينتين مستقلتين أو أكثر؛
🔴 منخفض = عينة وحدة أو معرفة عامة. أي شي بدون أدلة = منخفض."""
HIGH, MEDIUM, LOW = "high", "medium", "low"
ICON = {HIGH: "🟢", MEDIUM: "🟡", LOW: "🔴"}
LABEL = {HIGH: "ثقة عالية", MEDIUM: "ثقة متوسطة", LOW: "ثقة منخفضة"}
_RANK = {LOW: 0, MEDIUM: 1, HIGH: 2}


def cap(level: str, ceiling: str) -> str:
    return level if _RANK[level] <= _RANK[ceiling] else ceiling


def lowest(levels):
    levels = list(levels)
    return min(levels, key=lambda x: _RANK[x]) if levels else LOW


def fact(n_evidence: int) -> str:
    """اقتباس مباشر موجود بالعينات"""
    return HIGH if n_evidence >= 1 else LOW


def pattern(hits: int, total: int) -> str:
    """استنتاج نمط (مثلاً «يركز على السعر»): كم عينة من المجموع تدعمه"""
    if hits <= 0 or total <= 0:
        return LOW
    if hits >= 3 and hits / total >= 0.4 and total >= 4:
        return HIGH
    if hits >= 2:
        return MEDIUM
    return LOW


def overall(total_samples: int, levels) -> str:
    """ثقة التقرير الكلية: محدودة بحجم البيانات، وبأضعف المستويات الرئيسية"""
    if total_samples < 3:
        return LOW
    base = lowest(levels) if levels else LOW
    return cap(base, HIGH if total_samples >= 8 else MEDIUM)


def badge(level: str) -> str:
    return ICON.get(level, "🔴") + " " + LABEL.get(level, LABEL[LOW])
