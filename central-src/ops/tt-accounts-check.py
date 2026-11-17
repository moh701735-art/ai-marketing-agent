#!/usr/bin/env python3
"""فحص حي (قراءة فقط) لحالة حسابات تيك توك الإعلانية عبر الـBroker (tiktok.read_advertiser): الحالة، العملة، الرصيد، وأي خطأ من تيك توك بنصه.
لا يكتب شي. من /opt/central:
  SA_SLUG=all python3 ops/tt-accounts-check.py                 ← كل العملاء: يطبع فقط الحسابات غير السليمة + ملخص
  SA_SLUG=mohm SA_NAME=بنين python3 ops/tt-accounts-check.py    ← حسابات عميل بالاسم (تفاصيل كاملة)"""
import json, os, re, subprocess, sys
SLUG = os.environ.get("SA_SLUG", "").strip(); NAME = os.environ.get("SA_NAME", "").strip(); ACCT = os.environ.get("SA_ACCT", "").strip()
PG = os.environ.get("PG_CONTAINER", "central-stg-pg"); NET = os.environ.get("BROKER_NETWORK", "central-stg_backend"); IMG = os.environ.get("BROKER_IMAGE", "central-broker:prod")
BROKER_HOST = os.environ.get("BROKER_HOST", "central-stg-broker"); SECRETS = os.environ.get("SA_SECRETS", os.path.abspath("deploy/.secrets/broker_secrets.json"))
if SLUG != "all" and not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", SLUG): sys.exit("set SA_SLUG=all | <slug> [SA_NAME=<جزء من الاسم>] [SA_ACCT=<id>]")
if ACCT and not re.fullmatch(r"[0-9]{6,25}", ACCT): sys.exit("bad SA_ACCT")
if NAME and not re.fullmatch(r"[^'\"\;\x00-\x1f]{1,40}", NAME): sys.exit("bad SA_NAME")


def psql(sql):
    r = subprocess.run(["docker", "exec", "-i", PG, "psql", "-U", "postgres", "-d", "central", "-At", "-F", "|", "-c", sql], capture_output=True, text=True)
    if r.returncode: sys.exit("psql failed: " + r.stderr.strip()[-200:])
    return [l for l in r.stdout.splitlines() if l]


tenants = psql("select slug, tenant_id from core.tenants order by slug") if SLUG == "all" else psql("select slug, tenant_id from core.tenants where slug='%s'" % SLUG)
if not tenants: sys.exit("tenant not found")
jobs = []
for row in tenants:
    slug, tid = row.split("|")
    ctx = psql("select ctx from api.job_contexts_for_status(ARRAY['TESTING','NEEDS_REVIEW','READY'],100) where tenant_id='%s'" % tid)
    if not ctx: continue
    q = "select external_id, coalesce(name,''), coalesce(currency,'') from api.list_ad_accounts('%s') where platform::text='tiktok' and enabled" % ctx[0]
    if NAME: q += " and name ilike '%%%s%%'" % NAME
    if ACCT: q += " and external_id='%s'" % ACCT
    accts = [a.split("|") for a in psql(q)]
    if accts: jobs.append({"slug": slug, "ctx": ctx[0], "accts": accts})
if not jobs: sys.exit("no matching tiktok ad accounts")
job = json.dumps({"host": BROKER_HOST, "jobs": jobs})
PY = r'''
import base64, hmac, hashlib, json, secrets, sys, time, urllib.request, urllib.error
job = json.loads(sys.stdin.read())
S = json.load(open("/s.json")); key = base64.b64decode(S["hmac_keys"]["n8n-runtime"]["key"])
def call(ctx, acct):
    body = json.dumps({"ctx": ctx, "platform": "tiktok", "op": "tiktok.read_advertiser", "ad_account": acct, "params": {}, "idempotency_key": "chk-" + secrets.token_hex(12)}).encode()
    ts, n = int(time.time()), secrets.token_hex(12)
    sig = hmac.new(key, ("%d.%s." % (ts, n)).encode() + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request("http://%s:8080/v1/call" % job["host"], data=body, method="POST", headers={"content-type": "application/json", "x-key-id": "n8n-runtime", "x-timestamp": str(ts), "x-nonce": n, "x-signature": sig})
    try: return json.loads(urllib.request.urlopen(req, timeout=40).read())
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read() or b"{}")
        except Exception: return {"ok": False, "error": {"message": "http %s" % e.code}}
    except Exception as e: return {"ok": False, "error": {"message": str(e)[:160]}}
def find(d):
    if isinstance(d, dict):
        if "advertiser_id" in d or "status" in d: return d
        for v in d.values():
            r = find(v)
            if r: return r
    if isinstance(d, list):
        for v in d:
            r = find(v)
            if r: return r
    return None
out = []
for j in job["jobs"]:
    for aid, name, cur in j["accts"]:
        r = call(j["ctx"], aid); info = find(r.get("data")) if r.get("ok") else None
        out.append({"slug": j["slug"], "id": aid, "name": name, "cur_db": cur, "ok": bool(r.get("ok")), "err": r.get("error"), "info": info})
print(json.dumps(out, ensure_ascii=False))
'''
r = subprocess.run(["docker", "run", "--rm", "-i", "--network", NET, "-v", SECRETS + ":/s.json:ro", "--entrypoint", "python", IMG, "-c", PY], input=job, capture_output=True, text=True)
if r.returncode or not r.stdout.strip(): sys.exit("call failed: " + (r.stderr or r.stdout)[-300:])
res = json.loads(r.stdout.strip().splitlines()[-1])
GOOD = ("STATUS_ENABLE", "ENABLE", "ACTIVE", "STATUS_ACTIVE")
bad = 0; detailed = bool(NAME or ACCT)
for x in res:
    i = x["info"] or {}; st = str(i.get("status", "")); cur = str(i.get("currency", "") or "")
    problem = (not x["ok"]) or (st and st.upper() not in GOOD) or (cur and x["cur_db"] and cur.upper() != x["cur_db"].upper())
    if problem: bad += 1
    if problem or detailed:
        line = "%s %s | %s | %s" % ("⚠️" if problem else "✅", x["slug"], x["id"], x["name"][:26])
        if x["ok"]: line += " | status=%s | cur=%s (DB:%s) | balance=%s | %s" % (st or "?", cur or "?", x["cur_db"] or "?", i.get("balance", "?"), str(i.get("timezone", ""))[:24])
        else: line += " | ERR: " + json.dumps(x["err"], ensure_ascii=False)[:300]
        print(line)
        if detailed and x["ok"]: print("   ", json.dumps({k: i[k] for k in list(i)[:14]}, ensure_ascii=False)[:420])
print("=" * 60); print("الحسابات المفحوصة: %d | فيها ملاحظة: %d" % (len(res), bad))
