import json, os, re, subprocess, sys, tempfile, unittest, uuid
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(H, "..", ".."))
import importlib.util
spec = importlib.util.spec_from_file_location("radar_pages", os.path.join(H, "..", "pages.py")); PG = importlib.util.module_from_spec(spec); spec.loader.exec_module(PG)
from competitor_radar.service.app import Auth

KEY = "k" * 40; CTX = "ctx-tenant-A-0001"; ID = str(uuid.uuid4())


class FakeW:
    def __init__(self): self.nodes, self.links = [], []
    def add(self, name, typ, ver, params):
        n = {"name": name, "type": typ, "typeVersion": ver, "parameters": params}; self.nodes.append(n); return n
    def link(self, a, b, i=0): self.links.append((a["name"] if isinstance(a, dict) else a, b["name"] if isinstance(b, dict) else b, i))
    def chain(self, *ns):
        for a, b in zip(ns, ns[1:]): self.link(a, b)


class FakeB:
    def __init__(self): self.used_broker = False
    def code(self, w, name, js): n = w.add(name, "n8n-nodes-base.code", 2, {"jsCode": js}); return n
    def pg(self, w, name, sql, params, CRT, always=False): return w.add(name, "n8n-nodes-base.postgres", 2.5, {"query": sql, "queryReplacement": params})
    def call_broker(self, *a, **k): self.used_broker = True


def built():
    w, b = FakeW(), FakeB(); sw = {"name": "Command"}
    PG.build(b, w, sw, 37, lambda name, js: w.add(name, "n8n-nodes-base.code", 2, {"jsCode": js}), None)
    return w, b


W, B = built(); JS = {n["name"]: n["parameters"].get("jsCode") for n in W.nodes}
def run(name, ctx):
    d = tempfile.mkdtemp(); open(d + "/b.js", "w", encoding="utf-8").write(JS[name]); open(d + "/c.json", "w", encoding="utf-8").write(json.dumps(ctx))
    r = subprocess.run(["node", os.path.join(H, "run_node.cjs"), d + "/b.js", d + "/c.json"], capture_output=True, text=True); assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)[0]["json"]


def plan(route, cfg=True, key=KEY, state=None, age=5):
    rows = [{"kind": "cfg", "a": json.dumps({"enabled": cfg})}]
    if state is not None: rows.append({"kind": "state", "a": json.dumps(state), "b": str(age)})
    if key is not None: rows.append({"kind": "key", "a": key})
    return run("CR: plan", {"nodes": {"Route": {"ctx": CTX, "chatId": "77", **route}}, "inputs": rows, "input": rows[0]})


def render(P, resp):
    return run("CR: render", {"nodes": {"CR: plan": P, "Route": {}}, "input": resp})


def kb_ok(t, kb):
    t.assertLessEqual(len(kb), 8)
    for row in kb:
        t.assertLessEqual(len(row), 3)
        for b in row: t.assertTrue(1 <= len(b["t"]) <= 40, b); t.assertRegex(b["c"], r"^[a-z0-9_:-]{1,48}$")


class Build(unittest.TestCase):
    def test_graph_and_no_broker(self):
        names = [n["name"] for n in W.nodes]
        self.assertEqual(names, ["CR: data", "CR: plan", "CR: need call?", "CR: sign", "CR: http", "CR: render", "CR: save state", "CR: reply"]); self.assertFalse(B.used_broker)
        self.assertIn(("Command", "CR: data", 37), W.links); self.assertIn(("CR: need call?", "CR: sign", 1), W.links); self.assertIn(("CR: need call?", "CR: render", 0), W.links); self.assertIn(("CR: render", "CR: save state", 0), W.links)
        h = next(n for n in W.nodes if n["name"] == "CR: http")["parameters"]; self.assertEqual((h["method"], h["contentType"], h["body"], h["url"]), ("POST", "raw", "={{ $json.raw }}", "={{ $json.url }}"))
        self.assertEqual({p["name"] for p in h["headerParameters"]["parameters"]}, {"x-radar-ts", "x-radar-sig"}); self.assertEqual(h["url"], "={{ $json.url }}")

    def test_sql_only_new_schema_and_state(self):
        sqls = " ".join(n["parameters"]["query"] for n in W.nodes if "query" in n["parameters"]).lower()
        self.assertEqual(sorted(set(re.findall(r"competitor_radar\.\w+", sqls))), ["competitor_radar.config", "competitor_radar.service_key"]); self.assertIn("api.ui_get", sqls); self.assertIn("api.ui_set", sqls)
        for forb in ("core.", "campaign", "ad_account", "broker"): self.assertNotIn(forb, sqls)
        for n in W.nodes: self.assertNotIn("broker", json.dumps(n.get("parameters", {})).lower().replace("broker", "") + "")   # لا إشارة للـBroker بالمعاملات
        self.assertTrue(all("onError" in n for n in W.nodes if n["name"] in ("CR: data", "CR: http", "CR: save state")))


class Plan(unittest.TestCase):
    def test_disabled_and_unconfigured(self):
        p = plan({"cb": "cr:m"}, cfg=False); self.assertIn("غير مفعّل", p["text"]); self.assertFalse(p["need"]); kb_ok(self, p["keyboard"])
        p = plan({"cb": "cr:m"}, key=None); self.assertIn("غير مهيأ", p["text"]); self.assertFalse(p["need"])

    def test_menu(self):
        for r in ({"cb": "cr:m"}, {"cmd": "radar", "args": ""}):
            p = plan(r); labels = [b["t"] for row in p["keyboard"] for b in row]; self.assertEqual(labels, ["➕ إضافة منافس", "📊 منافسي", "🌎 رادار السوق", "🥊 خطة المنافسة", "⬅️ رجوع"]); kb_ok(self, p["keyboard"]); self.assertEqual(p["state"], "{}")
        self.assertTrue(plan({"cb": "cr:m"})["edit"]); self.assertFalse(plan({"cmd": "radar", "args": ""})["edit"])

    def test_add_flow(self):
        p = plan({"cb": "cr:a"}); self.assertEqual(len(p["keyboard"]), 3); kb_ok(self, p["keyboard"])
        p = plan({"cb": "cr:p:tiktok"}); self.assertEqual(json.loads(p["state"]), {"st": "add", "pl": "tiktok"}); self.assertIn("سطرين", p["text"])
        self.assertIn("غير معروفة", plan({"cb": "cr:p:myspace"})["text"])
        p = plan({"cmd": "radar", "args": "متجر الأناقة\nhttps://www.tiktok.com/@shop"}, state={"st": "add", "pl": "tiktok"})
        self.assertEqual((p["need"], p["op"], p["body"]), (True, "competitor_add", {"platform": "tiktok", "name": "متجر الأناقة", "url": "https://www.tiktok.com/@shop"})); self.assertEqual(p["key"], KEY)
        p = plan({"cmd": "radar", "args": "https://x.com/only"}, state={"st": "add", "pl": "other"}); self.assertFalse(p["need"]); self.assertEqual(json.loads(p["state"]), {"st": "add", "pl": "other"})   # اسم مفقود: تبقى الحالة
        self.assertFalse(plan({"cmd": "radar", "args": "x" * 81}, state={"st": "add", "pl": "other"})["need"])
        p = plan({"cmd": "radar", "args": "اسم فقط"}, state={"st": "add", "pl": "snapchat"}); self.assertEqual(p["body"], {"platform": "snapchat", "name": "اسم فقط"})

    def test_text_without_or_with_stale_state_goes_to_menu(self):
        self.assertFalse(plan({"cmd": "radar", "args": "اي شي"})["need"])
        p = plan({"cmd": "radar", "args": "متجر"}, state={"st": "add", "pl": "tiktok"}, age=2000); self.assertFalse(p["need"]); self.assertIn("رادار المنافسين", p["text"])

    def test_samples_and_market(self):
        p = plan({"cmd": "radar", "args": "عينة اولى\n\nعينة ثانية"}, state={"st": "smp", "id": ID}); self.assertEqual((p["op"], p["body"]), ("competitor_samples", {"id": ID, "text": "عينة اولى\n\nعينة ثانية"}))
        p = plan({"cmd": "radar", "args": "فساتين نسائية في العراق\nعينة ١\n\nعينة ٢"}, state={"st": "mk"}); self.assertEqual((p["op"], p["body"]["query"], p["body"]["text"]), ("market", "فساتين نسائية في العراق", "عينة ١\n\nعينة ٢"))
        p = plan({"cmd": "radar", "args": "ساعات"}, state={"st": "mk"}); self.assertNotIn("text", p["body"])
        p = plan({"cb": "cr:k"}); self.assertEqual(json.loads(p["state"]), {"st": "mk"}); p = plan({"cb": "cr:n:" + ID}); self.assertEqual(json.loads(p["state"]), {"st": "smp", "id": ID})

    def test_id_ops_and_validation(self):
        for cb, op in (("c", "competitor_get"), ("r", "report"), ("o", "report"), ("x", "analyze"), ("s", "strategy"), ("dd", "competitor_delete")):
            p = plan({"cb": "cr:%s:%s" % (cb, ID)}); self.assertEqual((p["need"], p["op"], p["body"]["id"]), (True, op, ID), cb)
        self.assertTrue(plan({"cb": "cr:x:" + ID})["body"]["force"]); self.assertEqual(len("cr:dd:" + ID), 42)
        for bad in ("cr:c:123", "cr:c:", "cr:r:' OR 1=1", "cr:dd:" + ID.upper()): p = plan({"cb": bad}); self.assertFalse(p["need"], bad); self.assertIn("⚠️", p["text"])
        p = plan({"cb": "cr:d:" + ID}); self.assertFalse(p["need"]); kb_ok(self, p["keyboard"]); self.assertEqual(p["keyboard"][0][0]["c"], "cr:dd:" + ID)   # تأكيد الحذف
        self.assertEqual(plan({"cb": "cr:l"})["op"], "competitor_list"); self.assertEqual(plan({"cb": "cr:sp"})["ui"], {"kind": "list_s"})

    def test_unknown_op_goes_back(self):
        p = plan({"cb": "cr:zzz"}); self.assertFalse(p["need"]); kb_ok(self, p["keyboard"])


class Render(unittest.TestCase):
    def P(self, kind, **ui): return {"ctx": CTX, "chatId": "77", "edit": True, "need": True, "state": "", "ui": {"kind": kind, **ui}, "S": {"st": "add", "pl": "tiktok"}}

    def rep_ok(self):
        return {"status": "ok", "platform": "instagram", "usable_samples": 5, "business": {"name": "منافس 1", "domain": "فساتين"}, "products": [{"name": "فساتين", "count": 4, "level": "high"}],
                "messages": [{"label": "السعر", "count": 4, "of": 5, "level": "high", "quotes": ["سعر مخفض بس 25 ألف"]}], "content": {"ctas": [{"phrase": "واتساب", "level": "high"}], "hooks": [{}], "video_mentions": 0, "repeated": []},
                "strengths": [{"text": "تركيز على السعر", "level": "high", "kind": "data"}, {"text": "نقطة ذكاء", "level": "medium", "kind": "ai"}], "opportunities": [{"text": "جرّب الضمان", "level": "medium", "kind": "recommendation"}], "overall_confidence": "medium", "disclaimer": "التحليل مبني على العينات"}

    def test_report_and_opps(self):
        o = render(self.P("report", id=ID), {"ok": True, "data": {"report": self.rep_ok()}}); kb_ok(self, o["keyboard"]); self.assertIn("🏪 معلومات النشاط", o["text"]); self.assertIn("🟢 ثقة عالية", o["text"]); self.assertIn("توصية AI", o["text"]); self.assertIn("الثقة الكلية: 🟡", o["text"]); self.assertEqual(o["state"], "{}")
        o = render(self.P("opps", id=ID), {"ok": True, "data": {"report": self.rep_ok()}}); self.assertIn("💡 فرص محتملة", o["text"]); self.assertIn("توصيات وليست حقائق", o["text"])
        ins = {"status": "insufficient", "needs": "الصق 3 منشورات"}
        for k in ("report", "opps"): self.assertIn("⚠️ بيانات غير كافية للتحليل.", render(self.P(k, id=ID), {"ok": True, "data": {"report": ins}})["text"])
        o = render(self.P("analyzed", id=ID), {"ok": True, "data": {"report": self.rep_ok(), "cached": True}}); self.assertIn("♻️", o["text"])

    def test_strategy_texts(self):
        plan_ = {"status": "ok", "angle": {"label": "الجودة", "why": "لم تظهر عند المنافس (توصية وليست حقيقة)"}, "hook": "جرّب الجودة", "ad_idea": "فيديو عن قرب", "cta": "اضغط واتساب", "audience": "نساء 18–44", "budget": "توصية فقط 5–10$",
                 "tests": [{"angle": "جودة", "hook": "h1", "idea": "i1"}, {"angle": "ضمان", "hook": "h2", "idea": "i2"}, {"angle": "ثقة", "hook": "h3", "idea": "i3"}], "confidence": "medium", "source": "rules", "originality": {"max_overlap": 0.02}, "disclaimer": "توصية فقط"}
        o = render(self.P("strategy", id=ID), {"ok": True, "data": {"plan": plan_}}); kb_ok(self, o["keyboard"])
        for frag in ("🎯 الزاوية المقترحة", "🪝 Hook مقترح", "🎬 فكرة إعلان", "📣 CTA", "👥 الجمهور المقترح", "🧪 اختبارات مقترحة", "💰 ميزانية الاختبار", "ما تنسخ المنافس", "تطابق 2%"): self.assertIn(frag, o["text"])
        self.assertIn("⚠️", render(self.P("strategy", id=ID), {"ok": True, "data": {"plan": {"status": "insufficient", "message": "بيانات غير كافية"}}})["text"])

    def test_market(self):
        m = {"status": "ok", "query": "فساتين نسائية في العراق", "sources": {"competitor_reports": 2, "pasted_samples": 3}, "frequent_products": [{"name": "فساتين", "sources": 2, "level": "medium"}], "frequent_angles": [{"label": "السعر", "sources": 2, "level": "medium"}],
             "opportunities": [{"text": "جرّب الضمان", "level": "low"}], "model_knowledge": [{"text": "فكرة عامة"}], "note": "استنتاجات وتوصيات"}
        o = render(self.P("market"), {"ok": True, "data": {"market": m}}); self.assertIn("💎 Market Opportunities", o["text"]); self.assertIn("🔴 معرفة عامة وليست بيانات حية", o["text"]); kb_ok(self, o["keyboard"])
        self.assertIn("⚠️", render(self.P("market"), {"ok": True, "data": {"market": {"status": "insufficient", "message": "بيانات غير كافية"}}})["text"])

    def test_lists_and_comp(self):
        cs = [{"id": str(uuid.uuid4()), "name": "منافس %d" % i, "status": "done", "confidence": "high"} for i in range(11)]
        o = render(self.P("list"), {"ok": True, "data": {"competitors": cs}}); kb_ok(self, o["keyboard"]); self.assertEqual(len(o["keyboard"]), 8); self.assertEqual(o["keyboard"][-1][0]["c"], "cr:m"); self.assertIn("و4 غيرهم", o["text"]); self.assertTrue(o["keyboard"][0][0]["c"].startswith("cr:c:"))
        o = render(self.P("list_s"), {"ok": True, "data": {"competitors": cs[:2]}}); self.assertTrue(o["keyboard"][0][0]["c"].startswith("cr:s:")); self.assertIn("خطة المنافسة", o["text"])
        self.assertIn("ما أضفت منافسين", render(self.P("list"), {"ok": True, "data": {"competitors": []}})["text"])
        c = {"id": ID, "name": "منافس", "status": "done", "platform": "tiktok", "samples": 5, "url": "https://x.com/a", "confidence": "low"}
        o = render(self.P("comp", id=ID), {"ok": True, "data": {"competitor": c}}); kb_ok(self, o["keyboard"]); labels = [b["t"] for r in o["keyboard"] for b in r]
        for l in ("📊 التقرير", "💡 الفرص", "🥊 خطة المنافسة", "🔄 إعادة التحليل", "🗑 حذف من راداري"): self.assertIn(l, labels)

    def test_added_samples_deleted(self):
        o = render(self.P("added"), {"ok": True, "data": {"id": ID}}); self.assertEqual(json.loads(o["state"]), {"st": "smp", "id": ID}); self.assertIn("🔎 حلّل الآن", [b["t"] for r in o["keyboard"] for b in r]); kb_ok(self, o["keyboard"])
        o = render(self.P("samples", id=ID), {"ok": True, "data": {"added": 3, "total": 5}}); self.assertIn("انضافت 3", o["text"]); self.assertEqual(json.loads(o["state"])["id"], ID)
        self.assertIn("انحذف", render(self.P("deleted"), {"ok": True, "data": {"deleted": True}})["text"])

    def test_errors_honest(self):
        for cls, frag in (("disabled", "غير مفعّل"), ("no_report", "ما في تقرير"), ("not_found", "غير موجود"), ("limit", "الحد الأقصى"), ("rate_limited", "⏳"), ("internal", "خطأ داخلي")):
            o = render(self.P("report", id=ID), {"ok": False, "error": {"class": cls, "message": ("وصلت الحد الأقصى" if cls == "limit" else "رسالة")}}); self.assertIn(frag, o["text"], cls); kb_ok(self, o["keyboard"]); self.assertEqual(o["state"], "{}")
        o = render(self.P("added"), {"ok": False, "error": {"class": "bad_url", "message": "الرابط غير مقبول (blocked_address)."}}); self.assertIn("blocked_address", o["text"]); self.assertEqual(json.loads(o["state"]), {"st": "add", "pl": "tiktok"})   # تبقى الحالة لإعادة الكتابة
        for bad in ({}, {"error": {"message": "x"}}, {"ok": "yes"}): self.assertIn("خدمة الرادار غير متاحة", render(self.P("report", id=ID), bad)["text"])
        self.assertLessEqual(len(render(self.P("report", id=ID), {"ok": True, "data": {"report": {**self.rep_ok(), "messages": self.rep_ok()["messages"] * 50}}})["text"]), 3800)

    def test_passthrough_ui_pages(self):
        P = {"ctx": CTX, "chatId": "77", "edit": False, "need": False, "text": "نص", "keyboard": [[{"t": "ا", "c": "cr:m"}]], "state": "{}"}
        o = render(P, {}); self.assertEqual((o["text"], o["state"], o["edit"]), ("نص", "{}", False))


class Sign(unittest.TestCase):
    def test_signature_verifies_with_real_service_auth(self):
        for op, body in (("competitor_list", {}), ("competitor_add", {"platform": "tiktok", "name": "متجر الأناقة ✨", "url": "https://x.com/é"}), ("market", {"query": "فساتين", "text": "عينة\n\nعينة 2"})):
            s = run("CR: sign", {"input": {"ctx": CTX, "chatId": "77", "op": op, "body": body, "key": KEY}})
            self.assertEqual(s["url"], "http://radar:8088/v1/" + op); self.assertEqual(json.loads(s["raw"]), {"ctx": CTX, **body})
            a = Auth(KEY, clock=lambda: float(s["ts"])); self.assertTrue(a.check(s["ts"], s["sig"], "/v1/" + op, s["raw"].encode("utf-8")), op)
            self.assertFalse(Auth(KEY, clock=lambda: float(s["ts"])).check(s["ts"], s["sig"], "/v1/other", s["raw"].encode("utf-8")))
        s = run("CR: sign", {"input": {"ctx": CTX, "chatId": "77", "op": "config", "body": {}, "key": "z" * 40}}); self.assertFalse(Auth(KEY, clock=lambda: float(s["ts"])).check(s["ts"], s["sig"], "/v1/config", s["raw"].encode()))

    def test_long_key_hashing_matches(self):
        long_key = "L" * 100; s = run("CR: sign", {"input": {"ctx": CTX, "chatId": "77", "op": "report", "body": {"id": ID}, "key": long_key}})
        self.assertTrue(Auth(long_key, clock=lambda: float(s["ts"])).check(s["ts"], s["sig"], "/v1/report", s["raw"].encode()))


if __name__ == "__main__":
    unittest.main(verbosity=1)
