"""TDD for refguard.py (hardened v2). stdlib only.
Run: python -m unittest test_refguard -v
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refguard as G

BIG = "x" * 5000


class SoftBlock(unittest.TestCase):
    def test_cloudflare_challenge_shell_is_blocked(self):
        r = G.detect_softblock("<html><body>Just a moment...</body></html>", status=200, selector_hit=False)
        self.assertTrue(r["blocked"]); self.assertEqual(r["verdict"], "blocked")

    def test_akamai_abck_unpassed_blocked_even_with_hit(self):
        r = G.detect_softblock("<html>ok</html>", cookies={"_abck": "ABC~-1~xyz"}, selector_hit=True)
        self.assertTrue(r["blocked"])

    # --- FALSE-POSITIVE fixes (v1 bugs) -----------------------------------
    def test_marker_in_normal_article_with_hit_is_not_blocked(self):
        # v1 BUG: "access denied" in a real article + selector_hit=True returned blocked.
        r = G.detect_softblock("<article>we discuss access denied errors " + BIG + "</article>", selector_hit=True)
        self.assertFalse(r["blocked"]); self.assertEqual(r["verdict"], "ok")

    def test_marker_on_large_body_unknown_selector_is_suspect_not_blocked(self):
        r = G.detect_softblock("<div>access denied appears here " + BIG + "</div>", selector_hit=None)
        self.assertFalse(r["blocked"]); self.assertEqual(r["verdict"], "suspect")

    def test_http_404_is_http_error_not_blocked(self):
        r = G.detect_softblock("<html>Not Found</html>", status=404)
        self.assertFalse(r["blocked"]); self.assertEqual(r["verdict"], "http_error")

    def test_http_500_is_http_error_not_blocked(self):
        r = G.detect_softblock("", status=503)
        self.assertFalse(r["blocked"]); self.assertEqual(r["verdict"], "http_error")

    def test_http_403_with_marker_is_blocked(self):
        r = G.detect_softblock("Access Denied", status=403)
        self.assertTrue(r["blocked"])

    def test_http_403_without_marker_is_suspect(self):
        r = G.detect_softblock("<html>forbidden page " + BIG + "</html>", status=403, selector_hit=None)
        self.assertEqual(r["verdict"], "suspect"); self.assertFalse(r["blocked"])

    def test_markerless_403_selector_false_is_suspect_not_blocked(self):
        # Codex 3rd: a markerless 403 (permission error) must not be conflated with an anti-bot wall.
        r = G.detect_softblock("<html>forbidden " + BIG + "</html>", status=403, selector_hit=False)
        self.assertEqual(r["verdict"], "suspect"); self.assertFalse(r["blocked"])

    def test_tiny_challenge_blocks_even_if_selector_hit(self):
        # Codex 3rd: a 29-byte "Just a moment" must not be rescued by a spurious selector hit.
        r = G.detect_softblock("Just a moment...", status=200, selector_hit=True)
        self.assertTrue(r["blocked"]); self.assertEqual(r["verdict"], "blocked")

    def test_large_article_with_marker_and_hit_still_ok(self):
        # ...but a real large article that mentions a marker phrase, with a genuine hit, stays ok.
        r = G.detect_softblock("<article>access denied is discussed " + BIG + "</article>", selector_hit=True)
        self.assertEqual(r["verdict"], "ok"); self.assertFalse(r["blocked"])

    def test_bad_tiny_body_type_does_not_crash(self):
        r = G.detect_softblock("<p>hi</p>", tiny_body="notint", selector_hit=True)
        self.assertEqual(r["verdict"], "ok")

    def test_small_legit_page_with_hit_is_ok(self):
        r = G.detect_softblock("<ul><li>one</li></ul>", selector_hit=True)
        self.assertFalse(r["blocked"]); self.assertEqual(r["verdict"], "ok")

    def test_small_body_no_signal_no_selector_is_weak_ok(self):
        self.assertEqual(G.detect_softblock("<p>hi</p>")["verdict"], "weak_ok")

    def test_empty_shell_blocked(self):
        r = G.detect_softblock("<html></html>", selector_hit=False)
        self.assertEqual(r["verdict"], "empty_shell"); self.assertTrue(r["blocked"])

    def test_js_wall_not_blocked(self):
        r = G.detect_softblock("<noscript>Please enable JavaScript to run this app</noscript>")
        self.assertEqual(r["verdict"], "js_wall"); self.assertFalse(r["blocked"])

    def test_bytes_html_does_not_crash(self):
        r = G.detect_softblock(b"<html>bytes body</html>", selector_hit=True)
        self.assertEqual(r["verdict"], "ok")

    def test_hostile_cookie_does_not_crash(self):
        class Boom:
            def get(self, k): raise RuntimeError("nope")
        r = G.detect_softblock("<p>x</p>", cookies=Boom(), selector_hit=True)
        self.assertIn("cookie-scan-error", r["signals"])

    def test_empty_body_with_selector_hit_is_empty_shell(self):   # C2.1: a hit on an empty body is impossible
        r = G.detect_softblock(html="", status=200, selector_hit=True, tiny_body=500)
        self.assertEqual(r["verdict"], "empty_shell")
        self.assertTrue(r["blocked"])
        self.assertIn("empty-body-selector-conflict", r["signals"])

    def test_negative_tiny_body_does_not_disable_challenge(self):   # C2.2: invalid threshold must not slip a shell through
        r = G.detect_softblock(html="Just a moment...", status=200, selector_hit=True, tiny_body=-1)
        self.assertEqual(r["verdict"], "blocked")
        self.assertIn("invalid-tiny_body-defaulted", r["signals"])

    def test_string_status_is_suspect_not_ok(self):   # C2.3: a malformed status can't be read as a clean 200
        r = G.detect_softblock(html="x" * 5000, status="403", selector_hit=True, tiny_body=500)
        self.assertEqual(r["verdict"], "suspect")
        self.assertTrue(any(s.startswith("invalid-status:") for s in r["signals"]))


class ValueValidation(unittest.TestCase):
    def test_clean_no_issues(self):
        rows = [{"name": "A", "price": "1000"}, {"name": "B", "price": "2000"}]
        self.assertEqual(G.validate_values(rows, {"name": {"required": True, "type": "str"},
                                                  "price": {"type": "int", "min": 1, "max": 10_000_000}}), [])

    def test_empty_ratio_independent_of_required(self):
        # v1 BUG: empty ratio only checked when required=True.
        rows = [{"n": "A"}, {"n": ""}, {"n": ""}]
        issues = G.validate_values(rows, {"n": {"max_empty_ratio": 0.1}})
        self.assertTrue(any("empty ratio" in i for i in issues))

    def test_out_of_range(self):
        rows = [{"p": "1000"}, {"p": "-5"}, {"p": "999999999"}]
        issues = G.validate_values(rows, {"p": {"type": "int", "min": 1, "max": 100_000_000}})
        self.assertTrue(any("< min" in i for i in issues) and any("> max" in i for i in issues))

    def test_nan_inf_flagged(self):
        # v1 BUG: NaN passed min/max silently.
        issues = G.validate_values([{"p": "nan"}, {"p": "inf"}], {"p": {"type": "float", "min": 1, "max": 100}})
        self.assertTrue(any("non-finite" in i for i in issues))

    def test_bad_reject_regex_is_issue_not_exception(self):
        # v1 BUG: invalid regex raised re.error.
        issues = G.validate_values([{"n": "a"}], {"n": {"reject_regex": "["}})
        self.assertTrue(any("invalid reject_regex" in i for i in issues))

    def test_reject_regex_catches_ad(self):
        rows = [{"n": "상품A"}, {"n": "광고: 지금 구매!"}]
        issues = G.validate_values(rows, {"n": {"reject_regex": r"광고|sponsored|\bAd\b"}})
        self.assertTrue(any("known-junk" in i for i in issues))

    def test_unique_flags_duplicates(self):
        rows = [{"id": "1"}, {"id": "2"}, {"id": "1"}]
        issues = G.validate_values(rows, {"id": {"unique": True}})
        self.assertTrue(any("duplicate" in i for i in issues))

    def test_min_rows_cardinality(self):
        issues = G.validate_values([{"x": "1"}], {"x": {}}, min_rows=5)
        self.assertTrue(any("min_rows" in i for i in issues))

    def test_uniform_and_allow_uniform(self):
        rows = [{"c": "shoes"}] * 12
        self.assertTrue(any("identical" in i for i in G.validate_values(rows, {"c": {}})))
        self.assertEqual(G.validate_values(rows, {"c": {"allow_uniform": True}}), [])

    def test_str_type_flags_nonstr(self):
        issues = G.validate_values([{"n": 5}, {"n": "ok"}], {"n": {"type": "str"}})
        self.assertTrue(any("not str" in i for i in issues))

    def test_malformed_rule_does_not_crash(self):
        issues = G.validate_values([{"n": "a"}], {"n": {"min": "notnumber", "type": "int"}})
        self.assertIsInstance(issues, list)   # never raises

    def test_non_dict_schema_is_issue_not_crash(self):
        issues = G.validate_values([{"n": "a"}], ["not", "a", "dict"])
        self.assertTrue(any("schema must be a dict" in i for i in issues))

    def test_non_list_rows_is_issue_not_crash(self):
        issues = G.validate_values("notalist", {"n": {}})
        self.assertTrue(any("rows must be a list" in i for i in issues))

    def test_string_min_rows_is_visible_issue(self):   # C2.4: invalid config must fail visibly, not disable the guard
        issues = G.validate_values([{"n": "a"}], {"n": {}}, min_rows="5")
        self.assertIsInstance(issues, list)                       # never raises
        self.assertTrue(any("min_rows must be an int" in i for i in issues))

    def test_unknown_field_type_is_issue(self):   # C2.4: a typo'd type must not silently skip validation
        issues = G.validate_values([{"n": "a"}], {"n": {"type": "integer"}}, min_rows=0)
        self.assertTrue(any("unknown type" in i for i in issues))

    def test_non_dict_rows_under_schema_is_issue(self):   # C3.1/C2.4: junk rows must not validate clean
        issues = G.validate_values(["junk", "more"], {"n": {"type": "str"}}, min_rows=0)
        self.assertTrue(any("rows must be dicts" in i for i in issues))

    def test_empty_rows(self):
        self.assertEqual(G.validate_values([], {"x": {}}), ["no rows to validate"])


if __name__ == "__main__":
    unittest.main()
