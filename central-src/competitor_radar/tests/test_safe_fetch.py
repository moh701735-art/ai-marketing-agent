import http.server, os, socket, sys, threading, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from competitor_radar.service.safe_fetch import FetchError, Fetcher, check_url


def res(ip):
    return lambda host, port, type=None: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]


def code(fn):
    try:
        fn()
    except FetchError as e:
        return e.code
    return None


class Check(unittest.TestCase):
    def test_blocks_internal_targets(self):
        cases = {"http://localhost/x": "bad_host", "http://127.0.0.1/": "blocked_address", "http://10.0.0.5/": "blocked_address", "http://192.168.1.1/": "blocked_address", "http://172.16.0.1/": "blocked_address",
                 "http://169.254.169.254/latest/meta-data": "blocked_address", "http://[::1]/": "blocked_address", "http://0.0.0.0/": "blocked_address", "http://[::ffff:127.0.0.1]/": "blocked_address",
                 "http://central-stg-pg/": "bad_host", "http://broker.internal/": "bad_host", "http://n8n/": "bad_host", "http://printer.local/": "bad_host",
                 "ftp://example.com/": "bad_scheme", "file:///etc/passwd": "bad_scheme", "http://user:pw@example.com/": "credentials_in_url", "https://example.com:5432/": "bad_port",
                 "https://example.com:22/": "bad_port", "javascript:alert(1)": "bad_scheme", "": "bad_url", "http://exa mple.com/": "bad_url"}
        for u, c in cases.items(): self.assertEqual(code(lambda: check_url(u, res("93.184.216.34"))), c, u)

    def test_hostname_resolving_to_private_blocked(self):
        for ip in ("127.0.0.1", "10.1.2.3", "169.254.169.254", "100.64.0.1", "::1"):
            self.assertEqual(code(lambda: check_url("https://evil.example.com/", res(ip))), "blocked_address", ip)

    def test_mixed_dns_answers_blocked(self):
        r = lambda host, port, type=None: [(2, 1, 6, "", ("93.184.216.34", port)), (2, 1, 6, "", ("10.0.0.1", port))]
        self.assertEqual(code(lambda: check_url("https://evil.example.com/", r)), "blocked_address")

    def test_public_ok_and_dns_failure(self):
        self.assertEqual(check_url("https://example.com/a?b=1", res("93.184.216.34"))[:4], ("https", "example.com", 443, "/a?b=1"))
        def boom(*a, **k): raise socket.gaierror()
        self.assertEqual(code(lambda: check_url("https://example.com/", boom)), "dns_failed")


class Fake:
    def __init__(self, routes): self.routes, self.log = routes, []
    def __call__(self, scheme, host, port, path, ip, timeout):
        self.log.append((host, path, ip)); r = self.routes.get((host, path)) or self.routes.get(path)
        if isinstance(r, Exception): raise r
        return r or (404, {}, b"")


class Fetch(unittest.TestCase):
    def F(self, routes, **k): return Fetcher(transport=Fake(routes), resolver=res("93.184.216.34"), **k)

    def test_ok_html(self):
        f = self.F({"/robots.txt": (404, {}, b""), "/p": (200, {"content-type": "text/html; charset=utf-8"}, "<title>متجر</title>".encode())})
        r = f.fetch("https://shop.example.com/p"); self.assertEqual((r["status"], r["content_type"]), (200, "text/html")); self.assertIn("متجر", r["text"])

    def test_redirect_to_private_blocked_each_hop(self):
        calls = []
        def resolver(host, port, type=None):
            calls.append(host); return [(2, 1, 6, "", ("10.0.0.9" if host == "internal.example.com" else "93.184.216.34", port))]
        t = Fake({"/robots.txt": (404, {}, b""), "/a": (302, {"location": "http://internal.example.com/secret"}, b"")})
        self.assertEqual(code(lambda: Fetcher(transport=t, resolver=resolver).fetch("https://shop.example.com/a")), "blocked_address"); self.assertNotIn("internal.example.com", [x[0] for x in t.log])

    def test_redirect_loop_limited(self):
        self.assertEqual(code(lambda: self.F({"/robots.txt": (404, {}, b""), "/a": (302, {"location": "/a"}, b"")}).fetch("https://shop.example.com/a")), "too_many_redirects")

    def test_connects_to_pinned_ip(self):
        t = Fake({"/robots.txt": (404, {}, b""), "/p": (200, {"content-type": "text/html"}, b"<title>x</title>")}); Fetcher(transport=t, resolver=res("93.184.216.34")).fetch("https://shop.example.com/p")
        self.assertTrue(all(x[2] == "93.184.216.34" for x in t.log))

    def test_robots_disallow(self):
        f = self.F({"/robots.txt": (200, {"content-type": "text/plain"}, b"User-agent: *\nDisallow: /private"), "/private/x": (200, {"content-type": "text/html"}, b"hi")})
        self.assertEqual(code(lambda: f.fetch("https://shop.example.com/private/x")), "robots_disallow")
        self.assertEqual(code(lambda: self.F({"/robots.txt": (200, {}, b"User-agent: *\nDisallow: /private"), "/private/x": (200, {"content-type": "text/html"}, b"hi")}, respect_robots=False).fetch("https://shop.example.com/private/x")), None)

    def test_http_errors_login_wall_type_size_timeout(self):
        ok = {"/robots.txt": (404, {}, b"")}
        self.assertEqual(code(lambda: self.F({**ok, "/p": (403, {}, b"")}).fetch("https://a.example.com/p")), "http_403")
        self.assertEqual(code(lambda: self.F({**ok, "/p": (429, {}, b"")}).fetch("https://a.example.com/p")), "http_429")
        self.assertEqual(code(lambda: self.F({**ok, "/p": (200, {"content-type": "text/html"}, b"<form><input name=password>login</form>")}).fetch("https://a.example.com/p")), "login_wall")
        self.assertEqual(code(lambda: self.F({**ok, "/accounts/login/": (200, {"content-type": "text/html"}, b"x")}).fetch("https://a.example.com/accounts/login/")), "login_wall")
        self.assertEqual(code(lambda: self.F({**ok, "/p": (200, {"content-type": "application/pdf"}, b"%PDF")}).fetch("https://a.example.com/p")), "unsupported_type")
        self.assertEqual(code(lambda: self.F({**ok, "/p": (200, {"content-type": "text/html"}, b"x" * 1_000_001)}).fetch("https://a.example.com/p")), "too_large")
        self.assertEqual(code(lambda: self.F({**ok, "/p": socket.timeout()}).fetch("https://a.example.com/p")), "timeout")
        self.assertEqual(code(lambda: self.F({**ok, "/p": ConnectionResetError()}).fetch("https://a.example.com/p")), "network")

    def test_real_pinned_connection_to_local_server(self):
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(s):
                body = b"<title>local</title>" if s.path == "/p" else b""
                s.send_response(200 if body else 404); s.send_header("content-type", "text/html"); s.send_header("content-length", str(len(body))); s.end_headers(); s.wfile.write(body)
            def log_message(s, *a): pass
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            url = "http://127.0.0.1:%d/p" % srv.server_address[1]
            self.assertIn(code(lambda: Fetcher().fetch(url)), ("blocked_address", "bad_port"))   # الافتراضي يمنع المحلي
            self.assertIn("local", Fetcher(allow_private=True).fetch(url)["text"])
        finally: srv.shutdown()


if __name__ == "__main__":
    unittest.main(verbosity=1)
