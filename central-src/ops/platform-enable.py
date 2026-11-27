#!/usr/bin/env python3
"""يرجّع منصة (meta/tiktok/snapchat) لعميل بعد ما أطفأها النظام تلقائياً لانتهاء التوكن (p293)، وبعد تجديد التوكن.
الاستعمال (من /opt/central):  python3 ops/platform-enable.py --slug zainab-forever --platform meta [--apply]
بدون --apply = فحص فقط (ما يكتب شي). يشترط اتصالاً واحداً غير ملغى للمنصة (expired أو active). عند --apply: يرجّعه active ويضبط features.<منصة>=true.
بعدها شغّل: bash deploy/run-readiness.sh مرتين. إذا التوكن لسه ميت، الـBroker يطفّي المنصة تلقائياً مرة ثانية والبوت يبقى شغّال لباقي المنصات.
لا يلمس أي سر ولا يبدّل التوكن (التجديد بأدوات rotate/relink). لا يرجّع جاهزية بنفسه."""
import argparse, os, re, subprocess, sys

PLATFORMS = ("meta", "tiktok", "snapchat")
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]{1,48}")


def psql(sql, v=None):
    cmd = ["docker", "exec", "-i", os.environ.get("PG_CONTAINER", "central-stg-pg"), "psql", "-U", "postgres", "-d", os.environ.get("TENANT_DB", "central"), "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1"]
    for k, val in (v or {}).items(): cmd += ["-v", "%s=%s" % (k, val)]
    r = subprocess.run(cmd, input=sql, capture_output=True, text=True)
    if r.returncode: raise RuntimeError((r.stderr or r.stdout)[-300:])
    return r.stdout.strip()


def run(slug, platform, apply_, db=psql, out=print):
    if not SLUG_RE.fullmatch(slug or ""): out("FAIL: slug غير صالح"); return 2
    if platform not in PLATFORMS: out("FAIL: المنصة لازم وحدة من: " + ", ".join(PLATFORMS)); return 2
    rows = db("SELECT c.connection_id || '|' || c.status || '|' || coalesce((t.features->>:'plat'), 'null') FROM core.platform_connections c JOIN core.tenants t USING (tenant_id) "
              "WHERE t.slug = :'slug' AND c.platform = :'plat'::core.platform AND c.status <> 'revoked' ORDER BY 1", {"slug": slug, "plat": platform})
    conns = [r for r in rows.splitlines() if r.strip()]
    if not conns: out("FAIL: ما فيه اتصال %s غير ملغى للعميل %s. اربطه أول (link-*)." % (platform, slug)); return 1
    if len(conns) != 1: out("FAIL: عند %s أكثر من اتصال %s غير ملغى (%d). ما أخمّن أي واحد؛ صلّح الوضع يدوياً أول:" % (slug, platform, len(conns))); [out("  " + c) for c in conns]; return 1
    cid, st, feat = conns[0].split("|")
    out("العميل %s | المنصة %s | الاتصال %s | حالته %s | ميزة المنصة الآن: %s" % (slug, platform, cid[:8], st, feat))
    if st not in ("expired", "active"): out("FAIL: حالة الاتصال غير متوقعة: " + st); return 1
    if st == "active" and feat == "true": out("الوضع سليم أصلاً: لا شي يتغيّر."); return 0
    if not apply_: out("فحص فقط. للتنفيذ أضف --apply (يرجّع الاتصال active ويفعّل ميزة %s)." % platform); return 0
    n = db("WITH u AS (UPDATE core.platform_connections SET status = 'active' WHERE connection_id = :'cid' AND status IN ('expired','active') RETURNING 1), "
           "f AS (UPDATE core.tenants SET features = coalesce(features, '{}'::jsonb) || jsonb_build_object(:'plat'::text, true) WHERE slug = :'slug' RETURNING 1) "
           "SELECT (SELECT count(*) FROM u) || '|' || (SELECT count(*) FROM f)", {"cid": cid, "slug": slug, "plat": platform})
    out("تم: اتصال/ميزات محدّثة = " + n + ". الآن: bash deploy/run-readiness.sh مرتين. إذا التوكن لسه ميت، المنصة تنطفي تلقائياً والبوت يبقى شغّال.")
    return 0


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--slug", required=True); ap.add_argument("--platform", required=True); ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(); sys.exit(run(a.slug, a.platform, a.apply))


if __name__ == "__main__":
    main()
