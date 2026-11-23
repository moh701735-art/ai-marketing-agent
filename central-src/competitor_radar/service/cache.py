# -*- coding: utf-8 -*-
"""Cache بـTTL + منع الطلبات المتزامنة المتطابقة (single-flight) + حد معدّل لكل عميل. بالذاكرة (حاوية واحدة)؛ التخزين الدائم بالقاعدة منفصل."""
import threading, time


class TTLCache:
    def __init__(self, clock=time.monotonic, max_items=500):
        self.clock, self.max, self._d, self._lock = clock, max_items, {}, threading.Lock()

    def get(self, key):
        with self._lock:
            v = self._d.get(key)
            if v and v[0] > self.clock(): return v[1]
            self._d.pop(key, None)
            return None

    def set(self, key, value, ttl):
        with self._lock:
            if len(self._d) >= self.max:
                now = self.clock()
                for k in [k for k, v in self._d.items() if v[0] <= now] or [min(self._d, key=lambda k: self._d[k][0])]: self._d.pop(k, None)
            self._d[key] = (self.clock() + ttl, value)


class SingleFlight:
    """نفس المفتاح يشتغل مرة وحدة؛ الباقي ينتظر نفس النتيجة (أو نفس الاستثناء)"""
    def __init__(self):
        self._lock, self._calls = threading.Lock(), {}

    def run(self, key, fn):
        with self._lock:
            c = self._calls.get(key)
            leader = c is None
            if leader:
                c = self._calls[key] = {"ev": threading.Event(), "res": None, "err": None}
        if leader:
            try: c["res"] = fn()
            except BaseException as e: c["err"] = e
            finally:
                c["ev"].set()
                with self._lock: self._calls.pop(key, None)
        else:
            c["ev"].wait(60)
        if c["err"] is not None: raise c["err"]
        return c["res"]


class RateLimiter:
    def __init__(self, limit, window, clock=time.monotonic):
        self.limit, self.window, self.clock, self._h, self._lock = limit, window, clock, {}, threading.Lock()

    def allow(self, key):
        with self._lock:
            now = self.clock(); h = [t for t in self._h.get(key, []) if now - t < self.window]
            if len(h) >= self.limit:
                self._h[key] = h
                return False
            h.append(now); self._h[key] = h
            return True
