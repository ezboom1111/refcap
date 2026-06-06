"""TDD for the prediction-outcome calibration log (Rank-1 of the insight-accuracy R&D roadmap).
Layer-3 INSIGHT accuracy needs a NON-CIRCULAR oracle: a falsifiable forecast scored against a FUTURE
real-world outcome the model cannot author at forecast time (unlike a self-graded fixture or LLM-judge).
Code only persists forecast/outcome NOUNS + does arithmetic (Brier, reliability); the AGENT forecasts and
adjudicates (VERBS). Sharpening (from the adversarial-verify pass): a resolution may cite an OBSERVED+anchored
evidence artifact so the hit/miss is itself auditable bytes; calib splits Brier(all) vs Brier(anchored).
stdlib only. Run: python -m unittest test_predictions -v
"""
import os, sys, tempfile, shutil, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refledger as R


class PredictBasics(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_predict_appends_row_with_id(self):
        row = R.predict(self.r, "this sound peaks within 2 weeks", 0.7, "2026-06-20", operator="peaks_within")
        self.assertEqual(row["kind"], "prediction")
        self.assertTrue(row["prediction_id"].startswith("p_"))
        self.assertEqual(row["stated_confidence"], 0.7)
        self.assertEqual(row["operator"], "peaks_within")
        rows = R._read_jsonl(os.path.join(self.r, "predictions.jsonl"))
        self.assertEqual(len([x for x in rows if x["kind"] == "prediction"]), 1)

    def test_confidence_out_of_range_rejected(self):
        for bad in (1.5, -0.1, "abc"):
            with self.assertRaises(ValueError):
                R.predict(self.r, "c", bad, "2026-06-20")

    def test_two_same_second_predictions_have_distinct_ids(self):
        a = R.predict(self.r, "same claim", 0.5, "2026-06-20")
        b = R.predict(self.r, "same claim", 0.5, "2026-06-20")
        self.assertNotEqual(a["prediction_id"], b["prediction_id"])   # size-disambiguated, not time-only

    def test_anchor_validated_if_given(self):
        with self.assertRaises(ValueError):                          # dangling basis-evidence -> refuse
            R.predict(self.r, "c", 0.5, "2026-06-20", anchor_artifact_id="a_nope")
        art = R.ledger_append(self.r, type="text", source="s", method="m", path="p", sha256="h", quality_label="OK")
        ok = R.predict(self.r, "c", 0.5, "2026-06-20", anchor_artifact_id=art["artifact_id"])
        self.assertEqual(ok["anchor_artifact_id"], art["artifact_id"])


class ResolveAndReduce(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_resolve_unknown_prediction_rejected(self):
        with self.assertRaises(ValueError):
            R.resolve(self.r, "p_nope", "hit")

    def test_bad_outcome_rejected(self):
        p = R.predict(self.r, "c", 0.5, "2026-06-20")
        with self.assertRaises(ValueError):
            R.resolve(self.r, p["prediction_id"], "maybe")

    def test_latest_resolution_wins(self):                            # event-log reduce, like frontier_state
        p = R.predict(self.r, "c", 0.8, "2026-06-20")
        R.resolve(self.r, p["prediction_id"], "miss")
        R.resolve(self.r, p["prediction_id"], "hit")                  # correction; latest wins
        c = R.calibration(self.r)
        self.assertEqual(c["n_resolved"], 1)
        self.assertAlmostEqual(c["brier_all"], (0.8 - 1.0) ** 2, places=4)

    def test_unresolved_and_open_excluded_from_resolved(self):
        a = R.predict(self.r, "a", 0.9, "2026-06-20"); R.resolve(self.r, a["prediction_id"], "hit")
        b = R.predict(self.r, "b", 0.5, "2026-06-20"); R.resolve(self.r, b["prediction_id"], "unresolved")
        R.predict(self.r, "c", 0.5, "2026-06-20")                    # never resolved (open)
        c = R.calibration(self.r)
        self.assertEqual(c["n_predictions"], 3)
        self.assertEqual(c["n_resolved"], 1)
        self.assertAlmostEqual(c["resolution_rate"], 1 / 3, places=3)  # hedging/open is EXPOSED, not hidden


class EvidenceAnchoring(unittest.TestCase):   # the adversarial-verify SHARPENING: auditable resolutions
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)
        self.art = R.ledger_append(self.r, type="text", source="s", method="m", path="p", sha256="h", quality_label="OK")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_evidence_requires_an_OBSERVED_finding(self):
        p = R.predict(self.r, "c", 0.7, "2026-06-20")
        with self.assertRaises(ValueError):                          # artifact exists but no OBSERVED finding
            R.resolve(self.r, p["prediction_id"], "hit", evidence_artifact=self.art["artifact_id"])

    def test_evidence_unknown_artifact_rejected(self):
        p = R.predict(self.r, "c", 0.7, "2026-06-20")
        with self.assertRaises(ValueError):
            R.resolve(self.r, p["prediction_id"], "hit", evidence_artifact="a_nope")

    def test_anchored_resolution_is_marked(self):
        R.record_finding(self.r, "관측된 결과", "OBSERVED", self.art["artifact_id"], quote="x")
        p = R.predict(self.r, "c", 0.7, "2026-06-20")
        row = R.resolve(self.r, p["prediction_id"], "hit", evidence_artifact=self.art["artifact_id"])
        self.assertTrue(row["anchored"])

    def test_brier_split_surfaces_unanchored_grades(self):
        R.record_finding(self.r, "관측", "OBSERVED", self.art["artifact_id"], quote="x")
        a = R.predict(self.r, "a", 0.9, "2026-06-20")
        R.resolve(self.r, a["prediction_id"], "hit", evidence_artifact=self.art["artifact_id"])   # anchored
        b = R.predict(self.r, "b", 0.9, "2026-06-20")
        R.resolve(self.r, b["prediction_id"], "miss")                                             # unanchored
        c = R.calibration(self.r)
        self.assertAlmostEqual(c["brier_anchored"], (0.9 - 1) ** 2, places=4)                     # hit only
        self.assertAlmostEqual(c["brier_all"], ((0.9 - 1) ** 2 + (0.9 - 0) ** 2) / 2, places=4)
        self.assertIsNotNone(c["brier_divergence"])


class BrierAndReliability(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_empty_calibration_does_not_crash(self):
        c = R.calibration(self.r)
        self.assertEqual(c["n_predictions"], 0)
        self.assertEqual(c["n_resolved"], 0)
        self.assertIsNone(c["brier_all"])
        self.assertEqual(c["reliability_buckets"], [])

    def test_brier_score_and_reliability_buckets(self):
        a = R.predict(self.r, "a", 0.9, "d"); R.resolve(self.r, a["prediction_id"], "hit")    # y=1, (0.9-1)^2=0.01, bucket 4
        b = R.predict(self.r, "b", 0.2, "d"); R.resolve(self.r, b["prediction_id"], "miss")   # y=0, (0.2-0)^2=0.04, bucket 1
        c = R.calibration(self.r)
        self.assertAlmostEqual(c["brier_all"], 0.025, places=4)
        b4 = [x for x in c["reliability_buckets"] if x["n"] == 1 and x["hit_rate"] == 1.0][0]
        self.assertAlmostEqual(b4["gap"], 0.1, places=3)              # |0.9 - 1.0|
        self.assertAlmostEqual(c["worst_bucket_gap"], 0.2, places=3)  # |0.2 - 0.0| in the miss bucket


class EdgeCases(unittest.TestCase):   # gaps the adversarial python-reviewer flagged
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_confidence_0_and_1_land_in_edge_buckets(self):
        a = R.predict(self.r, "a", 0.0, "d"); R.resolve(self.r, a["prediction_id"], "miss")  # bucket 0
        b = R.predict(self.r, "b", 1.0, "d"); R.resolve(self.r, b["prediction_id"], "hit")   # bucket 4
        c = R.calibration(self.r)
        ranges = [x["range"] for x in c["reliability_buckets"]]
        self.assertIn("[0.0,0.2)", ranges)
        self.assertIn("[0.8,1.0]", ranges)
        self.assertAlmostEqual(c["brier_all"], 0.0, places=4)        # 0.0/miss and 1.0/hit are both perfect

    def test_reresolve_hit_to_unresolved_removes_from_resolved(self):
        p = R.predict(self.r, "c", 0.7, "d")
        R.resolve(self.r, p["prediction_id"], "hit")
        self.assertEqual(R.calibration(self.r)["n_resolved"], 1)
        R.resolve(self.r, p["prediction_id"], "unresolved")          # correction: latest wins -> re-opened
        c = R.calibration(self.r)
        self.assertEqual(c["n_resolved"], 0)
        self.assertIsNone(c["brier_all"])

    def test_all_unanchored_divergence_is_none(self):
        a = R.predict(self.r, "a", 0.9, "d"); R.resolve(self.r, a["prediction_id"], "hit")
        c = R.calibration(self.r)
        self.assertIsNone(c["brier_anchored"])
        self.assertIsNone(c["brier_divergence"])


class ResolveSlugConfinement(unittest.TestCase):   # _resolve path-traversal (reviewer [BUG])
    def test_bare_slug_resolves_under_research_root(self):
        self.assertTrue(R._resolve("r_abc").endswith(os.path.join("research", "r_abc")))

    def test_traversal_slug_refused(self):
        with self.assertRaises(ValueError):
            R._resolve(os.path.join("..", "..", "etc"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
