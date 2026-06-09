"""TDD for check_shapes.py — deterministic shape-budget validator for leesearch-alpha.
Locks in the classification fix (raw `type` vocabulary, NOT EVIDENCE_KIND labels: json→structured, not
unstructured) + the stakes-keyed budget floor. stdlib only. Run: python -m unittest test_check_shapes -v
"""
import os, sys, tempfile, shutil, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refledger as R
import check_shapes as CS


class ShapeClassification(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("cs", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _art(self, src, typ):
        p = os.path.join(self.r, "a_" + R.sha256_bytes((src + typ).encode())[:8] + ".txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("ev " + src)
        return R.ledger_append(self.r, type=typ, source=src, method="m", path=p,
                               canonical_path=p, sha256=R.sha256_file(p), quality_label="OK")

    def _shape_of(self, src, typ):
        return CS._classify_shape(self._art(src, typ))

    def test_html_is_unstructured(self):
        self.assertEqual(self._shape_of("https://news.a.com/1", "html"), "unstructured")

    def test_json_is_structured_not_unstructured(self):   # regression for the measured misclassification bug
        self.assertEqual(self._shape_of("https://ntis.go.kr/2", "json"), "structured")

    def test_csv_is_structured(self):
        self.assertEqual(self._shape_of("https://dart.fss.or.kr/3", "csv"), "structured")

    def test_pdf_is_semi_structured(self):
        self.assertEqual(self._shape_of("https://x.com/r.pdf", "pdf"), "semi-structured")

    def test_transcript_is_video(self):   # av modality = you consumed the spoken content
        self.assertEqual(self._shape_of("https://youtube.com/w", "transcript"), "video")

    def test_audio_and_video_types_are_video(self):
        self.assertEqual(self._shape_of("https://p.com/a", "audio"), "video")
        self.assertEqual(self._shape_of("https://p.com/v", "video"), "video")

    def test_image_is_semi_structured_not_video(self):   # a bare frame ≠ consuming the video (catches checkbox compliance)
        self.assertEqual(self._shape_of("https://p.com/frame", "image"), "semi-structured")

    def test_ocr_is_ocr(self):
        self.assertEqual(self._shape_of("https://p.com/scan", "ocr"), "ocr")

    def test_unknown_type_falls_back_to_extension_then_unstructured(self):
        self.assertEqual(self._shape_of("https://x.com/data.json", "weird"), "structured")
        self.assertEqual(self._shape_of("https://x.com/plain", "weird"), "unstructured")


class Budget(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("b", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _art(self, src, typ):
        p = os.path.join(self.r, "a_" + R.sha256_bytes((src + typ).encode())[:8] + ".txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("ev")
        return R.ledger_append(self.r, type=typ, source=src, method="m", path=p,
                               canonical_path=p, sha256=R.sha256_file(p), quality_label="OK")

    def _find(self, src, typ, hid=""):
        a = self._art(src, typ)
        R.record_finding(self.r, "sig " + src, "OBSERVED", a["artifact_id"], quote="ev",
                         hypothesis_id=hid, polarity="confirms")

    def test_low_stakes_passes_with_three_unstructured_and_total_floor(self):
        hid = R.set_hypothesis(self.r, "thesis", stakes="low")["hypothesis_id"]
        for i in range(13):   # low total floor = 12
            self._find(f"https://h{i}.com/p", "html", hid)
        res = CS.check_shapes(self.r)
        self.assertEqual(res["stakes"], "low")
        self.assertTrue(res["pass"], res.get("issues"))

    def test_low_stakes_fails_below_total_floor(self):
        hid = R.set_hypothesis(self.r, "thesis", stakes="low")["hypothesis_id"]
        for i in range(5):
            self._find(f"https://h{i}.com/p", "html", hid)
        res = CS.check_shapes(self.r)
        self.assertFalse(res["pass"])
        self.assertTrue(any("total-candidates" in s for s in res["issues"]))

    def test_med_stakes_flags_missing_structured_shape(self):
        hid = R.set_hypothesis(self.r, "thesis", stakes="med")["hypothesis_id"]
        for i in range(30):
            self._find(f"https://h{i}.com/p", "html", hid)   # all unstructured -> missing semi + structured
        res = CS.check_shapes(self.r)
        self.assertFalse(res["pass"])
        self.assertTrue(any("missing-structured" in s for s in res["issues"]))
        self.assertTrue(any("missing-semi-structured" in s for s in res["issues"]))

    def test_stakes_override_beats_hypothesis_value(self):
        R.set_hypothesis(self.r, "thesis", stakes="low")
        for i in range(3):
            self._find(f"https://h{i}.com/p", "html")
        self.assertEqual(CS.check_shapes(self.r, stakes_override="high")["stakes"], "high")

    def test_missing_ledger_returns_error_not_crash(self):
        res = CS.check_shapes(os.path.join(self.d, "no_such_dir"))
        self.assertFalse(res["pass"])
        self.assertIn("error", res)


if __name__ == "__main__":
    unittest.main()
