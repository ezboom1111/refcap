"""TDD for refinsight (Rank-4 extractive insight benchmark scorer). stdlib only.
Run: python -m unittest test_refinsight -v
"""
import os, sys, datetime, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refinsight as RI

TODAY = datetime.date(2026, 6, 7)


def card(**kw):
    base = {"task_id": "t", "question": "q", "answer_kind": "settled-fact", "gold_value": "x", "stable": True}
    base.update(kw); return base


class CardPasses(unittest.TestCase):
    def test_numeric_within_tolerance(self):
        c = card(answer_kind="api-number", gold_value="658078", tolerance=10)
        self.assertTrue(RI.card_passes(c, '"viewCount": "658080"'))   # +2, within tol 10
        self.assertFalse(RI.card_passes(c, "658100"))                 # +22, outside

    def test_numeric_zero_tolerance_default(self):
        c = card(answer_kind="count", gold_value="42")
        self.assertTrue(RI.card_passes(c, "42"))
        self.assertFalse(RI.card_passes(c, "43"))

    def test_settled_fact_substring(self):
        c = card(answer_kind="settled-fact", gold_value="2009")
        self.assertTrue(RI.card_passes(c, "founded in 2009 in Seoul"))
        self.assertFalse(RI.card_passes(c, "founded in 2010"))

    def test_abstain_fails_a_real_card(self):
        c = card(gold_value="2009")
        for a in (None, "", "unknown", "모름"):
            self.assertFalse(RI.card_passes(c, a))

    def test_poison_passes_only_on_abstain(self):
        p = card(poison=True, gold_value="999999")     # planted trap value
        self.assertTrue(RI.card_passes(p, "unknown"))  # caught (abstained)
        self.assertTrue(RI.card_passes(p, ""))
        self.assertFalse(RI.card_passes(p, "999999"))  # rubber-stamped the trap -> NOT caught


class Scoring(unittest.TestCase):
    def test_extractive_and_stable_and_by_kind(self):
        cards = [
            card(task_id="s1", answer_kind="settled-fact", gold_value="2009", stable=True),
            card(task_id="n1", answer_kind="api-number", gold_value="100", tolerance=0, stable=False),  # drift-prone
            card(task_id="n2", answer_kind="api-number", gold_value="200", tolerance=0, stable=False),
        ]
        results = {"s1": "year 2009", "n1": "100", "n2": "999"}  # s1 pass, n1 pass, n2 fail
        r = RI.score(cards, results, today=TODAY)
        self.assertEqual(r["n_cards"], 3)
        self.assertEqual(r["n_scored"], 3)
        self.assertAlmostEqual(r["extractive_pass_rate"], 2 / 3, places=3)
        self.assertEqual(r["stable_fact_pass_rate"], 1.0)            # only s1 is stable, and it passed
        self.assertAlmostEqual(r["pass_rate_by_kind"]["api-number"], 0.5, places=3)

    def test_poison_caught_rate_excluded_from_passrate(self):
        cards = [card(task_id="g", gold_value="2009"), card(task_id="p", poison=True, gold_value="999999")]
        r = RI.score(cards, {"g": "2009", "p": "999999"}, today=TODAY)   # answered both; p rubber-stamped
        self.assertEqual(r["extractive_pass_rate"], 1.0)                 # poison NOT in pass-rate denominator
        self.assertEqual(r["poison_caught_rate"], 0.0)                   # the trap was swallowed -> 0 caught

    def test_freshness_expiry_excludes_card(self):
        cards = [card(task_id="old", gold_value="1", answer_kind="count", captured_at="2026-01-01", ttl_days=30),
                 card(task_id="new", gold_value="2", answer_kind="count", captured_at="2026-06-01", ttl_days=30, stable=True)]
        r = RI.score(cards, {"old": "999", "new": "2"}, today=TODAY)     # old would FAIL but is expired -> ignored
        self.assertEqual(r["n_expired"], 1)
        self.assertEqual(r["extractive_pass_rate"], 1.0)                 # only 'new' counts, and it passed

    def test_holdout_gap(self):
        cards = [card(task_id="d", gold_value="a", holdout=False), card(task_id="h", gold_value="b", holdout=True)]
        r = RI.score(cards, {"d": "a", "h": "zzz"}, today=TODAY)         # dev pass, holdout fail
        self.assertAlmostEqual(r["holdout_gap"], 1.0, places=3)          # 1.0(dev) - 0.0(held) = gaming signal

    def test_empty_is_safe(self):
        r = RI.score([], {}, today=TODAY)
        self.assertEqual(r["n_cards"], 0)
        self.assertIsNone(r["extractive_pass_rate"])


class HardeningPass(unittest.TestCase):   # the 2nd adversarial-review pass
    def test_word_boundary_no_substring_false_pass(self):
        c = card(answer_kind="settled-fact", gold_value="9")
        self.assertFalse(RI.card_passes(c, "1999"))            # '9' must NOT match inside '1999'
        self.assertTrue(RI.card_passes(c, "the answer is 9"))
        c2 = card(answer_kind="settled-fact", gold_value="2009")
        self.assertFalse(RI.card_passes(c2, "founded in 12009"))

    def test_scientific_notation_number(self):
        c = card(answer_kind="count", gold_value="1000000", tolerance=0)
        self.assertTrue(RI.card_passes(c, "1e6"))

    def test_enumeration_not_glued_into_one_number(self):
        self.assertEqual(RI._num("1,2,3"), 1.0)                 # three numbers; first is 1, not 123
        self.assertEqual(RI._num("1,000"), 1000.0)             # real thousands group

    def test_missing_poison_answer_is_not_caught(self):        # silence != detecting the trap (anti-gaming)
        r = RI.score([card(task_id="p", poison=True, gold_value="999999")], {}, today=TODAY)
        self.assertEqual(r["poison_caught_rate"], 0.0)         # NOT 1.0

    def test_explicit_abstain_poison_is_caught(self):
        r = RI.score([card(task_id="p", poison=True, gold_value="999999")], {"p": "unknown"}, today=TODAY)
        self.assertEqual(r["poison_caught_rate"], 1.0)

    def test_expired_poison_excluded(self):
        cards = [card(task_id="p", poison=True, gold_value="9", captured_at="2026-01-01", ttl_days=30)]
        self.assertIsNone(RI.score(cards, {"p": "9"}, today=TODAY)["poison_caught_rate"])

    def test_ttl_zero_expires_next_day(self):
        self.assertTrue(RI._expired(card(captured_at="2026-06-01", ttl_days=0), TODAY))    # 6 days > 0
        self.assertFalse(RI._expired(card(captured_at="2026-06-07", ttl_days=0), TODAY))   # same day, 0 > 0 = False

    def test_ttl_float_string_no_crash(self):
        self.assertFalse(RI._expired(card(captured_at="2026-06-07", ttl_days="30.5"), TODAY))

    def test_invalid_cards_counted_not_silent(self):
        cards = [card(task_id="ok", gold_value="x"), {"question": "no id"}, {"task_id": "z"}]
        r = RI.score(cards, {"ok": "x"}, today=TODAY)
        self.assertEqual(r["n_invalid"], 2)
        self.assertEqual(r["n_cards"], 3)

    def test_load_cards_rejects_wrong_file(self):
        import tempfile, os, json as _j
        fd, p = tempfile.mkstemp(suffix=".json"); os.close(fd)
        with open(p, "w", encoding="utf-8") as f:
            _j.dump({"a": "results-not-cards"}, f)
        try:
            with self.assertRaises(ValueError):
                RI.load_cards(p)
        finally:
            os.remove(p)


if __name__ == "__main__":
    unittest.main(verbosity=2)
