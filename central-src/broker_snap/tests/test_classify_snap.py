import os, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load():
    calls = []
    ns = {"_tiktok": lambda st, b: calls.append((st, b)) or ("ST", st, b)}
    exec(open(os.path.join(ROOT, "classify_snap.py"), encoding="utf-8").read(), ns)
    return ns["_snapchat"], calls
class T(unittest.TestCase):
    def test_ok_response_passes_empty_body(self):
        f, c = load(); f(200, {"request_status": "SUCCESS", "adsquads": [{"sub_request_status": "SUCCESS"}]}); self.assertEqual(c[-1], (200, {}))
    def test_200_with_top_level_error_and_nested_reason(self):   # the real incident: HTTP 200 + ERROR
        f, c = load(); f(200, {"request_status": "ERROR", "request_id": "r1", "adsquads": [{"sub_request_status": "ERROR", "sub_request_error_reason": "Budget below minimum", "adsquad": {}}]})
        st, b = c[-1]; self.assertEqual(st, 400); self.assertIn("Budget below minimum", b["message"])
    def test_top_level_messages_and_code_collected_once(self):
        f, c = load(); f(400, {"request_status": "ERROR", "debug_message": "Invalid targeting", "display_message": "Invalid targeting", "error_code": "E2001"})
        st, b = c[-1]; self.assertEqual(st, 400); self.assertEqual(b["message"], "Invalid targeting | E2001")
    def test_no_message_fields_keeps_old_behaviour(self):
        f, c = load(); f(500, {"foo": 1}); self.assertEqual(c[-1], (500, {})); f(200, {"request_status": "ERROR"}); self.assertEqual(c[-1], (400, {}))
    def test_non_dict_body(self):
        f, c = load(); f(502, "<html>"); self.assertEqual(c[-1], (502, {}))
    def test_message_is_bounded_and_nested_depth_limited(self):
        f, c = load(); deep = cur = {}
        for _ in range(12): cur["x"] = {}; cur = cur["x"]
        cur["display_message"] = "too deep"; f(400, {"request_status": "ERROR", **deep}); self.assertEqual(c[-1], (400, {}))
        f(400, {"request_status": "ERROR", "adsquads": [{"sub_request_error_reason": "A" * 900}]}); self.assertLessEqual(len(c[-1][1]["message"]), 380)
if __name__ == "__main__": unittest.main()
