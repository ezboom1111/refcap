"""TDD for refopt.py (hardened v2). stdlib only, network injected (hermetic).
Run: python -m unittest test_refopt -v
"""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refopt as R


def fetch_text(text, status=200, content_type="text/plain"):
    """fetch() returning a robots body with an explicit status/content-type."""
    return lambda url: R.text_response(text, status=status, content_type=content_type)


def fetch_status(status, text="", content_type="text/plain"):
    return lambda url: R.text_response(text, status=status, content_type=content_type)


def fetch_raises(url):
    raise ConnectionError("boom")


def fetch_none(url):
    return None


class FailVisible(unittest.TestCase):
    def test_fetch_error_is_unknown(self):
        self.assertEqual(R.resolve_optout("https://x.com/a", fetch_raises)["status"], R.UNKNOWN)

    def test_fetch_none_is_unknown(self):
        self.assertEqual(R.resolve_optout("https://x.com/a", fetch_none)["status"], R.UNKNOWN)

    def test_login_html_as_robots_is_unknown_not_allowed(self):
        # v1 BUG: this returned allowed. HTML content-type must -> unknown.
        f = fetch_text("<html><title>Login</title></html>", status=200, content_type="text/html")
        self.assertEqual(R.resolve_optout("https://x.com/p", f)["status"], R.UNKNOWN)

    def test_robots_403_is_unknown(self):
        self.assertEqual(R.resolve_optout("https://x.com/p", fetch_status(403))["status"], R.UNKNOWN)

    def test_robots_500_is_unknown(self):
        self.assertEqual(R.resolve_optout("https://x.com/p", fetch_status(503))["status"], R.UNKNOWN)

    def test_robots_404_is_allow_all(self):
        # RFC 9309: no robots.txt == allow-all
        self.assertEqual(R.resolve_optout("https://x.com/anything", fetch_status(404))["status"], R.ALLOWED)


class AllowDisallow(unittest.TestCase):
    def test_clean_allowed(self):
        r = R.resolve_optout("https://x.com/page", fetch_text("User-agent: *\nAllow: /\n"))
        self.assertEqual(r["status"], R.ALLOWED)

    def test_disallow_prefix(self):
        r = R.resolve_optout("https://x.com/private/r", fetch_text("User-agent: *\nDisallow: /private\n"))
        self.assertEqual(r["status"], R.DISALLOWED)

    def test_other_path_allowed(self):
        r = R.resolve_optout("https://x.com/public/r", fetch_text("User-agent: *\nDisallow: /private\n"))
        self.assertEqual(r["status"], R.ALLOWED)

    def test_empty_disallow_allow_all(self):
        self.assertEqual(R.resolve_optout("https://x.com/x", fetch_text("User-agent: *\nDisallow:\n"))["status"], R.ALLOWED)

    def test_allow_overrides_disallow(self):
        robots = "User-agent: *\nDisallow: /\nAllow: /public\n"
        self.assertEqual(R.resolve_optout("https://x.com/public/x", fetch_text(robots))["status"], R.ALLOWED)
        self.assertEqual(R.resolve_optout("https://x.com/secret", fetch_text(robots))["status"], R.DISALLOWED)

    def test_wildcard_end_anchor_with_query(self):
        robots = "User-agent: *\nDisallow: /*.pdf$\n"
        self.assertEqual(R.resolve_optout("https://x.com/a/b.pdf", fetch_text(robots))["status"], R.DISALLOWED)
        self.assertEqual(R.resolve_optout("https://x.com/a/b.pdf?x=1", fetch_text(robots))["status"], R.ALLOWED)


class UserAgentMatching(unittest.TestCase):
    def test_ua_product_token_matches_versioned_ua(self):
        # v1 BUG: GoodBot/1.0 did not match group `GoodBot`.
        robots = "User-agent: *\nAllow: /\n\nUser-agent: GoodBot\nDisallow: /private\n"
        r = R.resolve_optout("https://x.com/private", fetch_text(robots), user_agent="GoodBot/1.0")
        self.assertEqual(r["status"], R.DISALLOWED)

    def test_ua_specific_group_not_applied_to_others(self):
        robots = "User-agent: BadBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
        r = R.resolve_optout("https://x.com/x", fetch_text(robots), user_agent="GoodBot/2.0")
        self.assertEqual(r["status"], R.ALLOWED)

    def test_most_specific_group_wins(self):
        robots = "User-agent: *\nAllow: /\n\nUser-agent: Goo\nDisallow: /x\n"
        # product token 'goodbot' startswith 'goo' -> matches the specific group
        r = R.resolve_optout("https://x.com/x", fetch_text(robots), user_agent="GoodBot/1.0")
        self.assertEqual(r["status"], R.DISALLOWED)


class Conditional(unittest.TestCase):
    def test_rsl_license_conditional(self):
        robots = "User-agent: *\nAllow: /\nLicense: https://x.com/license.xml\n"
        r = R.resolve_optout("https://x.com/p", fetch_text(robots))
        self.assertEqual(r["status"], R.CONDITIONAL)
        self.assertEqual(r["license_urls"], ["https://x.com/license.xml"])

    def test_tdmrep_meta_conditional(self):
        r = R.resolve_optout("https://x.com/p", fetch_text("User-agent: *\nAllow: /\n"),
                             page_html='<meta name="tdm-reservation" content="1">')
        self.assertEqual(r["status"], R.CONDITIONAL)

    def test_noai_meta_conditional_any_attr_order(self):
        # v1 BUG: content-before-name was missed.
        r = R.resolve_optout("https://x.com/p", fetch_text("User-agent: *\nAllow: /\n"),
                             page_html='<meta content="noai" name="robots">')
        self.assertEqual(r["status"], R.CONDITIONAL)
        self.assertIn("noai-meta", r["signals"])

    def test_noai_via_x_robots_header(self):
        r = R.resolve_optout("https://x.com/p", fetch_text("User-agent: *\nAllow: /\n"),
                             page_headers={"X-Robots-Tag": "noai, noindex"})
        self.assertEqual(r["status"], R.CONDITIONAL)

    def test_disallow_beats_license(self):
        robots = "User-agent: *\nDisallow: /\nLicense: https://x.com/l.xml\n"
        self.assertEqual(R.resolve_optout("https://x.com/p", fetch_text(robots))["status"], R.DISALLOWED)

    def test_llms_txt_not_optout(self):
        r = R.resolve_optout("https://x.com/p", fetch_text("User-agent: *\nAllow: /\n"),
                             page_html='<a href="/llms.txt">llms.txt</a>')
        self.assertEqual(r["status"], R.ALLOWED)


class Misc(unittest.TestCase):
    def test_crawl_delay(self):
        r = R.resolve_optout("https://x.com/p", fetch_text("User-agent: *\nCrawl-delay: 2.5\nAllow: /\n"))
        self.assertEqual(r["crawl_delay"], 2.5)

    def test_meta_parsed_by_htmlparser_not_regex(self):
        # uppercased tag + reordered attrs
        self.assertIn("noai", R.scan_noai('<META CONTENT="noai" NAME="ROBOTS">'))


if __name__ == "__main__":
    unittest.main()
