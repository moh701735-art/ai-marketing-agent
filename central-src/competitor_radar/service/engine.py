# -*- coding: utf-8 -*-
"""محرك الرادار: handle(op, ctx, params) → (status, {ok, data|error}). لا يمس أي حملة/منصة إعلانية؛ يقرأ فقط ما يعطيه المستخدم أو صفحات عامة.
ctx موقّع من النظام وتفرض القاعدة عزل العميل؛ المحرك ما يعرف tenant_id."""
import hashlib, urllib.parse
from . import analyze as A, confidence as C, extract as X, market as M, strategy as S
from .cache import RateLimiter, SingleFlight, TTLCache
from .llm import LLMUnavailable, NullLLM
from .safe_fetch import FetchError, Fetcher, check_url
from .store import PLATFORMS, StoreError

REPORT_TTL = 24 * 3600
MARKET_TTL = 6 * 3600
OPS = ("config", "competitor_add", "competitor_list", "competitor_get", "competitor_delete", "competitor_samples", "analyze", "report", "strategy", "market")


def _err(cls, msg="", st=200, **extra):
    return st, {"ok": False, "error": {"class": cls, "message": msg, **extra}}


def _ok(data):
    return 200, {"ok": True, "data": data}


def _id(v):
    return isinstance(v, str) and len(v) == 36 and all(c in "0123456789abcdef-" for c in v)


class Engine:
    def __init__(self, store, fetcher=None, llm=None, enabled=True, rate=None, clock=None):
        self.store, self.fetcher, self.llm, self.enabled = store, fetcher or Fetcher(), llm or NullLLM(), bool(enabled)
        self.rl_analyze = rate or RateLimiter(6, 600)
        self.rl_any = RateLimiter(60, 60)
        self.flight, self.mem = SingleFlight(), TTLCache()

    def _llm(self):
        return None if isinstance(self.llm, NullLLM) else self.llm

    def handle(self, op, ctx, p):
        if op not in OPS: return _err("unknown_op", st=404)
        if not isinstance(ctx, str) or not (8 <= len(ctx) <= 400) or not isinstance(p, dict): return _err("invalid_params", st=400)
        try:
            cfg = self.store.config(ctx)
            on = self.enabled and bool(cfg.get("enabled"))
            if op == "config": return _ok({"enabled": on})
            if not on: return _err("disabled", "ميزة رادار المنافسين غير مفعّلة.")
            if not self.rl_any.allow(hashlib.sha256(ctx.encode()).hexdigest()[:16]): return _err("rate_limited", "طلبات كثيرة، انتظر دقيقة.")
            return getattr(self, "op_" + op)(ctx, p)
        except StoreError as e:
            return _err(e.code, {"invalid_ctx": "جلسة غير صالحة.", "limit": "وصلت الحد الأقصى من المنافسين (20).", "not_found": "المنافس غير موجود.", "invalid": "مدخلات غير صالحة."}.get(e.code, "خطأ بالتخزين."), st=403 if e.code == "invalid_ctx" else 200)
        except Exception:
            return _err("internal", "خطأ داخلي بالرادار؛ لم يتأثر أي شي آخر.", st=500)

    # ---- منافسون ----
    def op_competitor_add(self, ctx, p):
        plat, name, url = p.get("platform"), " ".join(str(p.get("name") or "").split()), (p.get("url") or "").strip() or None
        if plat not in PLATFORMS or not (1 <= len(name) <= 80) or set(p) - {"platform", "name", "url"}: return _err("invalid_params", "المنصة أو الاسم غير صالح.")
        if url:
            try: check_url(url, self.fetcher.resolver, self.fetcher.allow_private)
            except FetchError as e: return _err("bad_url", "الرابط غير مقبول (%s)." % e.code)
        r = self.store.competitor_add(ctx, plat, name, url)
        return _ok(r)

    def op_competitor_list(self, ctx, p):
        return _ok({"competitors": self.store.competitor_list(ctx)})

    def op_competitor_get(self, ctx, p):
        if not _id(p.get("id")): return _err("invalid_params", st=400)
        c = self.store.competitor_get(ctx, p["id"])
        return _ok({"competitor": c}) if c else _err("not_found", "المنافس غير موجود.")

    def op_competitor_delete(self, ctx, p):
        if not _id(p.get("id")): return _err("invalid_params", st=400)
        return _ok({"deleted": self.store.competitor_delete(ctx, p["id"])})

    def op_competitor_samples(self, ctx, p):
        if not _id(p.get("id")) or not isinstance(p.get("text"), str) or len(p["text"]) > 30000: return _err("invalid_params", "النص طويل أو غير صالح.")
        s = X.from_pasted(p["text"])
        if not s: return _err("no_samples", "ما لقيت نص صالح (كل عينة ≥8 أحرف؛ افصل بين العينات بسطر فارغ).")
        return _ok({"added": len(s), "total": self.store.samples_add(ctx, p["id"], s)})

    # ---- التحليل ----
    def _collect(self, comp, stages):
        out = []
        url = comp.get("url")
        if not url: stages.append({"stage": "collect", "source": "url", "n": 0, "confidence": C.LOW, "note": "لا يوجد رابط (يعتمد على النص الملصوق)"}); return out
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        try:
            if comp["platform"] == "tiktok" and "tiktok.com" in host and "/video/" in url:
                r = self.fetcher.fetch("https://www.tiktok.com/oembed?url=" + urllib.parse.quote(url, safe=""), robots=False)   # واجهة رسمية عامة
                s, _ = X.from_oembed(r["text"]); out += s; stages.append({"stage": "collect", "source": "oembed", "n": len(s), "confidence": C.HIGH, "note": ""})
            else:
                r = self.fetcher.fetch(url)
                s, _ = X.from_html(r["text"]); out += s; stages.append({"stage": "collect", "source": "html_meta", "n": len(s), "confidence": C.HIGH if s else C.LOW, "note": ""})
        except FetchError as e:
            stages.append({"stage": "collect", "source": "public_fetch", "n": 0, "confidence": C.LOW, "note": "لا يوجد وصول (%s) — لم يُخمَّن أي شي" % e.code})
        return out

    def op_analyze(self, ctx, p):
        cid = p.get("id")
        if not _id(cid): return _err("invalid_params", st=400)
        comp = self.store.competitor_get(ctx, cid)
        if not comp: return _err("not_found", "المنافس غير موجود.")
        if not p.get("force"):
            r = self.store.report_get(ctx, cid)
            if r and r["age_s"] < REPORT_TTL: return _ok({"report": r["report"], "cached": True, "age_s": r["age_s"]})
        if not self.rl_analyze.allow(hashlib.sha256(ctx.encode()).hexdigest()[:16]): return _err("rate_limited", "حللت كثير مؤخراً؛ جرّب بعد قليل.")

        def work():
            stages = []
            fetched = self._collect(comp, stages)
            if fetched: self.store.samples_add(ctx, cid, fetched)
            samples = self.store.samples_list(ctx, cid)
            rep = A.analyze(comp, samples, self._llm())
            rep["stages"] = rep["stages"][:1] + stages + rep["stages"][1:]   # تفاصيل الجلب بعد مرحلة المصدر
            self.store.report_save(ctx, cid, rep, "done" if rep["status"] == "ok" else "insufficient", rep["overall_confidence"])
            return rep
        rep = self.flight.run("an:%s:%s" % (hashlib.sha256(ctx.encode()).hexdigest()[:12], cid), work)
        return _ok({"report": rep, "cached": False})

    def op_report(self, ctx, p):
        if not _id(p.get("id")): return _err("invalid_params", st=400)
        r = self.store.report_get(ctx, p["id"])
        return _ok({"report": r["report"], "age_s": r["age_s"]}) if r else _err("no_report", "ما في تقرير بعد. اضغط تحليل.")

    def op_strategy(self, ctx, p):
        cid = p.get("id")
        if not _id(cid): return _err("invalid_params", st=400)
        r = self.store.report_get(ctx, cid)
        if not r: return _err("no_report", "حلّل المنافس أولاً.")
        if not p.get("force"):
            c = self.store.plan_get(ctx, cid)
            if c and c["age_s"] < REPORT_TTL: return _ok({"plan": c["plan"], "cached": True})
        plan = S.build_strategy(r["report"], self.store.samples_list(ctx, cid), self._llm())
        if plan.get("status") == "ok": self.store.plan_save(ctx, cid, plan)
        return _ok({"plan": plan, "cached": False})

    def op_market(self, ctx, p):
        q = " ".join(str(p.get("query") or "").split())
        text = p.get("text") if isinstance(p.get("text"), str) else ""
        if len(text) > 30000: return _err("invalid_params", st=400)
        key = "mk:" + hashlib.sha256((q + "\n" + text).encode()).hexdigest()[:24]
        if not p.get("force"):
            hit = self.store.cache_get(ctx, key)
            if hit: return _ok({"market": hit, "cached": True})
        reports = []
        for c in self.store.competitor_list(ctx):
            r = self.store.report_get(ctx, c["id"]) if c.get("analyzed_at") else None
            if r: reports.append(r["report"])
        res = M.analyze_market(q, reports, X.from_pasted(text), self._llm())
        if res.get("status") == "ok": self.store.cache_set(ctx, key, res, MARKET_TTL)
        return _ok({"market": res, "cached": False})
