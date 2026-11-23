# -*- coding: utf-8 -*-
"""محوّل LLM مستقل للرادار (مفتاحه RADAR_LLM_API_KEY الخاص، ما يلمس مفاتيح الـBroker). الواجهة: complete_json(system, user, max_tokens) → dict.
أي فشل يرمي LLMUnavailable (الرادار يكمل بالتحليل الحتمي بدون LLM). لا يطبع المفتاح ولا نص المستخدم بالأخطاء."""
import json, time, urllib.error, urllib.request


class LLMUnavailable(Exception):
    pass


class NullLLM:
    def complete_json(self, system, user, max_tokens=1200):
        raise LLMUnavailable("no_llm_configured")


class GeminiLLM:
    URL = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent"

    def __init__(self, api_key, model="gemini-2.5-flash", timeout=20.0, retries=2, opener=None, sleep=time.sleep):
        if not api_key: raise LLMUnavailable("no_key")
        self.key, self.model, self.timeout, self.retries = api_key, model, timeout, max(0, min(2, retries))
        self.opener, self.sleep = opener or urllib.request.urlopen, sleep

    def complete_json(self, system, user, max_tokens=1200):
        body = json.dumps({"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": user}]}],
                           "generationConfig": {"temperature": 0.3, "maxOutputTokens": int(max_tokens), "responseMimeType": "application/json", "thinkingConfig": {"thinkingBudget": 0}}}).encode("utf-8")
        last = "error"
        for attempt in range(self.retries + 1):
            req = urllib.request.Request(self.URL % self.model, data=body, headers={"content-type": "application/json", "x-goog-api-key": self.key}, method="POST")
            try:
                with self.opener(req, timeout=self.timeout) as r:
                    d = json.loads(r.read().decode("utf-8"))
                txt = d["candidates"][0]["content"]["parts"][0]["text"]
                out = json.loads(txt)
                if not isinstance(out, dict): raise ValueError("not_object")
                return out
            except urllib.error.HTTPError as e:
                last = "http_%d" % e.code
                if e.code not in (429, 500, 502, 503, 504): break
            except (urllib.error.URLError, TimeoutError, OSError):
                last = "network"
            except (KeyError, IndexError, ValueError, TypeError):
                last = "bad_response"
                break
            if attempt < self.retries: self.sleep(1.5 * (attempt + 1))
        raise LLMUnavailable(last)
