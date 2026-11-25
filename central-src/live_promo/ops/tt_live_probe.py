#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""المرحلة A لـ«ترويج البث المباشر» (قراءة فقط، لا حملة/صرف/تعديل): هل حساب تيك توك يعرض قدرات LIVE؟ ماذا يسمّي تيك توك الأهداف عندنا؟ أي عمليات بالكتالوج لها علاقة؟
عمليات Broker المسموحة فقط ما يصفه الكتالوج الحي بأنه غير-كتابة (write=False) — يُفرض بالكود. الإخراج ASCII، غير المعروف = N/A/UNKNOWN، لا نخترع أي قيمة.
  SA_SLUG=mohm SA_ACCT=7593807340588253185 python3 ops/tt-live-probe.py"""
import importlib.util, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
NA = "N/A"
RX_OPS = r"identit|live|communit|promot|video_info|item|creative|boost|spark|tiktok_account|business_acc"
CAP_KEY = re.compile(r"^(can_.*|is_.*|identity_type|identity_id|status|identity_authorized.*|.*live.*|.*stream.*|.*ads.*|.*promot.*)$", re.I)
INTRO = r'''
import json, sys, re, os
for root in ("/app", "/srv", "/opt", "/"): sys.path.insert(0, root)
try: from app import catalog
except Exception:
    try: from broker.app import catalog
    except Exception as e: print(json.dumps({"error": "catalog import failed: %s" % type(e).__name__})); sys.exit(0)
rx = re.compile(os.environ.get("TL_RX"), re.I); out = {}
for n, o in sorted(catalog.OPS.items()):
    if n.startswith("tiktok.") and rx.search(n):
        ps = getattr(o, "params", {}) or {}
        out[n] = {"write": bool(getattr(o, "write", False)), "path": getattr(o, "path", None), "params": {k: (getattr(v, "kind", str(v)) + ("*" if getattr(v, "required", False) else "")) for k, v in ps.items()}}
print(json.dumps(out))
'''


def fold(s): return re.sub(r"[^ -~]", "?", str(s))


def sh(cmd, inp=None): return subprocess.run(cmd, input=inp, capture_output=True, text=True)


def introspect(img, runner=sh):
    """الكتالوج الحي داخل صورة الـBroker بلا شبكة. → {op: {write, path, params}} أو {'error':…}"""
    try: r = runner(["docker", "run", "--rm", "--network", "none", "-e", "TL_RX=" + RX_OPS, "--entrypoint", "python", img, "-c", INTRO])
    except OSError as e: return {"error": "docker unavailable (%s)" % type(e).__name__}
    try: return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception: return {"error": "introspection failed: " + (r.stderr or r.stdout or "").strip()[-160:]}


def guard(specs, calls):
    """يسمح فقط بعمليات يقول الكتالوج الحي إنها write=False (أو tiktok.read_* المعروفة). غيرها = رفض قبل أي استدعاء."""
    for c in calls:
        op = c["op"]; s = specs.get(op)
        if s is not None and not s.get("write"): continue
        if s is None and re.match(r"^tiktok\.read_[a-z_]+$", op): continue
        raise SystemExit("REFUSED: not a read-only op: " + op)
    return calls


def load_wad():
    p = os.environ.get("WA_DIAG_PATH", os.path.join(HERE, "wa-diagnose.py"))
    if not os.path.exists(p): raise SystemExit("missing ops/wa-diagnose.py (p263) - install it first")
    s = importlib.util.spec_from_file_location("wad", p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m


def identity_ops(specs):
    return sorted(n for n, s in specs.items() if "identit" in n and not s.get("write"))


def safe_identity(row):
    """مفاتيح القدرات/الحالة فقط + اسم مقتطع؛ لا توكنات"""
    out = {}
    for k, v in row.items():
        if re.search(r"token|secret|key|password", k, re.I): continue
        if k == "display_name": out[k] = fold(str(v))[:18]
        elif CAP_KEY.match(k) and not isinstance(v, (dict, list)): out[k] = v
    return out


def gather(wad, bk, specs):
    R = {"advertiser": {}, "identities": [], "id_keys": set(), "id_errors": [], "objectives": {}, "errors": [], "id_op": None}
    a = bk([{"label": "adv", "op": "tiktok.read_advertiser", "params": {}}])[0]
    if a["ok"]: R["advertiser"] = (wad.find_list(a.get("data")) or [{}])[0]
    else: R["errors"].append("read_advertiser: " + fold(wad.errtxt(a.get("error")))[:160])
    c = bk([{"label": "camps", "op": "tiktok.read_campaigns", "params": {"page": 1, "page_size": 100}}])[0]
    if c["ok"]:
        for x in wad.find_list(c.get("data")) or []:
            k = str(x.get("objective_type") or NA) + " / " + str(x.get("campaign_type") or NA); R["objectives"][k] = R["objectives"].get(k, 0) + 1
    else: R["errors"].append("read_campaigns: " + fold(wad.errtxt(c.get("error")))[:160])
    ops = identity_ops(specs)
    R["id_op"] = ops[0] if ops else None
    if R["id_op"]:
        spec = specs[R["id_op"]]["params"]
        variants = [{}]
        if any(k.startswith("identity_type") for k in spec): variants += [{"identity_type": t} for t in ("AUTH_CODE", "TT_USER", "BC_AUTH_TT")]
        for v in variants:
            v = {k: x for k, x in v.items() if k in spec}
            r = bk([{"label": "id", "op": R["id_op"], "params": v}])[0]
            if r["ok"]:
                for row in wad.find_list(r.get("data")) or []:
                    R["identities"].append(safe_identity(row)); R["id_keys"] |= {k for k in row if not re.search(r"token|secret|key|password", k, re.I)}
            else: R["id_errors"].append("%s: %s" % (json.dumps(v), fold(wad.errtxt(r.get("error")))[:140]))
    return R


def report(R, specs):
    L = ["== TikTok LIVE probe, phase A (read-only; nothing created, no spend; DB/Broker/n8n untouched) =="]
    adv = R["advertiser"]; L.append("ACCOUNT: name=%s status=%s currency=%s country=%s" % (fold(adv.get("name", NA))[:30], fold(adv.get("status", NA)), fold(adv.get("currency", NA)), fold(adv.get("country", NA))))
    for e in R["errors"]: L.append("  read error: " + e)
    L.append("\nCATALOG OPS related to identity/live/community/promote (%d):" % len([n for n in specs if n != "error"]))
    if "error" in specs: L.append("  " + fold(specs["error"]))
    for n, s in sorted((k, v) for k, v in specs.items() if k != "error"): L.append("  %s %s params=%s" % ("W" if s["write"] else "r", n, ",".join(sorted(s["params"])) or "-"))
    L.append("\nOBJECTIVES this account already uses (objective_type / campaign_type: count):")
    for k, n in sorted(R["objectives"].items()): L.append("  %s: %d" % (fold(k), n))
    L.append("\nIDENTITIES via %s (%d rows):" % (R["id_op"] or NA, len(R["identities"])))
    for i in R["identities"][:12]: L.append("  " + fold(json.dumps(i, ensure_ascii=False))[:300])
    for e in R["id_errors"][:4]: L.append("  identity read error: " + e)
    live = sorted(k for k in R["id_keys"] if re.search(r"live|stream", k, re.I))
    L += ["", "======== FINAL BLOCK (ASCII) ========",
          "IDENTITY OP FOUND: %s" % (R["id_op"] or "NO (no identity read op in catalog)"),
          "IDENTITY FIELD NAMES (all, non-secret): %s" % (", ".join(sorted(R["id_keys"])) or NA),
          "LIVE-RELATED IDENTITY FIELDS: %s" % (", ".join(live) or "NONE FOUND (field names only; absence does not prove LIVE ads are unavailable)"),
          "OBJECTIVE NAMES SEEN: %s" % (", ".join(sorted(R["objectives"])) or NA),
          "LIVE-RELATED CATALOG OPS: %s" % (", ".join(n for n in sorted(specs) if n != "error" and re.search(r"live|communit|boost", n)) or "NONE (a LIVE promotion op does not exist yet)"),
          "IRAQ AVAILABILITY OF LIVE ADS: UNKNOWN (no read endpoint says so; needs phase B: one PAUSED probe campaign, zero spend, owner approval)",
          "API VALUES for LIVE objective / promotion type / ad format: N/A (not verified; will be read from TikTok's own error lists in phase B)",
          "NO CAMPAIGN CREATED. Ops used: only catalog write=False ops (code-enforced)."]
    return "\n".join(L)


def main():
    slug = os.environ.get("SA_SLUG", "mohm").strip(); acct = os.environ.get("SA_ACCT", "7593807340588253185").strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,48}", slug) or not re.fullmatch(r"[0-9]{6,25}", acct): sys.exit("bad SA_SLUG / SA_ACCT")
    wad = load_wad(); env = wad.Env(); specs = introspect(env.img)
    tid = wad.psql(env, "select tenant_id from core.tenants where slug='%s'" % slug)
    ctxs = wad.psql(env, "select ctx from api.job_contexts_for_status(ARRAY['TESTING','NEEDS_REVIEW','READY'],100) where tenant_id='%s'" % tid[0]) if tid else []
    if not ctxs: sys.exit("tenant/ctx not found")
    R = gather(wad, lambda calls: wad.broker(env, ctxs[0], acct, guard(specs, calls)), specs)
    print(report(R, specs))


if __name__ == "__main__":
    main()
