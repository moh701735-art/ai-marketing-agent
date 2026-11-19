#!/usr/bin/env python3
"""يفحص اهتمامات جمهور محفوظ عند تيك توك (tiktok.check_interests) ويطبع الصالح وغير الصالح. افتراضياً قراءة فقط.
من /opt/central:  SA_SLUG=mohm SA_NAME='جمهور 1' python3 ops/tt-check-saved.py          (فحص)
                  APPLY=1 SA_SLUG=mohm SA_NAME='جمهور 1' python3 ops/tt-check-saved.py  (يشيل فقط الاهتمامات اللي تيك توك قال حالتها غير EFFECTIVE، ويحتفظ بالباقي بنفس الترتيب)"""
import json, os, re, subprocess, sys
SLUG = os.environ.get("SA_SLUG", "mohm").strip(); NAME = os.environ.get("SA_NAME", "جمهور 1").strip()
if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", SLUG): sys.exit("bad SA_SLUG")
if not re.fullmatch(r"[^'\;]{1,40}", NAME): sys.exit("bad SA_NAME")
PG = os.environ.get("PG_CONTAINER", "central-stg-pg"); NET = os.environ.get("BROKER_NETWORK", "central-stg_backend"); IMG = os.environ.get("BROKER_IMAGE", "central-broker:prod")
BROKER_HOST = os.environ.get("BROKER_HOST", "central-stg-broker"); SECRETS = os.environ.get("SA_SECRETS", os.path.abspath("deploy/.secrets/broker_secrets.json"))
def psql(sql):
    r = subprocess.run(["docker", "exec", "-i", PG, "psql", "-U", "postgres", "-d", "central", "-At", "-F", "|", "-c", sql], capture_output=True, text=True)
    if r.returncode: sys.exit("psql failed: " + r.stderr.strip()[-200:])
    return [l for l in r.stdout.splitlines() if l]
t = psql("select tenant_id from core.tenants where slug='%s'" % SLUG)
if not t: sys.exit("tenant not found")
ctx = psql("select ctx from api.job_contexts_for_status(ARRAY['TESTING','NEEDS_REVIEW','READY'],100) where tenant_id='%s'" % t[0])
if not ctx: sys.exit("no context for tenant")
acc = psql("select external_id from api.list_ad_accounts('%s') where platform::text='tiktok' and enabled limit 1" % ctx[0])
if not acc: sys.exit("no tiktok account")
rows = psql("select interests::text from smart_audience.saved_list('%s') where name = '%s'" % (ctx[0], NAME))
if len(rows) != 1: sys.exit("saved audience «%s» found %d times (names: %s)" % (NAME, len(rows), "; ".join(psql("select name from smart_audience.saved_list('%s')" % ctx[0]))))
iv = json.loads(rows[0]); ids = [str(a[0]) for a in iv]; names = {str(a[0]): str(a[1]) for a in iv}
job = json.dumps({"host": BROKER_HOST, "ctx": ctx[0], "acct": acc[0], "ids": ids})
PY = r'''
import base64, hmac, hashlib, json, secrets, sys, time, urllib.request, urllib.error
job = json.loads(sys.stdin.read())
S = json.load(open("/s.json")); key = base64.b64decode(S["hmac_keys"]["n8n-runtime"]["key"])
res = []
for i in range(0, len(job["ids"]), 50):
    body = json.dumps({"ctx": job["ctx"], "platform": "tiktok", "op": "tiktok.check_interests", "ad_account": job["acct"], "params": {"keyword_ids": job["ids"][i:i + 50]}, "idempotency_key": "chk-" + secrets.token_hex(12)}).encode()
    ts, n = int(time.time()), secrets.token_hex(12)
    sig = hmac.new(key, ("%d.%s." % (ts, n)).encode() + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request("http://%s:8080/v1/call" % job["host"], data=body, method="POST", headers={"content-type": "application/json", "x-key-id": "n8n-runtime", "x-timestamp": str(ts), "x-nonce": n, "x-signature": sig})
    try: out = urllib.request.urlopen(req, timeout=40).read()
    except urllib.error.HTTPError as e: out = e.read() or b"{}"
    except Exception as e: out = json.dumps({"ok": False, "error": {"message": str(e)[:200]}}).encode()
    res.append(json.loads(out.decode("utf-8", "replace")))
print(json.dumps(res, ensure_ascii=False))
'''
r = subprocess.run(["docker", "run", "--rm", "-i", "--network", NET, "-v", SECRETS + ":/s.json:ro", "--entrypoint", "python", IMG, "-c", PY], input=job, capture_output=True, text=True)
if r.returncode or not r.stdout.strip(): sys.exit("call failed: " + (r.stderr or r.stdout)[-300:])
res = json.loads(r.stdout.strip().splitlines()[-1])
seen = {}; bad_calls = 0
for x in res:
    if not x.get("ok"): bad_calls += 1; print("Broker/TikTok error:", json.dumps(x.get("error"), ensure_ascii=False)[:300]); continue
    body = (x.get("data") or {}).get("data") or {}
    arr = body.get("keywords") or body.get("list") or body.get("interest_keywords")
    if isinstance(arr, list):
        for y in arr: seen[str((y or {}).get("keyword_id") or (y or {}).get("id") or "")] = str((y or {}).get("status") or "")
print("جمهور «%s» (%s): %d اهتمام محفوظ، رجع من تيك توك %d، طلبات فاشلة %d" % (NAME, SLUG, len(ids), len(seen), bad_calls))
good = [i for i in ids if seen.get(i) == "EFFECTIVE"]; other = [i for i in ids if i in seen and seen[i] != "EFFECTIVE"]; missing = [i for i in ids if i not in seen]
print("صالح (EFFECTIVE): %d | حالة غير صالحة: %d | ما رجع أبداً: %d" % (len(good), len(other), len(missing)))
for i in other + missing: print("  ✗ %s  %s  [%s]" % (i, names.get(i, "")[:40], seen.get(i) or "غير موجود"))

if os.environ.get("APPLY") == "1":
    if bad_calls or not seen: sys.exit("APPLY ملغى: فشل التحقق من تيك توك (طلبات فاشلة %d)، ما غيّرت شي" % bad_calls)
    if not other: print("ما فيه اهتمامات غير صالحة صريحة، ما غيّرت شي"); sys.exit(0)
    if not good: sys.exit("APPLY ملغى: ما بقي أي اهتمام صالح، ما غيّرت شي")
    arr = "array[" + ",".join("'%s'" % i for i in other if re.fullmatch(r"[0-9]{3,25}", i)) + "]::text[]"
    r = psql("update smart_audience.saved s set interests = (select jsonb_agg(e order by ord) from jsonb_array_elements(s.interests) with ordinality as x(e, ord) where (e->>0) <> all(%s)), updated_at = now() from core.tenants t where t.tenant_id = s.tenant_id and t.slug = '%s' and s.name = '%s' returning jsonb_array_length(s.interests)" % (arr, SLUG, NAME))
    print("تم: شلت %d اهتمام غير صالح، المتبقي بالجمهور: %s" % (len(other), r[0] if r else "؟"))
