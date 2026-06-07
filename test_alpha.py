"""TDD for the Rank-7 ALPHA layer (thesis + weak-signal triangulation). stdlib only.
Alpha = a non-obvious inference where many WEAK signals converge though no single source states it. A hypothesis
is the agent's falsifiable thesis; signals are findings tagged hypothesis_id + polarity; triangulate() REPORTS
independent convergence (distinct host AND modality) and the agent judges if it is decisive (no brain-in-code).
Run: python -m unittest test_alpha -v
"""
import os, sys, tempfile, shutil, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refledger as R


class AlphaLayer(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("a", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _art(self, src, typ="html"):
        p = os.path.join(self.r, "a_" + R.sha256_bytes(src.encode())[:8] + ".txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("ev " + src)
        return R.ledger_append(self.r, type=typ, source=src, method="m", path=p, canonical_path=p,
                               sha256=R.sha256_file(p), quality_label="OK")

    def test_hypothesis_create_and_stable_id(self):
        h1 = R.set_hypothesis(self.r, "lab X is a hidden 한수원 powerhouse", signature="sole-source", decay="3yr")
        self.assertTrue(h1["hypothesis_id"].startswith("hyp_"))
        self.assertEqual(h1["signature"], "sole-source")
        self.assertEqual(h1["hypothesis_id"], R.set_hypothesis(self.r, "lab X is a hidden 한수원 powerhouse")["hypothesis_id"])
        with self.assertRaises(ValueError):
            R.set_hypothesis(self.r, "   ")

    def test_bad_polarity_rejected(self):
        a = self._art("https://x.com/1")
        with self.assertRaises(ValueError):
            R.record_finding(self.r, "s", "OBSERVED", a["artifact_id"], quote="q", hypothesis_id="hyp_1", polarity="maybe")

    def test_triangulate_counts_independent_convergence(self):
        h = R.set_hypothesis(self.r, "thesis")["hypothesis_id"]
        for src, typ in (("https://ntis.go.kr/p1", "json"), ("https://patents.google.com/p2", "html"),
                         ("https://news.kbs.co.kr/p3", "html"), ("https://ntis.go.kr/p4", "json")):  # last = dup-host echo
            a = self._art(src, typ)
            R.record_finding(self.r, "sig", "OBSERVED", a["artifact_id"], quote=src, hypothesis_id=h, polarity="confirms")
        ad = self._art("https://blind.com/p5")
        R.record_finding(self.r, "counter", "OBSERVED", ad["artifact_id"], quote="x", hypothesis_id=h, polarity="disconfirms")
        t = R.triangulate(self.r, h)
        self.assertEqual(t["confirming"], 4)
        self.assertEqual(t["independent_confirming_hosts"], 3)     # ntis.go.kr echo collapses 4 -> 3 distinct hosts
        self.assertEqual(t["disconfirming"], 1)
        self.assertEqual(t["net_independent"], 2)                  # 3 confirming hosts - 1 disconfirming host
        self.assertEqual(set(t["confirming_modalities"]), {"structured", "web"})   # json->structured, html->web

    def test_predict_ties_to_hypothesis(self):
        h = R.set_hypothesis(self.r, "t")["hypothesis_id"]
        p = R.predict(self.r, "lab X grads place into 한수원 >50%", 0.7, "2027-06-01", hypothesis_id=h)
        self.assertEqual(p["hypothesis_id"], h)


if __name__ == "__main__":
    unittest.main(verbosity=2)
