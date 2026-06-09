"""TDD for check_skill_staleness.py — skill freshness gate via last_verified frontmatter.
Isolated by monkeypatching the module SKILLS_DIR to a temp tree. stdlib only.
Run: python -m unittest test_check_skill_staleness -v
"""
import os, sys, tempfile, shutil, unittest
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_skill_staleness as SS


class Staleness(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.skills = os.path.join(self.d, "skills")
        os.makedirs(self.skills)
        self._orig = SS.SKILLS_DIR
        SS.SKILLS_DIR = self.skills

    def tearDown(self):
        SS.SKILLS_DIR = self._orig
        shutil.rmtree(self.d, ignore_errors=True)

    def _skill(self, name, last_verified=None):
        d = os.path.join(self.skills, name)
        os.makedirs(d, exist_ok=True)
        fm = f"name: {name}\n"
        if last_verified is not None:
            fm += f"last_verified: {last_verified}\n"
        with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(f"---\n{fm}---\n\n# {name}\nbody\n")

    def _today(self):
        return datetime.now(timezone.utc).date()

    def test_fresh_skill_passes(self):
        self._skill("fresh", self._today().isoformat())
        res = SS.check_staleness(ttl_days=30)
        self.assertTrue(res["pass"])
        self.assertEqual(res["skills"][0]["status"], "fresh")

    def test_stale_skill_fails(self):
        old = (self._today() - timedelta(days=60)).isoformat()
        self._skill("stale", old)
        res = SS.check_staleness(ttl_days=30)
        self.assertFalse(res["pass"])
        self.assertEqual(res["skills"][0]["status"], "stale")

    def test_missing_last_verified_fails(self):
        self._skill("nodate", None)
        res = SS.check_staleness(ttl_days=30)
        self.assertFalse(res["pass"])
        self.assertEqual(res["skills"][0]["status"], "missing")

    def test_invalid_date_fails(self):
        self._skill("baddate", "not-a-date")
        res = SS.check_staleness(ttl_days=30)
        self.assertFalse(res["pass"])
        self.assertEqual(res["skills"][0]["status"], "invalid-date")

    def test_fix_updates_stale_to_today(self):
        old = (self._today() - timedelta(days=99)).isoformat()
        self._skill("fixme", old)
        SS.check_staleness(ttl_days=30, fix=True)
        # re-check: now fresh
        res = SS.check_staleness(ttl_days=30)
        self.assertTrue(res["pass"])
        self.assertEqual(res["skills"][0]["last_verified"], self._today().isoformat())

    def test_fix_inserts_when_missing(self):
        self._skill("insertme", None)
        SS.check_staleness(ttl_days=30, fix=True)
        res = SS.check_staleness(ttl_days=30)
        self.assertEqual(res["skills"][0]["last_verified"], self._today().isoformat())

    def test_parse_frontmatter_reads_keys(self):
        self._skill("p", self._today().isoformat())
        fm, _ = SS._parse_frontmatter(os.path.join(self.skills, "p", "SKILL.md"))
        self.assertEqual(fm["name"], "p")
        self.assertIn("last_verified", fm)

    def test_exactly_ttl_days_old_is_stale(self):   # regression: boundary off-by-one (was lv < cutoff)
        self._skill("edge", (self._today() - timedelta(days=30)).isoformat())
        res = SS.check_staleness(ttl_days=30)
        self.assertEqual(res["skills"][0]["status"], "stale")
        self.assertFalse(res["pass"])

    def test_fixed_skill_reports_today_not_old_date(self):   # regression: return dict carried the pre-fix date
        self._skill("rep", (self._today() - timedelta(days=99)).isoformat())
        res = SS.check_staleness(ttl_days=30, fix=True)
        self.assertEqual(res["skills"][0]["status"], "fixed")
        self.assertEqual(res["skills"][0]["last_verified"], self._today().isoformat())

    def test_empty_last_verified_value_does_not_eat_closing_delimiter(self):   # regression: --- corruption
        d = os.path.join(self.skills, "empty")
        os.makedirs(d)
        p = os.path.join(d, "SKILL.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write("---\nname: empty\nlast_verified:\n---\n\n# empty\nbody\n")
        SS.check_staleness(ttl_days=30, fix=True)
        with open(p, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("\n---\n", content)                       # closing delimiter survived
        fm, _ = SS._parse_frontmatter(p)
        self.assertEqual(fm.get("last_verified"), self._today().isoformat())

    def test_fix_ignores_body_last_verified_and_inserts_into_frontmatter(self):   # regression: body line mutated
        d = os.path.join(self.skills, "bodybug")
        os.makedirs(d)
        p = os.path.join(d, "SKILL.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write("---\nname: bodybug\n---\n\n# Notes\nlast_verified: was checked 2020-01-01\n")
        SS.check_staleness(ttl_days=30, fix=True)
        res = SS.check_staleness(ttl_days=30)
        self.assertEqual(res["skills"][0]["status"], "fresh")   # frontmatter got the key, not the body
        with open(p, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("last_verified: was checked 2020-01-01", content)   # body line untouched
        fm, _ = SS._parse_frontmatter(p)
        self.assertEqual(fm.get("last_verified"), self._today().isoformat())

    def test_fix_preserves_folded_yaml_block(self):   # real SKILL.md uses description: >- folded blocks
        d = os.path.join(self.skills, "folded")
        os.makedirs(d)
        p = os.path.join(d, "SKILL.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write("---\nname: folded\ndescription: >-\n  line one\n  line two\n"
                    "last_verified: 2020-01-01\n---\n\n# folded\nbody\n")
        SS.check_staleness(ttl_days=30, fix=True)
        fm, _ = SS._parse_frontmatter(p)
        self.assertEqual(fm.get("last_verified"), self._today().isoformat())
        with open(p, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("description: >-", content)               # folded block intact
        self.assertIn("  line one", content)
        self.assertIn("  line two", content)


if __name__ == "__main__":
    unittest.main()
