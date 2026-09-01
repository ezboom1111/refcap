"""TDD for check_skill_staleness.py — skill freshness gate via last_verified frontmatter.
Isolated by monkeypatching the module SKILLS_DIR to a temp tree. stdlib only.
Run: python -m unittest test_check_skill_staleness -v
"""
import os, sys, tempfile, shutil, unittest
from unittest import mock
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
        # frontmatter got the key (not the body); a --fix stamp reads back as stamped-unverified, not fresh
        self.assertEqual(res["skills"][0]["status"], "stamped-unverified")
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


    def test_cli_fix_requires_ack(self):   # false-green guard: bare --fix is refused at the CLI
        self._skill("gated", (self._today() - timedelta(days=99)).isoformat())
        with mock.patch.object(sys, "argv", ["check_skill_staleness.py", "--fix"]):
            with self.assertRaises(SystemExit) as cm:
                SS.main()
        self.assertNotEqual(cm.exception.code, 0)   # argparse.error exits non-zero
        res = SS.check_staleness(ttl_days=30)         # and the skill was NOT stamped
        self.assertEqual(res["skills"][0]["status"], "stale")

    def test_cli_fix_with_ack_stamps_and_flags_unverified(self):   # explicit unsafe path works + is flagged
        self._skill("acked", (self._today() - timedelta(days=99)).isoformat())
        with mock.patch.object(sys, "argv", ["check_skill_staleness.py", "--fix", "--yes-unverified", "--json"]):
            with self.assertRaises(SystemExit):
                SS.main()
        res = SS.check_staleness(ttl_days=30)
        self.assertTrue(res["pass"])                                       # date got stamped
        self.assertEqual(res["skills"][0]["last_verified"], self._today().isoformat())

    def test_check_staleness_flags_unverified_datestamp(self):   # the false-green marker is surfaced
        self._skill("marked", (self._today() - timedelta(days=99)).isoformat())
        res = SS.check_staleness(ttl_days=30, fix=True)
        self.assertIn("marked", res.get("unverified_datestamp", []))

    # --- provenance persistence (Codex 3rd/4th review: a --fix stamp must NOT silently look verified) ---

    def _skill_verified_by(self, name, last_verified, verified_by):
        d = os.path.join(self.skills, name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(f"---\nname: {name}\nlast_verified: {last_verified}\n"
                    f"verified_by: {verified_by}\n---\n\n# {name}\nbody\n")

    def test_fix_persists_verified_by_marker(self):   # the marker is written to the frontmatter
        self._skill("persist", (self._today() - timedelta(days=99)).isoformat())
        SS.check_staleness(ttl_days=30, fix=True)
        fm, _ = SS._parse_frontmatter(os.path.join(self.skills, "persist", "SKILL.md"))
        self.assertEqual(fm.get("verified_by"), "date-stamp-unverified")

    def test_stamped_skill_reports_stamped_unverified_not_fresh(self):   # within TTL but only date-stamped
        self._skill_verified_by("st", self._today().isoformat(), "date-stamp-unverified")
        res = SS.check_staleness(ttl_days=30)
        self.assertEqual(res["skills"][0]["status"], "stamped-unverified")
        self.assertIn("st", res.get("stamped_unverified", []))
        self.assertTrue(res["pass"])   # acknowledged stamp does not FAIL the gate — but is loudly, persistently flagged

    def test_stamped_unverified_survives_repeated_runs(self):   # the core Codex requirement: does not age into "fresh"
        self._skill("age", (self._today() - timedelta(days=99)).isoformat())
        SS.check_staleness(ttl_days=30, fix=True)          # stamp it
        for _ in range(3):                                  # every later run still sees it as unverified
            res = SS.check_staleness(ttl_days=30)
            self.assertEqual(res["skills"][0]["status"], "stamped-unverified")
            self.assertIn("age", res.get("stamped_unverified", []))

    def test_real_verification_marker_reads_fresh(self):   # a human re-verify (verified_by != date-stamp-unverified) is fresh
        self._skill_verified_by("real", self._today().isoformat(), "manual")
        res = SS.check_staleness(ttl_days=30)
        self.assertEqual(res["skills"][0]["status"], "fresh")
        self.assertNotIn("stamped_unverified", res)

    def test_stale_takes_precedence_over_stamp_marker(self):   # an old stamped skill is STALE, not merely stamped
        self._skill_verified_by("old", (self._today() - timedelta(days=99)).isoformat(), "date-stamp-unverified")
        res = SS.check_staleness(ttl_days=30)
        self.assertEqual(res["skills"][0]["status"], "stale")
        self.assertFalse(res["pass"])

    def test_strict_fails_on_stamped_unverified(self):   # C5: release gate can refuse a bare --fix stamp
        self._skill_verified_by("gate", self._today().isoformat(), "date-stamp-unverified")
        self.assertTrue(SS.check_staleness(ttl_days=30)["pass"])              # advisory default: passes
        self.assertFalse(SS.check_staleness(ttl_days=30, strict=True)["pass"])  # strict: fails

    def test_strict_still_passes_real_verification(self):   # a genuine verify is not caught by --strict
        self._skill_verified_by("real2", self._today().isoformat(), "content-reverify-2026-09-01")
        self.assertTrue(SS.check_staleness(ttl_days=30, strict=True)["pass"])


if __name__ == "__main__":
    unittest.main()
