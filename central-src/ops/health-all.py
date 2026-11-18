#!/usr/bin/env python3
"""فحص شامل (قراءة فقط) لكل العملاء والأنظمة الإعلانية والمشتغلات. لا يكتب شي، لا يطبع أسرار.
من /opt/central:  python3 ops/health-all.py
كل قسم مستقل: إذا فشل قسم يطبع السبب ويكمل. بالنهاية قائمة «تحتاج إجراء»."""
import datetime as dt, glob, json, os, re, shutil, sqlite3, subprocess, sys, tempfile
PG = os.environ.get("PG_CONTAINER", "central-stg-pg"); N8N = os.environ.get("N8N_CONTAINER", "central-stg-n8n")
NOW = dt.datetime.utcnow(); TODO = []


def sh(args, timeout=120, inp=None):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, input=inp)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return 99, "", str(e)


def psql(sql, db="central"):
    rc, out, err = sh(["docker", "exec", "-i", PG, "psql", "-U", "postgres", "-d", db, "-At", "-F", "|", "-c", sql])
    if rc: return None, (err.strip() or "rc=%s" % rc)[-240:]
    return [l for l in out.splitlines() if l], None


def jrows(sql, db="central"):
    rows, err = psql(sql, db)
    if err: return None, err
    out = []
    for l in rows:
        try: out.append(json.loads(l))
        except Exception: pass
    return out, None


def head(t): print("\n" + "=" * 8 + " " + t + " " + "=" * 8)
def flag(msg): TODO.append(msg); print("⚠️ " + msg)


def parse_date(v):
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(v or ""))
    if not m: return None
    try: return dt.datetime.strptime(m.group(1), "%Y-%m-%d")
    except Exception: return None


def sched_minutes(nodes_json):
    """أقل فاصل (دقايق) لعُقد Schedule Trigger بالـworkflow، أو None إذا بدون جدولة/غير معروف."""
    try: nodes = json.loads(nodes_json) if isinstance(nodes_json, str) else (nodes_json or [])
    except Exception: return None
    best = None; has = False
    for n in nodes:
        if "scheduleTrigger" not in str(n.get("type", "")) and "cron" not in str(n.get("type", "")).lower(): continue
        has = True
        for r in (n.get("parameters", {}).get("rule", {}) or {}).get("interval", []) or []:
            f = r.get("field")
            m = (r.get("minutesInterval") or 1) if f == "minutes" else (r.get("hoursInterval") or 1) * 60 if f == "hours" else (r.get("daysInterval") or 1) * 1440 if f == "days" else (r.get("weeksInterval") or 1) * 10080 if f == "weeks" else None
            if f == "cronExpression": m = 60
            if m: best = m if best is None else min(best, m)
    return best if has else None


# 1) الحاويات
head("1) الحاويات")
rc, out, err = sh(["docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}"])
if rc: flag("docker ps فشل: " + err[-120:])
for l in out.splitlines():
    if "central" not in l: continue
    n, s = l.split("|", 1); ok = s.startswith("Up") and "unhealthy" not in s
    print(("✅ " if ok else "❌ ") + n + " — " + s)
    if not ok: flag("حاوية %s: %s" % (n, s))

# 2) مراقب الصحة الموجود (جاهزية + webhook لكل بوت)
head("2) مراقب الصحة (جاهزية + webhook)")
if os.path.exists("ops/health-watch.py"):
    rc, out, err = sh(["python3", "ops/health-watch.py", "--dry"], timeout=170)
    print("\n".join((out or err).strip().splitlines()[-40:]) or "(بدون خرج)")
else: print("ops/health-watch.py غير موجود هنا (شغّل من /opt/central)")

# 3) العملاء والاشتراكات
head("3) العملاء والاشتراكات")
T, err = jrows("select row_to_json(t) from core.tenants t order by 1")
SLUG = {}; FE = {}
if err or T is None: flag("core.tenants: " + str(err))
else:
    subs, serr = jrows("select row_to_json(s) from core.subscriptions s")
    ends = {}
    for s in subs or []:
        for k, v in s.items():
            if re.search(r"(end|expire|until|valid)", k, re.I):
                d = parse_date(v)
                if d and s.get("tenant_id"): ends[s["tenant_id"]] = max(ends.get(s["tenant_id"], d), d)
    if serr: print("ℹ️ الاشتراكات: " + serr[:120])
    for t in T:
        tid = str(t.get("tenant_id", "")); SLUG[tid] = t.get("slug", tid[:8])
        d = ends.get(tid) or next((parse_date(v) for k, v in t.items() if re.search(r"(end|expire|until)", k, re.I) and parse_date(v)), None)
        left = (d - NOW).days if d else None
        st = next((str(t[k]) for k in ("status", "state", "readiness_status", "readiness", "phase") if k in t), "?")
        feats = t.get("features") or {}
        FE[t.get("slug")] = feats if isinstance(feats, dict) else {}
        on = ",".join(sorted(k for k, v in feats.items() if v is True)) if isinstance(feats, dict) else str(feats)[:40]
        line = "%s | %s | %s | %s | ينتهي: %s%s" % (t.get("slug"), st, t.get("currency", "?"), on or "-", d.strftime("%Y-%m-%d") if d else "؟", (" (%d يوم)" % left) if left is not None else "")
        low = st.upper() in ("READY", "ACTIVE", "TESTING") or st == "?"
        bad = (left is not None and left < 3) or not low
        print(("⚠️ " if bad else "✅ ") + line)
        if left is not None and left < 3: TODO.append("%s: الاشتراك يقترب/انتهى (%d يوم)" % (t.get("slug"), left))
        if not low: TODO.append("%s: الحالة %s" % (t.get("slug"), st))

# 4) الحسابات الإعلانية المربوطة
head("4) الحسابات الإعلانية المربوطة")
A, err = psql("select t.slug, a.platform::text, count(*) filter (where a.enabled and a.unlinked_at is null), count(*) from core.ad_accounts a join core.tenants t on t.tenant_id=a.tenant_id group by 1,2 order by 1,2")
if err: flag("core.ad_accounts: " + err)
else:
    for l in A: s, p, en, tot = l.split("|"); print("%s %s | %s: فعّال %s من %s" % ("✅" if (en != "0" or FE.get(s, {}).get(p) is not True) else "⚠️", s, p, en, tot)); (en == "0" and FE.get(s, {}).get(p) is True) and TODO.append("%s: المنصة %s مفعّلة بالميزات بس لا حساب فعّال" % (s, p))

# 5) فحص حي لحسابات تيك توك (قراءة)
head("5) حسابات تيك توك (قراءة حية)")
if os.path.exists("ops/tt-accounts-check.py"):
    env = dict(os.environ, SA_SLUG="all"); r = subprocess.run(["python3", "ops/tt-accounts-check.py"], capture_output=True, text=True, env=env, timeout=170)
    o = (r.stdout or r.stderr).strip().splitlines(); print("\n".join(o[-30:]))
    for l in o:
        if l.startswith("⚠️"): TODO.append("تيك توك: " + l[:150])
else: print("ops/tt-accounts-check.py غير موجود")

# 6) حارس الإيقاف وتغطية الحملات
head("6) حارس الإيقاف (rule) وتغطية الحملات")
G, err = psql("select t.slug, coalesce(c.rule_state,'-'), (c.rule_stop is null), coalesce(c.rule_stop::text,'-'), count(*) from core.campaigns c join core.tenants t on t.tenant_id=c.tenant_id group by 1,2,3,4 order by 1,2")
if err: flag("core.campaigns: " + err)
else:
    for l in G:
        s, stt, nul, stop, n = l.split("|"); print("%s | %s | rule_stop=%s | %s حملة" % (s, stt, stop, n))
        if stt == "watching" and stop not in ("0.5", "0.50"): TODO.append("%s: %s حملة مراقبة بحد %s (المفروض 0.5)" % (s, n, stop))
NR, err = psql("select t.slug, c.platform::text, c.external_id, left(coalesce(c.name,''),24), c.created_at::date from core.campaigns c join core.tenants t on t.tenant_id=c.tenant_id where c.rule_stop is null and c.created_at > now() - interval '5 days' order by c.created_at desc limit 15")
if err: print("ℹ️ حملات بلا قاعدة: " + err[:150])
elif NR:
    print("حملات حديثة (آخر 5 أيام) بدون rule_stop = ما تنطفي تلقائياً:")
    for l in NR: print("  ⚠️ " + l)
    TODO.append("%d حملة حديثة بدون قاعدة إيقاف" % len(NR))
else: print("✅ كل الحملات الحديثة مسجلة بالحارس")

# 7) أخطاء الـBroker آخر 24 ساعة
head("7) استدعاءات الـBroker آخر 24 ساعة")
done = False
for db in ("vault", "central"):
    R, err = psql("select left(tenant_id::text,8), platform, endpoint, count(*), count(*) filter (where http_status >= 400 or error_code is not null) from vault.api_call_log where at > now() - interval '24 hours' group by 1,2,3 order by 5 desc, 4 desc limit 18", db)
    if err: continue
    done = True; pref = {k[:8]: v for k, v in SLUG.items()}
    for l in R:
        t, p, e, n, bad = l.split("|"); print("%s %s | %s | %s | %s استدعاء، %s فاشل" % ("⚠️" if int(bad) else "✅", pref.get(t, t), p, e, n, bad))
        if int(bad) >= 3: TODO.append("Broker %s %s: %s فاشل من %s" % (pref.get(t, t), e, bad, n))
    E, err = psql("select platform, endpoint, coalesce(error_code,'-'), coalesce(http_status::text,'-'), count(*) from vault.api_call_log where at > now() - interval '24 hours' and (error_code is not null or http_status >= 400) group by 1,2,3,4 order by 5 desc limit 10", db)
    if E: print("أكثر الأخطاء: (المنصة|العملية|الصنف|HTTP|العدد)"); [print("  " + x) for x in E]
    break
if not done: print("ℹ️ ما لقيت vault.api_call_log (جرّبت vault وcentral)")

# 8) n8n: workflows والمشتغلات
head("8) n8n: workflows والمشتغلات")
tmp = tempfile.mkdtemp(prefix="hall-")
try:
    ok = False
    for base in ("/home/node/.n8n/database.sqlite", "/root/.n8n/database.sqlite"):
        rc, _, _ = sh(["docker", "cp", N8N + ":" + base, tmp + "/db.sqlite"])
        if rc == 0:
            for ext in ("-wal", "-shm"): sh(["docker", "cp", N8N + ":" + base + ext, tmp + "/db.sqlite" + ext])
            ok = True; break
    if not ok: flag("ما قدرت أنسخ قاعدة n8n للقراءة (المسار)")
    else:
        con = sqlite3.connect("file:%s/db.sqlite?mode=ro" % tmp, uri=True); cur = con.cursor()
        since = (NOW - dt.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        W = cur.execute("select id, name, active, nodes from workflow_entity order by name").fetchall()
        for wid, name, active, nodes in W:
            if not active: continue
            last = cur.execute("select max(startedAt) from execution_entity where workflowId=? and status='success'", (wid,)).fetchone()[0]
            errs = cur.execute("select count(*) from execution_entity where workflowId=? and status in ('error','crashed') and startedAt > ?", (wid, since)).fetchone()[0]
            tot = cur.execute("select count(*) from execution_entity where workflowId=? and startedAt > ?", (wid, since)).fetchone()[0]
            d = parse_date(last); age = None
            try: age = (NOW - dt.datetime.strptime(str(last)[:19], "%Y-%m-%d %H:%M:%S")).total_seconds() / 60 if last else None
            except Exception: pass
            iv = sched_minutes(nodes); stale = bool(iv and (age is None or age > 3 * iv + 10))
            line = "%s | آخر نجاح: %s | 24س: %s تنفيذ، %s خطأ%s" % (name[:34], ("قبل %d د" % age) if age is not None else "لا يوجد", tot, errs, (" | ⏰ كل %d د" % iv) if iv else "")
            bad = errs > 0 or stale
            print(("⚠️ " if bad else "✅ ") + line)
            if stale: TODO.append("المشتغل «%s» ما نجح من %s (المفروض كل %d د)" % (name[:30], ("%d د" % age) if age is not None else "ما اشتغل", iv))
            elif errs > 0: TODO.append("workflow «%s»: %d تنفيذ فاشل آخر 24 ساعة" % (name[:30], errs))
        inactive = [n for _, n, a, _ in W if not a]
        if inactive: print("ℹ️ workflows غير فعّالة: " + ", ".join(x[:28] for x in inactive[:12]))
        con.close()
except Exception as e: flag("n8n sqlite: %s" % str(e)[:160])
finally: shutil.rmtree(tmp, ignore_errors=True)

# 9) علامات حماية الأموال
head("9) علامات التحديثات وحماية الأموال")
def cnt(path, pat):
    try: return open(path, encoding="utf-8").read().count(pat)
    except Exception: return None
for label, path, pat in (("p199 ميزانية بدون عملة", "n8n/wf_ingress.py", "p199"), ("p200 تأكيد >300$", "n8n/wf_ingress.py", "p200"), ("p204 قاعدة المبلغ", "n8n/wf_ingress.py", "p204"),
                         ("p205 ميتا/واتساب", "n8n/wf_ingress.py", "p205"), ("p201 قاعدة 0.30/0.40/0.50", "n8n/wf_ingress.py", "{0.3,0.4}"), ("سقف الـBroker", "broker/app/spark.py", "BROKER_MAX_LAUNCH_USD")):
    c = cnt(path, pat); print(("✅ " if c else "❌ ") + "%s: %s" % (label, "غير موجود" if c is None else c))
    if not c: TODO.append("علامة %s غير موجودة" % label)

head("الخلاصة")
if TODO:
    print("تحتاج إجراء (%d):" % len(TODO)); [print(" %d. %s" % (i + 1, x)) for i, x in enumerate(TODO)]
else: print("✅ ما لقيت شي يحتاج إجراء.")
print("\nملاحظة: هذا الفحص قراءة فقط ويثبت أن الحسابات تُقرأ والمشتغلات حيّة. ما يثبت أن رفع حملة جديدة ينجح (يصرف فلوس).")
