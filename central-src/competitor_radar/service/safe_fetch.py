# -*- coding: utf-8 -*-
"""جلب صفحات عامة فقط، بحماية SSRF: بروتوكول http/https، منافذ 80/443، رفض عناوين داخلية/محلية/خاصة (بعد حلّ DNS وتثبيت الـIP للاتصال)،
إعادة تحقق عند كل تحويل (≤3)، مهلة، سقف حجم، نوع محتوى نصي فقط، احترام robots.txt. لا يرسل أي كوكي/هوية/مفاتيح."""
import http.client, ipaddress, socket, ssl, urllib.parse, urllib.robotparser

UA = "CompetitorRadarBot/1.0 (+public pages only; respects robots.txt)"
MAX_BYTES = 1_000_000
OK_TYPES = ("text/html", "application/xhtml+xml", "application/json", "text/plain")


class FetchError(Exception):
    def __init__(self, code, msg=""):
        super().__init__(code + (": " + msg if msg else ""))
        self.code = code


def _is_ip(h):
    try:
        ipaddress.ip_address(h)
        return True
    except ValueError:
        return False


def _bad_ip(ip: str) -> bool:
    a = ipaddress.ip_address(ip)
    if isinstance(a, ipaddress.IPv6Address) and a.ipv4_mapped:
        a = a.ipv4_mapped
    return a.is_private or a.is_loopback or a.is_link_local or a.is_multicast or a.is_reserved or a.is_unspecified or (not a.is_global)


def check_url(url: str, resolver=socket.getaddrinfo, allow_private: bool = False):
    """→ (scheme, host, port, path_qs, [ip,...]) أو FetchError"""
    if not isinstance(url, str) or not (8 <= len(url) <= 500) or any(ord(c) < 33 or ord(c) == 127 for c in url):
        raise FetchError("bad_url")
    u = urllib.parse.urlsplit(url)
    if u.scheme not in ("http", "https"):
        raise FetchError("bad_scheme")
    if u.username or u.password:
        raise FetchError("credentials_in_url")
    host = (u.hostname or "").lower().rstrip(".")
    if not host or (not _is_ip(host) and "." not in host and not allow_private) or host.endswith((".local", ".internal", ".localdomain", ".lan")):
        raise FetchError("bad_host")
    try:
        port = u.port or (443 if u.scheme == "https" else 80)
    except ValueError:
        raise FetchError("bad_port")
    if port not in (80, 443) and not allow_private:
        raise FetchError("bad_port")
    try:
        ips = [host] if _is_ip(host) else sorted({ai[4][0] for ai in resolver(host, port, type=socket.SOCK_STREAM)})
    except (socket.gaierror, OSError):
        raise FetchError("dns_failed")
    if not ips:
        raise FetchError("dns_failed")
    if not allow_private and any(_bad_ip(i) for i in ips):
        raise FetchError("blocked_address")
    return u.scheme, host, port, (u.path or "/") + ("?" + u.query if u.query else ""), ips


class _Conn(http.client.HTTPConnection):
    """يتصل بالـIP المتحقق منه مباشرة (يمنع DNS rebinding) ويحتفظ باسم المضيف لـHost وSNI"""

    def __init__(self, host, ip, port, tls, timeout):
        super().__init__(ip, port, timeout=timeout)
        self._name, self._tls = host, tls

    def connect(self):
        s = socket.create_connection((self.host, self.port), self.timeout)
        self.sock = ssl.create_default_context().wrap_socket(s, server_hostname=self._name) if self._tls else s


def _default_transport(scheme, host, port, path, ip, timeout):
    c = _Conn(host, ip, port, scheme == "https", timeout)
    try:
        c.request("GET", path, headers={"Host": host if port in (80, 443) else "%s:%d" % (host, port), "User-Agent": UA,
                                         "Accept": "text/html,application/json;q=0.9,*/*;q=0.1", "Accept-Encoding": "identity"})
        r = c.getresponse()
        body = r.read(MAX_BYTES + 1)
        return r.status, {k.lower(): v for k, v in r.getheaders()}, body
    finally:
        c.close()


class Fetcher:
    def __init__(self, transport=None, resolver=socket.getaddrinfo, timeout=8.0, allow_private=False, respect_robots=True):
        self.transport, self.resolver, self.timeout = transport or _default_transport, resolver, timeout
        self.allow_private, self.robots = allow_private, respect_robots

    def _get(self, url):
        for _ in range(4):
            scheme, host, port, path, ips = check_url(url, self.resolver, self.allow_private)
            try:
                st, hd, body = self.transport(scheme, host, port, path, ips[0], self.timeout)
            except (socket.timeout, TimeoutError):
                raise FetchError("timeout")
            except (OSError, http.client.HTTPException):
                raise FetchError("network")
            if st in (301, 302, 303, 307, 308) and hd.get("location"):
                url = urllib.parse.urljoin(url, hd["location"])
                continue
            return st, hd, body, url
        raise FetchError("too_many_redirects")

    def _robots_ok(self, url):
        u = urllib.parse.urlsplit(url)
        try:
            st, _, body, _ = self._get("%s://%s/robots.txt" % (u.scheme, u.netloc))
        except FetchError:
            return True   # لا robots قابل للقراءة = لا قيد معلن
        if st != 200:
            return True
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(body[:200000].decode("utf-8", "replace").splitlines())
        return rp.can_fetch(UA, url) and rp.can_fetch("*", url)

    def fetch(self, url, robots=None):
        """→ {url, status, content_type, text} أو FetchError(code). صفحات تسجيل الدخول/الحماية تُرجع login_wall ولا تُخمَّن."""
        check_url(url, self.resolver, self.allow_private)
        if (self.robots if robots is None else robots) and not self._robots_ok(url):
            raise FetchError("robots_disallow")
        st, hd, body, final = self._get(url)
        if st >= 400:
            raise FetchError("http_%d" % st)
        ct = (hd.get("content-type") or "").split(";")[0].strip().lower()
        if ct not in OK_TYPES:
            raise FetchError("unsupported_type", ct)
        if len(body) > MAX_BYTES:
            raise FetchError("too_large")
        text = body.decode("utf-8", "replace")
        low = text[:6000].lower()
        if any(k in final.lower() for k in ("/login", "/accounts/login", "/checkpoint")) or ("login" in low and "password" in low and "<form" in low):
            raise FetchError("login_wall")
        return {"url": final, "status": st, "content_type": ct, "text": text}
