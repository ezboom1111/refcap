"""Integration tests for refacquire — the enforced safety pipeline (P0-1). Fake transports.
Asserts the STOP conditions Codex required: no fetch past a bad opt-out, no parse past a block,
no promotion past a validation failure. Run: python -m unittest test_refacquire -v
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refacquire as A
import refopt


class Spy:
    """Records whether it was called (to prove a gate stopped the pipeline before it)."""
    def __init__(self, ret):
        self.ret = ret
        self.called = False

    def __call__(self, *a, **k):
        self.called = True
        return self.ret


def robots(text, status=200, content_type="text/plain"):
    return lambda u: refopt.text_response(text, status=status, content_type=content_type)


GOOD_ROWS = [{"name": "상품A", "price": "1000"}, {"name": "상품B", "price": "2000"}]
SCHEMA = {"name": {"required": True, "type": "str"}, "price": {"type": "int", "min": 1, "max": 10_000_000}}


class OptoutGate(unittest.TestCase):
    def test_disallowed_refuses_and_never_fetches(self):
        page = Spy(A.page_response("<html>rows</html>"))
        parser = Spy(GOOD_ROWS)
        r = A.acquire("https://x.com/private/p", fetch_robots=robots("User-agent: *\nDisallow: /private\n"),
                      fetch_page=page, parser=parser, schema=SCHEMA)
        self.assertEqual(r.evidence_state, "refused_optout")
        self.assertFalse(page.called, "page must NOT be fetched when opt-out disallows")
        self.assertFalse(parser.called)

    def test_unknown_optout_never_fetches(self):
        # robots returns HTML (a login/wall) -> unknown -> fail-visible stop, no fetch
        page = Spy(A.page_response("<html>rows</html>"))
        r = A.acquire("https://x.com/p", fetch_robots=robots("<html>login</html>", content_type="text/html"),
                      fetch_page=page, parser=Spy(GOOD_ROWS), schema=SCHEMA)
        self.assertEqual(r.evidence_state, "undecidable_optout")
        self.assertFalse(page.called, "page must NOT be fetched when opt-out is unknown")

    def test_conditional_needs_consent_by_default(self):
        page = Spy(A.page_response("<html>rows</html>"))
        r = A.acquire("https://x.com/p", fetch_robots=robots("User-agent: *\nAllow: /\nLicense: https://x/l.xml\n"),
                      fetch_page=page, parser=Spy(GOOD_ROWS), schema=SCHEMA)
        self.assertEqual(r.evidence_state, "needs_consent")
        self.assertFalse(page.called)

    def test_conditional_proceeds_when_allowed(self):
        page = A.page_response("<html>rows</html>")
        r = A.acquire("https://x.com/p", fetch_robots=robots("User-agent: *\nAllow: /\nLicense: https://x/l.xml\n"),
                      fetch_page=lambda u: page, parser=lambda b: GOOD_ROWS, schema=SCHEMA,
                      allow_conditional=True, selector_hit=True)
        self.assertTrue(r.ok)
        self.assertEqual(r.evidence_state, "ok")


class SoftblockGate(unittest.TestCase):
    def test_block_never_parses(self):
        parser = Spy(GOOD_ROWS)
        r = A.acquire("https://x.com/p", fetch_robots=robots("User-agent: *\nAllow: /\n"),
                      fetch_page=lambda u: A.page_response("<html>Just a moment...</html>", cookies={}),
                      parser=parser, schema=SCHEMA, selector_hit=False)
        self.assertEqual(r.evidence_state, "blocked")
        self.assertFalse(parser.called, "parser must NOT run on a soft-blocked page")

    def test_http_error_stops(self):
        parser = Spy(GOOD_ROWS)
        r = A.acquire("https://x.com/p", fetch_robots=robots("User-agent: *\nAllow: /\n"),
                      fetch_page=lambda u: A.page_response("Not Found", status=404),
                      parser=parser, schema=SCHEMA)
        self.assertEqual(r.evidence_state, "http_error")
        self.assertFalse(parser.called)

    def test_js_wall_stops_for_escalation(self):
        r = A.acquire("https://x.com/p", fetch_robots=robots("User-agent: *\nAllow: /\n"),
                      fetch_page=lambda u: A.page_response("<noscript>enable javascript</noscript>"),
                      parser=lambda b: GOOD_ROWS, schema=SCHEMA)
        self.assertEqual(r.evidence_state, "js_wall")


class ValidateGate(unittest.TestCase):
    def test_validation_failure_not_promoted(self):
        bad_rows = [{"name": "상품A", "price": "1000"}, {"name": "광고", "price": "-5"}]
        r = A.acquire("https://x.com/p", fetch_robots=robots("User-agent: *\nAllow: /\n"),
                      fetch_page=lambda u: A.page_response("<html>rows</html>"),
                      parser=lambda b: bad_rows,
                      schema={"name": {"reject_regex": r"광고"}, "price": {"type": "int", "min": 1}},
                      selector_hit=True)
        self.assertFalse(r.ok)
        self.assertEqual(r.evidence_state, "validation_failed")
        self.assertTrue(r.rows)                 # rows are present...
        self.assertTrue(r.issues)               # ...but NOT promoted, with issues surfaced

    def test_parse_empty_flagged(self):
        r = A.acquire("https://x.com/p", fetch_robots=robots("User-agent: *\nAllow: /\n"),
                      fetch_page=lambda u: A.page_response("<html></html>"),
                      parser=lambda b: [], schema=SCHEMA, selector_hit=True)
        self.assertEqual(r.evidence_state, "parse_empty")

    def test_happy_path_ok(self):
        r = A.acquire("https://x.com/p", fetch_robots=robots("User-agent: *\nAllow: /\n"),
                      fetch_page=lambda u: A.page_response("<html>rows</html>"),
                      parser=lambda b: GOOD_ROWS, schema=SCHEMA, selector_hit=True)
        self.assertTrue(r.ok)
        self.assertEqual(r.evidence_state, "ok")


class RegistryHook(unittest.TestCase):
    def test_registry_warnings_surface_but_do_not_block(self):
        r = A.acquire("https://x.com/p", fetch_robots=robots("User-agent: *\nAllow: /\n"),
                      fetch_page=lambda u: A.page_response("<html>rows</html>"),
                      parser=lambda b: GOOD_ROWS, schema=SCHEMA, selector_hit=True,
                      registry_check=lambda: ["F-001 stale (effective_at passed)"])
        self.assertTrue(r.ok)
        self.assertTrue(any("F-001 stale" in x for x in r.reasons))


if __name__ == "__main__":
    unittest.main()
