"""Doc-contract regression tests for the leesearch skill (canonical copy in refcap/skills/).

Codex review finding #4: md5 deploy-sync proves the copies MATCH, not that the content is
CORRECT — a bad edit deploys identically to every host. These cheap assertions pin the
load-bearing method rules added 2026-09 so a future prune can't silently delete them, and
verify the code modules the skill points at actually exist and expose their entry points.

stdlib only. Run: python -m unittest test_leesearch_contract -v
"""
import os, re, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "skills", "leesearch", "SKILL.md")
REGISTRY = os.path.join(HERE, "skills", "leesearch", "facts.registry.md")


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


class SkillContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = _read(SKILL)
        cls.registry = _read(REGISTRY)

    def test_frontmatter_last_verified_parseable(self):
        m = re.search(r"(?m)^last_verified:\s*(\d{4}-\d{2}-\d{2})\s*$", self.skill)
        self.assertIsNotNone(m, "SKILL.md must carry a parseable last_verified date")

    # --- method rules added this session (must survive future prunes) -----
    def test_ab_seam_sentence_present(self):
        self.assertIn("이음매", self.skill)
        self.assertTrue("자동/동의" in self.skill or "자동 진행" in self.skill,
                        "the auto/consent seam must remain in the escalation ladder")

    def test_optout_rule_present(self):
        self.assertIn("opt-out", self.skill.lower())    # the opt-out signal rule
        self.assertIn("License:", self.skill)          # RSL directive
        self.assertIn("llms.txt", self.skill)           # the non-standard caveat must stay
        for status in ("allowed", "disallowed", "conditional", "unknown"):
            self.assertIn(status, self.skill)

    def test_softblock_value_rule_present(self):
        self.assertIn("detect_softblock", self.skill)
        self.assertIn("validate_values", self.skill)
        self.assertTrue("wrong-target" in self.skill or "wrong_target" in self.skill)

    # --- pointers must resolve to real files/entry points -----------------
    def test_skill_points_at_existing_modules(self):
        self.assertIn("refopt.py", self.skill)
        self.assertIn("refguard.py", self.skill)
        self.assertIn("refacquire.py", self.skill)          # the enforcing facade must be referenced
        self.assertIn("facts.registry.md", self.skill)
        for mod in ("refopt.py", "refguard.py", "refacquire.py"):
            self.assertTrue(os.path.exists(os.path.join(HERE, mod)))
        self.assertTrue(os.path.exists(REGISTRY))

    def test_referenced_entrypoints_importable(self):
        sys.path.insert(0, HERE)
        import refopt, refguard, refacquire
        self.assertTrue(hasattr(refopt, "resolve_optout"))
        self.assertTrue(hasattr(refguard, "detect_softblock"))
        self.assertTrue(hasattr(refguard, "validate_values"))
        self.assertTrue(hasattr(refacquire, "acquire"))     # pipeline entrypoint exists

    # --- registry structure ----------------------------------------------
    def test_registry_has_status_vocab_and_facts(self):
        for status in ("observed", "announced", "effective", "unverified"):
            self.assertIn(status, self.registry)
        for fid in ("F-001", "F-002", "F-003"):
            self.assertIn(fid, self.registry)

    def test_registry_declares_method_only_boundary(self):
        # the registry must keep asserting SKILL.md = method only, registry = dated facts
        self.assertIn("METHOD", self.registry)
        self.assertTrue("registry가 최신" in self.registry or "registry가 SKILL" in self.registry)


if __name__ == "__main__":
    unittest.main()
