#!/usr/bin/env python3
"""قراءة فقط: يجلب قائمة لغات تيك توك الرسمية (tool/language) عبر الـBroker ويطبع كود العربية والكردية. لا يكتب شي.
من /opt/central:  python3 ops/tt-languages-probe.py   (SA_SLUG=mohm افتراضياً)"""
import json, os, re, subprocess, sys
SLUG = os.environ.get("SA_SLUG", "mohm").strip()
if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", SLUG): sys.exit("bad SA_SLUG")
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
job = json.dumps({"host": BROKER_HOST, "ctx": ctx[0], "acct": acc[0]})
PY = r'''
import base64, hmac, hashlib, json, secrets, sys, time, urllib.request, urllib.error
job = json.loads(sys.stdin.read())
S = json.load(open("/s.json")); key = base64.b64decode(S["hmac_keys"]["n8n-runtime"]["key"])
body = json.dumps({"ctx": job["ctx"], "platform": "tiktok", "op": "tiktok.read_languages", "ad_account": job["acct"], "params": {}, "idempotency_key": "chk-" + secrets.token_hex(12)}).encode()
ts, n = int(time.time()), secrets.token_hex(12)
sig = hmac.new(key, ("%d.%s." % (ts, n)).encode() + body, hashlib.sha256).hexdigest()
req = urllib.request.Request("http://%s:8080/v1/call" % job["host"], data=body, method="POST", headers={"content-type": "application/json", "x-key-id": "n8n-runtime", "x-timestamp": str(ts), "x-nonce": n, "x-signature": sig})
try: out = urllib.request.urlopen(req, timeout=40).read()
except urllib.error.HTTPError as e: out = e.read() or b"{}"
except Exception as e: out = json.dumps({"ok": False, "error": {"message": str(e)[:200]}}).encode()
print(out.decode("utf-8", "replace"))
'''
r = subprocess.run(["docker", "run", "--rm", "-i", "--network", NET, "-v", SECRETS + ":/s.json:ro", "--entrypoint", "python", IMG, "-c", PY], input=job, capture_output=True, text=True)
if r.returncode or not r.stdout.strip(): sys.exit("call failed: " + (r.stderr or r.stdout)[-300:])
res = json.loads(r.stdout.strip().splitlines()[-1])
if not res.get("ok"): sys.exit("TikTok/Broker error: " + json.dumps(res.get("error"), ensure_ascii=False)[:400])
def items(d):
    if isinstance(d, list) and d and isinstance(d[0], dict): return d
    if isinstance(d, dict):
        for v in d.values():
            r = items(v)
            if r: return r
    return []
L = items(res.get("data")); print("عدد اللغات المتاحة: %d" % len(L))
hit = [x for x in L if re.search(r"(^|[^a-z])(ar|ku|ckb|kmr|sdh)([^a-z]|$)|arab|kurd|كرد|عرب", json.dumps(x, ensure_ascii=False), re.I)]
for x in hit: print("  ", json.dumps(x, ensure_ascii=False))
if not hit: print("ما لقيت عربية ولا كردية! أول 8:", json.dumps(L[:8], ensure_ascii=False))
else: print("الكردية موجودة" if any(re.search(r"kurd|ku\b|ckb|kmr|كرد", json.dumps(x, ensure_ascii=False), re.I) for x in hit) else "⚠️ ما أكو كردية بالقائمة (العربية فقط)")
