#!/usr/bin/env python3
"""فحص حي لسناب (قراءة فقط) عبر الـBroker بالتوكن المحفوظ: me، المنظمات، الحسابات الإعلانية، الحملات، وإحصاءات الحساب. لا يطبع أي توكن ولا ينشئ/يعدّل شي.
من /opt/central:  SA_SLUG=mohm python3 ops/snap-probe.py"""
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
if not ctx: sys.exit("no ctx (tenant status must be READY/TESTING/NEEDS_REVIEW)")
accts = psql("select external_id, coalesce(name,''), coalesce(currency,'') from api.list_ad_accounts('%s') where platform='snapchat' and enabled" % ctx[0])
if not accts: sys.exit("no snapchat ad account linked for this tenant (run ops/link-snapchat-web.py)")
job = json.dumps({"ctx": ctx[0], "host": BROKER_HOST, "accts": [a.split("|") for a in accts]})
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
out = []
def rec(name, r, summ=None):
    d = r.get("data")
    out.append({"op": name, "ok": r.get("ok"), "err": r.get("error"), "sum": summ(d) if (summ and d is not None and r.get("ok")) else None})
    return r
r = rec("snapchat.me", call("snapchat.me"), lambda d: {"id": str(((d or {}).get("me") or {}).get("id", ""))[:12] + "..."})
r = rec("snapchat.orgs", call("snapchat.orgs"), lambda d: [{"org": ((o or {}).get("organization") or {}).get("name"), "id": ((o or {}).get("organization") or {}).get("id")} for o in ((d or {}).get("organizations") or [])])
org = None
out_ad = {}
try: org = r["data"]["organizations"][0]["organization"]["id"]
except Exception: pass
if org:
    r_ad = call("snapchat.adaccounts", {"oid": org}); out_ad = (r_ad.get("data") or {}) if r_ad.get("ok") else {}
    rec("snapchat.adaccounts", r_ad, lambda d: [{"id": ((x or {}).get("adaccount") or {}).get("id"), "name": ((x or {}).get("adaccount") or {}).get("name"), "cur": ((x or {}).get("adaccount") or {}).get("currency"), "status": ((x or {}).get("adaccount") or {}).get("status")} for x in ((d or {}).get("adaccounts") or [])])
import datetime
try: import zoneinfo
except Exception: zoneinfo = None
tzname = None
try:
    for x in (out_ad.get("adaccounts") or []):
        ad = (x or {}).get("adaccount") or {}
        if ad.get("id") == job["accts"][0][0]: tzname = ad.get("timezone")
except Exception: pass
def isot(day_offset):
    try: tz = zoneinfo.ZoneInfo(tzname)
    except Exception: tz = datetime.timezone(datetime.timedelta(hours={"Asia/Baghdad": 3, "Asia/Riyadh": 3, "Asia/Dubai": 4}.get(tzname, 0)))
    d = (datetime.datetime.now(tz) + datetime.timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
    return d.isoformat(timespec="milliseconds")
for aid, name, cur in job["accts"]:
    camps = []
    r = rec("snapchat.campaigns [%s]" % (name or aid[:8]), call("snapchat.campaigns", {"oid": aid, "limit": 20}), lambda d: [{"name": ((c or {}).get("campaign") or {}).get("name"), "status": ((c or {}).get("campaign") or {}).get("status"), "id": ((c or {}).get("campaign") or {}).get("id")} for c in ((d or {}).get("campaigns") or [])][:20])
    try: camps = [((c or {}).get("campaign") or {}).get("id") for c in r["data"]["campaigns"]]
    except Exception: pass
    st, en = isot(-7), isot(1)
    variants = [("account TOTAL بدون وقت", "snapchat.account_stats", {"oid": aid}),
                ("account TOTAL مع وقت (آخر 7 أيام، توقيت الحساب %s)" % tzname, "snapchat.account_stats", {"oid": aid, "start_time": st, "end_time": en}),
                ("account DAY مع وقت", "snapchat.account_stats", {"oid": aid, "granularity": "DAY", "start_time": st, "end_time": en})]
    if camps: variants += [("campaign TOTAL مع وقت", "snapchat.stats", {"oid": camps[0], "start_time": st, "end_time": en})]
    for label, op, prm in variants:
        rec(label, call(op, prm), lambda d: json.dumps(d, ensure_ascii=False)[:500])
print(json.dumps(out, ensure_ascii=False))
'''
r = subprocess.run(["docker", "run", "--rm", "-i", "--network", NET, "-v", SECRETS + ":/s.json:ro", "--entrypoint", "python", IMG, "-c", PY], input=job, capture_output=True, text=True)
if r.returncode or not r.stdout.strip(): sys.exit("call failed: " + (r.stderr or r.stdout)[-300:])
res = json.loads(r.stdout.strip().splitlines()[-1])
print("حسابات سناب المربوطة:", ", ".join("%s (%s)" % (a.split("|")[1] or a.split("|")[0][:8], a.split("|")[2] or "?") for a in accts)); print("=" * 70)
for x in res:
    print(("✅ " if x["ok"] else "❌ ") + x["op"])
    if x["ok"]: print("   ", json.dumps(x["sum"], ensure_ascii=False)[:600])
    else: print("    خطأ:", json.dumps(x["err"], ensure_ascii=False)[:400])
    print("-" * 70)
print("ملاحظة: مبالغ سناب تُرجَع بوحدات ميكرو (÷1,000,000). هذا فحص قراءة فقط.")
