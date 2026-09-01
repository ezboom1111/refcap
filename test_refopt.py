"""TDD for refopt.py — opt-out signal resolver. stdlib only, network injected (hermetic).
Run: python -m unittest test_refopt -v
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refopt as R


def fetch_ok(text):
    """Return a fetch() that always yields `text` (ignores the robots URL)."""
    return lambda url: text


def fetch_raises(url):
    raise ConnectionError("boom")


def fetch_none(url):
    return None


class Resolve(unittest.TestCase):
    # --- fail-visible ------------------------------------------------------
    def test_fetch_error_is_unknown_not_allowed(self):
        r = R.resolve_optout("https://x.com/a", fetch_raises)
        self.assertEqual(r["status"], R.UNKNOWN)
        self.assertTrue(any("error" in s for s in r["reasons"]))

    def test_fetch_none_is_unknown(self):
        r = R.resolve_optout("https://x.com/a", fetch_none)
        self.assertEqual(r["status"], R.UNKNOWN)

    # --- allowed / disallowed ---------------------------------------------
    def test_clean_robots_is_allowed(self):
        r = R.resolve_optout("https://x.com/page", fetch_ok("User-agent: *\nAllow: /\n"))
        self.assertEqual(r["status"], R.ALLOWED)
        self.assertEqual(r["signals"], [])

    def test_disallow_prefix_is_disallowed(self):
        robots = "User-agent: *\nDisallow: /private\n"
        r = R.resolve_optout("https://x.com/private/report", fetch_ok(robots))
        self.assertEqual(r["status"], R.DISALLOWED)
        self.assertIn("robots-disallow", r["signals"])

    def test_disallow_does_not_match_other_path(self):
        robots = "User-agent: *\nDisallow: /private\n"
        r = R.resolve_optout("https://x.com/public/report", fetch_ok(robots))
        self.assertEqual(r["status"], R.ALLOWED)

    def test_empty_disallow_means_allow_all(self):
        r = R.resolve_optout("https://x.com/anything", fetch_ok("User-agent: *\nDisallow:\n"))
        self.assertEqual(r["status"], R.ALLOWED)

    def test_allow_overrides_disallow_longest_match(self):
        robots = "User-agent: *\nDisallow: /\nAllow: /public\n"
        r = R.resolve_optout("https://x.com/public/x", fetch_ok(robots))
        self.assertEqual(r["status"], R.ALLOWED)
        r2 = R.resolve_optout("https://x.com/secret", fetch_ok(robots))
        self.assertEqual(r2["status"], R.DISALLOWED)

    def test_wildcard_and_end_anchor(self):
        robots = "User-agent: *\nDisallow: /*.pdf$\n"
        self.assertEqual(R.resolve_optout("https://x.com/a/b.pdf", fetch_ok(robots))["status"], R.DISALLOWED)
        self.assertEqual(R.resolve_optout("https://x.com/a/b.pdf?x=1", fetch_ok(robots))["status"], R.ALLOWED)

    # --- UA-specific groups ------------------------------------------------
    def test_ua_specific_group_does_not_apply_to_star(self):
        robots = "User-agent: BadBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
        r = R.resolve_optout("https://x.com/x", fetch_ok(robots), user_agent="GoodBot")
        self.assertEqual(r["status"], R.ALLOWED)

    def test_ua_exact_match_group_wins(self):
        robots = "User-agent: *\nAllow: /\n\nUser-agent: GoodBot\nDisallow: /x\n"
        r = R.resolve_optout("https://x.com/x", fetch_ok(robots), user_agent="GoodBot")
        self.assertEqual(r["status"], R.DISALLOWED)

    # --- conditional: RSL / TDM / noai ------------------------------------
    def test_rsl_license_directive_is_conditional(self):
        robots = "User-agent: *\nAllow: /\nLicense: https://x.com/license.xml\n"
        r = R.resolve_optout("https://x.com/page", fetch_ok(robots))
        self.assertEqual(r["status"], R.CONDITIONAL)
        self.assertIn("rsl-license", r["signals"])
        self.assertEqual(r["license_urls"], ["https://x.com/license.xml"])

    def test_tdmrep_meta_is_conditional(self):
        html = '<html><head><meta name="tdm-reservation" content="1"></head></html>'
        r = R.resolve_optout("https://x.com/p", fetch_ok("User-agent: *\nAllow: /\n"), page_html=html)
        self.assertEqual(r["status"], R.CONDITIONAL)
        self.assertIn("tdmrep", r["signals"])

    def test_noai_meta_is_conditional(self):
        html = '<meta name="robots" content="index, noai">'
        r = R.resolve_optout("https://x.com/p", fetch_ok("User-agent: *\nAllow: /\n"), page_html=html)
        self.assertEqual(r["status"], R.CONDITIONAL)
        self.assertIn("noai-meta", r["signals"])

    def test_noai_via_x_robots_header(self):
        r = R.resolve_optout("https://x.com/p", fetch_ok("User-agent: *\nAllow: /\n"),
                             page_headers={"X-Robots-Tag": "noai, noindex"})
        self.assertEqual(r["status"], R.CONDITIONAL)
        self.assertIn("noai-meta", r["signals"])

    def test_disallow_wins_over_conditional(self):
        robots = "User-agent: *\nDisallow: /\nLicense: https://x.com/license.xml\n"
        r = R.resolve_optout("https://x.com/p", fetch_ok(robots))
        self.assertEqual(r["status"], R.DISALLOWED)   # disallow beats a license signal

    # --- llms.txt is NOT an opt-out (must be ignored) ----------------------
    def test_llms_txt_is_not_treated_as_optout(self):
        # even if a page mentions llms.txt, it must not flip status; only robots/RSL/TDM/noai count
        html = '<a href="/llms.txt">llms.txt</a>'
        r = R.resolve_optout("https://x.com/p", fetch_ok("User-agent: *\nAllow: /\n"), page_html=html)
        self.assertEqual(r["status"], R.ALLOWED)

    # --- crawl-delay -------------------------------------------------------
    def test_crawl_delay_parsed(self):
        r = R.resolve_optout("https://x.com/p", fetch_ok("User-agent: *\nCrawl-delay: 2.5\nAllow: /\n"))
        self.assertEqual(r["crawl_delay"], 2.5)


class ParseUnits(unittest.TestCase):
    def test_parse_collects_license_urls_globally(self):
        p = R.parse_robots("License: https://a/l.xml\nUser-agent: *\nDisallow: /x\n")
        self.assertEqual(p["license_urls"], ["https://a/l.xml"])

    def test_scan_noai_detects_tokens(self):
        self.assertIn("noai", R.scan_noai('<meta name="robots" content="noai">'))
        self.assertIn("tdmrep", R.scan_noai('<meta name="tdm-reservation" content="1">'))

    def test_scan_noai_empty_when_clean(self):
        self.assertEqual(R.scan_noai("<html><body>hi</body></html>"), set())


if __name__ == "__main__":
    unittest.main()
