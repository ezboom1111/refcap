"""TDD for refguard.py — soft-block detection + value validation. stdlib only.
Run: python -m unittest test_refguard -v
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refguard as G


class SoftBlock(unittest.TestCase):
    def test_cloudflare_challenge_is_blocked(self):
        r = G.detect_softblock("<html><body>Just a moment...</body></html>", status=200)
        self.assertTrue(r["blocked"])
        self.assertEqual(r["verdict"], "blocked")

    def test_akamai_abck_unpassed_is_blocked(self):
        r = G.detect_softblock("<html>ok looking</html>", cookies={"_abck": "ABC~-1~xyz"}, selector_hit=True)
        self.assertTrue(r["blocked"])
        self.assertIn("akamai:_abck-unpassed", r["signals"])

    def test_http_4xx_is_blocked(self):
        r = G.detect_softblock("<html>err</html>", status=403)
        self.assertTrue(r["blocked"])

    # --- FALSE-POSITIVE guard (the whole point) ---------------------------
    def test_small_legit_page_is_not_blocked(self):
        # 200, tiny body, but the content selector DID hit -> must NOT be a block
        r = G.detect_softblock("<ul><li>one</li></ul>", status=200, selector_hit=True)
        self.assertFalse(r["blocked"])
        self.assertEqual(r["verdict"], "ok")

    def test_small_body_no_signal_no_selector_is_weak_ok_not_blocked(self):
        r = G.detect_softblock("<p>hi</p>", status=200)
        self.assertFalse(r["blocked"])
        self.assertEqual(r["verdict"], "weak_ok")

    def test_empty_shell_tiny_and_selector_missed_is_blocked(self):
        r = G.detect_softblock("<html><body></body></html>", status=200, selector_hit=False)
        self.assertTrue(r["blocked"])
        self.assertEqual(r["verdict"], "empty_shell")

    def test_selector_missed_on_normal_body_is_suspect_not_blocked(self):
        big = "<html><body>" + ("x" * 5000) + "</body></html>"
        r = G.detect_softblock(big, status=200, selector_hit=False)
        self.assertFalse(r["blocked"])
        self.assertEqual(r["verdict"], "suspect")

    def test_js_wall_is_not_a_block(self):
        r = G.detect_softblock("<noscript>Please enable JavaScript to run this app</noscript>", status=200)
        self.assertFalse(r["blocked"])
        self.assertEqual(r["verdict"], "js_wall")


class ValueValidation(unittest.TestCase):
    def test_clean_rows_no_issues(self):
        rows = [{"name": "A", "price": "1000"}, {"name": "B", "price": "2000"}]
        issues = G.validate_values(rows, {"name": {"required": True, "type": "str"},
                                          "price": {"type": "int", "min": 1, "max": 10_000_000}})
        self.assertEqual(issues, [])

    def test_empty_ratio_flagged(self):
        rows = [{"name": "A"}, {"name": ""}, {"name": ""}]
        issues = G.validate_values(rows, {"name": {"required": True, "max_empty_ratio": 0.1}})
        self.assertTrue(any("empty ratio" in i for i in issues))

    def test_out_of_range_flagged(self):
        rows = [{"price": "1000"}, {"price": "-5"}, {"price": "999999999"}]
        issues = G.validate_values(rows, {"price": {"type": "int", "min": 1, "max": 100_000_000}})
        self.assertTrue(any("< min" in i for i in issues))
        self.assertTrue(any("> max" in i for i in issues))

    def test_wrong_target_reject_regex_catches_ad(self):
        rows = [{"name": "상품A"}, {"name": "상품B"}, {"name": "광고: 지금 구매!"}]
        issues = G.validate_values(rows, {"name": {"reject_regex": r"광고|sponsored|\bAd\b"}})
        self.assertTrue(any("wrong-target" in i for i in issues))

    def test_uniform_flagged_and_allow_uniform_exempts(self):
        rows = [{"cat": "shoes"}] * 12
        flagged = G.validate_values(rows, {"cat": {}})
        self.assertTrue(any("identical" in i for i in flagged))
        exempt = G.validate_values(rows, {"cat": {"allow_uniform": True}})
        self.assertEqual(exempt, [])

    def test_type_coercion_failure_flagged(self):
        rows = [{"price": "1000"}, {"price": "not-a-number"}]
        issues = G.validate_values(rows, {"price": {"type": "int"}})
        self.assertTrue(any("not coercible" in i for i in issues))

    def test_empty_rows_reports(self):
        self.assertEqual(G.validate_values([], {"x": {}}), ["no rows to validate"])


if __name__ == "__main__":
    unittest.main()
