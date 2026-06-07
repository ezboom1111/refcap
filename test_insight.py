"""TDD for the insight-accuracy advisory surfacers (Rank 2/3/5):
  Rank 2 - measure_capture_error: a NUMBER (CER) on layer-1 capture fidelity vs a human truth span.
  Rank 3 - verify.fake_corroboration (a 'corroborated' finding whose sources share a host) + numeric_conflicts.
  Rank 5 - verify.open_at_stop (what frontier was left open when verify/digest ran).
All SURFACE, never adjudicate (ok stays = dangling/mismatch/unverifiable). stdlib only.
Run: python -m unittest test_insight -v
"""
import os, sys, tempfile, shutil, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refledger as R


def _art(r, src):
    return R.ledger_append(r, type="html", source=src, method="m", path="p", sha256="h", quality_label="OK")


class CaptureError(unittest.TestCase):  # Rank 2
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)
        self.a = _art(self.r, "https://x.com/v")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_cer_math(self):
        self.assertEqual(R._cer("hallo", "hello"), 0.2)   # 1 sub / 5 chars
        self.assertEqual(R._cer("", "hello"), 1.0)
        self.assertEqual(R._cer("hello", "hello"), 0.0)
        self.assertEqual(R._cer("x", ""), 0.0)            # empty ref -> 0 (nothing to score against)

    def test_measure_appends_and_surfaces_in_verify(self):
        R.measure_capture_error(self.r, self.a["artifact_id"], "내돈내산 캉캉", "내 돈 내산 캉캉 스커트")
        R.record_finding(self.r, "주장", "OBSERVED", self.a["artifact_id"], quote="내돈내산 캉캉")
        v = R.verify(self.r)
        self.assertIn(self.a["artifact_id"], v["capture_errors"])
        self.assertGreater(v["capture_errors"][self.a["artifact_id"]], 0.0)

    def test_measure_unknown_artifact_rejected(self):
        with self.assertRaises(ValueError):
            R.measure_capture_error(self.r, "a_nope", "x", "y")


class FakeCorroboration(unittest.TestCase):  # Rank 3
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_same_host_corroboration_flagged(self):
        a = _art(self.r, "https://site-a.com/1")
        b = _art(self.r, "https://www.site-a.com/2")   # SAME registrable host (www stripped) -> fake independence
        R.record_finding(self.r, "교차검증됨", "OBSERVED", a["artifact_id"], quote="q", corroborated_by=[b["artifact_id"]])
        v = R.verify(self.r)
        self.assertIn(a["artifact_id"], v["fake_corroboration"])

    def test_distinct_hosts_not_flagged(self):
        a = _art(self.r, "https://site-a.com/1")
        b = _art(self.r, "https://site-b.com/2")       # genuinely independent domains
        R.record_finding(self.r, "교차검증됨", "OBSERVED", a["artifact_id"], quote="q", corroborated_by=[b["artifact_id"]])
        v = R.verify(self.r)
        self.assertEqual(v["fake_corroboration"], [])

    def test_dangling_corroboration_rejected(self):
        a = _art(self.r, "https://site-a.com/1")
        with self.assertRaises(ValueError):
            R.record_finding(self.r, "x", "OBSERVED", a["artifact_id"], corroborated_by=["a_nope"])


class NumericConflicts(unittest.TestCase):  # Rank 3 (narrow advisory — false-flag bar matters)
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)
        self.a = _art(self.r, "https://x.com/1")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_shared_entity_differing_numbers_flagged(self):
        R.record_finding(self.r, "가격 정보", "OBSERVED", self.a["artifact_id"], quote="가격은 9900원")
        R.record_finding(self.r, "가격 정보", "OBSERVED", self.a["artifact_id"], quote="가격은 19900원")
        v = R.verify(self.r)
        self.assertEqual(len(v["numeric_conflicts"]), 1)
        self.assertEqual(set(v["numeric_conflicts"][0]["numbers"]), {"9900", "19900"})

    def test_no_false_flag_on_unrelated_findings(self):
        # different entities (조회수 vs 구독자), numbers differ but NO shared content token -> NOT a conflict
        R.record_finding(self.r, "유튜브 지표", "OBSERVED", self.a["artifact_id"], quote="조회수 100")
        R.record_finding(self.r, "유튜브 지표", "OBSERVED", self.a["artifact_id"], quote="구독자 5000")
        self.assertEqual(R.verify(self.r)["numeric_conflicts"], [])

    def test_same_number_not_flagged(self):
        R.record_finding(self.r, "가격", "OBSERVED", self.a["artifact_id"], quote="가격은 9900원")
        R.record_finding(self.r, "가격", "OBSERVED", self.a["artifact_id"], quote="가격은 9900원입니다")
        self.assertEqual(R.verify(self.r)["numeric_conflicts"], [])

    def test_english_stopwords_do_not_false_flag(self):
        # share only 'is'/'the' (ASCII <4 chars, skipped) -> different numbers but no real shared entity
        R.record_finding(self.r, "m", "OBSERVED", self.a["artifact_id"], quote="the rank is 5")
        R.record_finding(self.r, "m", "OBSERVED", self.a["artifact_id"], quote="the price is 100")
        self.assertEqual(R.verify(self.r)["numeric_conflicts"], [])


class OpenAtStop(unittest.TestCase):  # Rank 5
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_open_at_stop_reports_unclosed_frontier(self):
        R.frontier_open(self.r, "공식 사이트 미확인", kind="question")
        R.frontier_open(self.r, "반대 후기 미확인", kind="question")
        R.frontier_close(self.r, "공식 사이트 미확인", reason="declined")
        v = R.verify(self.r)
        self.assertEqual(v["open_at_stop"], ["반대 후기 미확인"])   # the one still open when verify ran


class HardeningPass(unittest.TestCase):   # the 2nd adversarial-review pass (copula / subdomain / empty-truth)
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_measure_rejects_empty_truth(self):
        a = _art(self.r, "https://x.com/v")
        with self.assertRaises(ValueError):                       # empty ref -> CER undefined, don't persist 0.0
            R.measure_capture_error(self.r, a["artifact_id"], "machine text", "")

    def test_korean_copula_does_not_false_flag(self):            # 입니다 is a copula, not an entity
        a = _art(self.r, "https://x.com/v")
        R.record_finding(self.r, "m", "OBSERVED", a["artifact_id"], quote="조회수 100입니다")
        R.record_finding(self.r, "m", "OBSERVED", a["artifact_id"], quote="구독자 200입니다")
        self.assertEqual(R.verify(self.r)["numeric_conflicts"], [])

    def test_subdomain_same_org_is_fake_corroboration(self):     # news.naver.com vs blog.naver.com = same org
        a = _art(self.r, "https://news.naver.com/1")
        b = _art(self.r, "https://blog.naver.com/2")
        R.record_finding(self.r, "교차", "OBSERVED", a["artifact_id"], quote="q", corroborated_by=[b["artifact_id"]])
        self.assertIn(a["artifact_id"], R.verify(self.r)["fake_corroboration"])

    def test_distinct_kr_orgs_not_flagged(self):
        a = _art(self.r, "https://news.naver.com/1")
        b = _art(self.r, "https://news.daum.net/2")
        R.record_finding(self.r, "교차", "OBSERVED", a["artifact_id"], quote="q", corroborated_by=[b["artifact_id"]])
        self.assertEqual(R.verify(self.r)["fake_corroboration"], [])

    def test_host_reduces_subdomain_and_keeps_cctld(self):
        self.assertEqual(R._host("https://news.naver.com/x"), "naver.com")
        self.assertEqual(R._host("https://sub.example.co.kr/x"), "example.co.kr")
        self.assertEqual(R._host("https://www.site.com"), "site.com")

    def test_fake_corroboration_deduped(self):                   # two findings on same artifact -> one entry
        a = _art(self.r, "https://site.com/1")
        b = _art(self.r, "https://site.com/2")
        R.record_finding(self.r, "c1", "OBSERVED", a["artifact_id"], quote="q1", corroborated_by=[b["artifact_id"]])
        R.record_finding(self.r, "c2", "OBSERVED", a["artifact_id"], quote="q2", corroborated_by=[b["artifact_id"]])
        self.assertEqual(R.verify(self.r)["fake_corroboration"].count(a["artifact_id"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
