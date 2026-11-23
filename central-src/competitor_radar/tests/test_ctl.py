import importlib.util, os, shutil, stat, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("ctl", os.path.join(H, "..", "deploy", "competitor_radar_ctl.py")); CTL = importlib.util.module_from_spec(spec); spec.loader.exec_module(CTL)


class Fake:
    def __init__(self, fail=None, healthy=True, nets="central-stg_default "):
        self.calls, self.fail, self.healthy, self.nets = [], fail, healthy, nets
    def __call__(self, cmd, input=None, check=True):
        self.calls.append((list(cmd), input))
        j = " ".join(cmd)
        if self.fail and self.fail in j + (input or ""):
            if check: raise SystemExit("FAIL: simulated")
            return 1, "", "err"
        if "docker inspect" in j and "Networks" in j: return 0, self.nets, ""
        if "docker inspect" in j and "State.Status" in j: return 0, "running\n", ""
        if "healthz" in j: return (0, "200\n", "") if self.healthy else (1, "", "x")
        if "RETURNING slug" in (input or ""): return 0, ("acme\n" if "'acme'" in input else ""), ""
        if "SELECT value::text" in (input or ""): return 0, "false\n", ""
        return 0, "", ""


class T(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(); CTL.ROOT = self.root; CTL.ENV = self.root + "/radar.env"
        for f, c in (("db/80_competitor_radar.sql", "-- sql\n"), ("deploy/Dockerfile", "FROM x\n"), ("service/app.py", "x=1\n")):
            os.makedirs(os.path.dirname(os.path.join(self.root, f)), exist_ok=True); open(os.path.join(self.root, f), "w").write(c)
        self.f = Fake(); CTL.run = self.f; CTL.time_sleep = None

    def sqls(self): return [i for c, i in self.f.calls if i]

    def test_install_flow_and_secrets(self):
        import io, contextlib
        out = io.StringIO()
        with contextlib.redirect_stdout(out): CTL.cmd_install(prompt=lambda p: "GEMINI-SECRET-KEY")
        env = CTL.read_env(); self.assertEqual(env["COMPETITOR_RADAR_ENABLED"], "false"); self.assertEqual(len(env["RADAR_HMAC_KEY"]), 64); self.assertEqual(env["RADAR_LLM_PROVIDER"], "gemini")
        self.assertEqual(oct(os.stat(CTL.ENV).st_mode & 0o777), "0o600"); self.assertTrue(env["RADAR_DB_DSN"].startswith("postgresql://radar_rt:") and "@central-stg-pg:5432/central" in env["RADAR_DB_DSN"])
        self.assertIn("INSTALL_OK", out.getvalue()); self.assertNotIn(env["RADAR_HMAC_KEY"], out.getvalue()); self.assertNotIn("GEMINI-SECRET-KEY", out.getvalue()); self.assertNotIn(env["RADAR_DB_DSN"].split(":")[2].split("@")[0], out.getvalue())
        argv = " ".join(" ".join(c) for c, _ in self.f.calls); self.assertNotIn("GEMINI-SECRET-KEY", argv); self.assertNotIn(env["RADAR_HMAC_KEY"], argv)   # الأسرار ما تظهر بسطر الأوامر
        s = self.sqls(); self.assertTrue(s[0].startswith("-- sql")); self.assertTrue(any("ALTER ROLE radar_rt LOGIN PASSWORD" in x for x in s)); self.assertTrue(any("service_key" in x for x in s))
        self.assertTrue(any(c[:2] == ["docker", "build"] for c, _ in self.f.calls)); run_ = next(c for c, _ in self.f.calls if c[:2] == ["docker", "run"])
        for flag in ("--read-only", "--cap-drop", "--network-alias", "--memory", "--pids-limit", "no-new-privileges:true"): self.assertIn(flag, run_)
        self.assertNotIn("-p", run_); self.assertNotIn("--publish", run_); self.assertIn("central-stg_default", run_)

    def test_reinstall_keeps_secrets_and_flag(self):
        import io, contextlib
        with contextlib.redirect_stdout(io.StringIO()): CTL.cmd_install(prompt=lambda p: "")
        e1 = CTL.read_env(); self.assertEqual(e1["RADAR_LLM_PROVIDER"], ""); e1["COMPETITOR_RADAR_ENABLED"] = "true"; CTL.write_env(e1)
        self.f.calls.clear()
        with contextlib.redirect_stdout(io.StringIO()): CTL.cmd_install(prompt=lambda p: "")
        e2 = CTL.read_env(); self.assertEqual((e2["RADAR_HMAC_KEY"], e2["RADAR_DB_DSN"], e2["COMPETITOR_RADAR_ENABLED"]), (e1["RADAR_HMAC_KEY"], e1["RADAR_DB_DSN"], "true"))
        self.assertFalse(any("ALTER ROLE" in x for x in self.sqls()))

    def test_migration_failure_stops_before_anything(self):
        self.f.fail = "-- sql"
        with self.assertRaises(SystemExit): CTL.cmd_install(prompt=lambda p: "")
        self.assertFalse(os.path.exists(CTL.ENV)); self.assertFalse(any(c[:2] in (["docker", "build"], ["docker", "run"]) for c, _ in self.f.calls))

    def test_missing_files_refused(self):
        os.remove(self.root + "/service/app.py")
        with self.assertRaises(SystemExit) as cm: CTL.cmd_install()
        self.assertIn("p251", str(cm.exception)); self.assertEqual(self.f.calls, [])

    def test_on_off(self):
        CTL.write_env({"RADAR_HMAC_KEY": "k" * 64, "COMPETITOR_RADAR_ENABLED": "false"})
        CTL.set_global(True); self.assertEqual(CTL.read_env()["COMPETITOR_RADAR_ENABLED"], "true"); self.assertTrue(any("'true'::jsonb" in x for x in self.sqls())); self.assertTrue(any(c[:2] == ["docker", "restart"] for c, _ in self.f.calls))
        CTL.set_global(False); self.assertEqual(CTL.read_env()["COMPETITOR_RADAR_ENABLED"], "false"); self.assertTrue(any("'false'::jsonb" in x for x in self.sqls()))

    def test_on_refused_when_unhealthy_or_not_installed(self):
        with self.assertRaises(SystemExit): CTL.set_global(True)
        CTL.write_env({"RADAR_HMAC_KEY": "k" * 64}); self.f.healthy = False; self.f.calls.clear()
        with self.assertRaises(SystemExit) as cm: CTL.set_global(True)
        self.assertIn("not healthy", str(cm.exception)); self.assertFalse(any("UPDATE competitor_radar" in (i or "") for _, i in self.f.calls))
        CTL.set_global(False)   # الإطفاء مسموح دائماً

    def test_tenant(self):
        CTL.set_tenant("acme", True)
        with self.assertRaises(SystemExit): CTL.set_tenant("nobody", True)
        for bad in ("", "A", "x;drop", "a b", "../x", "x'--"):
            with self.assertRaises(SystemExit): CTL.set_tenant(bad, True)
        self.assertTrue(any("'competitor_radar', true" in x and "slug = 'acme'" in x for x in self.sqls()))

    def test_status_and_down_touch_only_radar(self):
        import io, contextlib
        CTL.write_env({"RADAR_HMAC_KEY": "k" * 64, "COMPETITOR_RADAR_ENABLED": "false"}); o = io.StringIO()
        with contextlib.redirect_stdout(o): CTL.cmd_status(); CTL.main(["x", "down"])
        self.assertIn("container=running healthy=True env_flag=false db_flag=false", o.getvalue()); self.assertIn("DOWN_OK", o.getvalue())
        rms = [c for c, _ in self.f.calls if c[:2] == ["docker", "rm"]]; self.assertTrue(rms and all(c[-1] == "central-stg-radar" for c in rms))

    def test_unknown_command_usage(self):
        with self.assertRaises(SystemExit) as cm: CTL.main(["x", "wipe"])
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
