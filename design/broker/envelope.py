"""تشفير مغلّف (envelope encryption) للأسرار. AES-256-GCM.

- كل سر له مفتاح بيانات (DEK) عشوائي. الـ DEK يُغلَّف بمفتاح رئيسي (KEK) يعيش بذاكرة/بيئة الـ Broker فقط، لا بأي قاعدة بيانات.
- AAD (بيانات موثّقة غير مشفّرة) = tenant_id|kind|version|secret_ref. لذلك نسخ مشفّر سر عميل إلى صف عميل آخر،
  أو إلى نسخة/نوع آخر، يفشل فك تشفيره (InvalidTag) حتى لو كان بيد المهاجم المفتاح الرئيسي.
- تدوير KEK (rewrap) لا يلمس النص المشفّر: يُعاد تغليف الـ DEK فقط.
"""
import base64
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE = 12


def load_kek(b64: str) -> bytes:
    k = base64.b64decode(b64)
    if len(k) != 32:
        raise ValueError("KEK must be 32 bytes (base64 of 32 random bytes)")
    return k


def _aad(tenant_id: str, kind: str, version: int, secret_ref: str) -> bytes:
    for part in (tenant_id, kind, secret_ref):
        if "|" in part:
            raise ValueError("'|' not allowed in AAD parts")
    return f"{tenant_id}|{kind}|{int(version)}|{secret_ref}".encode()


@dataclass(frozen=True)
class Sealed:
    ciphertext: bytes   # nonce || AESGCM(secret)
    dek_wrapped: bytes  # nonce || AESGCM(DEK) بالـ KEK


def seal(plaintext: bytes, kek: bytes, tenant_id: str, kind: str, version: int, secret_ref: str) -> Sealed:
    dek = AESGCM.generate_key(bit_length=256)
    n1, n2 = os.urandom(NONCE), os.urandom(NONCE)
    ct = n1 + AESGCM(dek).encrypt(n1, plaintext, _aad(tenant_id, kind, version, secret_ref))
    wrapped = n2 + AESGCM(kek).encrypt(n2, dek, b"dek|" + secret_ref.encode())
    return Sealed(ct, wrapped)


def open_(sealed: Sealed, kek: bytes, tenant_id: str, kind: str, version: int, secret_ref: str) -> bytes:
    """يرفع cryptography.exceptions.InvalidTag عند أي عبث أو عدم تطابق tenant/kind/version/ref."""
    dek = AESGCM(kek).decrypt(sealed.dek_wrapped[:NONCE], sealed.dek_wrapped[NONCE:], b"dek|" + secret_ref.encode())
    return AESGCM(dek).decrypt(sealed.ciphertext[:NONCE], sealed.ciphertext[NONCE:], _aad(tenant_id, kind, version, secret_ref))


def rewrap(sealed: Sealed, old_kek: bytes, new_kek: bytes, secret_ref: str) -> Sealed:
    dek = AESGCM(old_kek).decrypt(sealed.dek_wrapped[:NONCE], sealed.dek_wrapped[NONCE:], b"dek|" + secret_ref.encode())
    n = os.urandom(NONCE)
    return Sealed(sealed.ciphertext, n + AESGCM(new_kek).encrypt(n, dek, b"dek|" + secret_ref.encode()))
