"""إخفاء الأسرار من أي نص/سجل/استثناء/رد. ثلاث طبقات:
1) أنماط معروفة (Telegram/Meta/TikTok/رؤوس/معاملات URL).
2) مفاتيح قواميس حسّاسة (token/secret/password/authorization/access-token...).
3) سجل بالقيم المعروفة: أي سر فُكّ تشفيره بالذاكرة يُسجَّل هنا، فيُحجب نصّه الحرفي حتى لو بصيغة غير متوقعة.
"""
import logging
import re
import threading
from collections import OrderedDict

MASK = "[REDACTED]"
_PATTERNS = [
    re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"),            # Telegram bot token
    re.compile(r"/bot\d{8,10}:[A-Za-z0-9_-]+"),                  # داخل URL
    re.compile(r"\bEA[A-Za-z0-9]{20,}"),                         # Meta (EAA..., EAAG...)
    re.compile(r"\b[0-9a-f]{40}\b"),                             # TikTok access token (40 hex)
    re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)((?:access[_-]?token|client[_-]?secret|app[_-]?secret|refresh[_-]?token|auth[_-]?code|code|password|secret[_-]?token)=)[^&\s\"']+"),
    re.compile(r"(?i)((?:access-token|authorization|x-telegram-bot-api-secret-token|x-api-key)\s*[:=]\s*)[^\s,;\"']+"),
]
_SENSITIVE_KEY = re.compile(r"(?i)(token|secret|password|passwd|authorization|api[_-]?key|credential|ciphertext|dek|cookie)")


class KnownSecrets:
    """قيم أسرار حيّة بالذاكرة (محدودة العدد). تُستعمل للحجب الحرفي."""
    def __init__(self, limit: int = 5000):
        self._d: "OrderedDict[str, None]" = OrderedDict()
        self._limit, self._lock = limit, threading.Lock()

    def add(self, value: str):
        if value and len(value) >= 8:
            with self._lock:
                self._d[value] = None
                self._d.move_to_end(value)
                while len(self._d) > self._limit:
                    self._d.popitem(last=False)

    def scrub(self, text: str) -> str:
        with self._lock:
            vals = sorted(self._d, key=len, reverse=True)
        for v in vals:
            text = text.replace(v, MASK)
        return text


KNOWN = KnownSecrets()


def redact_text(text: str) -> str:
    text = KNOWN.scrub(text)
    for p in _PATTERNS:
        text = p.sub(lambda m: (m.group(1) + MASK) if p.groups else MASK, text)
    return text


def redact(obj):
    """يعمل على str/dict/list/tuple/Exception ويعيد نسخة نظيفة (لا يعدّل الأصل)."""
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, BaseException):
        return redact_text(f"{type(obj).__name__}: {obj}")
    if isinstance(obj, dict):
        return {k: (MASK if isinstance(k, str) and _SENSITIVE_KEY.search(k) else redact(v)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(redact(v) for v in obj)
    return obj


class RedactingFilter(logging.Filter):
    """يُركَّب على كل handler. يحجب الرسالة والمعاملات واستثناءها (traceback أيضاً)."""
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact_text(record.getMessage())
        except Exception:
            record.msg = MASK
        record.args = ()
        if record.exc_info:
            import traceback
            record.msg += "\n" + redact_text("".join(traceback.format_exception(*record.exc_info)))
            record.exc_info = None
            record.exc_text = None
        return True
