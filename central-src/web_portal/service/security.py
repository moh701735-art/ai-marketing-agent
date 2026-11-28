# -*- coding: utf-8 -*-
"""أدوات أمان صغيرة بدون مكتبات خارجية: scrypt لكلمات السر، رموز عشوائية، sha256 للجلسات/الدعوات، CSRF بالمقارنة الثابتة."""
import base64, hashlib, hmac, os, re, secrets

SCRYPT_LOG_N, SCRYPT_R, SCRYPT_P = 15, 8, 1
MIN_PWD, MAX_PWD = 10, 200
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,64}$")
_b64 = lambda b: base64.urlsafe_b64encode(b).decode().rstrip("=")
_unb64 = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _scrypt(password: str, salt: bytes, log_n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2 ** log_n, r=r, p=p, dklen=32, maxmem=128 * 2 ** log_n * r * 2 + 2 ** 20)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    return "scrypt$%d$%d$%d$%s$%s" % (SCRYPT_LOG_N, SCRYPT_R, SCRYPT_P, _b64(salt), _b64(_scrypt(password, salt, SCRYPT_LOG_N, SCRYPT_R, SCRYPT_P)))


def verify_password(password: str, encoded) -> bool:
    """مقارنة ثابتة الزمن. إن كان المخزَّن ناقص/تالف يرجع False (بعد نفس الكلفة تقريباً حتى ما يُعرف إن كان الإيميل موجود)."""
    try:
        kind, ln, r, p, salt, h = str(encoded).split("$")
        if kind != "scrypt" or not (10 <= int(ln) <= 17) or int(r) > 16 or int(p) > 4: raise ValueError
        got = _scrypt(password, _unb64(salt), int(ln), int(r), int(p))
        return hmac.compare_digest(got, _unb64(h))
    except Exception:
        _scrypt(password, b"\0" * 16, SCRYPT_LOG_N, SCRYPT_R, SCRYPT_P)
        return False


def dummy_verify(password: str) -> None:
    _scrypt(password, b"\0" * 16, SCRYPT_LOG_N, SCRYPT_R, SCRYPT_P)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(tok: str) -> str:
    return hashlib.sha256(tok.encode("utf-8")).hexdigest()


def valid_token(tok) -> bool:
    return isinstance(tok, str) and bool(TOKEN_RE.fullmatch(tok))


def csrf_ok(cookie_val, form_val) -> bool:
    return isinstance(cookie_val, str) and isinstance(form_val, str) and valid_token(cookie_val) and hmac.compare_digest(cookie_val, form_val)


def password_problem(pwd: str, confirm: str):
    if not isinstance(pwd, str) or len(pwd) < MIN_PWD: return "كلمة السر لازم تكون %d أحرف على الأقل." % MIN_PWD
    if len(pwd) > MAX_PWD: return "كلمة السر طويلة جداً."
    if pwd != confirm: return "كلمتا السر غير متطابقتين."
    if pwd.lower() in ("password123", "1234567890", "qwertyuiop") or len(set(pwd)) < 4: return "كلمة السر ضعيفة، اختر كلمة أصعب."
    return None
