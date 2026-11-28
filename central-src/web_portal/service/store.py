# -*- coding: utf-8 -*-
"""طبقة قاعدة البيانات: كل شي عبر دوال web.* و api.list_* (SECURITY DEFINER). الدور web_rt ما يقدر يقرأ أي جدول مباشرة."""
import json

try:
    import psycopg
except Exception:   # الاختبارات تستعمل FakeStore
    psycopg = None


class Store:
    def __init__(self, dsn):
        self.dsn = dsn

    def _one(self, sql, args=()):
        with psycopg.connect(self.dsn, connect_timeout=5, autocommit=True) as c:
            r = c.execute(sql, args).fetchone()
            return r[0] if r else None

    def ping(self): return self._one("SELECT 1") == 1
    def invite_peek(self, h): return self._one("SELECT web.invite_peek(%s)", (h,))
    def invite_accept(self, h, pwd): return self._one("SELECT web.invite_accept(%s, %s)", (h, pwd))
    def login_lookup(self, email): return self._one("SELECT web.login_lookup(%s)", (email,))
    def login_fail(self, uid): self._one("SELECT web.login_fail(%s::uuid)", (uid,))
    def login_ok(self, uid): self._one("SELECT web.login_ok(%s::uuid)", (uid,))
    def session_create(self, uid, h, ttl_h): self._one("SELECT web.session_create(%s::uuid, %s, %s)", (uid, h, ttl_h))
    def session_get(self, h): return self._one("SELECT web.session_get(%s)", (h,))
    def session_delete(self, h): self._one("SELECT web.session_delete(%s)", (h,))

    def dashboard(self, uid):
        """(accounts, campaigns) لعميل المستخدم فقط (ctx قراءة فقط مدته 5 دقائق)، أو None لو ما كو ctx."""
        with psycopg.connect(self.dsn, connect_timeout=5, autocommit=True) as c:
            ctx = (c.execute("SELECT web.ctx(%s::uuid)", (uid,)).fetchone() or [None])[0]
            if not ctx: return None
            accts = [dict(zip(("platform", "external_id", "name", "currency", "status", "enabled"), r)) for r in c.execute("SELECT platform, external_id, name, currency, status, enabled FROM api.list_ad_accounts(%s)", (ctx,)).fetchall()]
            camps = []
            for (j,) in c.execute("SELECT to_jsonb(x) FROM api.list_campaigns(%s, NULL) x LIMIT 50", (ctx,)).fetchall():
                d = j if isinstance(j, dict) else json.loads(j)
                camps.append({"name": d.get("name") or d.get("campaign_name"), "external_id": d.get("external_id"), "status": d.get("status"), "created_at": d.get("created_at")})
            return accts, camps
