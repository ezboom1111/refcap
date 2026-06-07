"""TDD for the QA-300 ingest fixes (300-scenario cross-domain QA found these):
  #1 remote register-only kinds (pdf/csv/text/image/audio/transcript over http) are now FETCHED, not left as
     empty unverifiable shells (sha256=None). The single most-cited cross-domain defect.
  #2 an HTML-routed body that is actually JSON (a keyed endpoint on a non-'api.' host) is labeled via
     json_quality (mechanical json.loads sniff), so API_ERROR/MALFORMED/EMPTY detection runs.
_http_get is MOCKED (no network). stdlib only. Run: python -m unittest test_ingest_fetch -v
"""
import os, sys, tempfile, shutil, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refledger as R


class _MockHttp:
    """Context manager: replace R._http_get with a writer returning canned bytes (no real network)."""
    def __init__(self, payload=b"BYTES", status=200, raise_exc=None):
        self.payload, self.status, self.raise_exc = payload, status, raise_exc

    def __enter__(self):
        self.orig = R._http_get
        outer = self

        def fake(url, dest, max_bytes=50_000_000):
            if outer.raise_exc:
                raise outer.raise_exc
            with open(dest, "wb") as f:
                f.write(outer.payload)
            return outer.status
        R._http_get = fake
        return self

    def __exit__(self, *a):
        R._http_get = self.orig


class RemoteFetch(unittest.TestCase):   # QA-300 #1
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_remote_pdf_downloaded_not_empty_shell(self):
        with _MockHttp(payload=b"%PDF-1.4 fake bytes"):
            art = R.ingest(self.r, "https://proceedings.neurips.cc/paper/abc.pdf")
        self.assertEqual(art["type"], "pdf")
        self.assertIsNotNone(art["sha256"])              # was None (the defect) -> empty unverifiable shell
        self.assertTrue(os.path.exists(art["path"]))
        self.assertEqual(art["method"], "refledger/fetch")
        self.assertTrue(R.verify(self.r)["ok"])          # no longer flagged 'unverifiable'

    def test_remote_csv_downloaded(self):
        with _MockHttp(payload=b"a,b\n1,2\n"):
            art = R.ingest(self.r, "https://example.com/data/benchmarks.csv")
        self.assertEqual(art["type"], "csv")
        self.assertIsNotNone(art["sha256"])

    def test_remote_transcript_fetched_and_parsed(self):
        body = "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\n한 줄\n".encode("utf-8")
        with _MockHttp(payload=body):
            art = R.ingest(self.r, "https://example.com/subs.vtt")
        self.assertEqual(art["type"], "transcript")
        self.assertIsNotNone(art["sha256"])              # parsed -> canonical segments hashed

    def test_local_file_still_register_only(self):
        p = os.path.join(self.d, "note.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write("로컬 텍스트")
        art = R.ingest(self.r, p)
        self.assertEqual(art["method"], "register")      # local path -> no fetch
        self.assertIsNotNone(art["sha256"])

    def test_fetch_failure_returns_error(self):
        with _MockHttp(raise_exc=ValueError("refused private/loopback host")):
            res = R.ingest(self.r, "https://example.com/x.pdf")
        self.assertIn("error", res)


class JsonSniff(unittest.TestCase):   # QA-300 #2 (applied during verify) - regression-lock it
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.r = R.open_research("g", base=self.d)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_html_routed_json_error_envelope_labeled_api_error(self):
        # registry.npmjs.org/react -> detect_type 'html' (no .json, host !startswith 'api.'), but body is JSON
        with _MockHttp(payload=b'{"error":"Not found","code":404}'):
            art = R.ingest(self.r, "https://registry.npmjs.org/react")
        self.assertEqual(art["type"], "html")
        self.assertEqual(art["quality_label"], "API_ERROR")   # json_quality ran via the sniff, not web_quality

    def test_html_real_page_still_web_quality_ok(self):
        body = ("<html><body>" + ("real article content. " * 200) + "</body></html>").encode("utf-8")
        with _MockHttp(payload=body):
            art = R.ingest(self.r, "https://example.com/article")
        self.assertEqual(art["type"], "html")
        self.assertEqual(art["quality_label"], "OK")          # not JSON -> web_quality; content-rich -> OK


if __name__ == "__main__":
    unittest.main(verbosity=2)
