"""TDD for trendwatch.py — deterministic YouTube trend snapshot collector + velocity/half-life report.
Code is NOUNS + arithmetic only (fetch, append-only ledger, delta/hours, log-linear decay fit);
whether something IS a trend stays the agent's judgment. stdlib only; fetch is injected (no network).
Run: python -m unittest test_trendwatch -v
"""
import json
import math
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trendwatch as TW


class ParseIds(unittest.TestCase):
    def test_raw_video_id_passes_through(self):
        self.assertEqual(TW.parse_video_id("9bZkp7q19f0"), "9bZkp7q19f0")

    def test_watch_url(self):
        self.assertEqual(TW.parse_video_id("https://www.youtube.com/watch?v=9bZkp7q19f0&t=10s"), "9bZkp7q19f0")

    def test_youtu_be_and_shorts(self):
        self.assertEqual(TW.parse_video_id("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(TW.parse_video_id("https://www.youtube.com/shorts/abcDEF12345"), "abcDEF12345")

    def test_garbage_raises(self):
        with self.assertRaises(ValueError):
            TW.parse_video_id("https://example.com/not-youtube")


class WatchlistRoundTrip(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_add_list_remove(self):
        TW.watchlist_add(self.d, "video", "9bZkp7q19f0", note="demo")
        TW.watchlist_add(self.d, "channel", "UC123", note="acct")
        items = TW.watchlist_load(self.d)
        self.assertEqual([(i["kind"], i["id"]) for i in items], [("video", "9bZkp7q19f0"), ("channel", "UC123")])
        TW.watchlist_remove(self.d, "UC123")
        self.assertEqual(len(TW.watchlist_load(self.d)), 1)

    def test_add_same_id_twice_is_idempotent(self):
        TW.watchlist_add(self.d, "video", "9bZkp7q19f0")
        TW.watchlist_add(self.d, "video", "9bZkp7q19f0", note="again")
        self.assertEqual(len(TW.watchlist_load(self.d)), 1)


def fake_fetch_factory(views_by_id, subs_by_id=None):
    """Fixture fetch: answers videos?...id=a,b and channels?...id=... with statistics."""
    def fake_fetch(url):
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(url).query)
        ids = q["id"][0].split(",")
        assert "key" in q, "API key must be on the request"
        if "/videos" in url:
            return {"items": [{"id": i, "statistics": {"viewCount": str(views_by_id[i]), "likeCount": "1"}}
                              for i in ids if i in views_by_id]}
        return {"items": [{"id": i, "statistics": {"viewCount": str(views_by_id.get(i, 0)),
                                                   "subscriberCount": str((subs_by_id or {}).get(i, 0))}}
                          for i in ids if i in views_by_id or i in (subs_by_id or {})]}
    return fake_fetch


class Snapshot(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        TW.watchlist_add(self.d, "video", "vidAAAAAAA1")
        TW.watchlist_add(self.d, "channel", "UCchan1")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_snapshot_appends_rows_with_at_and_raw_stats(self):
        rows = TW.snapshot(self.d, key="K", fetch=fake_fetch_factory({"vidAAAAAAA1": 100, "UCchan1": 5000}, {"UCchan1": 10}),
                           at="2026-06-10T00:00:00Z")
        self.assertEqual(len(rows), 2)
        ledger = TW.read_snapshots(self.d)
        self.assertEqual(len(ledger), 2)
        vid = [r for r in ledger if r["kind"] == "video"][0]
        self.assertEqual(vid["stats"]["viewCount"], "100")  # raw API strings preserved (registerable verbatim)
        self.assertEqual(vid["at"], "2026-06-10T00:00:00Z")

    def test_missing_item_recorded_not_silently_dropped(self):
        TW.watchlist_add(self.d, "video", "vidGONE0000")
        rows = TW.snapshot(self.d, key="K", fetch=fake_fetch_factory({"vidAAAAAAA1": 100, "UCchan1": 1}),
                           at="2026-06-10T00:00:00Z")
        gone = [r for r in rows if r["id"] == "vidGONE0000"]
        self.assertEqual(len(gone), 1)
        self.assertTrue(gone[0].get("missing"))  # a vanished video is itself a trend signal

    def test_no_api_key_in_ledger_rows(self):
        TW.snapshot(self.d, key="SECRETKEY", fetch=fake_fetch_factory({"vidAAAAAAA1": 1, "UCchan1": 1}),
                    at="2026-06-10T00:00:00Z")
        raw = open(os.path.join(self.d, "snapshots.jsonl"), encoding="utf-8").read()
        self.assertNotIn("SECRETKEY", raw)


class VelocityMath(unittest.TestCase):
    def _snaps(self, pairs):  # [(at, views)]
        return [{"at": a, "kind": "video", "id": "v", "stats": {"viewCount": str(v)}} for a, v in pairs]

    def test_two_snapshots_give_views_per_hour(self):
        pts = TW.velocity_series(self._snaps([("2026-06-10T00:00:00Z", 1000), ("2026-06-10T12:00:00Z", 1600)]))
        self.assertEqual(len(pts), 1)
        self.assertAlmostEqual(pts[0]["viewsPerHour"], 50.0)

    def test_unsorted_input_is_sorted_and_zero_gap_skipped(self):
        pts = TW.velocity_series(self._snaps([
            ("2026-06-11T00:00:00Z", 2000), ("2026-06-10T00:00:00Z", 1000), ("2026-06-11T00:00:00Z", 2000)]))
        self.assertEqual(len(pts), 1)
        self.assertAlmostEqual(pts[0]["viewsPerHour"], 1000 / 24)

    def test_half_life_recovered_from_synthetic_exponential_decay(self):
        # v(t) = 4096 * 0.5^(t/2days) sampled daily -> half-life ~= 2 days
        pairs, views, t = [], 0.0, 0
        for day in range(7):
            vel = 4096 * (0.5 ** (day / 2))          # views/hour during this day
            views += vel * 24
            pairs.append((f"2026-06-{10+day:02d}T00:00:00Z", int(views)))
        est = TW.estimate_half_life(TW.velocity_series(self._snaps(pairs)))
        self.assertEqual(est["status"], "ok")
        self.assertAlmostEqual(est["halfLifeDays"], 2.0, delta=0.2)

    def test_insufficient_points_is_honest(self):
        est = TW.estimate_half_life(TW.velocity_series(self._snaps([
            ("2026-06-10T00:00:00Z", 100), ("2026-06-11T00:00:00Z", 200)])))
        self.assertEqual(est["status"], "insufficient_data")

    def test_growing_video_reports_not_decaying(self):
        pairs = [(f"2026-06-{10+d:02d}T00:00:00Z", 1000 * (d + 1) ** 2) for d in range(5)]
        est = TW.estimate_half_life(TW.velocity_series(self._snaps(pairs)))
        self.assertEqual(est["status"], "not_decaying")


class Report(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        TW.watchlist_add(self.d, "video", "vidAAAAAAA1", note="demo")
        for day, views in [(10, 1000), (11, 4000), (12, 5500), (13, 6250)]:
            TW.snapshot(self.d, key="K", fetch=fake_fetch_factory({"vidAAAAAAA1": views}),
                        at=f"2026-06-{day}T00:00:00Z")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_report_has_latest_peak_and_half_life_fields(self):
        rep = TW.report(self.d)
        item = rep["items"][0]
        self.assertEqual(item["id"], "vidAAAAAAA1")
        self.assertEqual(item["snapshots"], 4)
        self.assertAlmostEqual(item["peakViewsPerHour"], 3000 / 24)
        self.assertAlmostEqual(item["latestViewsPerHour"], 750 / 24)
        self.assertIn(item["halfLife"]["status"], ("ok", "insufficient_data", "not_decaying"))


def fake_chart_fetch_factory(days):
    """Fixture: days = {at_prefix: [(id, title, channel, categoryId, views)]} keyed by request count order."""
    calls = {"n": 0}
    sequence = list(days)

    def fake_fetch(url):
        assert "chart=mostPopular" in url and "key=" in url
        day = sequence[min(calls["n"], len(sequence) - 1)]
        calls["n"] += 1
        return {"items": [{"id": vid, "snippet": {"title": t, "channelTitle": c, "categoryId": cat},
                           "statistics": {"viewCount": str(v)}}
                          for vid, t, c, cat, v in days[day]]}
    return fake_fetch


class ChartLedger(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_chart_snapshot_appends_ranked_rows_with_titles(self):
        fetch = fake_chart_fetch_factory({"d1": [("vidA", "A제목", "chanX", "10", 100), ("vidB", "B", "chanY", "24", 90)]})
        rows = TW.chart_snapshot(self.d, key="K", region="KR", fetch=fetch, at="2026-06-10T00:00:00Z")
        self.assertEqual([(r["rank"], r["id"]) for r in rows], [(1, "vidA"), (2, "vidB")])
        self.assertEqual(rows[0]["title"], "A제목")  # report must not be id-only (Monday-morning readability)
        ledger = TW.read_chart(self.d, "KR")
        self.assertEqual(len(ledger), 2)
        self.assertEqual(ledger[0]["stats"]["viewCount"], "100")  # raw strings preserved (farm-registerable)

    def test_no_key_in_chart_ledger(self):
        fetch = fake_chart_fetch_factory({"d1": [("vidA", "A", "c", "10", 1)]})
        TW.chart_snapshot(self.d, key="SECRETKEY", region="KR", fetch=fetch, at="2026-06-10T00:00:00Z")
        raw = open(os.path.join(self.d, "chart-KR.jsonl"), encoding="utf-8").read()
        self.assertNotIn("SECRETKEY", raw)

    def test_chart_stats_entries_exits_residence(self):
        days = {
            "2026-06-10": [("vidA", "A", "c1", "10", 100), ("vidB", "B", "c2", "24", 90)],
            "2026-06-11": [("vidA", "A", "c1", "10", 200), ("vidC", "C", "c3", "10", 150)],
            "2026-06-12": [("vidC", "C", "c3", "10", 300)],
        }
        fetch = fake_chart_fetch_factory(days)
        for at_day in days:
            TW.chart_snapshot(self.d, key="K", region="KR", fetch=fetch, at=f"{at_day}T00:00:00Z")
        stats = TW.chart_stats(self.d, "KR")
        self.assertEqual(stats["days"], 3)
        by_day = {d["day"]: d for d in stats["daily"]}
        self.assertEqual(by_day["2026-06-11"]["entries"], ["vidC"])
        self.assertEqual(by_day["2026-06-11"]["exits"], ["vidB"])
        self.assertEqual(by_day["2026-06-12"]["exits"], ["vidA"])
        by_id = {v["id"]: v for v in stats["videos"]}
        self.assertEqual(by_id["vidA"]["daysOnChart"], 2)
        self.assertEqual(by_id["vidB"]["daysOnChart"], 1)
        self.assertEqual(by_id["vidC"]["daysOnChart"], 2)
        self.assertEqual(by_id["vidA"]["bestRank"], 1)

    def test_same_day_rerun_is_idempotent_in_stats(self):
        fetch = fake_chart_fetch_factory({
            "r1": [("vidA", "A", "c", "10", 100)],
            "r2": [("vidB", "B", "c", "10", 50)],  # later same-day run replaces the earlier one
        })
        TW.chart_snapshot(self.d, key="K", region="KR", fetch=fetch, at="2026-06-10T00:00:00Z")
        TW.chart_snapshot(self.d, key="K", region="KR", fetch=fetch, at="2026-06-10T09:00:00Z")
        stats = TW.chart_stats(self.d, "KR")
        self.assertEqual(stats["days"], 1)
        self.assertEqual([v["id"] for v in stats["videos"]], ["vidB"])


if __name__ == "__main__":
    unittest.main()
