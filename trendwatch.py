#!/usr/bin/env python
"""trendwatch.py — deterministic YouTube trend snapshot collector + velocity / half-life report.

The structural gap this closes: view-velocity needs >= 2 timestamped snapshots, and trend
half-life needs a daily series — but snapshots were taken by hand. This script is the
model-free collector half (run it from Task Scheduler / cron; no agent involved):

    python trendwatch.py add video <id-or-url> [--note "..."]
    python trendwatch.py add channel <UC-channel-id> [--note "..."]
    python trendwatch.py remove <id>  |  list
    python trendwatch.py snapshot          # keyed Data API fetch -> append research/trendwatch/snapshots.jsonl
    python trendwatch.py report [--json]   # velocity series + decay half-life per watched item

Design rules (refcap house style):
- NOUNS + arithmetic only: fetch, append-only ledger, delta/hours, log-linear decay fit.
  Whether something IS a trend / worth acting on stays the agent's judgment — no thresholds decide here.
- stdlib only; the network fetch is injected so tests run fixture-only.
- Raw API statistics strings are preserved verbatim per row (registerable into the farm as-is;
  per youtube-research SKILL, anchor the exact substring e.g. "viewCount": "658078").
- The API key comes from env YOUTUBE_API_KEY, is never written to the ledger, and is scrubbed
  from error messages (urllib errors embed the URL).
- subscriberCount is API-rounded; treat channel velocity as coarse. A vanished item is recorded
  ({"missing": true}) — disappearance is itself a signal, never silently dropped.
"""
import argparse
import json
import math
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BASE = os.path.join(HERE, "research", "trendwatch")
API = "https://www.googleapis.com/youtube/v3"
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_URL_VIDEO_ID = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _scrub_key(text, key):
    return text.replace(key, "***") if key else text


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_video_id(value):
    if _VIDEO_ID.match(value):
        return value
    match = _URL_VIDEO_ID.search(value)
    if match:
        return match.group(1)
    raise ValueError(f"not a YouTube video id/url: {value}")


# ---- watchlist (one json file; idempotent add by id) ----

def _watchlist_path(base):
    return os.path.join(base, "watchlist.json")


def watchlist_load(base):
    try:
        with open(_watchlist_path(base), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _watchlist_save(base, items):
    os.makedirs(base, exist_ok=True)
    with open(_watchlist_path(base), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)


def watchlist_add(base, kind, item_id, note=""):
    if kind not in ("video", "channel"):
        raise ValueError("kind must be video|channel")
    items = watchlist_load(base)
    if any(i["id"] == item_id for i in items):
        return items
    items.append({"kind": kind, "id": item_id, "note": note, "addedAt": now_iso()})
    _watchlist_save(base, items)
    return items


def watchlist_remove(base, item_id):
    items = [i for i in watchlist_load(base) if i["id"] != item_id]
    _watchlist_save(base, items)
    return items


# ---- snapshot (append-only jsonl ledger) ----

def _snapshots_path(base):
    return os.path.join(base, "snapshots.jsonl")


def read_snapshots(base):
    rows = []
    try:
        with open(_snapshots_path(base), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue  # one corrupt line must not kill the series
    except FileNotFoundError:
        pass
    return rows


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def snapshot(base, key, fetch=fetch_json, at=None):
    """Fetch statistics for every watched item and append one row per item. Returns the new rows."""
    if not key:
        raise SystemExit("YOUTUBE_API_KEY is not set")
    items = watchlist_load(base)
    if not items:
        raise SystemExit("watchlist is empty - add items first (trendwatch.py add video <id-or-url>)")
    at = at or now_iso()
    rows = []
    for kind, endpoint in (("video", "videos"), ("channel", "channels")):
        ids = [i["id"] for i in items if i["kind"] == kind]
        for batch in _chunks(ids, 50):  # videos.list/channels.list take up to 50 ids per unit of quota
            url = f"{API}/{endpoint}?part=statistics&id={','.join(batch)}&key={key}"
            try:
                payload = fetch(url)
            except Exception as err:  # urllib errors embed the URL (and so the key) - scrub it
                raise SystemExit(f"API fetch failed: {_scrub_key(str(err), key)}") from None
            got = {item["id"]: item.get("statistics", {}) for item in payload.get("items", [])}
            for item_id in batch:
                if item_id in got:
                    rows.append({"at": at, "kind": kind, "id": item_id, "stats": got[item_id]})
                else:
                    rows.append({"at": at, "kind": kind, "id": item_id, "missing": True})
    os.makedirs(base, exist_ok=True)
    with open(_snapshots_path(base), "a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return rows


# ---- chart ledger (top-50 mostPopular; the CHART is the watchlist, so nothing here ages) ----

def _chart_path(base, region):
    return os.path.join(base, f"chart-{region}.jsonl")


def read_chart(base, region):
    rows = []
    try:
        with open(_chart_path(base, region), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except FileNotFoundError:
        pass
    return rows


def chart_snapshot(base, key, region="KR", fetch=fetch_json, at=None):
    """Append today's top-50 mostPopular chart (rank, id, title, channel, categoryId, raw stats).
    1 quota unit per call; no fixed list to curate — the platform refreshes the population daily."""
    if not key:
        raise SystemExit("YOUTUBE_API_KEY is not set")
    at = at or now_iso()
    url = (f"{API}/videos?part=snippet,statistics&chart=mostPopular"
           f"&regionCode={region}&maxResults=50&key={key}")
    try:
        payload = fetch(url)
    except Exception as err:
        raise SystemExit(f"API fetch failed: {_scrub_key(str(err), key)}") from None
    rows = []
    for rank, item in enumerate(payload.get("items", []), 1):
        snippet = item.get("snippet", {})
        rows.append({"at": at, "region": region, "rank": rank, "id": item["id"],
                     "title": snippet.get("title", ""), "channelTitle": snippet.get("channelTitle", ""),
                     "categoryId": snippet.get("categoryId", ""),
                     "stats": item.get("statistics", {})})
    os.makedirs(base, exist_ok=True)
    with open(_chart_path(base, region), "a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return rows


def chart_stats(base, region):
    """Set arithmetic over the chart series: per-day entries/exits/churn + per-video chart
    residence (daysOnChart, bestRank, first/last seen). Same-day reruns: the LAST snapshot of a
    calendar day wins (idempotent). What a rising format MEANS stays the agent's judgment."""
    rows = read_chart(base, region)
    by_snapshot = {}
    for row in rows:
        by_snapshot.setdefault(row["at"], {})[row["id"]] = row
    latest_per_day = {}
    for at_value in sorted(by_snapshot):
        latest_per_day[at_value[:10]] = by_snapshot[at_value]   # later 'at' overwrites = last wins
    days = sorted(latest_per_day)
    per_video = {}
    daily = []
    prev_ids = None
    for day in days:
        snapshot = latest_per_day[day]
        current_ids = set(snapshot)
        for vid, row in snapshot.items():
            entry = per_video.setdefault(vid, {
                "id": vid, "title": row["title"], "channelTitle": row["channelTitle"],
                "categoryId": row["categoryId"], "firstSeen": day, "lastSeen": day,
                "daysOnChart": 0, "bestRank": row["rank"], "latestRank": row["rank"]})
            entry["daysOnChart"] += 1
            entry["lastSeen"] = day
            entry["latestRank"] = row["rank"]
            entry["bestRank"] = min(entry["bestRank"], row["rank"])
            entry["title"] = row["title"]   # titles get edited mid-trend; keep the latest
        if prev_ids is None:
            daily.append({"day": day, "entries": sorted(current_ids), "exits": [], "size": len(current_ids)})
        else:
            daily.append({"day": day,
                          "entries": sorted(current_ids - prev_ids),
                          "exits": sorted(prev_ids - current_ids),
                          "size": len(current_ids)})
        prev_ids = current_ids
    return {"region": region, "days": len(days), "daily": daily,
            "videos": sorted(per_video.values(), key=lambda v: (-v["daysOnChart"], v["bestRank"]))}


# ---- velocity + half-life (arithmetic only; the agent judges the numbers) ----

def _parse_at(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def velocity_series(snaps):
    """Consecutive-pair views/hour for ONE item's snapshot rows. Sorted, deduped by timestamp;
    zero/negative time gaps are skipped; rows without a parseable viewCount are skipped."""
    usable = []
    seen_at = set()
    for row in sorted(snaps, key=lambda r: r["at"]):
        if row.get("missing") or row["at"] in seen_at:
            continue
        try:
            views = int(row.get("stats", {}).get("viewCount"))
        except (TypeError, ValueError):
            continue
        seen_at.add(row["at"])
        usable.append((_parse_at(row["at"]), row["at"], views))
    points = []
    for (t0, _, v0), (t1, at1, v1) in zip(usable, usable[1:]):
        hours = (t1 - t0).total_seconds() / 3600
        if hours <= 0:
            continue
        points.append({"at": at1, "viewsPerHour": (v1 - v0) / hours, "hours": hours})
    return points


def estimate_half_life(velocity_points, min_decline_points=3):
    """Log-linear fit v(t)=v0*exp(-lambda*t) over the post-peak declining segment.
    Honest statuses instead of guesses: insufficient_data / not_decaying / ok(halfLifeDays, r2)."""
    if len(velocity_points) < min_decline_points:
        return {"status": "insufficient_data", "have": len(velocity_points), "need": min_decline_points}
    peak_idx = max(range(len(velocity_points)), key=lambda i: velocity_points[i]["viewsPerHour"])
    segment = [p for p in velocity_points[peak_idx:] if p["viewsPerHour"] > 0]
    if len(segment) < min_decline_points:
        return {"status": "not_decaying" if peak_idx >= len(velocity_points) - 1 else "insufficient_data",
                "have": len(segment), "need": min_decline_points}
    t0 = _parse_at(segment[0]["at"])
    xs = [(_parse_at(p["at"]) - t0).total_seconds() / 3600 for p in segment]
    ys = [math.log(p["viewsPerHour"]) for p in segment]
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0:
        return {"status": "insufficient_data", "have": n, "need": min_decline_points}
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / sxx
    if slope >= 0:
        return {"status": "not_decaying"}
    sst = sum((y - mean_y) ** 2 for y in ys)
    sse = sum((y - (mean_y + slope * (x - mean_x))) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - (sse / sst) if sst > 0 else 1.0
    half_life_hours = math.log(2) / -slope
    return {"status": "ok", "halfLifeDays": round(half_life_hours / 24, 2), "r2": round(r2, 3),
            "declinePoints": n}


def report(base):
    items = watchlist_load(base)
    by_id = {}
    for row in read_snapshots(base):
        by_id.setdefault(row["id"], []).append(row)
    out = {"generatedAt": now_iso(), "items": []}
    for item in items:
        snaps = by_id.get(item["id"], [])
        vel = velocity_series(snaps)
        entry = {
            "id": item["id"], "kind": item["kind"], "note": item.get("note", ""),
            "snapshots": len(snaps),
            "firstAt": snaps[0]["at"] if snaps else None,
            "lastAt": snaps[-1]["at"] if snaps else None,
            "latestStats": next((r.get("stats") for r in reversed(snaps) if not r.get("missing")), None),
            "missingInLastSnapshot": bool(snaps and snaps[-1].get("missing")),
            "latestViewsPerHour": round(vel[-1]["viewsPerHour"], 2) if vel else None,
            "peakViewsPerHour": round(max(p["viewsPerHour"] for p in vel), 2) if vel else None,
            "halfLife": estimate_half_life(vel),
        }
        out["items"].append(entry)
    return out


def _print_report(rep):
    print(f"# trendwatch report ({rep['generatedAt']})")
    for it in rep["items"]:
        hl = it["halfLife"]
        hl_text = f"half-life {hl['halfLifeDays']}d (r2={hl['r2']})" if hl["status"] == "ok" else hl["status"]
        views = (it["latestStats"] or {}).get("viewCount", "?")
        print(f"{it['kind']:7} {it['id']:24} snaps={it['snapshots']:3} views={views:>14} "
              f"v={it['latestViewsPerHour'] if it['latestViewsPerHour'] is not None else '-':>10}/h "
              f"peak={it['peakViewsPerHour'] if it['peakViewsPerHour'] is not None else '-':>10}/h  {hl_text}"
              + ("  [MISSING]" if it["missingInLastSnapshot"] else "")
              + (f"  # {it['note']}" if it["note"] else ""))


def main():
    # Korean chart titles vs a cp949 console: force utf-8 (replace) so printing never crashes the task.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser(description="YouTube trend snapshot collector + velocity report")
    parser.add_argument("--base", default=DEFAULT_BASE, help="data dir (default: refcap/research/trendwatch)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_add = sub.add_parser("add")
    p_add.add_argument("kind", choices=["video", "channel"])
    p_add.add_argument("target", help="video id/url, or UC... channel id")
    p_add.add_argument("--note", default="")
    p_rm = sub.add_parser("remove")
    p_rm.add_argument("target")
    sub.add_parser("list")
    sub.add_parser("snapshot")
    p_rep = sub.add_parser("report")
    p_rep.add_argument("--json", action="store_true")
    p_chart = sub.add_parser("chart", help="append today's top-50 mostPopular chart for a region")
    p_chart.add_argument("region", nargs="?", default="KR")
    p_cstats = sub.add_parser("chartstats", help="entries/exits/churn + chart-residence stats")
    p_cstats.add_argument("region", nargs="?", default="KR")
    p_cstats.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.cmd == "add":
        item_id = parse_video_id(args.target) if args.kind == "video" else args.target
        watchlist_add(args.base, args.kind, item_id, note=args.note)
        print(f"added {args.kind} {item_id}")
    elif args.cmd == "remove":
        watchlist_remove(args.base, args.target)
        print(f"removed {args.target}")
    elif args.cmd == "list":
        for item in watchlist_load(args.base):
            print(f"{item['kind']:7} {item['id']:24} {item.get('note', '')}")
    elif args.cmd == "snapshot":
        rows = snapshot(args.base, key=os.environ.get("YOUTUBE_API_KEY", ""))
        print(f"snapshot ok: {len(rows)} rows appended at {rows[0]['at'] if rows else '-'}")
    elif args.cmd == "report":
        rep = report(args.base)
        if args.json:
            print(json.dumps(rep, ensure_ascii=False, indent=1))
        else:
            _print_report(rep)
    elif args.cmd == "chart":
        rows = chart_snapshot(args.base, key=os.environ.get("YOUTUBE_API_KEY", ""), region=args.region)
        print(f"chart ok: {len(rows)} rows ({args.region}) at {rows[0]['at'] if rows else '-'}")
    elif args.cmd == "chartstats":
        stats = chart_stats(args.base, args.region)
        if args.json:
            print(json.dumps(stats, ensure_ascii=False, indent=1))
        else:
            print(f"# chart {stats['region']}: {stats['days']} day(s)")
            for day in stats["daily"][-7:]:
                print(f"{day['day']}  in={len(day['entries']):2}  out={len(day['exits']):2}  size={day['size']}")
            print("# longest chart residence (top 15)")
            for video in stats["videos"][:15]:
                print(f"{video['daysOnChart']:3}d  best#{video['bestRank']:2}  {video['channelTitle'][:18]:18} {video['title'][:48]}")


if __name__ == "__main__":
    main()
