"""TDD for validate_independence.py — independence + echo + prediction gate for leesearch-alpha.
Locks in the prediction-source fix (predictions.jsonl, NOT ledger.jsonl — the false no-prediction RECON bug)
plus echo-cluster + host-concentration detection. stdlib only.
Run: python -m unittest test_validate_independence -v
"""
import os, sys, tempfile, shutil, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refledger as R
import validate_independence as VI


class IndependenceGate(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("vi", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _art(self, src, typ):
        p = os.path.join(self.r, "a_" + R.sha256_bytes((src + typ).encode())[:8] + ".txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("ev")
        return R.ledger_append(self.r, type=typ, source=src, method="m", path=p,
                               canonical_path=p, sha256=R.sha256_file(p), quality_label="OK")

    def _confirm(self, hid, src, typ, text):
        a = self._art(src, typ)
        R.record_finding(self.r, text, "OBSERVED", a["artifact_id"], quote="ev",
                         hypothesis_id=hid, polarity="confirms")

    def _alpha_grade_fixture(self):
        """3 distinct hosts, 2 modalities (web+structured), distinct texts, 1 prediction = ALPHA."""
        hid = R.set_hypothesis(self.r, "hidden powerhouse thesis", stakes="med")["hypothesis_id"]
        self._confirm(hid, "https://news.aaa.com/1", "html", "first signal about reactor capacity expansion")
        self._confirm(hid, "https://ntis.go.kr/2", "json", "second structured row funding allocation rose")
        self._confirm(hid, "https://bbb.org/3", "html", "third independent host notes export volume climbing")
        R.predict(self.r, "this entity leads its niche by 2027", 0.6, "2027-06-30", hypothesis_id=hid)
        return hid

    def test_alpha_when_independent_multimodal_with_prediction(self):
        self._alpha_grade_fixture()
        res = VI.validate_independence(self.r)
        h = res["hypotheses"][0]
        self.assertEqual(h["label"], "ALPHA", h["issues"])
        self.assertTrue(res["pass"])
        self.assertEqual(h["independent_hosts"], 3)
        self.assertIn("structured", h["modalities"])

    def test_prediction_counted_from_predictions_jsonl(self):   # regression: was read from ledger.jsonl -> 0
        hid = self._alpha_grade_fixture()
        h = VI.validate_independence(self.r, hid)["hypotheses"][0]
        self.assertEqual(h["predictions"], 1)
        self.assertNotIn("no-falsifiable-prediction", h["issues"])

    def test_thin_hosts_is_recon(self):
        hid = R.set_hypothesis(self.r, "thin thesis", stakes="med")["hypothesis_id"]
        self._confirm(hid, "https://only.aaa.com/1", "html", "one host says alpha thing here")
        self._confirm(hid, "https://only.aaa.com/2", "json", "same host structured second claim")
        R.predict(self.r, "claim", 0.6, "2027-06-30", hypothesis_id=hid)
        res = VI.validate_independence(self.r, hid)
        self.assertEqual(res["hypotheses"][0]["label"], "RECON")
        self.assertFalse(res["pass"])

    def test_echo_cluster_detected_and_blocks_pass(self):
        hid = R.set_hypothesis(self.r, "echo thesis", stakes="med")["hypothesis_id"]
        echo = "the company announced a record breaking quarter with surging international revenue today"
        self._confirm(hid, "https://wire1.com/1", "html", echo)
        self._confirm(hid, "https://wire2.com/2", "html", echo + " reported")   # near-identical = echo
        self._confirm(hid, "https://real.org/3", "json", "an unrelated structured datapoint entirely")
        R.predict(self.r, "claim", 0.6, "2027-06-30", hypothesis_id=hid)
        h = VI.validate_independence(self.r, hid)["hypotheses"][0]
        self.assertGreaterEqual(h["echo_clusters"], 1)
        self.assertFalse(h["pass"])
        self.assertTrue(any("echo-clusters" in s for s in h["issues"]))

    def test_host_concentration_blocks_pass(self):
        hid = R.set_hypothesis(self.r, "concentrated thesis", stakes="med")["hypothesis_id"]
        # 3 of 4 confirming findings from one host (>50%) but distinct text -> concentration, not echo
        self._confirm(hid, "https://dom.com/a", "html", "alpha aaa unique sentence number one here")
        self._confirm(hid, "https://dom.com/b", "json", "beta bbb totally different content two here")
        self._confirm(hid, "https://dom.com/c", "html", "gamma ccc yet another distinct line three")
        self._confirm(hid, "https://other.org/d", "html", "delta ddd from a separate independent host")
        R.predict(self.r, "claim", 0.6, "2027-06-30", hypothesis_id=hid)
        h = VI.validate_independence(self.r, hid)["hypotheses"][0]
        self.assertFalse(h["pass"])
        self.assertTrue(any("host-concentration" in s for s in h["issues"]))

    def test_missing_ledger_returns_error(self):
        res = VI.validate_independence(os.path.join(self.d, "no_such"))
        self.assertFalse(res["pass"])
        self.assertIn("error", res)


if __name__ == "__main__":
    unittest.main()
