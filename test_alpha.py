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

    def test_digest_surfaces_alpha_and_predictions(self):   # alpha layer must be VISIBLE in the digest, not siloed
        h = R.set_hypothesis(self.r, "thesis Z is a hidden powerhouse")["hypothesis_id"]
        a = self._art("https://x.com/1")
        R.record_finding(self.r, "sig", "OBSERVED", a["artifact_id"], quote="q", hypothesis_id=h, polarity="confirms")
        R.predict(self.r, "X will happen by 2027", 0.6, "2027-01-01", hypothesis_id=h)
        txt = open(R.digest(self.r), encoding="utf-8").read()
        self.assertIn("알파 가설", txt)          # Rank-7 surfaced
        self.assertIn("예측", txt)               # predictions surfaced
        self.assertIn("thesis Z", txt)

    def test_verify_flags_alpha_signal_on_walled_capture(self):   # Rank-7 advisory: alpha signal resting on a walled capture
        h = R.set_hypothesis(self.r, "thesis")["hypothesis_id"]
        p = os.path.join(self.r, "bad.txt"); open(p, "w", encoding="utf-8").write("login required")
        a = R.ledger_append(self.r, type="html", source="https://x.com/login", method="m", path=p,
                            canonical_path=p, sha256=R.sha256_file(p), quality_label="LOGIN_WALL")
        R.record_finding(self.r, "sig", "OBSERVED", a["artifact_id"], quote="login required", hypothesis_id=h, polarity="confirms")
        v = R.verify(self.r)
        self.assertIn(a["artifact_id"], v["alpha_signals_on_bad_capture"])
        self.assertTrue(v["ok"])                 # advisory only — ok unchanged (warning, agent decides)


# The REAL hidden-gem-natl bug fixtures (predict() ran twice with a paraphrase, inflating "predict 3" to a true 2).
# _DUP_A vs _DUP_B are the actual duplicate pair (measured 3-gram Jaccard 0.727); _DISTINCT scored 0.000 vs both.
# The fix ANNOTATES (near_duplicate_of) + counts distinct — never drops (append-only).
_DUP_A = "채용조건형 계약학과 협약 대학/정원이 2027학년도까지 추가 확대된다 (현 13개교 18개학과 대비 증가) — '입학=취업보장' 트랙의 알파가 priced-in 되며 입결 경쟁률 상승"
_DUP_B = "채용조건형 계약학과 협약 대학/정원이 2027학년도까지 추가 확대된다 (현 13개교 18개학과 대비 증가): 입학=취업보장 트랙 알파가 priced-in 되며 입결 경쟁률 상승"
_DISTINCT = "코리아텍·UST·과기원(DGIST 등) 류 '저브랜드·고취업/전액펀딩' 학교의 일반인 인지도가 2027년까지 상승해 입학 경쟁률이 오른다(알파 decay)"


class AlphaDedupeAndStakes(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("dedup", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _art(self, src, typ="html"):
        p = os.path.join(self.r, "a_" + R.sha256_bytes(src.encode())[:8] + ".txt")
        open(p, "w", encoding="utf-8").write("ev " + src)
        return R.ledger_append(self.r, type=typ, source=src, method="m", path=p, canonical_path=p,
                               sha256=R.sha256_file(p), quality_label="OK")

    def test_predict_flags_near_duplicate_resubmit(self):
        h = R.set_hypothesis(self.r, "t")["hypothesis_id"]
        p1 = R.predict(self.r, _DUP_A, 0.7, "2027-06-30", hypothesis_id=h)
        p2 = R.predict(self.r, _DUP_B, 0.7, "2027-06-30", hypothesis_id=h)   # paraphrase, same date+hyp
        self.assertEqual(p1["near_duplicate_of"], "")
        self.assertEqual(p2["near_duplicate_of"], p1["prediction_id"])       # flagged, not dropped
        rows = [r for r in R._read_jsonl(os.path.join(self.r, "predictions.jsonl")) if r.get("kind") == "prediction"]
        self.assertEqual(len(rows), 2)                                       # append-only preserved

    def test_predict_not_flagged_when_distinct_or_different_deadline(self):
        h = R.set_hypothesis(self.r, "t")["hypothesis_id"]
        R.predict(self.r, _DUP_A, 0.7, "2027-06-30", hypothesis_id=h)
        self.assertEqual(R.predict(self.r, _DISTINCT, 0.6, "2027-12-31", hypothesis_id=h)["near_duplicate_of"], "")
        # SAME claim but a DIFFERENT resolve_by is a genuine re-forecast, not a dup
        self.assertEqual(R.predict(self.r, _DUP_A, 0.7, "2028-01-01", hypothesis_id=h)["near_duplicate_of"], "")

    def test_calibration_counts_distinct_predictions(self):
        h = R.set_hypothesis(self.r, "t")["hypothesis_id"]
        R.predict(self.r, _DUP_A, 0.7, "2027-06-30", hypothesis_id=h)
        R.predict(self.r, _DUP_B, 0.7, "2027-06-30", hypothesis_id=h)        # near-dup of A
        R.predict(self.r, _DISTINCT, 0.6, "2027-12-31", hypothesis_id=h)
        cal = R.calibration(self.r)
        self.assertEqual(cal["n_predictions"], 3)
        self.assertEqual(cal["n_distinct_predictions"], 2)                   # the inflation is now surfaced

    def test_triangulate_reports_distinct_claims(self):
        h = R.set_hypothesis(self.r, "t")["hypothesis_id"]
        echo = "코리아텍 취업률 80 퍼센트 전국 3위 라는 동일 주장 의 반복 신호 입니다"
        for src in ("https://aa.com/1", "https://bb.com/2"):                 # same CLAIM text, two distinct hosts
            a = self._art(src)
            R.record_finding(self.r, echo, "OBSERVED", a["artifact_id"], quote=src, hypothesis_id=h, polarity="confirms")
        a3 = self._art("https://cc.com/3")
        R.record_finding(self.r, "UST 등록금 면제 월 stipend 전액장학 생활비 레그 라는 별개 신호",
                         "OBSERVED", a3["artifact_id"], quote="x", hypothesis_id=h, polarity="confirms")
        t = R.triangulate(self.r, h)
        self.assertEqual(t["confirming"], 3)
        self.assertEqual(t["confirming_distinct_claims"], 2)                 # 2 echoed collapse -> 1, + 1 distinct = 2

    def test_set_hypothesis_stakes_validated_and_stored(self):
        self.assertEqual(R.set_hypothesis(self.r, "thesis hi", stakes="high")["stakes"], "high")
        self.assertEqual(R.set_hypothesis(self.r, "thesis default")["stakes"], "")
        with self.assertRaises(ValueError):
            R.set_hypothesis(self.r, "thesis bad", stakes="huge")

    def test_alpha_label_single_modality_alone_is_mild_recon(self):
        # RECALIBRATED (live n=2: single-modality fires near-universally on KR runs since authority sources are
        # JS-walled -> 'web'). single-modality ALONE = honest RECON label, but NOT a loud cry-wolf warning.
        tri = {"confirming": 5, "confirming_modalities": ["web"], "confirming_distinct_claims": 5, "net_independent": 4}
        lab = R.alpha_label(tri, stakes="high")
        self.assertFalse(lab["alpha"]); self.assertEqual(lab["label"], "RECON")
        self.assertEqual(lab["reasons"], ["single-modality"])
        self.assertEqual(lab["warning"], "")                                 # no alarm on the common single-modality case

    def test_alpha_label_loud_when_shortfall_beyond_single_modality(self):
        # the REAL hidden-gem-natl shape: single-modality AND echoed predictions -> egregious -> LOUD (still caught).
        tri = {"confirming": 5, "confirming_modalities": ["web"], "confirming_distinct_claims": 5, "net_independent": 4}
        lab = R.alpha_label(tri, stakes="high", distinct_predictions=2, raw_predictions=3)
        self.assertEqual(lab["label"], "RECON")
        self.assertTrue(any("echoed-predictions" in r for r in lab["reasons"]))
        self.assertEqual(lab["warning"], "HIGH-STAKES EFFORT SHORTFALL")

    def test_alpha_label_alpha_on_multimodal_converging(self):
        tri = {"confirming": 3, "confirming_modalities": ["web", "structured"],
               "confirming_distinct_claims": 3, "net_independent": 2}
        lab = R.alpha_label(tri, stakes="high", distinct_predictions=1)
        self.assertTrue(lab["alpha"]); self.assertEqual(lab["label"], "ALPHA"); self.assertEqual(lab["reasons"], [])

    def test_alpha_label_flags_echoed_and_missing_prediction(self):
        tri = {"confirming": 5, "confirming_modalities": ["web", "structured"],
               "confirming_distinct_claims": 3, "net_independent": 2}
        lab = R.alpha_label(tri, stakes="low", distinct_predictions=0)
        self.assertFalse(lab["alpha"])
        self.assertTrue(any("echoed-claims" in r for r in lab["reasons"]))
        self.assertIn("no-falsifiable-prediction", lab["reasons"])
        self.assertEqual(lab["warning"], "")                                 # low stakes -> quiet, just labeled

    def test_alpha_label_zero_confirming_signals_is_legible(self):           # reviewer MEDIUM-1
        tri = {"confirming": 0, "confirming_modalities": [], "confirming_distinct_claims": 0, "net_independent": 0}
        lab = R.alpha_label(tri)
        self.assertFalse(lab["alpha"])
        self.assertIn("no-confirming-signals", lab["reasons"])               # not the misleading "single-modality"

    def test_alpha_label_flags_echoed_predictions(self):                     # reviewer MEDIUM-2
        tri = {"confirming": 3, "confirming_modalities": ["web", "structured"],
               "confirming_distinct_claims": 3, "net_independent": 2}
        lab = R.alpha_label(tri, distinct_predictions=2, raw_predictions=3)  # 3 registered, only 2 distinct
        self.assertFalse(lab["alpha"])
        self.assertTrue(any("echoed-predictions(3->2)" in r for r in lab["reasons"]))
        # but a clean 1:1 prediction set is NOT flagged
        clean = R.alpha_label(tri, distinct_predictions=2, raw_predictions=2)
        self.assertTrue(clean["alpha"])

    def test_digest_surfaces_echoed_predictions_for_real_bug_shape(self):    # end-to-end: the hidden-gem-natl symptom
        h = R.set_hypothesis(self.r, "thesis with two modalities converging here", stakes="high")["hypothesis_id"]
        for src, typ in (("https://aa.com/1", "html"), ("https://ntis.go.kr/2", "json")):  # 2 modalities -> not single
            a = self._art(src, typ)
            R.record_finding(self.r, "distinct signal " + src, "OBSERVED", a["artifact_id"], quote=src,
                             hypothesis_id=h, polarity="confirms")
        R.predict(self.r, _DUP_A, 0.7, "2027-06-30", hypothesis_id=h)
        R.predict(self.r, _DUP_B, 0.7, "2027-06-30", hypothesis_id=h)        # near-dup -> echoed-predictions(2->1)
        txt = open(R.digest(self.r), encoding="utf-8").read()
        self.assertIn("echoed-predictions(2->1)", txt)
        self.assertIn("distinct 1", txt)                                     # 예측 header shows distinct count

    def test_digest_stamps_recon_for_single_modality(self):
        h = R.set_hypothesis(self.r, "single modality thesis here", stakes="high")["hypothesis_id"]
        a = self._art("https://x.com/1")                                     # html -> web (one modality)
        R.record_finding(self.r, "sig one", "OBSERVED", a["artifact_id"], quote="q", hypothesis_id=h, polarity="confirms")
        txt = open(R.digest(self.r), encoding="utf-8").read()
        self.assertIn("RECON", txt)                                          # the mislabel-as-alpha is now structurally visible

    def test_alpha_criteria_is_agent_overridable_not_code_fixed(self):       # (3): no immovable methodology in the spine
        tri = {"confirming": 3, "confirming_modalities": ["web"], "confirming_distinct_claims": 3, "net_independent": 2}
        # default: single modality -> RECON
        self.assertEqual(R.alpha_label(tri, distinct_predictions=1)["label"], "RECON")
        # agent overrides the bar (e.g. a domain where one modality is acceptable) -> ALPHA, no spine edit needed
        self.assertEqual(R.alpha_label(tri, distinct_predictions=1, criteria={"min_modalities": 1})["label"], "ALPHA")

    def test_host_collapse_is_not_region_skewed(self):                       # de-bias _MULTI_SUFFIX (LatAm/SEA/etc.)
        self.assertEqual(R._host("https://shop.example.com.mx"), "example.com.mx")   # not "com.mx"
        self.assertEqual(R._host("https://a.example.com.sg"), "example.com.sg")
        self.assertEqual(R._host("https://b.example.co.za"), "example.co.za")
        self.assertEqual(R._host("https://news.naver.com/x"), "naver.com")           # 2-label still correct


if __name__ == "__main__":
    unittest.main(verbosity=2)
