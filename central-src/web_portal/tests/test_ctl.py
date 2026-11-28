import hashlib, importlib.util, os, re, shutil, stat, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..")
spec = importlib.util.spec_from_file_location("ctl", os.path.join(ROOT, "deploy", "web_portal_ctl.py")); ctl = importlib.util.module_from_spec(spec); spec.loader.exec_module(ctl)
CF0 = "{\n\temail a@b.co\n}\n\nagent.mohammedai.tech {\n\trespond \"ok\"\n}\n\n# BEGIN wa-pages (x)\ntwasuliraq.com {\n\trespond \"\" 404\n}\n# END wa-pages\n"


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); ctl.ROOT = self.d; ctl.CF = self.d + "/Caddyfile"; ctl.ENV = self.d + "/web.env"
        for f, t in (("Dockerfile", "FROM x"), ("service/app.py", "x"), ("db/81_web_portal.sql", "-- migration sql")):
            os.makedirs(os.path.dirname(os.path.join(self.d, f)), exist_ok=True); open(os.path.join(self.d, f), "w").write(t)
        open(ctl.CF, "w").write(CF0); self.cmds = []; self.fail = set(); self.out = []; self.sql = []
        def run(cmd, input=None, check=True, timeout=300):
            self.cmds.append(list(cmd)); key = " ".join(cmd[:4])
            if input is not None and "psql" in cmd: self.sql.append(input)
            for f in self.fail:
                if f in " ".join(cmd):
                    if check: raise ctl.Fail("FAIL " + f)
                    return 1, "", "boom"
            if cmd[:2] == ["docker", "inspect"]: return 0, "net1 net2 ", ""
            if cmd[:2] == ["docker", "exec"] and "psql" in cmd and "READY" in (input or ""): return 0, "mohm\n", ""
            if cmd[:2] == ["docker", "exec"] and "psql" in cmd and "api.list_ad_accounts" in (input or ""): return 0, "3\n", ""
            return 0, "", ""
        ctl.run = run; ctl.healthy = lambda seconds=40: "health" not in self.fail
        self.p = lambda *a: self.out.append(" ".join(map(str, a)))
    def tearDown(self): shutil.rmtree(self.d, ignore_errors=True)

    def test_01_caddy_block_add_remove_idempotent_keeps_others(self):
        t = ctl.update_caddyfile(CF0); self.assertIn(ctl.BEGIN, t); self.assertIn("reverse_proxy web-portal:8090", t); self.assertIn("agent.mohammedai.tech", t); self.assertIn("# BEGIN wa-pages", t)
        self.assertEqual(ctl.update_caddyfile(t), t); r = ctl.update_caddyfile(t, remove=True); self.assertNotIn("web-portal", r); self.assertEqual(r.strip(), CF0.strip())
        self.assertEqual(ctl.update_caddyfile(CF0, remove=True), CF0)
        with self.assertRaises(SystemExit): ctl.update_caddyfile(CF0 + ctl.BEGIN + "\n")

    def test_02_install_order_secrets_and_hardening(self):
        ctl.cmd_install(None, self.p); c = [" ".join(x) for x in self.cmds]
        idx = lambda frag: next(i for i, x in enumerate(c) if frag in x)
        self.assertLess(idx("docker build"), idx("docker run")); self.assertLess(idx("docker run"), idx("caddy validate")); self.assertLess(idx("caddy validate"), idx("caddy reload"))
        run = next(x for x in self.cmds if x[:3] == ["docker", "run", "-d"])
        for flag in ("--read-only", "--cap-drop", "no-new-privileges", "--memory", "--pids-limit"): self.assertIn(flag, run)
        self.assertEqual(run[run.index("--network-alias") + 1], "web-portal"); self.assertNotIn("-p", run); self.assertEqual(run[run.index("--network") + 1], "net1")
        self.assertEqual(stat.S_IMODE(os.stat(ctl.ENV).st_mode), 0o600); env = ctl.read_env(); self.assertTrue(env["WEB_DB_DSN"].startswith("postgresql://web_rt:") and env["WEB_COOKIE_SECURE"] == "1")
        pw = re.search(r"web_rt:([^@]+)@", env["WEB_DB_DSN"]).group(1); self.assertTrue(any("ALTER ROLE web_rt LOGIN PASSWORD '%s'" % pw in s for s in self.sql)); self.assertTrue(any("-- migration sql" in s for s in self.sql))
        self.assertNotIn(pw, "\n".join(self.out)); self.assertTrue(any("✅ مقبول" in o for o in self.out)); self.assertIn(ctl.BEGIN, open(ctl.CF).read())

    def test_03_reinstall_reuses_env_password(self):
        ctl.cmd_install(None, self.p); first = open(ctl.ENV).read(); self.sql.clear(); ctl.cmd_install(None, self.p)
        self.assertEqual(open(ctl.ENV).read(), first); self.assertFalse(any("ALTER ROLE web_rt LOGIN" in s for s in self.sql))

    def test_04_caddy_validate_failure_restores(self):
        self.fail.add("caddy validate")
        with self.assertRaises(SystemExit): ctl.cmd_install(None, self.p)
        self.assertEqual(open(ctl.CF).read(), CF0)

    def test_05_unhealthy_aborts_before_caddy(self):
        self.fail.add("health")
        with self.assertRaises(SystemExit): ctl.cmd_install(None, self.p)
        self.assertEqual(open(ctl.CF).read(), CF0); self.assertFalse(any("caddy" in " ".join(x) and "validate" in " ".join(x) for x in self.cmds))

    def test_06_missing_files_and_no_shared_network(self):
        os.remove(self.d + "/Dockerfile")
        with self.assertRaises(SystemExit): ctl.cmd_install(None, self.p)
        open(self.d + "/Dockerfile", "w").write("x"); orig = ctl.run
        def run2(cmd, input=None, check=True, timeout=300):
            if cmd[:2] == ["docker", "inspect"]: return 0, ("n1 " if ctl.PG in cmd else "n2 "), ""
            return orig(cmd, input, check, timeout)
        ctl.run = run2
        with self.assertRaises(SystemExit): ctl.network()

    def test_07_invite_hash_only_and_validation(self):
        a = type("A", (), {"slug": "acme", "email": "c@acme.com", "hours": 72})(); ctl.cmd_invite(a, self.p)
        line = [o for o in self.out if "/invite/" in o][0]; tok = line.rsplit("/", 1)[1]; self.assertRegex(tok, r"^[0-9a-hjkmnp-tv-z]{12}$")
        shown = [o for o in self.out if o.startswith("رمز الدعوة")][0]; self.assertTrue(shown.endswith("-".join(tok[i:i + 4] for i in range(0, 12, 4)))); self.assertTrue(any(o == "الصفحة: https://%s/invite" % ctl.HOST for o in self.out))
        self.assertTrue(any(o.endswith(hashlib.sha256(tok.encode()).hexdigest()[:8]) and "مرجع" in o for o in self.out))
        cmd = [c for c in self.cmds if "psql" in c][-1]; self.assertIn("h=" + hashlib.sha256(tok.encode()).hexdigest(), cmd); self.assertNotIn(tok, " ".join(" ".join(c) for c in self.cmds))
        for bad in ({"slug": "Bad Slug", "email": "c@acme.com", "hours": 72}, {"slug": "acme", "email": "x';drop--@a.co", "hours": 72}, {"slug": "acme", "email": "c@acme.com", "hours": 0}, {"slug": "acme", "email": "c@acme.com", "hours": 999}):
            with self.assertRaises(SystemExit): ctl.cmd_invite(type("A", (), bad)(), self.p)
        self.fail.add("psql")
        with self.assertRaises(SystemExit): ctl.cmd_invite(a, self.p)

    def test_08_down_removes_block_and_container(self):
        ctl.cmd_install(None, self.p); self.cmds.clear(); ctl.cmd_down(None, self.p)
        self.assertEqual(open(ctl.CF).read().strip(), CF0.strip()); self.assertTrue(any(c[:3] == ["docker", "rm", "-f"] for c in self.cmds))

    def test_09_package_builds_and_dockerfile_matches_layout(self):
        d = open(os.path.join(ROOT, "Dockerfile")).read(); self.assertIn("COPY service /app/web_portal/service", d); self.assertIn("web_portal.service.app", d); self.assertIn("USER 10002", d)
        for f in ("app.py", "security.py", "pages.py", "store.py", "__init__.py"): self.assertTrue(os.path.exists(os.path.join(ROOT, "service", f)))
if __name__ == "__main__": unittest.main()
