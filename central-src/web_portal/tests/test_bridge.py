import importlib.util, os, shutil, sys, tempfile, unittest
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..")
spec = importlib.util.spec_from_file_location("ctl", os.path.join(ROOT, "deploy", "web_portal_ctl.py")); ctl = importlib.util.module_from_spec(spec); spec.loader.exec_module(ctl)
sys.path.insert(0, ROOT)
CF0 = ("{\n\temail a@b.co\n}\n\nagent.mohammedai.tech {\n\tencode zstd gzip\n\t@tg path POST /webhook/tg-ingress\n\treverse_proxy @tg n8n:5678\n"
       "\thandle /tiktok-code {\n\t\trespond `<html>code</html>`\n\t}\n\thandle {\n\t\trespond \"\" 404\n\t}\n}\n\n" + "# BEGIN web-portal (x)\napp.mohammedai.tech {\n\treverse_proxy web-portal:8090\n}\n# END web-portal\n")
WANT = "https://app.mohammedai.tech/tiktok/callback?state=w-selftest&auth_code=SELFTEST"


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); ctl.ROOT = self.d; ctl.CF = self.d + "/Caddyfile"; ctl.ENV = self.d + "/web.env"
        open(ctl.CF, "w").write(CF0); self.cmds = []; self.invalid = set(); self.works = {"expression"}; self.sig = {"expression": "{http.request.uri.query.state}.startsWith", "vars_regexp": "vars_regexp", "expression-short": "{query.state}.startsWith"}; self.out = []; self.restarted = 0
        def run(cmd, input=None, check=True, timeout=300):
            self.cmds.append(list(cmd)); cur = open(ctl.CF).read(); j = " ".join(cmd)
            if "caddy validate" in j or ("caddy" in cmd and "validate" in cmd):
                for v in self.invalid:
                    if v in cur: return 1, "", "bad matcher " + v
                return 0, "", ""
            if cmd[0] == "curl":
                if "state=w-selftest" in j:
                    ok = any(self.sig[w] in cur for w in self.works) and ctl.BR_BEGIN in cur
                    return (0, "302 " + WANT, "") if ok else (0, "200 ", "")
                return 0, "200 ", ""
            return 0, "", ""
        ctl.run = run; ctl.healthy = lambda seconds=40: True; ctl.start_container = lambda: setattr(self, "restarted", self.restarted + 1)
    def tearDown(self): shutil.rmtree(self.d, ignore_errors=True)
    def o(self, *a): self.out.append(" ".join(map(str, a)))

    def test_01_insert_before_anchor_idempotent_remove_exact(self):
        v = dict(ctl.bridge_variants())["expression"]; t = ctl.update_bridge(CF0, v)
        self.assertEqual(t.count(ctl.BR_BEGIN), 1); self.assertLess(t.index(ctl.BR_BEGIN), t.index("handle /tiktok-code")); self.assertIn("\t" + ctl.BR_BEGIN, t)
        self.assertIn("redir @webbridge https://app.mohammedai.tech/tiktok/callback?{http.request.uri.query} 302", t)
        self.assertEqual(ctl.update_bridge(t, v), t); self.assertEqual(ctl.update_bridge(t), CF0)
        self.assertEqual(ctl.update_bridge(CF0), CF0)
        t2 = ctl.update_bridge(t, dict(ctl.bridge_variants())["vars_regexp"]); self.assertEqual(t2.count(ctl.BR_BEGIN), 1); self.assertIn("vars_regexp", t2); self.assertNotIn("startsWith", t2)

    def test_02_anchor_must_be_unique_and_markers_complete(self):
        for bad in (CF0.replace("\thandle /tiktok-code {", "\thandle /other {"), CF0.replace("\thandle {", "\thandle /tiktok-code {")):
            with self.assertRaises(SystemExit): ctl.update_bridge(bad, ["x"])
        with self.assertRaises(SystemExit): ctl.update_bridge(CF0 + ctl.BR_BEGIN + "\n", ["x"])

    def test_03_first_variant_passes_selftest_env_written_container_restarted(self):
        self.assertTrue(ctl.cmd_install_bridge(None, self.o)); cur = open(ctl.CF).read()
        self.assertIn("expression {http.request.uri.query.state}", cur); self.assertEqual(ctl.read_env().get("TIKTOK_REDIRECT"), "https://agent.mohammedai.tech/tiktok-code"); self.assertEqual(self.restarted, 1)
        self.assertTrue(any(c[0] == "curl" and "--resolve" in c for c in self.cmds)); self.assertTrue(any("✅" in x for x in self.out))
        self.assertTrue(os.path.exists(ctl.CF + ".prebridge")); self.assertEqual(open(ctl.CF + ".prebridge").read(), CF0)

    def test_04_falls_through_validate_failure_to_next_variant(self):
        self.invalid = {"startsWith"}; self.works = {"vars_regexp"}
        self.assertTrue(ctl.cmd_install_bridge(None, self.o)); self.assertIn("vars_regexp", open(ctl.CF).read()); self.assertNotIn("startsWith", open(ctl.CF).read())

    def test_05_selftest_failure_restores_and_tries_next(self):
        self.works = {"expression-short"}; self.assertTrue(ctl.cmd_install_bridge(None, self.o)); self.assertIn("expression {query.state}", open(ctl.CF).read())

    def test_06_all_variants_fail_restores_exact_original_no_env_no_restart(self):
        self.works = set()
        with self.assertRaises(SystemExit): ctl.cmd_install_bridge(None, self.o)
        self.assertEqual(open(ctl.CF).read(), CF0); self.assertNotIn("TIKTOK_REDIRECT", ctl.read_env()); self.assertEqual(self.restarted, 0)

    def test_07_bridge_down_removes_block_and_env(self):
        ctl.cmd_install_bridge(None, self.o); self.restarted = 0; ctl.cmd_bridge_down(None, self.o)
        self.assertEqual(open(ctl.CF).read(), CF0); self.assertNotIn("TIKTOK_REDIRECT", ctl.read_env()); self.assertEqual(self.restarted, 1)

    def test_08_install_twice_is_stable(self):
        ctl.cmd_install_bridge(None, self.o); once = open(ctl.CF).read(); ctl.cmd_install_bridge(None, self.o); self.assertEqual(open(ctl.CF).read(), once)

    def test_09_control_request_redirected_is_rejected(self):
        orig = ctl.run
        def run(cmd, input=None, check=True, timeout=300):
            if cmd[0] == "curl" and "state=other" in " ".join(cmd): return 0, "302 https://x", ""
            return orig(cmd, input, check, timeout)
        ctl.run = run
        with self.assertRaises(SystemExit): ctl.cmd_install_bridge(None, self.o)
        self.assertEqual(open(ctl.CF).read(), CF0)


class TState(unittest.TestCase):
    def test_state_helpers(self):
        from service import security as sec
        s = sec.new_state(); self.assertTrue(s.startswith("w-")); self.assertTrue(sec.valid_state(s)); self.assertTrue(sec.valid_state(sec.new_token()))
        for bad in ("", "w-", "w-abc", None, s + "!"): self.assertFalse(sec.valid_state(bad))


if __name__ == "__main__": unittest.main()
