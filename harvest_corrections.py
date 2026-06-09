#!/usr/bin/env python
"""harvest_corrections.py — extract correction patterns from past leesearch-alpha runs.

Scans completed runs to find RECON→ALPHA progressions (runs that started RECON then reached
ALPHA after remediation passes). Extracts what shapes/sources were added in the successful
remediation, building a correction knowledge base for future skill improvements.

Usage:
    python harvest_corrections.py                      # scan all runs
    python harvest_corrections.py --since 2026-01-01   # since date
    python harvest_corrections.py --json
"""
import os, sys, json, argparse, glob, re
from datetime import datetime, timezone
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from refledger import _read_jsonl, _host, _MODALITY_CLASS

RESEARCH_DIR = os.path.join(HERE, "research")


def _analyze_run(rdir):
    ledger_path = os.path.join(rdir, "ledger.jsonl")
    if not os.path.exists(ledger_path):
        return None

    rows = _read_jsonl(ledger_path)
    if not rows:
        return None

    hypotheses = [r for r in rows if r.get("kind") == "hypothesis"]
    findings = [r for r in rows if r.get("kind") == "finding"]
    artifacts = {r["artifact_id"]: r for r in rows if r.get("kind") == "artifact"}
    # predict() writes predictions.jsonl, NOT ledger.jsonl — reading them from `rows` (ledger) always found 0 and
    # falsely counted the no-prediction gap for every run (same class as the validate_independence fix).
    predictions = [r for r in _read_jsonl(os.path.join(rdir, "predictions.jsonl")) if r.get("kind") == "prediction"]

    if not hypotheses:
        return None

    slug = os.path.basename(rdir)

    modality_counts = Counter()
    host_counts = Counter()
    for f in findings:
        aid = f.get("artifact_id", "")
        art = artifacts.get(aid, {})
        mod = _MODALITY_CLASS.get(art.get("type", ""), "other")
        modality_counts[mod] += 1
        h = _host(art.get("source", ""))
        if h:
            host_counts[h] += 1

    has_prediction = len(predictions) > 0
    has_disconfirm = any(f.get("polarity") == "disconfirms" for f in findings)
    n_modalities = len(set(modality_counts.keys()) - {"other"})
    n_hosts = len(host_counts)

    summary_path = os.path.join(rdir, "SUMMARY.md")
    final_label = None
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as sf:
            text = sf.read()
        if "[ALPHA]" in text:
            final_label = "ALPHA"
        elif "[RECON]" in text:
            final_label = "RECON"

    correction_patterns = []

    if n_modalities >= 2 and final_label == "ALPHA":
        dominant_mod = modality_counts.most_common(1)[0][0] if modality_counts else "web"
        secondary_mods = [m for m, _ in modality_counts.most_common() if m != dominant_mod]
        if secondary_mods:
            correction_patterns.append({
                "type": "modality-expansion",
                "from": dominant_mod,
                "added": secondary_mods,
                "effect": "reached ALPHA",
            })

    if has_disconfirm and final_label == "ALPHA":
        disconfirm_sources = []
        for f in findings:
            if f.get("polarity") == "disconfirms":
                aid = f.get("artifact_id", "")
                art = artifacts.get(aid, {})
                disconfirm_sources.append(_host(art.get("source", "")))
        correction_patterns.append({
            "type": "disconfirm-added",
            "sources": [s for s in disconfirm_sources if s],
            "effect": "adversarial pass completed",
        })

    if n_hosts >= 3 and final_label == "ALPHA":
        top_hosts = [h for h, _ in host_counts.most_common(5)]
        correction_patterns.append({
            "type": "host-diversification",
            "hosts": top_hosts,
            "count": n_hosts,
        })

    created = ""   # for --since filtering: prefer meta.json, fall back to the earliest ledger ts
    meta_path = os.path.join(rdir, "meta.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as mf:
                created = json.load(mf).get("created", "") or ""
        except (ValueError, OSError):
            created = ""
    if not created:
        ts = [r.get("ts", "") for r in rows if r.get("ts")]
        created = min(ts) if ts else ""

    return {
        "slug": slug,
        "path": rdir,
        "created": created,
        "thesis": hypotheses[-1].get("thesis", "")[:100] if hypotheses else "",
        "stakes": hypotheses[-1].get("stakes", "") if hypotheses else "",
        "findings": len(findings),
        "modalities": dict(modality_counts),
        "n_modalities": n_modalities,
        "hosts": n_hosts,
        "has_prediction": has_prediction,
        "has_disconfirm": has_disconfirm,
        "final_label": final_label,
        "corrections": correction_patterns,
    }


def harvest(since=None):
    run_dirs = glob.glob(os.path.join(RESEARCH_DIR, "r_*"))
    run_dirs += glob.glob(os.path.join(RESEARCH_DIR, "research", "r_*"))
    # Dedup by canonical path: a stray research/research/<slug> nesting (a known historical mess) would otherwise
    # process + double-count the same logical run.
    seen_paths = set()
    deduped = []
    for rdir in sorted(run_dirs):
        rp = os.path.normpath(os.path.realpath(rdir))
        if rp in seen_paths:
            continue
        seen_paths.add(rp)
        deduped.append(rdir)

    results = []
    for rdir in deduped:
        analysis = _analyze_run(rdir)
        if analysis:
            # --since: drop runs created BEFORE the cutoff (ISO dates compare lexically; created may be a full
            # timestamp, so compare by the date prefix). A run with an UNKNOWN created date is KEPT, not dropped —
            # silently excluding undated runs from every --since call (even permissive ones) would lose real data.
            if since and analysis.get("created") and analysis["created"][:10] < since:
                continue
            results.append(analysis)

    alpha_runs = [r for r in results if r["final_label"] == "ALPHA"]
    recon_runs = [r for r in results if r["final_label"] == "RECON"]

    all_corrections = []
    for r in results:
        for c in r.get("corrections", []):
            all_corrections.append({**c, "slug": r["slug"]})   # copy — don't mutate the dict held in r["corrections"]

    correction_type_counts = Counter(c["type"] for c in all_corrections)

    common_recon_gaps = Counter()
    for r in recon_runs:
        if r.get("n_modalities", 0) <= 1:   # use the 'other'-stripped count (consistent with modality-expansion)
            common_recon_gaps["single-modality"] += 1
        if not r.get("has_prediction"):
            common_recon_gaps["no-prediction"] += 1
        if not r.get("has_disconfirm"):
            common_recon_gaps["no-disconfirm"] += 1
        if r.get("hosts", 0) < 3:
            common_recon_gaps["thin-hosts"] += 1

    return {
        "total_runs": len(results),
        "alpha_count": len(alpha_runs),
        "recon_count": len(recon_runs),
        "unlabeled": len(results) - len(alpha_runs) - len(recon_runs),
        "correction_patterns": correction_type_counts,
        "common_recon_gaps": dict(common_recon_gaps),
        "corrections": all_corrections,
        "runs": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Harvest correction patterns from alpha runs")
    parser.add_argument("--since", help="Only runs after this date (YYYY-MM-DD)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    result = harvest(args.since)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Runs: {result['total_runs']} (ALPHA={result['alpha_count']}, "
              f"RECON={result['recon_count']}, unlabeled={result['unlabeled']})")
        print(f"\nCommon RECON gaps: {dict(result['common_recon_gaps'])}")
        print(f"Correction patterns: {dict(result['correction_patterns'])}")
        if result["corrections"]:
            print(f"\nCorrections harvested ({len(result['corrections'])}):")
            for c in result["corrections"][:10]:
                print(f"  [{c['type']}] {c['slug']}: {c.get('effect', '')}")
    sys.exit(0)


if __name__ == "__main__":
    main()
