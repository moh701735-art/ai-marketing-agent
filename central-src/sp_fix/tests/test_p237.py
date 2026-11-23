import asyncio, importlib.util, os, shutil, subprocess, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..", "..")
spec = importlib.util.spec_from_file_location("t236", os.path.join(ROOT, "sp_toggle", "tests", "test_p236.py")); t236 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t236)
specb = importlib.util.spec_from_file_location("t236b", os.path.join(ROOT, "sp_toggle", "tests", "test_p236b.py")); t236b = importlib.util.module_from_spec(specb); specb.loader.exec_module(t236b)
specc = importlib.util.spec_from_file_location("t236c", os.path.join(ROOT, "sp_toggle", "tests", "test_p236c.py")); t236c = importlib.util.module_from_spec(specc); specc.loader.exec_module(t236c)
P237 = os.path.join(ROOT, "ops", "p237-smart-plus-fix.py.txt")
SERVICE = '''import datetime, time
class Svc:
    async def _launch_smart(self, ctx: str, ad_account: str, p: dict, cre: list, made: dict, wa: dict, budget: float, idem: str) -> None:
        """Smart+ (واتساب): حملة ثم مجموعة ثم إعلان؛ made['smart'] يوصف الحالة."""
        sm = made["smart"] = {"budget": budget}

        async def go(stage, op, prm, key):
            st, env = await self.call(ctx, "tiktok", op, ad_account, prm, key)
            if st != 200 or not env.get("ok"):
                sm["stage"] = stage
                sm["error"] = str((env.get("error") or {}).get("message") or "failed")[:160]
                return None
            return (env.get("data") or {}).get("data") or {}
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        start, end = now, now + datetime.timedelta(days=1)
        fmt = "%Y-%m-%d %H:%M:%S"
        name = f"{p['campaign_name'][:400]}-SMART-{int(time.time()) % 1000000}"
        c = await go("campaign", "tiktok.sp_create_campaign", {"campaign_name": name, "budget": budget, "budget_mode": "BUDGET_MODE_DYNAMIC_DAILY" if p["budget_mode"] == "daily" else "BUDGET_MODE_TOTAL"}, f"{idem}-sc")
        cid = str((c or {}).get("campaign_id") or "")
        if not cid:
            sm.setdefault("error", "campaign_id")
            return
        sm["campaign_id"] = cid
        g = await go("adgroup", "tiktok.sp_create_adgroup", {"campaign_id": cid, "adgroup_name": f"{name}-adgroup"[:512], "schedule_start_time": start.strftime(fmt), "schedule_end_time": end.strftime(fmt),
                                                              "message_event_set_id": wa["event_set"], "phone_number": wa["local"]}, f"{idem}-sg")
        gid = str((g or {}).get("adgroup_id") or "")
        if not gid:
            sm.setdefault("error", "adgroup_id")
            return
        a = await go("ad", "tiktok.sp_create_ad", {"adgroup_id": gid, "ad_name": f"{name}-ad"[:512], "ad_text": "x", "cta_portfolio_id": "9", "creatives": cre}, f"{idem}-sd")
        sm["ad_id"] = str((a or {}).get("smart_plus_ad_id") or "")[:30]
'''


def mk():
    d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "broker/app")); os.makedirs(os.path.join(d, "ops"))
    open(os.path.join(d, "broker/app/catalog.py"), "w", encoding="utf-8").write(t236.CAT); open(os.path.join(d, "broker/app/service.py"), "w", encoding="utf-8").write(SERVICE)
    assert "APPLY236_OK" in t236.apply(d).stdout; assert "APPLY236B_OK" in t236b.apply_b(d).stdout; assert "APPLY236C_OK" in t236c.apply_c(d).stdout
    return d


def apply37(d): return subprocess.run([sys.executable, P237], env={**os.environ, "P237_BASE": d + "/"}, capture_output=True, text=True)
rd = lambda p: open(p, encoding="utf-8").read()


def run_launch(svc_path, p):
    ns = {}; exec(compile(rd(svc_path), "service.py", "exec"), ns); calls = []
    class S(ns["Svc"]):
        async def call(self, ctx, platform, op, acct, prm, key):
            calls.append((op, dict(prm), key)); ids = {"tiktok.sp_create_campaign": {"campaign_id": "11"}, "tiktok.sp_create_adgroup": {"adgroup_id": "22"}, "tiktok.sp_create_ad": {"smart_plus_ad_id": "33"}}
            return 200, {"ok": True, "data": {"data": ids[op]}}
    made = {}; asyncio.run(S()._launch_smart("c", "7593", p, [{"x": 1}], made, {"event_set": "5", "local": "7829503973"}, 5000.0, p.get("idem", "tgupd-1-2-launch")))
    return calls, made


class T(unittest.TestCase):
    def setUp(self): self.d = mk()
    def tearDown(self): shutil.rmtree(self.d, ignore_errors=True)

    def test_01_apply_adds_request_id_param_to_adgroup_and_ad_only(self):
        cat = os.path.join(self.d, "broker/app/catalog.py"); before = t236.load_ops(cat); r = apply37(self.d); self.assertIn("APPLY237_OK", r.stdout, r.stdout + r.stderr); after = t236.load_ops(cat)
        for name in ("tiktok.sp_create_adgroup", "tiktok.sp_create_ad"):
            self.assertEqual(set(after[name]["params"]) - set(before[name]["params"]), {"request_id"}, name); self.assertEqual(after[name]["params"]["request_id"]["kind"], "id"); self.assertFalse(after[name]["params"]["request_id"].get("required", False))
            self.assertEqual(after[name]["forced"], before[name]["forced"])
        self.assertEqual(after["tiktok.sp_create_campaign"], before["tiktok.sp_create_campaign"]); self.assertEqual(after["tiktok.read_adgroups"], before["tiktok.read_adgroups"])
    def test_02_launch_sends_numeric_deterministic_request_id_on_all_three_calls(self):
        apply37(self.d); sv = os.path.join(self.d, "broker/app/service.py")
        calls, made = run_launch(sv, {"campaign_name": "x", "budget_mode": "total"}); self.assertEqual([c[0] for c in calls], ["tiktok.sp_create_campaign", "tiktok.sp_create_adgroup", "tiktok.sp_create_ad"])
        rids = [c[1]["request_id"] for c in calls]
        for r in rids: self.assertTrue(r.isdigit() and 10 <= len(r) <= 19, r)
        self.assertEqual(len(set(rids)), 3)                                               # مفتاح مختلف لكل خطوة
        calls2, _ = run_launch(sv, {"campaign_name": "x", "budget_mode": "total"}); self.assertEqual(rids, [c[1]["request_id"] for c in calls2])   # نفس الطلب = نفس request_id
        calls3, _ = run_launch(sv, {"campaign_name": "x", "budget_mode": "total", "idem": "tgupd-9-9-launch"}); self.assertNotEqual(rids[0], calls3[0][1]["request_id"])
        self.assertEqual(made["smart"]["ad_id"], "33"); self.assertNotIn("error", made["smart"])
    def test_03_request_id_values_pass_catalog_validation_shape(self):
        apply37(self.d); calls, _ = run_launch(os.path.join(self.d, "broker/app/service.py"), {"campaign_name": "x", "budget_mode": "total"})
        import re; [self.assertRegex(c[1]["request_id"], r"[0-9]{1,24}") for c in calls]
    def test_04_daily_mode_uses_the_valid_tiktok_value_total_unchanged(self):
        apply37(self.d); sv = os.path.join(self.d, "broker/app/service.py")
        daily, _ = run_launch(sv, {"campaign_name": "x", "budget_mode": "daily"}); total, _ = run_launch(sv, {"campaign_name": "x", "budget_mode": "total"})
        self.assertEqual(daily[0][1]["budget_mode"], "BUDGET_MODE_DYNAMIC_DAILY_BUDGET"); self.assertEqual(total[0][1]["budget_mode"], "BUDGET_MODE_TOTAL")
        self.assertIn(daily[0][1]["budget_mode"], t236.load_ops(os.path.join(self.d, "broker/app/catalog.py"))["tiktok.sp_create_campaign"]["params"]["budget_mode"]["values"])
    def test_05_other_params_untouched_and_idempotent(self):
        sv = os.path.join(self.d, "broker/app/service.py"); calls0, _ = run_launch(sv, {"campaign_name": "x", "budget_mode": "total"}); apply37(self.d); calls1, _ = run_launch(sv, {"campaign_name": "x", "budget_mode": "total"})
        for a, b in zip(calls0, calls1):
            b2 = {k: v for k, v in b[1].items() if k != "request_id"}; self.assertEqual(a[1], b2); self.assertEqual(a[2], b[2])
        self.assertIn("changed=0", apply37(self.d).stdout); self.assertEqual(rd(sv).count("p237"), 1 + rd(sv).count("# p237: القيمة"))
    def test_06_failures_write_nothing(self):
        sv = os.path.join(self.d, "broker/app/service.py"); cat = os.path.join(self.d, "broker/app/catalog.py"); s0, c0 = rd(sv), rd(cat)
        for name, (path, old, new) in {"no go call": (sv, "prm, key)", "prm, KEY)"), "no daily literal": (sv, '"BUDGET_MODE_DYNAMIC_DAILY" if', '"X" if'), "no ad creatives anchor": (cat, '"creatives": P("creatives", required=True)}', '"creatives": P("creatives")}')}.items():
            open(path, "w", encoding="utf-8").write(rd(path).replace(old, new, 1)); before = (rd(sv), rd(cat)); r = apply37(self.d)
            self.assertNotEqual(r.returncode, 0, name); self.assertIn("PATCH FAIL (nothing written)", r.stdout + r.stderr, name); self.assertEqual((rd(sv), rd(cat)), before, name); self.assertFalse(os.path.exists(sv + ".pre237"), name)
            open(sv, "w", encoding="utf-8").write(s0); open(cat, "w", encoding="utf-8").write(c0)
    def test_07_requires_p236c_and_refuses_half_applied(self):
        d = t236.mk(); sv = os.path.join(d, "broker/app/service.py"); open(sv, "w", encoding="utf-8").write(SERVICE); t236.apply(d)
        try: r = apply37(d); self.assertIn("p236c must be applied first", r.stdout + r.stderr)
        finally: shutil.rmtree(d, ignore_errors=True)
        sv2 = os.path.join(self.d, "broker/app/service.py"); open(sv2, "a", encoding="utf-8").write("\n# p237\n"); r = apply37(self.d); self.assertIn("half-applied", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
