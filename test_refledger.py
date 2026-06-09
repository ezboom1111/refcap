"""TDD spec for refledger.py — the research-agent SPINE (evidence ledger + resume frontier).
Encodes the verified design philosophy + the 3 red-team MIN_FIXES as executable tests.
stdlib only (unittest). Run: python -m unittest test_refledger -v
"""
import os, sys, json, re, tempfile, shutil, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refledger as R

TIMED = (
    "# transcript (lang=ko, model=large-v3, via=accuracy-best-of-2(...)) - WASAPI loopback | "
    "gate=DEGENERATE coverage=0.8 voiced=44.2/55.1s logprob=-0.7\n"
    "[  0.0-  3.0] 첫 번째 문장입니다\n"
    "[  3.0-  7.5] 두 번째 문장 go go go\n"
)
TIMED_OK = (
    "# transcript (lang=ko, model=medium) - WASAPI loopback | gate=OK coverage=0.99\n"
    "[  0.0-  2.0] 깨끗한 내레이션\n"
)


class TestCanonical(unittest.TestCase):
    def test_parse_timed_strips_header_and_timestamps(self):
        segs, q = R.parse_timed(TIMED)
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0], {"start": 0.0, "end": 3.0, "text": "첫 번째 문장입니다"})
        self.assertEqual(segs[1]["text"], "두 번째 문장 go go go")  # text has NO '[..]' prefix, NO header
        for s in segs:                                    # the VO text alone, no timestamp/header noise
            self.assertNotIn("[", s["text"])
            self.assertNotIn("#", s["text"])
            self.assertNotIn("model=", s["text"])

    def test_quality_label_from_header(self):
        _, q = R.parse_timed(TIMED)
        self.assertEqual(q, "DEGENERATE")
        _, q2 = R.parse_timed(TIMED_OK)
        self.assertEqual(q2, "OK")
        _, q3 = R.parse_timed("[  0.0-  1.0] no header\n")
        self.assertEqual(q3, "UNKNOWN")

    def test_to_vtt_is_real_webvtt(self):  # FIX1: real WebVTT so farm parseWebVtt yields cues
        segs, _ = R.parse_timed(TIMED)
        vtt = R.to_vtt(segs)
        self.assertTrue(vtt.startswith("WEBVTT"))
        self.assertIn("-->", vtt)
        self.assertIn("00:00:00.000 --> 00:00:03.000", vtt)
        self.assertIn("첫 번째 문장입니다", vtt)

    def test_canonical_json_deterministic(self):  # FIX3: hash the canonical, not the version-stamped txt
        segs, _ = R.parse_timed(TIMED)
        a = R.canonical_json(segs)
        b = R.canonical_json(segs)
        self.assertEqual(a, b)
        self.assertEqual(R.sha256_bytes(a.encode()), R.sha256_bytes(b.encode()))
        # the version-stamped header (model=..., via=...) must NOT influence the canonical hash
        segs2, _ = R.parse_timed(TIMED.replace("large-v3", "medium").replace("accuracy-best-of-2(...)", "x"))
        self.assertEqual(R.canonical_json(segs2), a)  # same segments -> same hash regardless of run metadata


class TestWebQuality(unittest.TestCase):
    # (B) pre-capture quality label for web fetch — coverage_gate analogue; capture-FAILURE not content-type
    def test_ok_on_rich_content(self):
        self.assertEqual(R.web_quality("<p>" + ("진짜 콘텐츠 문장. " * 60) + "</p>"), "OK")

    def test_bot_wall(self):
        self.assertEqual(R.web_quality("Checking your browser before accessing. Cloudflare. captcha"), "BOT_WALL")

    def test_js_wall_distinct_from_bot_wall(self):   # JS shell -> escalate to browser render (login-free), NOT a bot challenge
        self.assertEqual(R.web_quality("<div id='root'></div> You need to enable JavaScript to run this app."), "JS_WALL")
        self.assertEqual(R.web_quality("Checking your browser before accessing. Cloudflare. captcha"), "BOT_WALL")  # bot unchanged
        rich = "<p>" + ("실제 본문 문장. " * 220) + " enable javascript</p>"   # marker word but content-rich
        self.assertEqual(R.web_quality(rich), "OK")                          # sparsity guard: not flagged

    def test_rich_page_with_passing_marker_is_OK(self):
        # REGRESSION (caught live): a 1.2MB Wikipedia article that MENTIONS 'captcha' once is NOT a bot wall.
        # Same lesson as the gyeongju degeneracy false-positive: a local marker in a big doc != failure.
        rich = "<p>" + ("리얼 기사 본문 내용입니다. " * 200) + " captcha 라는 단어가 한 번 나옴 </p>"
        self.assertGreater(len(re.sub(r"<[^>]+>", "", rich)), 1500)
        self.assertEqual(R.web_quality(rich), "OK")

    def test_empty_page(self):
        self.assertEqual(R.web_quality("<html><body></body></html>"), "EMPTY")

    def test_http_error_status(self):
        self.assertEqual(R.web_quality("Not Found", http_status=404), "HTTP_ERROR")

    def test_login_wall_only_when_sparse(self):
        self.assertEqual(R.web_quality("로그인이 필요합니다"), "LOGIN_WALL")          # sparse + marker -> wall
        rich = "로그인" + (" 일반 콘텐츠 본문." * 80)                                 # marker word but rich content
        self.assertEqual(R.web_quality(rich), "OK")                                  # not flagged (has real content)

    def test_bad_quality_set_includes_web_failures(self):
        for lbl in ("BOT_WALL", "JS_WALL", "LOGIN_WALL", "PAYWALL", "EMPTY", "HTTP_ERROR"):
            self.assertIn(lbl, R.BAD_QUALITY)                                        # -> verify warns on citation


class TestLedger(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.r = R.open_research("test goal", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_open_research_ascii_safe_dir(self):
        # Korean goal must NOT produce a non-ascii directory leaf (Windows subprocess/farm path safety)
        r2 = R.open_research("한글 목표 비디오 분석", base=self.d)
        leaf = os.path.basename(r2.rstrip("/\\"))
        self.assertTrue(leaf.isascii(), f"dir leaf must be ascii: {leaf!r}")

    def test_ledger_dedupe_by_logical_key_not_content_hash(self):
        # FIX3: same source+method dedupes EVEN IF content sha differs (non-deterministic whisper)
        a = R.ledger_append(self.r, type="video", source="http://x/v", method="refextract",
                            path="p1", sha256="HASH_A", quality_label="OK")
        b = R.ledger_append(self.r, type="video", source="http://x/v", method="refextract",
                            path="p2", sha256="HASH_B_DIFFERENT", quality_label="OK")
        self.assertEqual(a["artifact_id"], b["artifact_id"])  # deduped by (source|method)
        with open(os.path.join(self.r, "ledger.jsonl"), encoding="utf-8") as _fh:
            rows = [json.loads(l) for l in _fh]
        arts = [x for x in rows if x["kind"] == "artifact"]
        self.assertEqual(len(arts), 1)

    def test_record_finding_dangling_raises(self):  # local cite-or-fail
        with self.assertRaises(ValueError):
            R.record_finding(self.r, "주장", "OBSERVED", artifact_id="a_doesnotexist", locator="cue=1")

    def test_record_finding_ok(self):
        art = R.ledger_append(self.r, type="text", source="s", method="m", path="p", sha256="h", quality_label="OK")
        f = R.record_finding(self.r, "주장입니다", "OBSERVED", art["artifact_id"], locator="char=0..5")
        self.assertEqual(f["kind"], "finding")
        self.assertEqual(f["artifact_id"], art["artifact_id"])


class TestFrontier(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_frontier_reduce(self):  # event log -> reduced state; code persists/reduces, never prioritizes
        R.frontier_open(self.r, "구글: X", "question", "시드")
        R.frontier_open(self.r, "홈페이지 Y", "semi", "다음")
        R.frontier_close(self.r, "구글: X", "조사완료")
        st = R.frontier_state(self.r)
        self.assertIn("홈페이지 Y", st["open"])
        self.assertIn("구글: X", st["closed"])
        self.assertNotIn("구글: X", st["open"])


class TestVerify(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)
        self.f = os.path.join(self.d, "art.txt")
        with open(self.f, "w", encoding="utf-8") as _fh:
            _fh.write("증거 바이트")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_verify_detects_tamper(self):
        sha = R.sha256_file(self.f)
        art = R.ledger_append(self.r, type="text", source="s", method="m", path=self.f, sha256=sha, quality_label="OK")
        self.assertTrue(R.verify(self.r)["ok"])
        with open(self.f, "w", encoding="utf-8") as _fh:
            _fh.write("변조됨")  # tamper
        v = R.verify(self.r)
        self.assertFalse(v["ok"])
        self.assertTrue(v["hash_mismatch"])

    def test_verify_flags_low_quality_citation(self):  # principle 5: preserve label, agent decides (warn not block)
        art = R.ledger_append(self.r, type="video", source="s", method="m", path=self.f,
                             sha256=R.sha256_file(self.f), quality_label="DEGENERATE")
        R.record_finding(self.r, "이 환각전사에 근거한 주장", "OBSERVED", art["artifact_id"], locator="cue=1")
        v = R.verify(self.r)
        self.assertTrue(v["low_quality_citations"])  # warned, not blocked


class TestFarmPlan(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)
        self.txt = os.path.join(self.d, "t.txt")
        with open(self.txt, "w", encoding="utf-8") as _fh:
            _fh.write("hi")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_no_http_url_emits_no_transcript_channel_and_no_file_uri(self):  # FIX2
        art = R.ledger_append(self.r, type="transcript", source=self.txt, method="refrecord",
                             path=self.txt, canonical_path=self.txt, sha256=R.sha256_file(self.txt),
                             quality_label="OK")  # source is a local path, NOT http
        R.record_finding(self.r, "라이브캡처 주장", "OBSERVED", art["artifact_id"], locator="cue=1")
        plan = R.farm_plan(self.r)
        blob = json.dumps(plan, ensure_ascii=False)
        self.assertNotIn("file://", blob)
        self.assertFalse(any(c["tool"] == "farm_register_transcript" for c in plan["calls"]))
        self.assertTrue(any(s.get("reason") == "no_source_url" for s in plan["skipped"]))

    def test_add_claim_typed_and_anchored_to_verbatim_quote(self):
        # e2e-learned (farm round-trip): add_claim needs claimType+evidenceKind, and the anchor must be a
        # VERBATIM quote from the bytes (the claim text itself != bytes -> gate rejects "claim text not found")
        vtt = os.path.join(self.d, "t.vtt")
        with open(vtt, "w", encoding="utf-8") as _fh:
            _fh.write("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\n내돈내산 하신 캉캉 스커트\n")
        art = R.ledger_append(self.r, type="transcript", source="https://youtube.com/watch?v=X",
                             method="refextract", path=self.txt, canonical_path=vtt,
                             sha256=R.sha256_file(vtt), quality_label="OK")
        R.record_finding(self.r, "첫 추천템은 캉캉 스커트다", "OBSERVED", art["artifact_id"],
                        quote="내돈내산 하신 캉캉 스커트")   # verbatim span, distinct from the claim text
        addc = [c for c in R.farm_plan(self.r)["calls"] if c["tool"] == "farm_add_claim"][0]["args"]
        self.assertEqual(addc["claimType"], "text")
        self.assertEqual(addc["evidenceKind"], "transcript_cue")
        self.assertEqual(addc["anchor"]["type"], "text_span")
        self.assertEqual(addc["anchor"]["quote"], "내돈내산 하신 캉캉 스커트")  # NOT the claim text
        self.assertNotEqual(addc["anchor"]["quote"], "첫 추천템은 캉캉 스커트다")

    def test_http_transcript_uses_vtt_and_http_sourceurl(self):
        vtt = os.path.join(self.d, "t.vtt")
        with open(vtt, "w", encoding="utf-8") as _fh:
            _fh.write("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhi\n")
        art = R.ledger_append(self.r, type="transcript", source="https://youtube.com/watch?v=X",
                             method="refextract", path=self.txt, canonical_path=vtt,
                             sha256=R.sha256_file(vtt), quality_label="OK")
        R.record_finding(self.r, "유튜브 VO 주장", "OBSERVED", art["artifact_id"], locator="cue=0")
        plan = R.farm_plan(self.r)
        regs = [c for c in plan["calls"] if c["tool"] == "farm_register_transcript"]
        self.assertEqual(len(regs), 1)
        self.assertTrue(regs[0]["args"]["sourceUrl"].startswith("https://"))
        self.assertIn(".vtt", regs[0]["args"].get("vttPath", ""))


class TestDigestRobustness(unittest.TestCase):
    """digest must not crash on real-world artifacts whose sha256 is explicitly None (e.g. farm frame samples).
    Regression: `a.get('sha256','')[:12]` returned None (key present, value None) -> None[:12] TypeError."""
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("dg", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_digest_survives_none_sha_artifact_and_renders_hypothesis_and_prediction(self):
        a = R.ledger_append(self.r, type="image", source="local/frame.png", method="frame",
                            path="local/frame.png", sha256=None, quality_label="OK")
        hid = R.set_hypothesis(self.r, "X is a hidden powerhouse", stakes="med")["hypothesis_id"]
        R.record_finding(self.r, "signal", "OBSERVED", a["artifact_id"], quote="q",
                         hypothesis_id=hid, polarity="confirms")
        R.predict(self.r, "X beats its record by 2027", 0.6, "2027-06-30", hypothesis_id=hid)
        out = R.digest(self.r)                       # must NOT raise
        txt = open(out, encoding="utf-8").read()
        self.assertIn("X is a hidden powerhouse", txt)   # the INFERENCE is rendered
        self.assertIn("X beats its record by 2027", txt)  # the FORECAST is rendered alongside


class TestDetectType(unittest.TestCase):
    def test_inline_dispatch_extension_and_scheme_only(self):  # depth-0, NO content branching
        self.assertEqual(R.detect_type("a.mp4"), "video")
        self.assertEqual(R.detect_type("https://youtube.com/watch?v=x"), "video")
        self.assertEqual(R.detect_type("b.png"), "image")
        self.assertEqual(R.detect_type("c.vtt"), "transcript")
        self.assertEqual(R.detect_type("https://api.x.com/d.json"), "json")
        self.assertEqual(R.detect_type("https://site.com/page"), "html")
        self.assertEqual(R.detect_type("notes.txt"), "text")


if __name__ == "__main__":
    unittest.main(verbosity=2)
