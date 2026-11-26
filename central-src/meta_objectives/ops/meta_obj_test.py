#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبار حي صغير لأهداف فيسبوك الجديدة (p286): ينشئ حملة **متوقفة** (PAUSED) بهدف وعي/زيارات/تفاعل من رابط منشور فيديو، ميزانية صغيرة (افتراضي 1 دولار ليوم)، ثم يطبع ما انخلق والحالة المقروءة.
لا يفعّل شيئاً. تحذف الحملة التجريبية بعدين من Ads Manager.  من /opt/central:
  MO_SLUG=omar-iyad MO_ACCT=act_123 MO_OBJ=traffic MO_POST=https://... MO_LINK=https://... python3 ops/meta-obj-test.py
  (MO_OBJ = awareness|traffic|engagement ؛ MO_LINK لازم للزيارات ؛ MO_BUDGET بالدولار، MO_DAYS)"""
import json, os, re, secrets, subprocess, sys

OBJS = ("awareness", "traffic", "engagement")
PY = r'''
import base64, hmac, hashlib, json, secrets, sys, time, urllib.request, urllib.error
job = json.loads(sys.stdin.read())
S = json.load(open("/s.json")); key = base64.b64decode(S["hmac_keys"]["n8n-runtime"]["key"])
body = json.dumps({"ctx": job["ctx"], "platform": "meta", "op": "meta.launch_whatsapp", "ad_account": job["acct"], "params": job["params"], "idempotency_key": job["idem"]}).encode()
ts, n = int(time.time()), secrets.token_hex(12)
sig = hmac.new(key, ("%d.%s." % (ts, n)).encode() + body, hashlib.sha256).hexdigest()
req = urllib.request.Request("http://%s:8080/v1/call" % job["host"], data=body, method="POST", headers={"content-type": "application/json", "x-key-id": "n8n-runtime", "x-timestamp": str(ts), "x-nonce": n, "x-signature": sig})
try: print(json.dumps(json.loads(urllib.request.urlopen(req, timeout=120).read()), ensure_ascii=False))
except urllib.error.HTTPError as e: print(e.read().decode("utf-8", "replace") or json.dumps({"ok": False, "error": {"message": "http %s" % e.code}}))
except Exception as e: print(json.dumps({"ok": False, "error": {"message": str(e)[:200]}}))
'''


def build_params(obj, post, link, budget, days, name):
    if obj not in OBJS: raise SystemExit("MO_OBJ must be one of " + ", ".join(OBJS))
    if not str(post).startswith("https://"): raise SystemExit("MO_POST (https link of a Facebook video post) is required")
    if obj == "traffic" and not str(link).startswith("https://"): raise SystemExit("MO_LINK (https website) is required for traffic")
    p = {"objective_key": obj, "post_url": post, "budget_usd": float(budget), "days": int(days), "name": name, "budget_mode": "total", "countries": ["IQ"]}
    if obj == "traffic": p["link_url"] = link
    if p["budget_usd"] > 5: raise SystemExit("test budget above 5 USD refused")
    return p


def fold(s): return re.sub(r"[^ -~]", "?", str(s))


def report(res):
    L = ["== Meta objective test (PAUSED, nothing activated) =="]
    if not res.get("ok"):
        e = res.get("error") or {}; L.append("FAILED class=%s message=%s" % (e.get("class"), fold(e.get("message"))[:400]))
        d = res.get("data") or {}
        if d: L.append("created before failure: " + fold(json.dumps(d))[:400])
        return "\n".join(L)
    d = res.get("data") or {}
    for k in ("objective", "campaign_objective", "optimization_goal", "currency", "budget_minor", "campaign_id", "adset_id", "creative_id", "ad_id", "status", "readback", "activation_error"):
        if k in d: L.append("%s = %s" % (k, fold(d[k])))
    L.append("Result metric for reports: %s (NOT messages)" % d.get("result_metric", "N/A"))
    L.append("Check in Meta Ads Manager: campaign must be PAUSED; delete it when done.")
    return "\n".join(L)


def main():
    slug = os.environ.get("MO_SLUG", "").strip(); acct = os.environ.get("MO_ACCT", "").strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", slug) or not re.fullmatch(r"act_[0-9]{5,25}", acct): sys.exit("set MO_SLUG=<slug> MO_ACCT=act_<digits>")
    params = build_params(os.environ.get("MO_OBJ", ""), os.environ.get("MO_POST", ""), os.environ.get("MO_LINK", ""), os.environ.get("MO_BUDGET", "1"), os.environ.get("MO_DAYS", "1"), "PROBE-META-%s-DELETE-ME" % os.environ.get("MO_OBJ", "x"))
    pg = os.environ.get("PG_CONTAINER", "central-stg-pg"); net = os.environ.get("BROKER_NETWORK", "central-stg_backend"); img = os.environ.get("BROKER_IMAGE", "central-broker:prod")
    host = os.environ.get("BROKER_HOST", "central-stg-broker"); sec = os.environ.get("SA_SECRETS", os.path.abspath("deploy/.secrets/broker_secrets.json"))

    def psql(sql):
        r = subprocess.run(["docker", "exec", pg, "psql", "-U", "postgres", "-d", "central", "-At", "-F", "|", "-c", sql], capture_output=True, text=True)
        if r.returncode: sys.exit("psql failed: " + r.stderr.strip()[-200:])
        return [l for l in r.stdout.splitlines() if l]
    tid = psql("select tenant_id from core.tenants where slug='%s'" % slug)
    ctx = psql("select ctx from api.job_contexts_for_status(ARRAY['TESTING','NEEDS_REVIEW','READY'],100) where tenant_id='%s'" % tid[0]) if tid else []
    if not ctx: sys.exit("tenant/ctx not found")
    job = json.dumps({"ctx": ctx[0], "host": host, "acct": acct, "params": params, "idem": "mo-" + secrets.token_hex(14)})
    r = subprocess.run(["docker", "run", "--rm", "-i", "--network", net, "-v", sec + ":/s.json:ro", "--entrypoint", "python", img, "-c", PY], input=job, capture_output=True, text=True)
    if r.returncode or not r.stdout.strip(): sys.exit("call failed: " + (r.stderr or r.stdout)[-300:])
    print(report(json.loads(r.stdout.strip().splitlines()[-1])))


if __name__ == "__main__":
    main()
