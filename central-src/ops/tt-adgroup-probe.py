#!/usr/bin/env python3
"""فحص حي (قراءة فقط) لمجموعة إعلانية تيك توك عبر الـBroker (tiktok.read_adgroups): يطبع كل حقولها، ويبرز الحقول المرشّحة (ميزانية/سرعة/مزايدة/قواعد).
الهدف: نعرف أي حقل بالـAPI يمثّل الزر الأخضر بالميزانية. أنشئ حملتين متطابقتين بتيك توك (وحدة بالزر وحدة بدونه) وقارنهم:
  SA_SLUG=mohm SA_CAMP=<campaign_id بالزر> SA_CAMP2=<campaign_id بدون الزر> python3 ops/tt-adgroup-probe.py
(SA_ACCT=<advertiser_id> اختياري: بدونه يدوّر بكل حسابات تيك توك المفعّلة للعميل. SA_CAMP2 اختياري. لا يكتب أي شي ولا يغيّر أي حملة)"""
import json, os, re, subprocess, sys

CAND = re.compile(r"budget|pac|bid|rule|optim|auto|safe|dynamic|scal|boost|extra|increase|cost|smart|deliver|goal|target|cap|limit|step|times", re.I)
SKIP_DIFF = {"adgroup_id", "adgroup_name", "campaign_id", "campaign_name", "create_time", "modify_time", "schedule_start_time", "schedule_end_time", "operation_status", "secondary_status", "ad_ids"}


def short(v, n=160):
    if isinstance(v, str): return v if len(v) <= n else v[:n] + "…(%d)" % len(v)
    if isinstance(v, (dict, list)):
        s = json.dumps(v, ensure_ascii=False)
        return s if len(s) <= n else s[:n] + "…(%d)" % len(s)
    return repr(v)


def find_list(d):
    if isinstance(d, dict):
        if isinstance(d.get("list"), list): return d["list"]
        for v in d.values():
            r = find_list(v)
            if r is not None: return r
    return None


def spaced(k):
    """اسم الحقل بحروف مفصولة بمسافات حتى ترجمة المتصفح ما تغيّره."""
    return " ".join(str(k))


def render(ag, brief=False):
    """سطور وصف مجموعة إعلانية: المرشّحات أولاً (قيمة كاملة تقريباً) ثم باقي الحقول مختصرة."""
    keys = sorted(ag)
    cand = [k for k in keys if CAND.search(k)]
    out = ["-- حقول مرشّحة للزر (%d) --" % len(cand)] + ["  %s = %s" % (k, short(ag[k], 400)) for k in cand]
    out += ["-- أسماء المرشّحة بحروف مفصولة (ضد الترجمة) --"] + ["  " + spaced(k) for k in cand]
    if brief: return out + ["-- (باقي الحقول %d مخفية: SA_BRIEF) --" % (len(keys) - len(cand))]
    out += ["-- باقي الحقول (%d) --" % (len(keys) - len(cand))] + ["  %s = %s" % (k, short(ag[k], 100)) for k in keys if k not in cand]
    return out


def diff(a, b):
    """فروقات حقل-بحقل بين مجموعتين (يتجاهل الأسماء/المعرّفات/الأوقات). يرجع (فروقات القيم، حقول عند A فقط، حقول عند B فقط)."""
    ka, kb = set(a) - SKIP_DIFF, set(b) - SKIP_DIFF
    vals = [(k, a[k], b[k]) for k in sorted(ka & kb) if json.dumps(a[k], sort_keys=True) != json.dumps(b[k], sort_keys=True)]
    return vals, sorted(ka - kb), sorted(kb - ka)


def report(a, b=None, brief=False):
    out = ["=== مجموعة A: %s | الحملة %s ===" % (a.get("adgroup_name", "?"), a.get("campaign_id", "?"))] + render(a, brief)
    if b is not None:
        out += ["", "=== مجموعة B: %s | الحملة %s ===" % (b.get("adgroup_name", "?"), b.get("campaign_id", "?"))] + render(b, brief)
        vals, only_a, only_b = diff(a, b)
        out += ["", "=== الفروقات (A = بالزر ، B = بدونه) ==="]
        out += ["  %s: A=%s | B=%s" % (k, short(x, 120), short(y, 120)) for k, x, y in vals] or ["  (لا فروقات بالقيم)"]
        out += ["  حقول عند A فقط: " + (", ".join(only_a) or "لا شي"), "  حقول عند B فقط: " + (", ".join(only_b) or "لا شي")]
    return out


def pick(attempts):
    """من محاولات كل الحسابات لحملة وحدة: (الحساب، المجموعة الإعلانية الأولى) أو (None، سبب)."""
    last = "no accounts"
    for t in attempts:
        if t.get("ok"):
            lst = find_list(t.get("data")) or []
            if lst: return t["acct"], lst[0]
            last = "حساب %s: ما فيه مجموعة بهذي الحملة" % t["acct"]
        else:
            last = "حساب %s: %s" % (t["acct"], json.dumps(t.get("error"), ensure_ascii=False)[:160])
    return None, last


PY = r'''
import base64, hmac, hashlib, json, secrets, sys, time, urllib.request, urllib.error
job = json.loads(sys.stdin.read())
S = json.load(open("/s.json")); key = base64.b64decode(S["hmac_keys"]["n8n-runtime"]["key"])
def call(c):
    body = json.dumps({"ctx": job["ctx"], "platform": "tiktok", "op": c["op"], "ad_account": c["acct"], "params": c["params"], "idempotency_key": "probe-" + secrets.token_hex(12)}).encode()
    ts, n = int(time.time()), secrets.token_hex(12)
    sig = hmac.new(key, ("%d.%s." % (ts, n)).encode() + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request("http://%s:8080/v1/call" % job["host"], data=body, method="POST", headers={"content-type": "application/json", "x-key-id": "n8n-runtime", "x-timestamp": str(ts), "x-nonce": n, "x-signature": sig})
    try: return json.loads(urllib.request.urlopen(req, timeout=40).read())
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read() or b"{}")
        except Exception: return {"ok": False, "error": {"message": "http %s" % e.code}}
    except Exception as e: return {"ok": False, "error": {"message": str(e)[:160]}}
out = []
for c in job["calls"]:
    r = call(c); out.append({"acct": c["acct"], "op": c["op"], "ok": bool(r.get("ok")), "data": r.get("data"), "error": r.get("error")})
    if c.get("stop_on_hit") and r.get("ok") and (r.get("data") or {}).get("list"): break
print(json.dumps(out, ensure_ascii=False))
'''


def run_calls(env, ctx, calls):
    r = subprocess.run(["docker", "run", "--rm", "-i", "--network", env["net"], "-v", env["secrets"] + ":/s.json:ro", "--entrypoint", "python", env["img"], "-c", PY],
                       input=json.dumps({"host": env["host"], "ctx": ctx, "calls": calls}), capture_output=True, text=True)
    if r.returncode or not r.stdout.strip(): sys.exit("call failed: " + (r.stderr or r.stdout)[-300:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def first(res, op):
    for t in res:
        if t["op"] == op and t.get("ok"):
            lst = find_list(t.get("data")) or []
            if lst: return lst[0]
    return None


def main():
    slug, acct, c1, c2 = (os.environ.get(k, "").strip() for k in ("SA_SLUG", "SA_ACCT", "SA_CAMP", "SA_CAMP2"))
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", slug) or (acct and not re.fullmatch(r"[0-9]{6,25}", acct)) or not re.fullmatch(r"[0-9]{6,25}", c1) or (c2 and not re.fullmatch(r"[0-9]{6,25}", c2)):
        sys.exit("set SA_SLUG=<slug> SA_CAMP=<campaign_id> [SA_CAMP2=<campaign_id>] [SA_ACCT=<advertiser_id>]")
    pg = os.environ.get("PG_CONTAINER", "central-stg-pg")
    env = {"net": os.environ.get("BROKER_NETWORK", "central-stg_backend"), "img": os.environ.get("BROKER_IMAGE", "central-broker:prod"), "host": os.environ.get("BROKER_HOST", "central-stg-broker"),
           "secrets": os.environ.get("SA_SECRETS", os.path.abspath("deploy/.secrets/broker_secrets.json"))}

    def psql(sql):
        r = subprocess.run(["docker", "exec", pg, "psql", "-U", "postgres", "-d", "central", "-At", "-c", sql], capture_output=True, text=True)
        if r.returncode: sys.exit("psql failed: " + r.stderr.strip()[-200:])
        return [l for l in r.stdout.splitlines() if l]
    tid = psql("select tenant_id from core.tenants where slug='%s'" % slug)
    if not tid: sys.exit("tenant not found")
    ctx = psql("select ctx from api.job_contexts_for_status(ARRAY['TESTING','NEEDS_REVIEW','READY'],100) where tenant_id='%s'" % tid[0])
    if not ctx: sys.exit("no context for this tenant")
    accts = [acct] if acct else [l.strip() for l in psql("select external_id from api.list_ad_accounts('%s') where platform::text='tiktok' and enabled order by external_id" % ctx[0]) if l.strip()]
    if not accts: sys.exit("no enabled tiktok ad accounts for this tenant")
    sections = {"AG": [], "SPC": [], "SPA": []}; camps = [c for c in (c1, c2) if c]
    for camp in camps:
        res = run_calls(env, ctx[0], [{"acct": a, "op": "tiktok.read_adgroups", "params": {"campaign_ids": [camp], "page_size": 5}, "stop_on_hit": True} for a in accts])
        a, g = pick([t for t in res if t["op"] == "tiktok.read_adgroups"])
        if a is None: sys.exit("الحملة %s ما انلقت: %s (جرّبت %d حساب)" % (camp, g, len(res)))
        print("الحملة %s ← الحساب %s" % (camp, a)); sections["AG"].append(g)
        sp = run_calls(env, ctx[0], [{"acct": a, "op": op, "params": {"campaign_ids": [camp], "page_size": 5}} for op in ("tiktok.sp_read_campaigns", "tiktok.sp_read_adgroups")])
        for key, op in (("SPC", "tiktok.sp_read_campaigns"), ("SPA", "tiktok.sp_read_adgroups")):
            x = first(sp, op); sections[key].append(x)
            if x is None:
                e = [t for t in sp if t["op"] == op]
                print("  (%s: ما رجع شي — %s)" % (op, json.dumps((e[0].get("error") if e else None), ensure_ascii=False)[:200]))
    for key, title in (("AG", "المجموعة الإعلانية الكلاسيكية /adgroup/get"), ("SPC", "حملة Smart+ /smart_plus/campaign/get"), ("SPA", "مجموعة Smart+ /smart_plus/adgroup/get")):
        lst = sections[key]
        if lst and lst[0] is not None:
            print("\n######## %s ########" % title)
            print("\n".join(report(lst[0], lst[1] if len(lst) > 1 and lst[1] is not None else None, bool(os.environ.get("SA_BRIEF")))))


if __name__ == "__main__":
    main()
