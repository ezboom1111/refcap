"""Scenario-driven QA/QC tests — reproduce the REAL code defects the 100-scenario workflow found
(by probing the actual code), then assert the FIXED behavior. Design-intentional limits (speaker
attribution, contradiction detection, fabrication-at-capture) are NOT tested as bugs — they are the
agent's/farm's job by design. stdlib only. Run: python -m unittest test_scenarios -v
"""
import os, sys, json, re, tempfile, shutil, unittest, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refledger as R


class S_JsonlIntegrity(unittest.TestCase):  # op-02 (HIGHEST impact: a truncated line bricks everything)
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_truncated_last_line_does_not_brick(self):
        R.ledger_append(self.r, type="text", source="s", method="m", path="p", sha256="h", quality_label="OK")
        with open(os.path.join(self.r, "ledger.jsonl"), "a", encoding="utf-8") as f:
            f.write('{"kind":"artifact","artifact_id":"a_trunc"')   # crash mid-write -> partial line, no newline
        # verify/digest/plan/state must NOT raise JSONDecodeError; they tolerate the partial line
        v = R.verify(self.r)
        self.assertIsInstance(v, dict)
        self.assertEqual(R.frontier_state(self.r), {"open": [], "closed": [], "visited": []})


class S_VerifyIntegrity(unittest.TestCase):  # evidence_failure-09/10: false-pass holes
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)
        self.f = os.path.join(self.d, "a.txt")
        with open(self.f, "w", encoding="utf-8") as _fh:
            _fh.write("증거")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_deleted_file_makes_verify_not_ok(self):  # was: ok=true false-pass
        a = R.ledger_append(self.r, type="text", source="s", method="m", path=self.f,
                            sha256=R.sha256_file(self.f), quality_label="OK")
        self.assertTrue(R.verify(self.r)["ok"])
        os.remove(self.f)                              # capture file gone
        v = R.verify(self.r)
        self.assertFalse(v["ok"])                      # MUST NOT silently pass
        self.assertIn(a["artifact_id"], v.get("unverifiable", []))

    def test_none_hash_artifact_is_flagged(self):  # was: excluded from tamper detection
        a = R.ledger_append(self.r, type="image", source="s", method="m", path=self.f,
                            sha256=None, quality_label="UNKNOWN")
        v = R.verify(self.r)
        self.assertFalse(v["ok"])
        self.assertIn(a["artifact_id"], v.get("unverifiable", []))


class S_JsonQuality(unittest.TestCase):  # structured-02/03/10: json branch hardcoded 'OK'
    def test_error_envelope_not_OK(self):
        self.assertEqual(R.json_quality('{"error":"not found","code":404}'), "API_ERROR")
        self.assertEqual(R.json_quality('{"message":"API rate limit exceeded"}'), "API_ERROR")

    def test_malformed_json(self):
        self.assertEqual(R.json_quality('{"a":1,'), "MALFORMED")     # truncated

    def test_empty_json(self):
        self.assertEqual(R.json_quality("[]"), "EMPTY")

    def test_valid_json_ok(self):
        self.assertEqual(R.json_quality('{"items":[1,2,3],"ok":true}'), "OK")

    def test_json_bad_labels_in_BAD_QUALITY(self):
        for lbl in ("API_ERROR", "MALFORMED"):
            self.assertIn(lbl, R.BAD_QUALITY)


class S_FailedHeader(unittest.TestCase):  # unstructured-09 / adversarial-09
    def test_failed_extract_header_is_bad_quality(self):  # was: UNKNOWN (not warned)
        segs, q = R.parse_timed("# transcript FAILED: RuntimeError: bad container\n")
        self.assertEqual(segs, [])
        self.assertEqual(q, "EXTRACT_FAILED")
        self.assertIn("EXTRACT_FAILED", R.BAD_QUALITY)


class S_RealVttSrt(unittest.TestCase):  # semi-01/02: real WebVTT/SRT were parsed to []
    def test_real_webvtt_parses_cues(self):
        vtt = "WEBVTT\n\n00:00:00.000 --> 00:00:03.000\n첫 자막\n\n00:00:03.000 --> 00:00:05.500\n둘째 자막\n"
        segs, _ = R.parse_timed(vtt)
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0], {"start": 0.0, "end": 3.0, "text": "첫 자막"})

    def test_real_srt_parses_cues(self):
        srt = "1\n00:00:00,000 --> 00:00:02,000\n에스알티 한 줄\n\n2\n00:00:02,000 --> 00:00:04,000\n둘\n"
        segs, _ = R.parse_timed(srt)
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0]["text"], "에스알티 한 줄")
        self.assertAlmostEqual(segs[0]["end"], 2.0)

    def test_refcap_bracket_format_still_works(self):  # no regression
        segs, _ = R.parse_timed("# gate=OK\n[  0.0-  3.0] 브래킷 포맷\n")
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["text"], "브래킷 포맷")


class S_DetectTypeFixes(unittest.TestCase):  # sp-03/04/05/10, structured-07, unstructured-11
    def test_api_substring_does_not_force_json_for_html_docs(self):
        self.assertEqual(R.detect_type("https://github.com/api/docs"), "html")   # was: json (over-match)
        self.assertEqual(R.detect_type("https://api.example.com/v1/items"), "json")  # real api host -> json

    def test_video_host_requires_video_path(self):
        self.assertEqual(R.detect_type("https://youtube.com/@channel/about"), "html")  # was: video (over-match)
        self.assertEqual(R.detect_type("https://instagram.com/p/abc"), "html")         # photo post, not video
        self.assertEqual(R.detect_type("https://www.youtube.com/watch?v=X"), "video")  # real video path
        self.assertEqual(R.detect_type("https://youtu.be/abc"), "video")
        self.assertEqual(R.detect_type("https://www.tiktok.com/@u/video/123"), "video")

    def test_audio_and_csv_recognized(self):
        self.assertEqual(R.detect_type("podcast.mp3"), "audio")   # was: unknown
        self.assertEqual(R.detect_type("data.csv"), "csv")        # was: unknown
        self.assertEqual(R.detect_type("a.wav"), "audio")


class S_FrontierVisit(unittest.TestCase):  # multi_source-08: visited dead-path (no writer existed)
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_visit_writer_populates_visited(self):
        R.frontier_visit(self.r, "https://x.com/seen", "이미 봄")
        self.assertIn("https://x.com/seen", R.frontier_state(self.r)["visited"])


class S_HttpSafety(unittest.TestCase):  # adversarial-03/04: SSRF + size cap
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_ssrf_private_host_refused(self):
        dest = os.path.join(self.d, "x.html")
        for url in ("http://169.254.169.254/latest/meta-data/", "http://localhost:8080/admin", "http://127.0.0.1/"):
            with self.assertRaises(Exception):
                R._http_get(url, dest)


class S_Concurrency(unittest.TestCase):  # op-03: dedupe TOCTOU race (was: 20 threads -> arts>1)
    def test_dedupe_holds_under_thread_race(self):
        d = tempfile.mkdtemp()
        try:
            r = R.open_research("g", base=d)
            def w():
                R.ledger_append(r, type="t", source="http://x/v", method="m", path="p", sha256="h", quality_label="OK")
            ths = [threading.Thread(target=w) for _ in range(20)]
            for t in ths: t.start()
            for t in ths: t.join()
            with open(os.path.join(r, "ledger.jsonl"), encoding="utf-8") as _fh:
                rows = [json.loads(l) for l in _fh]
            arts = [x for x in rows if x["kind"] == "artifact"]
            self.assertEqual(len(arts), 1)   # dedupe is atomic under concurrency
        finally:
            shutil.rmtree(d, ignore_errors=True)


class S_PathSafety(unittest.TestCase):  # adversarial-05: path traversal into system files
    def test_path_ok_denies_system_dirs(self):
        self.assertFalse(R._path_ok(r"C:\Windows\win.ini"))
        self.assertFalse(R._path_ok("/etc/passwd"))
        self.assertFalse(R._path_ok("/sys/kernel/x"))
        self.assertTrue(R._path_ok("refs/clip/transcript.txt"))   # normal artifact path is fine

    def test_ingest_refuses_system_path(self):
        d = tempfile.mkdtemp()
        try:
            r = R.open_research("g", base=d)
            res = R.ingest(r, r"C:\Windows\System32\drivers\etc\hosts.txt")  # registerable ext, system dir
            self.assertIn("error", res)                                       # refused, not fingerprinted
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
