"""test_debunk.py — DEBUNK mode + event-origin echo collapse (derived from the 2026-06-19 11-thesis batch test).

DEBUNK mode = the twin of alpha DISCOVER: the hypothesis is the FALSIFICATION ("claim C is false/stale/
misattributed"); confirming findings = PRIMARY contradictions. Measured gap: framing the popular claim as the
hypothesis and disconfirming it stamps RECON "no-confirming-signals" — a successful debunk read as failure.
Fix: a debunk verdict vocabulary (CONFIRMED-FALSE/TRUE/UNRESOLVED). Event-origin: N outlets re-reporting one
press cycle / one investigation = 1 independent observation (measured G2: 5 of 6 "independent" hosts were one
acquisition press cycle); `finding --origin` collapses them.
"""
import os, shutil, sys, json, subprocess, tempfile, unittest
import refledger as R


class _Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.r = R.open_research("debunk-test", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _art(self, src, typ="html"):
        p = os.path.join(self.r, "a_" + R.sha256_bytes(src.encode())[:8] + ".txt")
        open(p, "w", encoding="utf-8").write("ev " + src)
        return R.ledger_append(self.r, type=typ, source=src, method="m", path=p,
                               canonical_path=p, sha256=R.sha256_file(p), quality_label="OK")


class HypothesisMode(_Base):
    def test_mode_defaults_to_discover_and_persists(self):
        self.assertEqual(R.set_hypothesis(self.r, "a thesis")["mode"], "discover")
        self.assertEqual(R.set_hypothesis(self.r, "b thesis", mode="debunk")["mode"], "debunk")

    def test_mode_is_validated(self):
        with self.assertRaises(ValueError):
            R.set_hypothesis(self.r, "c thesis", mode="bogus")

    def test_finding_origin_persists_and_defaults_empty(self):
        a = self._art("https://x.com/1")
        self.assertEqual(R.record_finding(self.r, "s", "OBSERVED", a["artifact_id"], quote="q").get("origin"), "")
        self.assertEqual(R.record_finding(self.r, "s2", "OBSERVED", a["artifact_id"], quote="q",
                                          origin="event:acq-2025-11-17")["origin"], "event:acq-2025-11-17")


class OriginCollapse(_Base):
    def test_same_origin_collapses_across_distinct_hosts(self):
        # 3 DISTINCT hosts, but all re-report ONE event -> 1 independent observation (G2 press-cycle echo).
        h = R.set_hypothesis(self.r, "company X pivots", mode="discover")["hypothesis_id"]
        for src in ("https://a.com/1", "https://b.com/2", "https://c.com/3"):
            a = self._art(src)
            R.record_finding(self.r, "distinct wording " + src, "OBSERVED", a["artifact_id"], quote=src,
                             hypothesis_id=h, polarity="confirms", origin="event:acq-2025-11-17")
        t = R.triangulate(self.r, h)
        self.assertEqual(t["independent_confirming_hosts"], 3)          # raw hosts unchanged (transparency)
        self.assertEqual(t["independent_confirming_origins"], 1)        # collapsed to one observation
        self.assertEqual(t["net_independent_origins"], 1)

    def test_no_origin_means_origins_equal_hosts(self):
        h = R.set_hypothesis(self.r, "back-compat thesis")["hypothesis_id"]
        for src in ("https://a.com/1", "https://b.com/2"):
            a = self._art(src)
            R.record_finding(self.r, "sig " + src, "OBSERVED", a["artifact_id"], quote=src,
                             hypothesis_id=h, polarity="confirms")
        t = R.triangulate(self.r, h)
        self.assertEqual(t["independent_confirming_origins"], t["independent_confirming_hosts"])
        self.assertEqual(t["net_independent_origins"], t["net_independent"])

    def test_mixed_origin_partial_tagging(self):
        # 2 findings share one origin, a 3rd is untagged (falls back to host) -> 2 independent observations, 3 hosts.
        h = R.set_hypothesis(self.r, "mixed origin thesis")["hypothesis_id"]
        for i, (src, org) in enumerate((("https://a.com/1", "event:E"), ("https://b.com/2", "event:E"),
                                        ("https://c.com/3", ""))):
            a = self._art(src)
            kw = {"origin": org} if org else {}
            R.record_finding(self.r, f"sig {i}", "OBSERVED", a["artifact_id"], quote=src,
                             hypothesis_id=h, polarity="confirms", **kw)
        t = R.triangulate(self.r, h)
        self.assertEqual(t["independent_confirming_hosts"], 3)
        self.assertEqual(t["independent_confirming_origins"], 2)   # {origin:E, c.com}

    def test_origin_string_does_not_collide_with_a_host(self):
        # an origin literally equal to a bare host must NOT collapse with an untagged finding on that host.
        h = R.set_hypothesis(self.r, "namespace thesis")["hypothesis_id"]
        a1 = self._art("https://b.com/1"); a2 = self._art("https://a.com/2")
        R.record_finding(self.r, "tagged", "OBSERVED", a1["artifact_id"], quote="q1",
                         hypothesis_id=h, polarity="confirms", origin="a.com")   # origin string == a host
        R.record_finding(self.r, "untagged on a.com", "OBSERVED", a2["artifact_id"], quote="q2",
                         hypothesis_id=h, polarity="confirms")                    # host a.com, no origin
        t = R.triangulate(self.r, h)
        self.assertEqual(t["independent_confirming_origins"], 2)   # {origin:a.com, a.com} stay distinct


class AlphaUsesOrigins(_Base):
    def test_event_echo_collapses_alpha_independence(self):
        # 5 same-event hosts should NOT clear the 3-independent-host alpha floor once origin-collapsed.
        tri = {"confirming": 5, "confirming_modalities": ["web", "structured"], "confirming_distinct_claims": 5,
               "net_independent": 4, "independent_confirming_hosts": 5,
               "net_independent_origins": 1, "independent_confirming_origins": 1}
        lab = R.alpha_label(tri, stakes="high", distinct_predictions=1)
        self.assertEqual(lab["label"], "RECON")
        self.assertTrue(any("thin-independence(1<3)" in x for x in lab["reasons"]))

    def test_alpha_label_falls_back_to_hosts_when_no_origin_keys(self):
        # hand-built tri dicts (existing tests) without origin keys must behave exactly as before.
        tri = {"confirming": 3, "confirming_modalities": ["web", "structured"],
               "confirming_distinct_claims": 3, "net_independent": 2, "independent_confirming_hosts": 3}
        self.assertEqual(R.alpha_label(tri, distinct_predictions=1)["label"], "ALPHA")


class DebunkLabel(_Base):
    def _tri(self, **kw):
        base = {"confirming": 0, "disconfirming": 0, "confirming_modalities": [], "confirming_distinct_claims": 0,
                "net_independent": 0, "independent_confirming_hosts": 0, "independent_disconfirming_hosts": 0,
                "net_independent_origins": 0, "independent_confirming_origins": 0, "independent_disconfirming_origins": 0}
        base.update(kw)
        return base

    def test_confirmed_false_on_corroborated_falsification(self):
        tri = self._tri(confirming=3, confirming_distinct_claims=3, confirming_modalities=["web"],
                        net_independent_origins=3, independent_confirming_origins=3)
        lab = R.debunk_label(tri, distinct_predictions=1)
        self.assertEqual(lab["label"], "CONFIRMED-FALSE")
        self.assertTrue(lab["confirmed_false"])
        self.assertTrue(lab["resolved"])

    def test_confirmed_true_when_falsification_is_itself_refuted(self):
        tri = self._tri(disconfirming=3, net_independent_origins=-3, independent_disconfirming_origins=3)
        lab = R.debunk_label(tri, distinct_predictions=1)
        self.assertEqual(lab["label"], "CONFIRMED-TRUE")
        self.assertFalse(lab["confirmed_false"])

    def test_unresolved_when_thin(self):
        tri = self._tri(confirming=1, confirming_distinct_claims=1, confirming_modalities=["web"],
                        net_independent_origins=1, independent_confirming_origins=1)
        lab = R.debunk_label(tri, distinct_predictions=1)
        self.assertEqual(lab["label"], "UNRESOLVED")
        self.assertTrue(any("thin-independence" in x for x in lab["reasons"]))

    def test_echo_and_single_modality_are_advisory_not_fatal(self):
        # provenance debunks legitimately rest on one authoritative investigation restated by fact-checkers:
        # echo + single-modality are REPORTED but must NOT flip a corroborated CONFIRMED-FALSE.
        tri = self._tri(confirming=3, confirming_distinct_claims=1, confirming_modalities=["web"],
                        net_independent_origins=3, independent_confirming_origins=3)
        lab = R.debunk_label(tri, distinct_predictions=1)
        self.assertEqual(lab["label"], "CONFIRMED-FALSE")
        self.assertTrue(any("echoed-claims(3->1)" in x for x in lab["reasons"]))
        self.assertIn("single-modality", lab["reasons"])

    def test_high_stakes_unresolved_warns(self):
        tri = self._tri(confirming=1, confirming_distinct_claims=1, confirming_modalities=["web"],
                        net_independent_origins=1, independent_confirming_origins=1)
        lab = R.debunk_label(tri, stakes="high", distinct_predictions=1)
        self.assertEqual(lab["warning"], "HIGH-STAKES DEBUNK UNRESOLVED")

    def test_criteria_overridable(self):
        tri = self._tri(confirming=1, confirming_distinct_claims=1, confirming_modalities=["web"],
                        net_independent_origins=1, independent_confirming_origins=1)
        lab = R.debunk_label(tri, distinct_predictions=1, criteria={"min_independent_origins": 1})
        self.assertEqual(lab["label"], "CONFIRMED-FALSE")

    def test_no_overturn_condition_reason(self):
        tri = self._tri(confirming=3, confirming_distinct_claims=3, confirming_modalities=["web", "structured"],
                        independent_confirming_origins=3)
        self.assertIn("no-overturn-condition", R.debunk_label(tri, distinct_predictions=0)["reasons"])

    def test_echoed_predictions_reason(self):
        tri = self._tri(confirming=3, confirming_distinct_claims=3, confirming_modalities=["web", "structured"],
                        independent_confirming_origins=3)
        lab = R.debunk_label(tri, distinct_predictions=1, raw_predictions=3)
        self.assertTrue(any("echoed-predictions(3->1)" in x for x in lab["reasons"]))

    def test_balanced_evidence_is_unresolved_not_false(self):
        # a TIE (equal independent origins both sides) must be UNRESOLVED, never silently CONFIRMED-FALSE.
        tri = self._tri(confirming=2, disconfirming=2, confirming_distinct_claims=2,
                        confirming_modalities=["web", "structured"],
                        independent_confirming_origins=2, independent_disconfirming_origins=2)
        lab = R.debunk_label(tri, distinct_predictions=1)
        self.assertEqual(lab["label"], "UNRESOLVED")
        self.assertIn("balanced-evidence", lab["reasons"])

    def test_tie_stays_unresolved_even_if_agent_drops_min_net_to_zero(self):
        tri = self._tri(confirming=2, disconfirming=2, confirming_distinct_claims=2,
                        confirming_modalities=["web", "structured"],
                        independent_confirming_origins=2, independent_disconfirming_origins=2)
        self.assertEqual(R.debunk_label(tri, distinct_predictions=1, criteria={"min_net": 0})["label"], "UNRESOLVED")

    def test_confirmed_true_suppresses_confirming_side_caveats(self):
        # disconfirm wins; echo/single-modality describe the LOSING confirming side -> must NOT be attached.
        tri = self._tri(confirming=2, disconfirming=5, confirming_distinct_claims=1, confirming_modalities=["web"],
                        independent_confirming_origins=2, independent_disconfirming_origins=5)
        lab = R.debunk_label(tri, distinct_predictions=1)
        self.assertEqual(lab["label"], "CONFIRMED-TRUE")
        self.assertNotIn("single-modality", lab["reasons"])
        self.assertFalse(any("echoed-claims" in x for x in lab["reasons"]))

    def test_net_derived_from_floor_counts_not_trusted_field(self):
        # a hand-built tri whose net_independent_origins lies must not override the floor counts (idisc dominates).
        tri = self._tri(confirming=2, disconfirming=5, confirming_distinct_claims=2,
                        confirming_modalities=["web", "structured"], net_independent_origins=2,
                        independent_confirming_origins=2, independent_disconfirming_origins=5)
        self.assertEqual(R.debunk_label(tri, distinct_predictions=1)["label"], "CONFIRMED-TRUE")

    def test_verdict_label_routes_by_mode(self):
        tri_alpha = {"confirming": 3, "confirming_modalities": ["web", "structured"], "confirming_distinct_claims": 3,
                     "net_independent": 2, "independent_confirming_hosts": 3}
        self.assertEqual(R.verdict_label(tri_alpha, mode="discover", distinct_predictions=1)["label"], "ALPHA")
        tri_deb = self._tri(confirming=3, confirming_distinct_claims=3, confirming_modalities=["web", "structured"],
                            independent_confirming_origins=3)
        self.assertEqual(R.verdict_label(tri_deb, mode="debunk", distinct_predictions=1)["label"], "CONFIRMED-FALSE")
        # an unknown/corrupted mode falls back to the discover verdict (defensive default)
        self.assertEqual(R.verdict_label(tri_alpha, mode="garbage", distinct_predictions=1)["label"], "ALPHA")


class DebunkEndToEnd(_Base):
    def test_digest_stamps_confirmed_false_for_debunk_mode(self):
        h = R.set_hypothesis(self.r, "claim C is misattributed and false", mode="debunk")["hypothesis_id"]
        for src in ("https://quoteinvestigator.com/x", "https://snopes.com/y", "https://archive.org/z"):
            a = self._art(src)
            R.record_finding(self.r, "primary contradiction at " + src, "OBSERVED", a["artifact_id"],
                             quote=src, hypothesis_id=h, polarity="confirms")
        R.predict(self.r, "any primary source linking the claim would overturn this", 0.9, "2027-06-30", hypothesis_id=h)
        txt = open(R.digest(self.r), encoding="utf-8").read()
        self.assertIn("CONFIRMED-FALSE", txt)
        self.assertNotIn("no-confirming-signals", txt)   # the OLD mislabel must be gone for a debunk

    def test_validate_independence_passes_a_corroborated_debunk(self):
        import validate_independence as VI
        h = R.set_hypothesis(self.r, "stat S has no primary source", mode="debunk")["hypothesis_id"]
        for src in ("https://bbc.com/a", "https://factcheck.org/b", "https://nature.com/c"):
            a = self._art(src)
            R.record_finding(self.r, "no primary source found per " + src, "OBSERVED", a["artifact_id"],
                             quote=src, hypothesis_id=h, polarity="confirms")
        R.predict(self.r, "a real study would overturn this", 0.9, "2027-06-30", hypothesis_id=h)
        res = VI.validate_independence(self.r, h)
        self.assertTrue(res["pass"])
        self.assertEqual(res["hypotheses"][0]["label"], "CONFIRMED-FALSE")

    def test_digest_stamps_confirmed_true_for_disconfirm_dominant_debunk(self):
        h = R.set_hypothesis(self.r, "claim D is false (but primaries actually SUPPORT it)", mode="debunk")["hypothesis_id"]
        for src in ("https://a.com/1", "https://b.com/2", "https://c.com/3"):
            a = self._art(src)
            R.record_finding(self.r, "primary source SUPPORTS the claim at " + src, "OBSERVED", a["artifact_id"],
                             quote=src, hypothesis_id=h, polarity="disconfirms")
        txt = open(R.digest(self.r), encoding="utf-8").read()
        self.assertIn("CONFIRMED-TRUE", txt)

    def test_unresolved_thin_debunk_stamps_and_fails_the_gate(self):
        import validate_independence as VI
        h = R.set_hypothesis(self.r, "claim E rests on one source", mode="debunk")["hypothesis_id"]
        a = self._art("https://only.com/1")
        R.record_finding(self.r, "single contradiction", "OBSERVED", a["artifact_id"], quote="q",
                         hypothesis_id=h, polarity="confirms")
        txt = open(R.digest(self.r), encoding="utf-8").read()
        self.assertIn("UNRESOLVED", txt)
        res = VI.validate_independence(self.r, h)
        self.assertFalse(res["pass"])                              # an UNRESOLVED debunk must NOT pass the gate
        self.assertEqual(res["hypotheses"][0]["label"], "UNRESOLVED")


class OriginFlipsVerdictEndToEnd(_Base):
    """THE seam the feature exists for: record_finding(origin) -> triangulate(_unit_of) -> alpha_label flip,
    proven through the REAL ledger (not a hand-built tri dict) so a bug dropping `origin` would be caught."""
    def _build(self, origin=None):
        h = R.set_hypothesis(self.r, "X is a hidden powerhouse with converging signals", mode="discover")["hypothesis_id"]
        rows = (("https://a.com/1", "json", "hiring velocity tripled across senior infrastructure roles last quarter"),
                ("https://b.com/2", "html", "patent filings in adjacent domains cluster tightly around one lab"),
                ("https://c.com/3", "html", "conference keynotes repeatedly cite the same obscure benchmark result"))
        for src, typ, text in rows:                              # GENUINELY distinct text so distinct_claims stays 3
            a = self._art(src, typ)
            kw = {"origin": origin} if origin else {}
            R.record_finding(self.r, text, "OBSERVED", a["artifact_id"],
                             quote=src, hypothesis_id=h, polarity="confirms", **kw)
        R.predict(self.r, "X reaches the milestone by 2027", 0.6, "2027-06-30", hypothesis_id=h)
        return h

    def test_three_independent_observations_are_alpha(self):
        import validate_independence as VI
        h = self._build(origin=None)                              # 3 distinct hosts, 2 modalities, distinct text, 1 predict
        res = VI.validate_independence(self.r, h)
        self.assertEqual(res["hypotheses"][0]["label"], "ALPHA")
        self.assertTrue(res["pass"])

    def test_one_press_cycle_collapses_to_recon(self):
        import validate_independence as VI
        h = self._build(origin="event:one-press-cycle")          # same 3 hosts, but ONE event -> 1 observation
        res = VI.validate_independence(self.r, h)
        self.assertEqual(res["hypotheses"][0]["label"], "RECON")
        self.assertFalse(res["pass"])
        self.assertTrue(any("thin-independence(1<3)" in x for x in res["hypotheses"][0]["issues"]))


class CliRoundtrip(unittest.TestCase):
    """The argparse->function wiring for the two new flags (positional order in main()'s record_finding call is
    fragile — origin is appended last). Runs the real CLI via subprocess on a throwaway slug, then cleans it up."""
    def setUp(self):
        self.here = os.path.dirname(os.path.abspath(R.__file__))
        self.slug = self._run("open", "cli-debunk-roundtrip-throwaway").stdout.strip()
        self.rdir = os.path.join(self.here, "research", self.slug)

    def tearDown(self):
        shutil.rmtree(self.rdir, ignore_errors=True)

    def _run(self, *args):
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        return subprocess.run([sys.executable, "refledger.py", *args], cwd=self.here,
                              capture_output=True, text=True, encoding="utf-8", env=env)

    def _art(self, src):
        p = os.path.join(self.rdir, "a_" + R.sha256_bytes(src.encode())[:8] + ".txt")
        open(p, "w", encoding="utf-8").write("ev " + src)
        return R.ledger_append(self.rdir, type="html", source=src, method="m", path=p,
                               canonical_path=p, sha256=R.sha256_file(p), quality_label="OK")["artifact_id"]

    def test_cli_mode_and_origin_roundtrip(self):
        h = json.loads(self._run("hypothesis", self.slug, "claim C is false", "--mode", "debunk").stdout)
        self.assertEqual(h["mode"], "debunk")
        hid = h["hypothesis_id"]
        a1, a2 = self._art("https://a.com/1"), self._art("https://b.com/2")
        f = json.loads(self._run("finding", self.slug, "contradiction 1", "OBSERVED", a1,
                                 "--quote", "q1", "--hypothesis", hid, "--polarity", "confirms",
                                 "--origin", "event:E").stdout)
        self.assertEqual(f["origin"], "event:E")                 # --origin reached the row through the positional chain
        self._run("finding", self.slug, "contradiction 2", "OBSERVED", a2,
                  "--quote", "q2", "--hypothesis", hid, "--polarity", "confirms", "--origin", "event:E")
        tri = json.loads(self._run("triangulate", self.slug, hid).stdout)
        self.assertEqual(tri["independent_confirming_hosts"], 2)  # 2 distinct hosts
        self.assertEqual(tri["independent_confirming_origins"], 1)  # collapsed by the shared origin


if __name__ == "__main__":
    unittest.main(verbosity=2)
