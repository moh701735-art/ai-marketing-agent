#!/usr/bin/env python3
"""اختبار حي صغير: ينشئ **حملة Smart+ متوقفة** (DISABLE بالـBroker، بدون مجموعة ولا إعلان، بدون صرف) اسمها PROBE-SMART-TOGGLE-DELETE-ME
بالحقل budget_auto_adjust_strategy=AUTO_BUDGET_INCREASE ثم يقرأها ويطبع القيمة المخزّنة (وhex لها). بعدها افتح الحملة بتيك توك Ads Manager
وصوّر قسم الميزانية (نسبة الزيادة وأقصى عدد مرات)، ثم احذفها. من /opt/central:
  SA_SLUG=mohm SA_ACCT=<advertiser_id> python3 ops/tt-smart-toggle-test.py        (SA_BUDGET اختياري؛ الافتراضي 10000 دينار أو 10 دولار)"""
import json, os, re, secrets, subprocess, sys

NAME = "PROBE-SMART-TOGGLE-DELETE-ME"
TOGGLE = "AUTO_BUDGET_INCREASE"


def default_budget(currency):
    return 10000 if str(currency or "").upper() == "IQD" else 10


def build_params(budget):
    return {"campaign_name": NAME, "budget": budget, "budget_mode": "BUDGET_MODE_DYNAMIC_DAILY", "budget_auto_adjust_strategy": TOGGLE}


def hexs(v):
    return str(v).encode().hex()


def summarize(read_item):
    """سطور وصف الحملة المقروءة (القيم المهمة + hex)."""
    keys = ("campaign_id", "campaign_name", "operation_status", "budget_mode", "budget", "budget_auto_adjust_strategy", "budget_optimize_on", "objective_type")
    out = ["  %s = %s" % (k, read_item.get(k)) for k in keys if k in read_item]
    out.append("  HEX budget_auto_adjust_strategy = %s" % hexs(read_item.get("budget_auto_adjust_strategy")))
    return out


PY = r'''
import base64, hmac, hashlib, json, secrets, sys, time, urllib.request, urllib.error
job = json.loads(sys.stdin.read())
S = json.load(open("/s.json")); key = base64.b64decode(S["hmac_keys"]["n8n-runtime"]["key"])
def call(op, params, idem):
    body = json.dumps({"ctx": job["ctx"], "platform": "tiktok", "op": op, "ad_account": job["acct"], "params": params, "idempotency_key": idem}).encode()
    ts, n = int(time.time()), secrets.token_hex(12)
    sig = hmac.new(key, ("%d.%s." % (ts, n)).encode() + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request("http://%s:8080/v1/call" % job["host"], data=body, method="POST", headers={"content-type": "application/json", "x-key-id": "n8n-runtime", "x-timestamp": str(ts), "x-nonce": n, "x-signature": sig})
    try: return json.loads(urllib.request.urlopen(req, timeout=60).read())
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read() or b"{}")
        except Exception: return {"ok": False, "error": {"message": "http %s" % e.code}}
    except Exception as e: return {"ok": False, "error": {"message": str(e)[:200]}}
create = call("tiktok.sp_create_campaign", job["params"], job["idem"])
res = {"create": create}
cid = str(((create.get("data") or {}).get("campaign_id") or (create.get("data") or {}).get("smart_plus_campaign_id") or "")) if create.get("ok") else ""
if cid: res["read"] = call("tiktok.sp_read_campaigns", {"campaign_ids": [cid], "page_size": 5}, "probe-" + secrets.token_hex(12))
print(json.dumps(res, ensure_ascii=False))
'''


def find_list(d):
    if isinstance(d, dict):
        if isinstance(d.get("list"), list): return d["list"]
        for v in d.values():
            r = find_list(v)
            if r is not None: return r
    return None


def main():
    slug, acct = os.environ.get("SA_SLUG", "").strip(), os.environ.get("SA_ACCT", "").strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", slug) or not re.fullmatch(r"[0-9]{6,25}", acct): sys.exit("set SA_SLUG=<slug> SA_ACCT=<advertiser_id>")
    pg = os.environ.get("PG_CONTAINER", "central-stg-pg"); net = os.environ.get("BROKER_NETWORK", "central-stg_backend"); img = os.environ.get("BROKER_IMAGE", "central-broker:prod")
    host = os.environ.get("BROKER_HOST", "central-stg-broker"); sec = os.environ.get("SA_SECRETS", os.path.abspath("deploy/.secrets/broker_secrets.json"))

    def psql(sql):
        r = subprocess.run(["docker", "exec", pg, "psql", "-U", "postgres", "-d", "central", "-At", "-F", "|", "-c", sql], capture_output=True, text=True)
        if r.returncode: sys.exit("psql failed: " + r.stderr.strip()[-200:])
        return [l for l in r.stdout.splitlines() if l]
    tid = psql("select tenant_id from core.tenants where slug='%s'" % slug)
    if not tid: sys.exit("tenant not found")
    ctx = psql("select ctx from api.job_contexts_for_status(ARRAY['TESTING','NEEDS_REVIEW','READY'],100) where tenant_id='%s'" % tid[0])
    if not ctx: sys.exit("no ctx")
    row = psql("select currency from api.list_ad_accounts('%s') where platform::text='tiktok' and enabled and external_id='%s'" % (ctx[0], acct))
    if not row: sys.exit("هذا الحساب مو من حسابات تيك توك المفعّلة لهذا العميل")
    budget = int(os.environ.get("SA_BUDGET") or default_budget(row[0]))
    params = build_params(budget)
    job = json.dumps({"ctx": ctx[0], "host": host, "acct": acct, "params": params, "idem": "probe-" + secrets.token_hex(12)})
    r = subprocess.run(["docker", "run", "--rm", "-i", "--network", net, "-v", sec + ":/s.json:ro", "--entrypoint", "python", img, "-c", PY], input=job, capture_output=True, text=True)
    if r.returncode or not r.stdout.strip(): sys.exit("call failed: " + (r.stderr or r.stdout)[-300:])
    res = json.loads(r.stdout.strip().splitlines()[-1]); cr = res["create"]
    print("حساب %s (%s) | ميزانية الاختبار %s" % (acct, row[0], budget))
    if not cr.get("ok"):
        print("❌ تيك توك/الـBroker رفض الإنشاء:", json.dumps(cr.get("error"), ensure_ascii=False)[:500]); return
    print("✅ انخلقت حملة Smart+ متوقفة: ", json.dumps(cr.get("data"), ensure_ascii=False)[:300])
    lst = find_list((res.get("read") or {}).get("data")) or []
    if lst: print("قراءة الحملة بعد الإنشاء:"); print("\n".join(summarize(lst[0])))
    else: print("⚠️ ما قدرت أقرأ الحملة بعد الإنشاء:", json.dumps((res.get("read") or {}).get("error"), ensure_ascii=False)[:300])
    print("\nالخطوة الجاية: افتح الحملة بتيك توك Ads Manager، صوّر قسم الميزانية (نسبة الزيادة وأقصى عدد مرات)، ثم احذفها: " + NAME)


if __name__ == "__main__":
    main()
