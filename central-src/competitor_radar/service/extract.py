# -*- coding: utf-8 -*-
"""تحويل المصادر المتاحة إلى «عينات» نصية قصيرة بمعرّف ثابت: نص يلصقه المستخدم (المصدر الأساسي)، وسوم HTML العامة (title/description/og)،
و oEmbed الرسمي (JSON). كل عينة: {id, src, text}. لا نخترع شي: ما نقدر نقرأه ما يدخل."""
import hashlib, html, json, re
from html.parser import HTMLParser

MAX_SAMPLE = 1500
MAX_SAMPLES = 30
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f‎‏‪-‮⁦-⁩]")


def clean(s: str) -> str:
    return re.sub(r"[ \t ]+", " ", _CTRL.sub("", str(s or ""))).strip()


def sample(src: str, text: str):
    t = clean(text)[:MAX_SAMPLE]
    if len(t) < 8:
        return None
    return {"id": hashlib.sha256(t.encode("utf-8")).hexdigest()[:12], "src": src, "text": t}


def from_pasted(text: str):
    """يقسّم على سطر فارغ أو --- ؛ كل مقطع عينة (حد 30)"""
    parts = [p for p in re.split(r"\n\s*\n|\n-{3,}\n", str(text or "")) if p.strip()]
    out = [s for s in (sample("pasted", p) for p in parts[:MAX_SAMPLES * 2]) if s]
    return out[:MAX_SAMPLES]


class _Meta(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.title, self._in_title, self.lang = {}, "", False, ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html" and a.get("lang"): self.lang = a["lang"][:12]
        if tag == "title": self._in_title = True
        if tag == "meta":
            k = (a.get("property") or a.get("name") or "").lower()
            if k in ("description", "og:title", "og:description", "og:site_name", "twitter:title", "twitter:description", "keywords") and a.get("content"):
                self.meta.setdefault(k, a["content"])

    def handle_endtag(self, tag):
        if tag == "title": self._in_title = False

    def handle_data(self, d):
        if self._in_title and len(self.title) < 300: self.title += d


def from_html(page: str):
    """وسوم عامة فقط (لا نمسح النص الكامل للصفحة): → (عينات، معلومات {name, lang})"""
    p = _Meta()
    try: p.feed(str(page or "")[:1_000_000])
    except Exception: pass
    m = p.meta
    name = clean(m.get("og:site_name") or m.get("og:title") or p.title)[:80]
    seen, out = set(), []
    for k, v in (("title", p.title), ("og:title", m.get("og:title")), ("description", m.get("description")), ("og:description", m.get("og:description")),
                 ("twitter:description", m.get("twitter:description")), ("keywords", m.get("keywords"))):
        s = sample("html_meta", html.unescape(v or ""))
        if s and s["id"] not in seen:
            seen.add(s["id"]); out.append(s)
    return out, {"name": name, "lang": p.lang}


def from_oembed(raw: str):
    try: d = json.loads(raw)
    except Exception: return [], {}
    if not isinstance(d, dict): return [], {}
    out = [s for s in (sample("oembed", d.get("title") or ""),) if s]
    return out, {"name": clean(d.get("author_name") or "")[:80]}


def dedup(samples):
    seen, out = set(), []
    for s in samples:
        if s and s["id"] not in seen:
            seen.add(s["id"]); out.append(s)
    return out[:MAX_SAMPLES]
