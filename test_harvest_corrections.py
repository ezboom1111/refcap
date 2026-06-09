"""TDD for harvest_corrections.py — RECON→ALPHA correction-pattern miner.
Isolated by monkeypatching the module RESEARCH_DIR to a temp tree; runs built via the real refledger API
with a hand-written SUMMARY.md stamp for deterministic label control. stdlib only.
Run: python -m unittest test_harvest_corrections -v
"""
import os, sys, tempfile, shutil, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refledger as R
import harvest_corrections as HC


class Harvest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.research = os.path.join(self.d, "research")
        os.makedirs(self.research)
        self._orig = HC.RESEARCH_DIR
        HC.RESEARCH_DIR = self.research

    def tearDown(self):
        HC.RESEARCH_DIR = self._orig
        shutil.rmtree(self.d, ignore_errors=True)

    def _art(self, rdir, src, typ):
        p = os.path.join(rdir, "a_" + R.sha256_bytes((src + typ).encode())[:8] + ".txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("ev")
        return R.ledger_append(rdir, type=typ, source=src, method="m", path=p,
                               canonical_path=p, sha256=R.sha256_file(p), quality_label="OK")

    def _build_run(self, goal, findings, label):
        """findings = list of (src, type, polarity). label = 'ALPHA'/'RECON' written into SUMMARY.md."""
        rdir = R.open_research(goal, base=self.research)
        hid = R.set_hypothesis(rdir, goal, stakes="med")["hypothesis_id"]
        for src, typ, pol in findings:
            a = self._art(rdir, src, typ)
            R.record_finding(rdir, "s " + src, "OBSERVED", a["artifact_id"], quote="ev",
                             hypothesis_id=hid, polarity=pol)
        with open(os.path.join(rdir, "SUMMARY.md"), "w", encoding="utf-8") as f:
            f.write(f"# digest\n\n- thesis  [{label}]\n")
        return rdir

    def test_empty_research_dir_reports_zero(self):
        res = HC.harvest()
        self.assertEqual(res["total_runs"], 0)

    def test_alpha_run_counted_and_corrections_extracted(self):
        self._build_run("alpha goal one", [
            ("https://news.aaa.com/1", "html", "confirms"),
            ("https://ntis.go.kr/2", "json", "confirms"),
            ("https://bbb.org/3", "html", "confirms"),
            ("https://ccc.net/4", "html", "disconfirms"),
        ], "ALPHA")
        res = HC.harvest()
        self.assertEqual(res["total_runs"], 1)
        self.assertEqual(res["alpha_count"], 1)
        types = {c["type"] for c in res["corrections"]}
        self.assertIn("modality-expansion", types)   # 2 modalities (web+structured) + ALPHA
        self.assertIn("disconfirm-added", types)      # has a disconfirm + ALPHA
        self.assertIn("host-diversification", types)  # >=3 hosts + ALPHA

    def test_recon_run_contributes_gaps_not_corrections(self):
        self._build_run("recon goal", [
            ("https://only.aaa.com/1", "html", "confirms"),
            ("https://only.aaa.com/2", "html", "confirms"),
        ], "RECON")
        res = HC.harvest()
        self.assertEqual(res["recon_count"], 1)
        self.assertEqual(res["alpha_count"], 0)
        gaps = res["common_recon_gaps"]
        self.assertGreaterEqual(gaps.get("single-modality", 0), 1)
        self.assertGreaterEqual(gaps.get("thin-hosts", 0), 1)

    def test_mixed_runs_tally_independently(self):
        self._build_run("a1", [("https://a.com/1", "html", "confirms"),
                               ("https://b.go.kr/2", "json", "confirms"),
                               ("https://c.org/3", "html", "confirms")], "ALPHA")
        self._build_run("r1", [("https://x.com/1", "html", "confirms")], "RECON")
        res = HC.harvest()
        self.assertEqual(res["total_runs"], 2)
        self.assertEqual(res["alpha_count"], 1)
        self.assertEqual(res["recon_count"], 1)

    def test_prediction_read_from_predictions_jsonl(self):   # regression: was read from ledger.jsonl -> always 0
        rdir = self._build_run("with pred", [("https://a.com/1", "html", "confirms")], "RECON")
        hid = R._read_jsonl(os.path.join(rdir, "ledger.jsonl"))
        hid = [r for r in hid if r.get("kind") == "hypothesis"][0]["hypothesis_id"]
        R.predict(rdir, "a falsifiable claim", 0.6, "2027-06-30", hypothesis_id=hid)
        res = HC.harvest()
        run = [r for r in res["runs"] if r["slug"] == os.path.basename(rdir)][0]
        self.assertTrue(run["has_prediction"])
        self.assertEqual(res["common_recon_gaps"].get("no-prediction", 0), 0)   # gap must NOT fire

    def test_no_prediction_gap_fires_only_when_truly_absent(self):
        self._build_run("nopred", [("https://x.com/1", "html", "confirms")], "RECON")   # no predict() call
        res = HC.harvest()
        self.assertEqual(res["common_recon_gaps"].get("no-prediction", 0), 1)

    def test_since_filter_excludes_future_cutoff(self):   # regression: --since was silently ignored
        self._build_run("dated", [("https://a.com/1", "html", "confirms")], "ALPHA")
        self.assertEqual(HC.harvest(since="2099-01-01")["total_runs"], 0)
        self.assertEqual(HC.harvest(since="2000-01-01")["total_runs"], 1)

    def test_single_modality_gap_ignores_other_class(self):   # regression: 'other' (ocr/text) inflated mod count
        # one real modality (web) + one 'other' (ocr type, absent from _MODALITY_CLASS) -> still single-modality
        self._build_run("mods", [("https://a.com/1", "html", "confirms"),
                                 ("https://b.com/2", "ocr", "confirms")], "RECON")
        res = HC.harvest()
        self.assertEqual(res["common_recon_gaps"].get("single-modality", 0), 1)

    def test_corrections_do_not_mutate_runs_entries(self):   # regression: slug injected into runs[].corrections
        self._build_run("clean", [("https://a.com/1", "html", "confirms"),
                                  ("https://b.go.kr/2", "json", "confirms"),
                                  ("https://c.org/3", "html", "confirms")], "ALPHA")
        res = HC.harvest()
        for run in res["runs"]:
            for c in run.get("corrections", []):
                self.assertNotIn("slug", c)   # the run's own correction dicts stay clean


if __name__ == "__main__":
    unittest.main()
