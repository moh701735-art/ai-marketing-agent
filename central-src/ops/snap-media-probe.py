#!/usr/bin/env python3
"""ينشئ **حملة سناب تجريبية متوقفة كاملة** (حملة + مجموعة + Creative + إعلان) بفيديو موجود مسبقاً بحسابك (media READY) عبر `snapchat.launch_draft`، للتأكد من حقول سناب قبل ربط تلغرام. ما فيها صرف (متوقفة).
من /opt/central:  SA_SLUG=mohm SA_MEDIA=<media_id> [SA_OBJ=trf|vid] [SA_PROFILE=<profile_id>] [SA_MIN=21 SA_MAX=34] python3 ops/snap-media-probe.py
بعد الفحص احذف الحملة «PROBE-AD-DELETE-ME» من Snap Ads Manager."""
import json, os, re, secrets, subprocess, sys
SLUG = os.environ.get("SA_SLUG", "").strip(); ACCT = os.environ.get("SA_ACCT", "").strip()
PG = os.environ.get("PG_CONTAINER", "central-stg-pg"); NET = os.environ.get("BROKER_NETWORK", "central-stg_backend"); IMG = os.environ.get("BROKER_IMAGE", "central-broker:prod")
BROKER_HOST = os.environ.get("BROKER_HOST", "central-stg-broker"); SECRETS = os.environ.get("SA_SECRETS", os.path.abspath("deploy/.secrets/broker_secrets.json"))
MEDIA = os.environ.get("SA_MEDIA", "").strip(); OBJ = os.environ.get("SA_OBJ", "trf").strip(); PROFILE = os.environ.get("SA_PROFILE", "").strip()
if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", SLUG): sys.exit("set SA_SLUG=<slug>")
if not re.fullmatch(r"[0-9a-fA-F\-]{8,64}", MEDIA): sys.exit("set SA_MEDIA=<media_id READY>")
if OBJ not in ("trf", "vid"): sys.exit("SA_OBJ = trf | vid")
def psql(sql):
    r = subprocess.run(["docker", "exec", "-i", PG, "psql", "-U", "postgres", "-d", "central", "-At", "-F", "|", "-c", sql], capture_output=True, text=True)
    if r.returncode: sys.exit("psql failed: " + r.stderr.strip()[-200:])
    return [l for l in r.stdout.splitlines() if l]
tid = psql("select tenant_id from core.tenants where slug='%s'" % SLUG)
if not tid: sys.exit("tenant not found")
ctx = psql("select ctx from api.job_contexts_for_status(ARRAY['TESTING','NEEDS_REVIEW','READY'],100) where tenant_id='%s'" % tid[0])
if not ctx: sys.exit("no ctx")
if not ACCT:
    a = psql("select external_id from api.list_ad_accounts('%s') where platform::text='snapchat' and enabled limit 1" % ctx[0])
    if not a: sys.exit("no snapchat ad account for this tenant")
    ACCT = a[0]
if not re.fullmatch(r"[0-9a-fA-F\-]{8,64}", ACCT): sys.exit("bad account id")
params = {"account_id": ACCT, "name": "PROBE-AD-DELETE-ME", "objective": OBJ, "budget": 5, "days": 1, "regions": [], "ages": ["18-20", "21-24", "25-34"], "gender": "a", "lang": "ar", "interests": [], "media_id": MEDIA, "headline": "تجربة", "brand_name": "Test", "cta": "MORE"}
if OBJ == "trf": params["landing_url"] = "https://t.me/example"
if PROFILE: params["profile_id"] = PROFILE
if os.environ.get("SA_MIN"): params["ages"] = []; params["min_age"] = int(os.environ["SA_MIN"])
if os.environ.get("SA_MAX"): params["max_age"] = int(os.environ["SA_MAX"])
job = json.dumps({"ctx": ctx[0], "host": BROKER_HOST, "params": params, "idem": "probe-" + secrets.token_hex(12)})
PY = r'''
import base64, hmac, hashlib, json, secrets, sys, time, urllib.request, urllib.error
job = json.loads(sys.stdin.read())
S = json.load(open("/s.json")); key = base64.b64decode(S["hmac_keys"]["n8n-runtime"]["key"])
body = json.dumps({"ctx": job["ctx"], "platform": "snapchat", "op": "snapchat.launch_draft", "ad_account": "", "params": job["params"], "idempotency_key": job["idem"]}).encode()
ts, n = int(time.time()), secrets.token_hex(12)
sig = hmac.new(key, ("%d.%s." % (ts, n)).encode() + body, hashlib.sha256).hexdigest()
req = urllib.request.Request("http://%s:8080/v1/call" % job["host"], data=body, method="POST", headers={"content-type": "application/json", "x-key-id": "n8n-runtime", "x-timestamp": str(ts), "x-nonce": n, "x-signature": sig})
try: print(urllib.request.urlopen(req, timeout=120).read().decode())
except urllib.error.HTTPError as e: print(e.read().decode() or json.dumps({"http": e.code}))
'''
r = subprocess.run(["docker", "run", "--rm", "-i", "--network", NET, "-v", SECRETS + ":/s.json:ro", "--entrypoint", "python", IMG, "-c", PY], input=job, capture_output=True, text=True)
if r.returncode or not r.stdout.strip(): sys.exit("call failed: " + (r.stderr or r.stdout)[-300:])
try: res = json.loads(r.stdout.strip().splitlines()[-1])
except Exception: sys.exit("bad reply: " + r.stdout[-300:])
d = res.get("data") or {}
print("حساب سناب:", ACCT)
if res.get("ok"):
    print("✅ انرفعت مسودة متوقفة: campaign_id=%s | adsquad_id=%s | الحالة=%s | العملة=%s | الإعلان=%s" % (d.get("campaign_id"), d.get("adsquad_id"), d.get("status"), d.get("currency"), d.get("creative")))
    print("   media=%s | profile=%s | creative=%s | ad=%s | stage=%s" % (d.get("media_id"), d.get("profile_id"), d.get("creative_id"), d.get("ad_id"), d.get("stage")))
    print("   من", d.get("start_time"), "إلى", d.get("end_time")); print("⚠️ احذف الحملة PROBE-AD-DELETE-ME من Snap Ads Manager.")
else:
    print("❌ فشل بمرحلة:", d.get("stage")); print("   الخطأ:", json.dumps(res.get("error"), ensure_ascii=False)[:500])
    for k in ("campaign_id", "adsquad_id", "media_id", "profile_id", "creative_id", "ad_id"):
        if d.get(k): print("   %s=%s" % (k, d[k]))
    if d.get("campaign_id"): print("   ⚠️ الحملة انعملت (متوقفة)، احذفها من Ads Manager.")
