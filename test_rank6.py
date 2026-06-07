"""TDD for the Rank-6 evidence-STANDARD layer (declare-then-check sufficiency grade). stdlib only.
The agent DECLARES the bar (set_standard); code only counts/date-diffs/host-clusters and GRADES. Grades
SUFFICIENCY, never truth. The min-N that stops the loop is the DECLARED bar, not a code constant.
Run: python -m unittest test_rank6 -v
"""
import os, sys, tempfile, shutil, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refledger as R


def _art(r, src):
    """Real file so verify().ok can be True (grading is advisory, must not change ok)."""
    p = os.path.join(r, "a_" + R.sha256_bytes(src.encode())[:8] + ".txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write("evidence " + src)
    return R.ledger_append(r, type="html", source=src, method="m", path=p, canonical_path=p,
                           sha256=R.sha256_file(p), quality_label="OK")


class SetStandard(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_unknown_knob_raises(self):
        with self.assertRaises(ValueError):
            R.set_standard(self.r, min_sources=3)            # typo: not in the closed whitelist

    def test_standard_id_and_clean(self):
        a = R.set_standard(self.r, min_independent_sources=3, fatal_domains=["breadth"])
        self.assertTrue(a["standard_id"].startswith("std_"))
        self.assertEqual(a["invalid_fields"], [])

    def test_coherence_guards(self):
        self.assertIn("volume_bar_incoherent", R.set_standard(self.r, min_independent_sources=2, min_distinct_hosts=3)["invalid_fields"])
        self.assertIn("fatal_set_trivial", R.set_standard(self.r, fatal_domains=["traceability"])["invalid_fields"])
        self.assertIn("dup_similarity_range", R.set_standard(self.r, dup_similarity=1.5)["invalid_fields"])


class SetPublished(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)
        self.a = _art(self.r, "https://x.com/1")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_validates_artifact_and_date(self):
        R.set_published(self.r, self.a["artifact_id"], "2026-06-01")
        with self.assertRaises(ValueError):
            R.set_published(self.r, "a_nope", "2026-06-01")
        with self.assertRaises(ValueError):
            R.set_published(self.r, self.a["artifact_id"], "not-a-date")


class GradeBreadth(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _std(self, **k):
        return R.set_standard(self.r, **k)["standard_id"]

    def test_three_distinct_hosts_meets(self):
        for i, h in enumerate(["a.com", "b.com", "c.com"]):
            art = _art(self.r, f"https://{h}/x")
            R.record_finding(self.r, "claim", "OBSERVED", art["artifact_id"], quote=f"finding number {i}", conclusion_id="C1")
        g = R.grade_conclusion(self.r, "C1", self._std(min_independent_sources=3, min_distinct_hosts=3, fatal_domains=["breadth"]))
        self.assertEqual(g["overall"], "MEETS")
        self.assertEqual(g["domains"]["breadth"]["value"]["effective_sources"], 3)

    def test_two_sources_shortfall(self):
        for h in ["a.com", "b.com"]:
            art = _art(self.r, f"https://{h}/x")
            R.record_finding(self.r, "claim", "OBSERVED", art["artifact_id"], quote="q", conclusion_id="C1")
        g = R.grade_conclusion(self.r, "C1", self._std(min_independent_sources=3, fatal_domains=["breadth"]))
        self.assertEqual(g["overall"], "SHORTFALL")
        self.assertIn("breadth", g["shortfall_reasons"])

    def test_same_host_collapses(self):
        for i in range(3):
            art = _art(self.r, f"https://naver.com/{i}")   # 3 supports, ONE registrable host
            R.record_finding(self.r, "claim", "OBSERVED", art["artifact_id"], quote=f"q{i}", conclusion_id="C1")
        g = R.grade_conclusion(self.r, "C1", self._std(min_independent_sources=3, fatal_domains=["breadth"]))
        self.assertEqual(g["domains"]["breadth"]["value"]["distinct_hosts"], 1)
        self.assertEqual(g["domains"]["breadth"]["value"]["effective_sources"], 1)
        self.assertEqual(g["overall"], "SHORTFALL")          # 3 copies of one source != 3 independent sources

    def test_determinism_order_independent(self):
        for h in ["a.com", "b.com", "c.com"]:
            art = _art(self.r, f"https://{h}/x")
            R.record_finding(self.r, "x", "OBSERVED", art["artifact_id"], quote="q", conclusion_id="C1")
        sid = self._std(min_independent_sources=3, fatal_domains=["breadth"])
        self.assertEqual(R.grade_conclusion(self.r, "C1", sid)["domains"]["breadth"]["value"],
                         R.grade_conclusion(self.r, "C1", sid)["domains"]["breadth"]["value"])


class GradeRecency(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _one(self, pubdate):
        art = _art(self.r, "https://a.com/x")
        if pubdate:
            R.set_published(self.r, art["artifact_id"], pubdate)
        R.record_finding(self.r, "claim", "OBSERVED", art["artifact_id"], quote="q", conclusion_id="C1")
        return R.set_standard(self.r, max_age_days=14, fatal_domains=["recency"])["standard_id"]

    def test_fresh_meets(self):
        g = R.grade_conclusion(self.r, "C1", self._one("2026-06-06"), as_of="2026-06-07")
        self.assertTrue(g["domains"]["recency"]["met"])
        self.assertEqual(g["overall"], "MEETS")

    def test_stale_shortfall(self):
        g = R.grade_conclusion(self.r, "C1", self._one("2026-01-01"), as_of="2026-06-07")
        self.assertFalse(g["domains"]["recency"]["met"])
        self.assertEqual(g["overall"], "SHORTFALL")

    def test_no_date_is_unknown(self):
        g = R.grade_conclusion(self.r, "C1", self._one(None), as_of="2026-06-07")
        self.assertIsNone(g["domains"]["recency"]["met"])
        self.assertEqual(g["overall"], "UNKNOWN")

    def test_future_date_flagged(self):
        g = R.grade_conclusion(self.r, "C1", self._one("2026-12-31"), as_of="2026-06-07")
        self.assertTrue(g["domains"]["recency"]["value"]["future_dated_artifacts"])


class GradeConsistencyOverall(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_conflict_shortfall(self):
        a, b = _art(self.r, "https://a.com/1"), _art(self.r, "https://b.com/2")
        R.record_finding(self.r, "price", "OBSERVED", a["artifact_id"], quote="가격은 9900원", conclusion_id="C1")
        R.record_finding(self.r, "price", "OBSERVED", b["artifact_id"], quote="가격은 19900원", conclusion_id="C1")
        g = R.grade_conclusion(self.r, "C1", R.set_standard(self.r, fatal_domains=["consistency"])["standard_id"])
        self.assertFalse(g["domains"]["consistency"]["met"])
        self.assertEqual(g["overall"], "SHORTFALL")

    def test_no_fatal_ungraded(self):
        a = _art(self.r, "https://a.com/1")
        R.record_finding(self.r, "x", "OBSERVED", a["artifact_id"], quote="q", conclusion_id="C1")
        g = R.grade_conclusion(self.r, "C1", R.set_standard(self.r, min_independent_sources=1)["standard_id"])
        self.assertEqual(g["overall"], "UNGRADED")

    def test_unknown_standard_and_missing_conclusion_raise(self):
        a = _art(self.r, "https://a.com/1")
        R.record_finding(self.r, "x", "OBSERVED", a["artifact_id"], quote="q", conclusion_id="C1")
        sid = R.set_standard(self.r, fatal_domains=["breadth"], min_independent_sources=1)["standard_id"]
        with self.assertRaises(ValueError):
            R.grade_conclusion(self.r, "C1", "std_nope")       # unknown standard -> never 'latest/only' fallback
        with self.assertRaises(ValueError):
            R.grade_conclusion(self.r, "NOPE", sid)            # no findings carry that conclusion_id


class VerifyFold(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_shortfall_surfaced_ok_unchanged(self):
        a = _art(self.r, "https://a.com/1")
        R.record_finding(self.r, "x", "OBSERVED", a["artifact_id"], quote="q", conclusion_id="C1")
        sid = R.set_standard(self.r, min_independent_sources=3, fatal_domains=["breadth"])["standard_id"]
        R.grade_conclusion(self.r, "C1", sid)                  # 1 source < 3 -> SHORTFALL
        v = R.verify(self.r)
        self.assertEqual(v["conclusion_grades"]["n_shortfall"], 1)
        self.assertTrue(v["ok"])                               # sufficiency grading is ADVISORY, never blocks ok

    def test_no_standard_empty_grades(self):
        a = _art(self.r, "https://a.com/1")
        R.record_finding(self.r, "x", "OBSERVED", a["artifact_id"], quote="q", conclusion_id="C1")
        self.assertEqual(R.verify(self.r)["conclusion_grades"], {})


class HardeningPass(unittest.TestCase):   # the adversarial python-reviewer pass
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_fatal_domains_typo_string_and_empty_flagged(self):
        self.assertIn("fatal_domains_unknown", R.set_standard(self.r, fatal_domains=["breadtth"], min_independent_sources=1)["invalid_fields"])
        self.assertIn("fatal_domains_not_list", R.set_standard(self.r, fatal_domains="breadth")["invalid_fields"])
        self.assertIn("fatal_set_trivial", R.set_standard(self.r, fatal_domains=[])["invalid_fields"])

    def test_no_hidden_length_gate_only_dup_similarity_gates(self):
        # B is far longer than A (length-ratio well below the old hardcoded 0.5); ONLY Jaccard>=dup_similarity decides
        a = _art(self.r, "https://a.com/1"); b = _art(self.r, "https://b.com/2")
        core = "alpha beta gamma delta epsilon zeta theta"
        R.record_finding(self.r, "x", "OBSERVED", a["artifact_id"], quote=core, conclusion_id="C1")
        R.record_finding(self.r, "x", "OBSERVED", b["artifact_id"],
                         quote=core + " plus lots more padding tokens here making this much longer than first indeed truly", conclusion_id="C1")
        sid = R.set_standard(self.r, min_independent_sources=2, dup_similarity=0.2, fatal_domains=["breadth"])["standard_id"]
        g = R.grade_conclusion(self.r, "C1", sid)
        self.assertEqual(g["domains"]["breadth"]["value"]["effective_sources"], 1)   # echo-collapsed, no length-gate block
        self.assertTrue(g["domains"]["breadth"]["value"]["syndication_suspected"])

    def test_as_of_garbage_raises(self):
        a = _art(self.r, "https://a.com/1")
        R.record_finding(self.r, "x", "OBSERVED", a["artifact_id"], quote="q", conclusion_id="C1")
        sid = R.set_standard(self.r, max_age_days=14, fatal_domains=["recency"])["standard_id"]
        with self.assertRaises(ValueError):
            R.grade_conclusion(self.r, "C1", sid, as_of="last week")

    def test_standard_warnings_surfaced_in_grade(self):
        a = _art(self.r, "https://a.com/1")
        R.record_finding(self.r, "x", "OBSERVED", a["artifact_id"], quote="q", conclusion_id="C1")
        sid = R.set_standard(self.r, min_independent_sources=2, min_distinct_hosts=3, fatal_domains=["breadth"])["standard_id"]
        self.assertIn("volume_bar_incoherent", R.grade_conclusion(self.r, "C1", sid)["standard_warnings"])

    def test_filler_word_not_false_conflict(self):   # Q300 comb-07: shared 'according' filler != a numeric conflict
        a, b = _art(self.r, "https://a.com/1"), _art(self.r, "https://b.com/2")
        R.record_finding(self.r, "x", "OBSERVED", a["artifact_id"], quote="revenue reached 500 according first", conclusion_id="C1")
        R.record_finding(self.r, "x", "OBSERVED", b["artifact_id"], quote="profit posted 700 according second", conclusion_id="C1")
        g = R.grade_conclusion(self.r, "C1", R.set_standard(self.r, fatal_domains=["consistency"])["standard_id"])
        self.assertTrue(g["domains"]["consistency"]["met"])      # different entities (revenue/profit), only filler shared
        self.assertEqual(g["overall"], "MEETS")

    def test_nonlist_fatal_domains_does_not_crash(self):   # Q300 inv-18: fatal_domains=5 -> set(5) crash
        a = _art(self.r, "https://a.com/1")
        R.record_finding(self.r, "x", "OBSERVED", a["artifact_id"], quote="q", conclusion_id="C1")
        std = R.set_standard(self.r, min_independent_sources=1, fatal_domains=5)
        self.assertIn("fatal_domains_not_list", std["invalid_fields"])
        self.assertEqual(R.grade_conclusion(self.r, "C1", std["standard_id"])["overall"], "UNGRADED")   # no crash

    def test_shingles_drops_en_stop_so_fillers_dont_inflate_near_dup(self):
        # REGRESSION: _shingles once dropped the _EN_STOP filter that _numeric_conflicts.toks applies -> EN fillers
        # inflated near-dup Jaccard -> falsely collapsed INDEPENDENT sources -> understated breadth (the opposite of
        # intent). Same content words + different fillers MUST give identical shingles; no filler may survive.
        self.assertEqual(R._shingles("revenue according between growth margin which during"),
                         R._shingles("revenue growth margin"))      # fillers stripped; content words & order identical
        flat = {w for sh in R._shingles("growth according margin between revenue") for w in sh}
        self.assertFalse(flat & R._EN_STOP)                          # no _EN_STOP filler survives into the shingles

    def test_host_ip_literals_not_collapsed_by_etld(self):   # stress G2#009: 1.2.3.4 & 9.8.3.4 are distinct origins
        self.assertEqual(R._host("https://1.2.3.4/p"), "1.2.3.4")               # IP returned whole, not last-2-labels
        self.assertNotEqual(R._host("https://1.2.3.4/p"), R._host("https://9.8.3.4/p"))   # was: both -> '3.4' (collapse)
        self.assertNotEqual(R._host("http://[2001:db8::1]/p"), R._host("http://[2001:db8::2]/p"))   # IPv6 distinct

    def test_decimal_int_same_value_not_false_conflict(self):   # stress G4#044: 3.0 == 3 numerically -> NOT a conflict
        a, b = _art(self.r, "https://a.com/1"), _art(self.r, "https://b.com/2")
        R.record_finding(self.r, "x", "OBSERVED", a["artifact_id"], quote="discount interest 3.0 fixed", conclusion_id="C1")
        R.record_finding(self.r, "x", "OBSERVED", b["artifact_id"], quote="discount interest 3 fixed", conclusion_id="C1")
        g = R.grade_conclusion(self.r, "C1", R.set_standard(self.r, fatal_domains=["consistency"])["standard_id"])
        self.assertTrue(g["domains"]["consistency"]["met"])     # display formatting (3.0 vs 3) is not a disagreement
        self.assertEqual(g["overall"], "MEETS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
