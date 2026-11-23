# -*- coding: utf-8 -*-
"""التخزين: كل شي عبر دوال SQL (SECURITY DEFINER) بمخطط competitor_radar؛ الخدمة ما تعرف tenant_id أبداً — تمرّر ctx الموقّع والقاعدة تفرض العزل.
MemoryStore للاختبارات (نفس العقد + عزل بين العملاء)."""
import json, time, uuid

PLATFORMS = ("tiktok", "instagram", "facebook", "snapchat", "other")


class StoreError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class MemoryStore:
    def __init__(self, ctx_map=None, enabled=True, max_competitors=20, clock=time.time):
        self.ctx_map, self.on, self.max, self.clock = ctx_map or {}, enabled, max_competitors, clock
        self.comp, self.samples, self.reports, self.plans, self.cache = {}, {}, {}, {}, {}

    def _t(self, ctx):
        t = self.ctx_map.get(ctx)
        if not t: raise StoreError("invalid_ctx")
        return t

    def config(self, ctx):
        self._t(ctx)
        return {"enabled": bool(self.on)}

    def competitor_add(self, ctx, platform, name, url):
        t = self._t(ctx)
        if platform not in PLATFORMS or not (1 <= len(name) <= 80) or (url is not None and len(url) > 500): raise StoreError("invalid")
        if sum(1 for c in self.comp.values() if c["t"] == t) >= self.max: raise StoreError("limit")
        cid = str(uuid.uuid4())
        self.comp[cid] = {"t": t, "id": cid, "platform": platform, "name": name, "url": url, "status": "new", "created_at": self.clock()}
        return {"id": cid}

    def _own(self, ctx, cid):
        t = self._t(ctx)
        c = self.comp.get(cid)
        return c if c and c["t"] == t else None

    def competitor_list(self, ctx):
        t = self._t(ctx)
        return [self._pub(c) for c in self.comp.values() if c["t"] == t]

    def _pub(self, c):
        r = self.reports.get(c["id"])
        return {"id": c["id"], "platform": c["platform"], "name": c["name"], "url": c["url"], "status": c["status"], "confidence": r["conf"] if r else None,
                "samples": len(self.samples.get(c["id"], {})), "analyzed_at": r["at"] if r else None}

    def competitor_get(self, ctx, cid):
        c = self._own(ctx, cid)
        return self._pub(c) if c else None

    def competitor_delete(self, ctx, cid):
        c = self._own(ctx, cid)
        if not c: return False
        for d in (self.comp, self.samples, self.reports, self.plans): d.pop(cid, None)
        return True

    def samples_add(self, ctx, cid, samples):
        if not self._own(ctx, cid): raise StoreError("not_found")
        d = self.samples.setdefault(cid, {})
        for s in samples[:30]: d.setdefault(s["id"], {"id": s["id"], "src": s["src"], "text": s["text"][:1500]})
        while len(d) > 60: d.pop(next(iter(d)))
        return len(d)

    def samples_list(self, ctx, cid):
        if not self._own(ctx, cid): raise StoreError("not_found")
        return list(self.samples.get(cid, {}).values())

    def report_save(self, ctx, cid, report, status, conf):
        c = self._own(ctx, cid)
        if not c: raise StoreError("not_found")
        if len(json.dumps(report)) > 60000: raise StoreError("too_large")
        c["status"] = status
        self.reports[cid] = {"report": report, "conf": conf, "at": self.clock()}
        return True

    def report_get(self, ctx, cid):
        if not self._own(ctx, cid): raise StoreError("not_found")
        r = self.reports.get(cid)
        return {"report": r["report"], "confidence": r["conf"], "age_s": int(self.clock() - r["at"])} if r else None

    def plan_save(self, ctx, cid, plan):
        if not self._own(ctx, cid): raise StoreError("not_found")
        self.plans[cid] = {"plan": plan, "at": self.clock()}
        return True

    def plan_get(self, ctx, cid):
        if not self._own(ctx, cid): raise StoreError("not_found")
        p = self.plans.get(cid)
        return {"plan": p["plan"], "age_s": int(self.clock() - p["at"])} if p else None

    def cache_get(self, ctx, key):
        t = self._t(ctx)
        v = self.cache.get((t, key))
        return v[1] if v and v[0] > self.clock() else None

    def cache_set(self, ctx, key, value, ttl):
        t = self._t(ctx)
        self.cache[(t, key)] = (self.clock() + ttl, value)
        return True


class PgStore:
    """connect: callable → اتصال DB-API (psycopg). كل استدعاء يفتح اتصالاً قصيراً (حاوية صغيرة، بدون pool)."""
    def __init__(self, connect):
        self.connect = connect

    def _call(self, fn, *args):
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT competitor_radar.%s(%s)" % (fn, ",".join(["%s"] * len(args))), [json.dumps(a) if isinstance(a, (dict, list)) else a for a in args])
                row = cur.fetchone()
            conn.commit()
            v = row[0] if row else None
            return json.loads(v) if isinstance(v, str) else v
        except Exception as e:
            try: conn.rollback()
            except Exception: pass
            st, msg = getattr(e, "sqlstate", None), str(e)
            if st == "28000" or "invalid_ctx" in msg: raise StoreError("invalid_ctx")
            for code in ("limit", "invalid", "not_found", "too_large"):
                if "radar_" + code in msg: raise StoreError(code)
            raise StoreError("db_error")
        finally:
            try: conn.close()
            except Exception: pass

    def config(self, ctx): return self._call("config", ctx)
    def competitor_add(self, ctx, platform, name, url): return self._call("competitor_add", ctx, platform, name, url)
    def competitor_list(self, ctx): return self._call("competitor_list", ctx) or []
    def competitor_get(self, ctx, cid): return self._call("competitor_get", ctx, cid)
    def competitor_delete(self, ctx, cid): return bool(self._call("competitor_delete", ctx, cid))
    def samples_add(self, ctx, cid, samples): return self._call("samples_add", ctx, cid, samples)
    def samples_list(self, ctx, cid): return self._call("samples_list", ctx, cid) or []
    def report_save(self, ctx, cid, report, status, conf): return bool(self._call("report_save", ctx, cid, report, status, conf))
    def report_get(self, ctx, cid): return self._call("report_get", ctx, cid)
    def plan_save(self, ctx, cid, plan): return bool(self._call("plan_save", ctx, cid, plan))
    def plan_get(self, ctx, cid): return self._call("plan_get", ctx, cid)
    def cache_get(self, ctx, key): return self._call("cache_get", ctx, key)
    def cache_set(self, ctx, key, value, ttl): return bool(self._call("cache_set", ctx, key, value, ttl))
