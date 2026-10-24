"""توثيق n8n -> Broker: HMAC-SHA256 على (timestamp.nonce.body) مع نافذة زمنية ومنع إعادة الإرسال (replay)."""
import hashlib
import hmac
import time


def sign(key: bytes, body: bytes, ts: int, nonce: str) -> str:
    return hmac.new(key, f"{ts}.{nonce}.".encode() + body, hashlib.sha256).hexdigest()


class Verifier:
    def __init__(self, key: bytes, window: int = 60, clock=time.time):
        self.key, self.window, self.clock = key, window, clock
        self._seen: dict[str, float] = {}

    def verify(self, body: bytes, ts: int, nonce: str, signature: str) -> bool:
        now = self.clock()
        if abs(now - ts) > self.window or not nonce or len(nonce) < 16:
            return False
        if not hmac.compare_digest(sign(self.key, body, ts, nonce), signature):
            return False
        self._seen = {n: t for n, t in self._seen.items() if now - t <= self.window * 2}
        if nonce in self._seen:
            return False        # إعادة إرسال
        self._seen[nonce] = now
        return True
