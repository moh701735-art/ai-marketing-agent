import json, os, re, shutil, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); P = os.path.join(H, "..", "..", "ops", "p240b-pause-by-name-ingress.py.txt"); RUN = os.path.join(H, "run_node.cjs")
INGRESS = '''# ingress
decide = code(w, "AI: decide", r"""
const d = $('Route').first().json; const r = $input.first().json;
const base = { ctx: d.ctx, chatId: d.chatId };
if (!r.ok || !r.data || !r.data.intent) return [{ json: { ...base, aiIdx: 6, text: String((($('AI: prep').first().json.params) || {}).text || '') } }];
const it = r.data.intent;
const map = { report: 0, accounts: 1, campaigns: 2, create: 3, help: 4, unknown: 5, campaign_status: 7, balance: 8, active: 9 };
return [{ json: { ...base, aiIdx: it.intent in map ? map[it.intent] : 5, it, codes: $('AI: prep').first().json.codes || [], text: String((($('AI: prep').first().json.params) || {}).text || '') } }];
""")
aisw = w.add("AI: route", "n8n-nodes-base.switch", 3.5, {})
stprep = code(w, "Stat: prep", r"""
const d = $('Route').first().json; const a = $('AI: decide').first().json;
const rows = $input.all().map(i => i.json).filter(r => r && r.external_id);
const name = String((a.it || {}).name || '').replace(/\\s+/g, ' ').trim().slice(0, 80);
const say = t => [{ json: { ctx: d.ctx, chatId: d.chatId, text: t, halt: true } }];
if (!name) return say('x');
if (!rows.length) return say('y');
return [{ json: { ctx: d.ctx, chatId: d.chatId, platform: 'tiktok', op: 'tiktok.find_campaign', ad_account: null, params: { name, accounts: rows.map(r => String(r.external_id)).slice(0, 40) }, askedName: name } }];
""")
stchoose = code(w, "Stat: choose", r"""
const p = $('Stat: prep').first().json; const r = $input.first().json;
const say = t => [{ json: { ctx: p.ctx, chatId: p.chatId, text: t, halt: true } }];
if (r.ok !== true) return say('err');
const d = r.data || {}, m = d.matches || [];
return say('find:' + m.length);
""")
'''
rd = lambda p: open(p, encoding="utf-8").read()
def mk(src=INGRESS, p240a=True):
    d = tempfile.mkdtemp(); os.makedirs(d + "/n8n"); os.makedirs(d + "/broker/app")
    open(d + "/n8n/wf_ingress.py", "w", encoding="utf-8").write(src); open(d + "/broker/app/service.py", "w", encoding="utf-8").write("# p240a\n" if p240a else "x = 1\n"); return d
def apply(d): return subprocess.run([sys.executable, P], env={**os.environ, "P240B_BASE": d + "/"}, capture_output=True, text=True)
def body(d, name):
    s = rd(d + "/n8n/wf_ingress.py"); m = re.search(r'code\(w, "' + re.escape(name) + r'", r"""', s); return s[m.end(): s.index('"""', m.end())]
def runjs(b, ctx):
    t = tempfile.mkdtemp(); open(t + "/b.js", "w", encoding="utf-8").write(b); open(t + "/c.json", "w", encoding="utf-8").write(json.dumps(ctx))
    r = subprocess.run(["node", RUN, t + "/b.js", t + "/c.json"], capture_output=True, text=True); assert r.returncode == 0, r.stderr; return json.loads(r.stdout)


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = mk(); r = apply(cls.d); assert "APPLY240B_OK" in r.stdout, r.stdout + r.stderr

    def decide(self, text, llm=None, cb=False):
        route = {"ctx": "c", "chatId": "9", "updateId": "5", "text": text, "fromCb": cb}
        return runjs(body(self.d, "AI: decide"), {"nodes": {"Route": route, "AI: prep": {"params": {"text": text}, "codes": []}}, "input": llm or {"ok": False}})[0]["json"]

    def test_positive_phrases(self):
        for t, n in (("طفي حملة زوز", "زوز"), ("اطفي لي الحملة زوز", "زوز"), ("أطفي حملة زوز مبيعات رمضان", "زوز مبيعات رمضان"), ("وقف حملة زوز", "زوز"),
                     ("اوقف لي حملة «زوز»", "زوز"), ("طفيلي حملة زوز.", "زوز"), ("لو سمحت طفي حملة  زوز ", "زوز"), ("إيقاف حملة زوز", "زوز"), ("طَفِّي حملة زوز", "زوز")):
            j = self.decide(t)
            self.assertEqual((j["aiIdx"], j["it"]["intent"], j["it"]["act"], j["it"]["name"]), (7, "campaign_status", "pause", n), t)

    def test_works_when_llm_failed_or_says_unknown(self):
        self.assertEqual(self.decide("طفي حملة زوز", llm={"ok": False})["aiIdx"], 7)
        self.assertEqual(self.decide("طفي حملة زوز", llm={"ok": True, "data": {"intent": {"intent": "unknown"}}})["it"]["act"], "pause")

    def test_negative_untouched(self):
        for t in ("ارفع حمله ساعه 10 بليل وقفها ساعه 7 صبح بحساب علي", "وقف الاعلان بعد ساعتين", "طفي حملة زوز بحساب علي", "طفي حملة", "وقفها ساعه 7", "روّج الساعة 22:00 وقف 10:00",
                  "كم صرفت حملة زوز", "شغل حملة زوز", "طفي الحساب", "وقف حملة 5 دولار الساعة 3", "ارفع حملة وقف حملة زوز"):
            j = self.decide(t, llm={"ok": True, "data": {"intent": {"intent": "unknown"}}})
            self.assertEqual((j["aiIdx"], "act" in j.get("it", {})), (5, False), t)
        self.assertEqual(self.decide("ازيد", llm={"ok": False})["aiIdx"], 6)   # فشل الـAI الأصلي بدون تغيير

    def test_callback_ignored(self):
        self.assertEqual(self.decide("طفي حملة زوز", cb=True)["aiIdx"], 6)

    def test_normal_intent_unchanged(self):
        j = self.decide("تقرير", llm={"ok": True, "data": {"intent": {"intent": "campaign_status", "name": "x"}}}); self.assertEqual((j["aiIdx"], j["it"]["name"], "act" in j["it"]), (7, "x", False))

    def prep(self, act, rows=2):
        ctx = {"nodes": {"Route": {"ctx": "c", "chatId": "123456789", "updateId": "987654321"}, "AI: decide": {"it": {"name": "زوز", **({"act": "pause"} if act else {})}}},
               "input": {"external_id": "7700000000000000001"}, "inputs": [{"external_id": "77000000000000000%02d" % i} for i in range(rows)]}
        return runjs(body(self.d, "Stat: prep"), ctx)[0]["json"]

    def test_prep_pause_and_find(self):
        j = self.prep(True); self.assertEqual((j["op"], j["idem"], j["params"]["name"], len(j["params"]["accounts"]), j["askedName"]), ("tiktok.pause_by_name", "tgupd-123456789-987654321-pbn", "زوز", 2, "زوز"))
        self.assertTrue(16 <= len(j["idem"]) <= 128); self.assertEqual(set(j["params"]), {"name", "accounts"})
        j = self.prep(False); self.assertEqual(j["op"], "tiktok.find_campaign"); self.assertNotIn("idem", j)

    def choose(self, data=None, ok=True, error=None, op="tiktok.pause_by_name"):
        inp = {"ok": ok, **({"data": data} if data is not None else {}), **({"error": error} if error else {})}
        return runjs(body(self.d, "Stat: choose"), {"nodes": {"Stat: prep": {"ctx": "c", "chatId": "9", "op": op, "askedName": "زوز", "params": {"name": "زوز"}}}, "input": inp})[0]["json"]

    def test_choose_replies(self):
        A = "7700000000000000001"; pz = lambda a, v=True: {"account": a, "campaign_id": "1", "name": "زوز", "verified": v}
        j = self.choose({"mode": "exact", "matched": 1, "paused": [pz(A)], "already_paused": [], "failed": [], "accounts_failed": {}}); self.assertTrue(j["halt"]); self.assertIn("أنا طفيت الحملة «زوز»", j["text"]); self.assertIn("…000001", j["text"]); self.assertNotIn("حملات)", j["text"])
        j = self.choose({"mode": "exact", "paused": [pz(A), pz(A)], "already_paused": [], "failed": [], "accounts_failed": {}}); self.assertIn("(2 حملات)", j["text"])
        j = self.choose({"mode": "exact", "paused": [pz(A, False)], "already_paused": [], "failed": [], "accounts_failed": {}}); self.assertIn("ما كدرت أتأكد", j["text"])
        j = self.choose({"mode": "exact", "paused": [], "already_paused": [pz(A)], "failed": [], "accounts_failed": {}}); self.assertIn("موقوفة أصلاً", j["text"]); self.assertNotIn("أنا طفيت", j["text"])
        j = self.choose({"mode": "exact", "paused": [], "already_paused": [], "failed": [{"account": A, "campaign_id": "1", "name": "زوز", "why": "bad_request no permission"}], "accounts_failed": {}}); self.assertIn("ما كدرت أطفي", j["text"]); self.assertIn("no permission", j["text"]); self.assertNotIn("أنا طفيت", j["text"])
        j = self.choose({"mode": "ambiguous", "ambiguous": [{"account": A, "campaign_id": "1", "name": "زوز 1"}, {"account": A, "campaign_id": "2", "name": "زوز 2"}], "paused": [], "accounts_failed": {}}); self.assertIn("ما طفيت شي", j["text"]); self.assertIn("زوز 2", j["text"])
        j = self.choose({"mode": "not_found", "similar": ["زوز مبيعات"], "paused": [], "accounts_failed": {A: "auth_expired token"}}); self.assertIn("ما لقيت حملة باسم «زوز»", j["text"]); self.assertIn("زوز مبيعات", j["text"]); self.assertIn("ما كدرت أقرأ 1 حساب", j["text"])
        j = self.choose({"mode": "contains", "paused": [pz(A)], "already_paused": [], "failed": [], "accounts_failed": {}}); self.assertIn("الأقرب الوحيد", j["text"])
        j = self.choose(ok=False, error={"class": "forbidden", "message": "role"}); self.assertIn("ما كدرت أطفي", j["text"]); self.assertIn("role", j["text"]); self.assertNotIn("أنا طفيت", j["text"])
        j = self.choose(ok=False, error=None); self.assertIn("غير معروف", j["text"])

    def test_choose_find_flow_untouched(self):
        j = self.choose({"matches": [1, 2, 3]}, op="tiktok.find_campaign"); self.assertEqual(j["text"], "find:3")
        j = runjs(body(self.d, "Stat: choose"), {"nodes": {"Stat: prep": {"ctx": "c", "chatId": "9", "op": "tiktok.find_campaign"}}, "input": {"ok": False}})[0]["json"]; self.assertEqual(j["text"], "err")

    def test_idempotent_backup_and_needs_p240a(self):
        d = mk(); self.assertIn("APPLY240B_OK", apply(d).stdout); a = rd(d + "/n8n/wf_ingress.py"); self.assertIn("already applied", apply(d).stdout)
        self.assertEqual(a, rd(d + "/n8n/wf_ingress.py")); self.assertEqual(rd(d + "/n8n/wf_ingress.py.pre240b"), INGRESS); self.assertEqual(a.count("p240b"), 3)
        d2 = mk(p240a=False); r = apply(d2); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertEqual(rd(d2 + "/n8n/wf_ingress.py"), INGRESS)

    def test_anchor_failures_write_nothing(self):
        for bad in (INGRESS.replace("const r = $input.first().json;", "let r = $input.first().json;"), INGRESS.replace("op: 'tiktok.find_campaign',", "op: \"tiktok.find_campaign\","),
                    INGRESS.replace('"Stat: choose"', '"Stat: pick"'), INGRESS + INGRESS):
            d = mk(bad); r = apply(d); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr); self.assertEqual(rd(d + "/n8n/wf_ingress.py"), bad); self.assertFalse(os.path.exists(d + "/n8n/wf_ingress.py.pre240b"))

    def test_build_failure_restores(self):
        d = mk(); os.makedirs(d + "/n8n", exist_ok=True); open(d + "/n8n/build.py", "w").write("import sys; sys.exit(3)\n")
        r = apply(d); self.assertIn("build failed", r.stdout + r.stderr); self.assertEqual(rd(d + "/n8n/wf_ingress.py"), INGRESS)


if __name__ == "__main__": unittest.main(verbosity=1)
