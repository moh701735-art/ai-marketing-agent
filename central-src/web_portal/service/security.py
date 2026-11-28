# -*- coding: utf-8 -*-
"""أدوات أمان صغيرة بدون مكتبات خارجية: scrypt لكلمات السر، رموز عشوائية، sha256 للجلسات/الدعوات، CSRF بالمقارنة الثابتة."""
import base64, hashlib, hmac, os, re, secrets

SCRYPT_LOG_N, SCRYPT_R, SCRYPT_P = 15, 8, 1
MIN_PWD, MAX_PWD = 6, 64
PWD_RE = re.compile(r"^[A-Za-z0-9]+$")
COMMON_PWDS = {"123456", "1234567", "12345678", "123456789", "abc123", "abcd1234", "abc12345", "qwerty", "qwerty123", "password", "password1", "pass123", "admin123", "a12345", "a123456", "aa123456", "1q2w3e", "iloveyou1", "test123", "user123", "welcome1", "asd123", "q12345", "zxc123"}
APP_ID_RE = re.compile(r"^[0-9]{5,25}$")
AUTH_CODE_RE = re.compile(r"^[A-Za-z0-9._~+/=-]{8,255}$")
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


STATE_PREFIX = "w-"   # حالة ربط تيك توك: الجسر (Caddy) يحوّل للبوابة فقط الطلبات اللي state فيها يبدأ بهذا؛ غيرها يبقى للصفحة القديمة


def new_state() -> str:
    return STATE_PREFIX + new_token()


def valid_state(s) -> bool:
    return isinstance(s, str) and valid_token(s[len(STATE_PREFIX):] if s.startswith(STATE_PREFIX) else s)


def csrf_ok(cookie_val, form_val) -> bool:
    return isinstance(cookie_val, str) and isinstance(form_val, str) and valid_token(cookie_val) and hmac.compare_digest(cookie_val, form_val)


def password_problem(pwd: str, confirm: str):
    """سياسة مخففة بطلب المالك: 6 خانات فأكثر، أرقام وحروف إنكليزية فقط، لازم حرف ورقم، وبدون الكلمات الشائعة. القفل بعد 5 محاولات يبقى بالقاعدة."""
    if not isinstance(pwd, str) or len(pwd) < MIN_PWD: return "كلمة السر لازم تكون %d خانات على الأقل." % MIN_PWD
    if len(pwd) > MAX_PWD: return "كلمة السر طويلة جداً."
    if not PWD_RE.fullmatch(pwd): return "كلمة السر أرقام وحروف إنكليزية فقط (بدون رموز أو مسافات أو حروف عربية)."
    if not (re.search(r"[A-Za-z]", pwd) and re.search(r"[0-9]", pwd)): return "كلمة السر لازم فيها حرف ورقم (مثل gm2026x)."
    if pwd != confirm: return "كلمتا السر غير متطابقتين."
    if pwd.lower() in COMMON_PWDS or len(set(pwd.lower())) < 3: return "كلمة السر شائعة وضعيفة، اختر غيرها."
    return None


# ---- رموز الدعوة القصيرة: 12 خانة من أبجدية بدون حروف متشابهة (Crockford: بدون i,l,o,u)، تُكتب بسهولة من صورة. 60 بت عشوائية ----
INVITE_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
INVITE_LEN = 12


def new_invite_code() -> str:
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(INVITE_LEN))


def norm_invite(raw):
    """يقبل الرمز بشرطات/مسافات/حروف كبيرة؛ يحوّل o→0 وi,l→1 (مثل Crockford). يرجع الرمز النظيف أو None."""
    if not isinstance(raw, str): return None
    t = re.sub(r"[\s\-_]", "", raw.strip().lower()).replace("o", "0").replace("i", "1").replace("l", "1")
    return t if len(t) == INVITE_LEN and all(c in INVITE_ALPHABET for c in t) else None


def invite_hash(raw):
    """هاش الدعوة: رمز قصير (يُنظَّف أولاً) أو رمز طويل قديم (32-64). None لو شكله غلط."""
    n = norm_invite(raw)
    if n: return hashlib.sha256(n.encode("utf-8")).hexdigest()
    if valid_token(raw): return token_hash(raw)
    return None


def fmt_invite(code: str) -> str:
    return "-".join(code[i:i + 4] for i in range(0, len(code), 4))
