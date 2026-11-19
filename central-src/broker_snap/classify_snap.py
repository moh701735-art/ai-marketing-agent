_SNAP_KEYS = ("sub_request_error_reason", "display_message", "debug_message", "error_description", "message", "error", "error_code", "reason")


def _snap_texts(x, out, depth=0):
    """يجمع نصوص الرفض من أي مستوى بجسم رد سناب (p197e): السبب الحقيقي غالباً متداخل داخل قائمة الطلبات الفرعية."""
    if depth > 6 or len(out) >= 8:
        return
    if isinstance(x, dict):
        for k, v in x.items():
            if k in _SNAP_KEYS and isinstance(v, str) and v.strip():
                t = v.strip()[:200]
                if t not in out:
                    out.append(t)
            elif isinstance(v, (dict, list)):
                _snap_texts(v, out, depth + 1)
    elif isinstance(x, list):
        for v in x[:10]:
            _snap_texts(v, out, depth + 1)


def _snapchat(status: int, body):
    """سناب (p191d + p197e): النجاح = 2xx وrequest_status ≠ ERROR؛ الفشل يحمل نص سبب الرفض كاملاً (حتى المتداخل) بدل كلمة bad_request فقط."""
    ok = 200 <= status < 300 and not (isinstance(body, dict) and str(body.get("request_status", "SUCCESS")).upper() == "ERROR")
    if ok:
        return _tiktok(status, {})
    texts = []
    _snap_texts(body, texts)
    msg = " | ".join(texts)[:380] if texts else None
    return _tiktok(status if status >= 400 else 400, {"message": msg} if msg else {})


