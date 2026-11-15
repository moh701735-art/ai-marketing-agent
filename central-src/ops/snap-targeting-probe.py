#!/usr/bin/env python3
"""فحص حي (قراءة فقط) لبيانات استهداف سناب عبر الـBroker: الدول، محافظات العراق، المدن، الاهتمامات، اللغات. يطبع ملخصاً (عدد، مفاتيح، عيّنة) بدون أي توكن.
من /opt/central:  SA_SLUG=mohm python3 ops/snap-targeting-probe.py"""
import json, os, re, subprocess, sys
SLUG = os.environ.get("SA_SLUG", "").strip()
PG = os.environ.get("PG_CONTAINER", "central-stg-pg"); NET = os.environ.get("BROKER_NETWORK", "central-stg_backend"); IMG = os.environ.get("BROKER_IMAGE", "central-broker:prod")
BROKER_HOST = os.environ.get("BROKER_HOST", "central-stg-broker"); SECRETS = os.environ.get("SA_SECRETS", os.path.abspath("deploy/.secrets/broker_secrets.json"))
if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", SLUG): sys.exit("set SA_SLUG=<slug>")
def psql(sql):
    r = subprocess.run(["docker", "exec", "-i", PG, "psql", "-U", "postgres", "-d", "central", "-At", "-F", "|", "-c", sql], capture_output=True, text=True)
    if r.returncode: sys.exit("psql failed: " + r.stderr.strip()[-200:])
    return [l for l in r.stdout.splitlines() if l]
tid = psql("select tenant_id from core.tenants where slug='%s'" % SLUG)
if not tid: sys.exit("tenant not found")
ctx = psql("select ctx from api.job_contexts_for_status(ARRAY['TESTING','NEEDS_REVIEW','READY'],100) where tenant_id='%s'" % tid[0])
if not ctx: sys.exit("no ctx")
job = json.dumps({"ctx": ctx[0], "host": BROKER_HOST})
PY = r'''
import base64, hmac, hashlib, json, secrets, sys, time, urllib.request, urllib.error
job = json.loads(sys.stdin.read())
S = json.load(open("/s.json")); key = base64.b64decode(S["hmac_keys"]["n8n-runtime"]["key"])
def call(op, params=None):
    body = json.dumps({"ctx": job["ctx"], "platform": "snapchat", "op": op, "ad_account": "", "params": params or {}, "idempotency_key": "probe-" + secrets.token_hex(12)}).encode()
    ts, n = int(time.time()), secrets.token_hex(12)
    sig = hmac.new(key, ("%d.%s." % (ts, n)).encode() + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request("http://%s:8080/v1/call" % job["host"], data=body, method="POST", headers={"content-type": "application/json", "x-key-id": "n8n-runtime", "x-timestamp": str(ts), "x-nonce": n, "x-signature": sig})
    try: return json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read() or b"{}")
        except Exception: return {"ok": False, "error": {"message": "http %s" % e.code}}
    except Exception as e: return {"ok": False, "error": {"message": str(e)[:160]}}
def shape(d):
    if isinstance(d, dict):
        out = {}
        for k, v in d.items():
            if isinstance(v, list): out[k] = {"n": len(v), "sample": json.dumps(v[:3], ensure_ascii=False)[:420]}
            elif isinstance(v, (str, int, float, bool)) or v is None: out[k] = v if not isinstance(v, str) else v[:80]
            else: out[k] = "{...}"
        return out
    return str(d)[:300]
res = []
for label, op, prm in (("الدول", "snapchat.t_countries", {}), ("محافظات العراق (iq)", "snapchat.t_regions", {"oid": "iq"}), ("مدن العراق", "snapchat.t_metros", {"oid": "iq"}),
                       ("اهتمامات SCL", "snapchat.t_scls", {}), ("اهتمامات DLX", "snapchat.t_dlx", {}), ("اللغات", "snapchat.t_langs", {})):
    r = call(op, prm); res.append({"label": label, "op": op, "ok": r.get("ok"), "err": r.get("error"), "shape": shape(r.get("data")) if r.get("ok") else None})
print(json.dumps(res, ensure_ascii=False))
'''
r = subprocess.run(["docker", "run", "--rm", "-i", "--network", NET, "-v", SECRETS + ":/s.json:ro", "--entrypoint", "python", IMG, "-c", PY], input=job, capture_output=True, text=True)
if r.returncode or not r.stdout.strip(): sys.exit("call failed: " + (r.stderr or r.stdout)[-300:])
for x in json.loads(r.stdout.strip().splitlines()[-1]):
    print(("✅ " if x["ok"] else "❌ ") + x["label"] + "  [" + x["op"] + "]")
    if x["ok"]:
        for k, v in x["shape"].items() if isinstance(x["shape"], dict) else []: print("   ", k, "=", json.dumps(v, ensure_ascii=False)[:520])
    else: print("    خطأ:", json.dumps(x["err"], ensure_ascii=False)[:360])
    print("-" * 70)
