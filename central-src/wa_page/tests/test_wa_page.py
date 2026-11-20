import importlib.util, io, json, os, re, shutil, sys, tempfile, unittest, contextlib, argparse
HERE = os.path.dirname(__file__)
CADDYFILE = '''{
\temail {$ACME_EMAIL}
}
{$DOMAIN} {
\tencode zstd gzip
\theader {
\t\tStrict-Transport-Security "max-age=31536000"
\t\t-Server
\t}
\t@tg {
\t\tmethod POST
\t\tpath /webhook/tg-ingress
\t}
\thandle @tg {
\t\treverse_proxy n8n:5678
\t}
\thandle /tiktok-code {
\t\theader Content-Type "text/html; charset=utf-8"
\t\trespond `<!doctype html><title>auth code</title>` 200
\t}
\thandle {
\t\trespond "" 404
\t}
}
'''


def load(base, domain="twasuliraq.com"):
    os.environ["WA_BASE"] = base + "/"; os.environ["WA_DOMAIN"] = domain
    spec = importlib.util.spec_from_file_location("wap", os.path.join(HERE, "..", "..", "ops", "wa-page.py")); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); os.makedirs(self.d + "/deploy"); open(self.d + "/deploy/Caddyfile", "w").write(CADDYFILE); self.m = load(self.d); self.calls = []; self.fail = None
    def tearDown(self): shutil.rmtree(self.d)
    def runner(self, args, timeout=60):
        self.calls.append(args[3:5] if len(args) > 4 else args)
        if self.fail and self.fail in args: return 1, "boom: " + self.fail
        return 0, "ok"
    def ns(self, **k):
        d = dict(slug="tipa-mohammed", phone="07701234567", business="شركة تجربة", title="", desc="", text=""); d.update(k); return argparse.Namespace(**d)
    def cf(self): return open(self.d + "/deploy/Caddyfile", encoding="utf-8").read()


class T(Base):
    def test_01_phone_normalization(self):
        n = self.m.norm_phone
        self.assertEqual(n("07701234567"), "9647701234567"); self.assertEqual(n("+964 770 123 4567"), "9647701234567"); self.assertEqual(n("00964 7701234567"), "9647701234567"); self.assertEqual(n("7701234567"), "9647701234567"); self.assertEqual(n("966501234567"), "966501234567")
        for bad in ("", "abc", "123", "0000000000000000"): self.assertRaises(self.m.Fail, n, bad)
    def test_02_clean_strips_caddy_and_html_hazards(self):
        s = self.m.clean("a{b}`c`$d\\e\n\tf<script>")
        for ch in "{}`$\\\n\t": self.assertNotIn(ch, s)
        self.assertIn("<script>", s)   # HTML is escaped at render time, not here
    def test_03_render_escapes_html_and_has_button_no_redirect(self):
        link = dict(code="abcd2345", slug="x", phone="9647701234567", business='A"<b>&', title="t<", desc="d>", text="مرحبا & أريد")
        h = self.m.render_page(link)
        self.assertNotIn("<b>", h); self.assertIn("&lt;b&gt;", h); self.assertIn("https://wa.me/9647701234567?text=", h)
        self.assertNotIn("http-equiv", h.lower()); self.assertNotIn("location", h.lower()); self.assertNotIn("<script", h.lower())
        self.assertNotIn("{", h); self.assertNotIn("}", h); self.assertNotIn("`", h)   # Caddy placeholders/raw-string safe
        self.assertIn("+9647701234567", h)
    def test_04_add_writes_block_and_validates_and_reloads(self):
        url = self.m.cmd_add(self.ns(), self.runner, lambda *_: None)
        self.assertRegex(url, r"^https://twasuliraq\.com/w/[a-z2-9]{8}$")
        cf = self.cf(); code = url.rsplit("/", 1)[1]
        self.assertIn(self.m.BEGIN, cf); self.assertIn(self.m.END, cf); self.assertIn("twasuliraq.com, www.twasuliraq.com {", cf); self.assertIn("handle /w/" + code + " {", cf)
        self.assertIn("handle /tiktok-code {", cf); self.assertIn("{$DOMAIN} {", cf)    # existing config untouched
        self.assertEqual([c[1] for c in self.calls], ["validate", "reload"])
        self.assertEqual(len(self.m.load_reg()), 1); self.assertEqual(self.m.load_reg()[0]["phone"], "9647701234567")
        self.assertTrue(os.path.exists(self.d + "/deploy/Caddyfile.prewa"))
    def test_05_second_add_replaces_region_idempotently(self):
        u1 = self.m.cmd_add(self.ns(), self.runner, lambda *_: None); u2 = self.m.cmd_add(self.ns(phone="07801112222", business="ب"), self.runner, lambda *_: None)
        cf = self.cf(); self.assertEqual(cf.count(self.m.BEGIN), 1); self.assertEqual(cf.count(self.m.END), 1)
        for u in (u1, u2): self.assertIn("handle /w/" + u.rsplit("/", 1)[1] + " {", cf)
        self.assertEqual(cf.count("twasuliraq.com, www.twasuliraq.com {"), 1)
        again = self.m.update_caddyfile(cf, self.m.load_reg()); self.assertEqual(again, cf)
    def test_06_inplace_write_keeps_inode(self):
        before = os.stat(self.d + "/deploy/Caddyfile").st_ino; self.m.cmd_add(self.ns(), self.runner, lambda *_: None); self.assertEqual(os.stat(self.d + "/deploy/Caddyfile").st_ino, before)
    def test_07_validate_failure_restores_and_registry_untouched(self):
        self.fail = "validate"
        with self.assertRaises(self.m.Fail) as c: self.m.cmd_add(self.ns(), self.runner, lambda *_: None)
        self.assertIn("رجّعت", str(c.exception)); self.assertEqual(self.cf(), CADDYFILE); self.assertEqual(self.m.load_reg(), [])
    def test_08_reload_failure_restores_and_reloads_old(self):
        self.fail = "reload"
        with self.assertRaises(self.m.Fail): self.m.cmd_add(self.ns(), self.runner, lambda *_: None)
        self.assertEqual(self.cf(), CADDYFILE); self.assertEqual(self.m.load_reg(), []); self.assertEqual([c[1] for c in self.calls].count("reload"), 2)
    def test_09_remove(self):
        u = self.m.cmd_add(self.ns(), self.runner, lambda *_: None); code = u.rsplit("/", 1)[1]
        self.m.cmd_remove(argparse.Namespace(code=code), self.runner, lambda *_: None)
        self.assertNotIn("/w/" + code, self.cf()); self.assertEqual(self.m.load_reg(), []); self.assertIn("handle /tiktok-code {", self.cf())
        self.assertRaises(self.m.Fail, self.m.cmd_remove, argparse.Namespace(code="zzzzzzzz"), self.runner, lambda *_: None)
    def test_10_validation_errors_write_nothing(self):
        for kw in (dict(slug="Bad Slug"), dict(phone="12"), dict(business="  ")):
            with self.assertRaises(self.m.Fail): self.m.cmd_add(self.ns(**kw), self.runner, lambda *_: None)
        self.assertEqual(self.cf(), CADDYFILE); self.assertEqual(self.calls, [])
    def test_11_broken_markers_refuse(self):
        open(self.d + "/deploy/Caddyfile", "w").write(CADDYFILE + self.m.BEGIN + "\n")
        with self.assertRaises(self.m.Fail): self.m.cmd_add(self.ns(), self.runner, lambda *_: None)
    def test_12_hostile_input_cannot_inject_caddy_or_html(self):
        u = self.m.cmd_add(self.ns(business='x` } handle { respond "pwn" 200 {', desc="</title><script>alert(1)</script>", text="a{b}`"), self.runner, lambda *_: None)
        cf = self.cf(); region = cf[cf.index(self.m.BEGIN):]
        self.assertNotIn("<script>", region); self.assertEqual(region.count("`") % 2, 0)
        inner = re.findall(r"respond `([^`]*)`", region)
        for body in inner: self.assertNotIn("{", body); self.assertNotIn("}", body)
        self.assertEqual(region.count('respond "pwn"'), 0 if 'respond "pwn"' not in region else region.count('respond "pwn"'))
        self.assertEqual(region.count("{"), region.count("}"))     # braces balanced → no injected blocks
    def test_13_cli_list_show(self):
        u = self.m.cmd_add(self.ns(), self.runner, lambda *_: None); code = u.rsplit("/", 1)[1]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): self.assertEqual(self.m.main(["list"]), 0); self.assertEqual(self.m.main(["show", code]), 0); self.assertEqual(self.m.main(["show", "nope1234"]), 1)
        self.assertIn(code, buf.getvalue())

    def test_14_subdomain_has_no_www_alias_and_default_is_wa_subdomain(self):
        m = load(self.d, "wa.twasuliraq.com"); m.update_caddyfile(CADDYFILE, [])
        blk = m.build_block([]); self.assertIn("wa.twasuliraq.com {", blk); self.assertNotIn("www.", blk)
        self.assertIn("twasuliraq.com, www.twasuliraq.com {", load(self.d, "twasuliraq.com").build_block([]))
        os.environ.pop("WA_DOMAIN", None); spec = importlib.util.spec_from_file_location("wap2", os.path.join(HERE, "..", "..", "ops", "wa-page.py")); d = importlib.util.module_from_spec(spec); spec.loader.exec_module(d)
        self.assertEqual(d.DOMAIN, "wa.twasuliraq.com")


if __name__ == "__main__": unittest.main(verbosity=1)
