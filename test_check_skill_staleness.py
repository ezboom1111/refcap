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


if __name__ == "__main__":
    unittest.main()
