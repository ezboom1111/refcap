#!/usr/bin/env python
"""validate_independence.py — deterministic independence + echo validator for leesearch-alpha.

Checks that triangulation meets alpha criteria: ≥3 independent hosts, no echo clusters,
cross-modal corroboration. Exits 0 = pass, 1 = fail.

Usage:
    python validate_independence.py <run_dir>
    python validate_independence.py <run_dir> --hypothesis <hid>   # specific hypothesis
    python validate_independence.py <run_dir> --json
"""
import os, sys, json, argparse
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from refledger import (_read_jsonl, _host, triangulate, alpha_label, _MODALITY_CLASS, _resolve,
                       _distinct_pred_count, _jaccard, _shingles, _NEAR_DUP_SIM)

MIN_INDEPENDENT_HOSTS = 3
MIN_MODALITIES = 2


def _text_similarity(a, b):
    """SYMMETRIC near-identity score, reusing the spine's 3-gram Jaccard (the same measure triangulate uses to
    collapse echoes). Order-independent and length-fair — unlike the old `intersection / len(text_i)` which keyed
    the denominator on whichever signal came first (a long-vs-subset pair flipped result on insertion order, and a
    single-word text forced denominator=1 → false echo)."""
    return _jaccard(_shingles(a), _shingles(b))


def _detect_echo_clusters(signals, cutoff=_NEAR_DUP_SIM):
    """Detect signals that are likely echoes of the same press release / wire service: confirming findings whose
    text is near-IDENTICAL (3-gram Jaccard >= cutoff, the spine's _NEAR_DUP_SIM). Symmetric, so the cluster is the
    same regardless of ledger insertion order."""
    clusters = []
    used = set()
    for i, s in enumerate(signals):
        if i in used:
            continue
        cluster = [i]
        text_i = s.get("text", "")
        for j in range(i + 1, len(signals)):
            if j in used:
                continue
            text_j = signals[j].get("text", "")
            if not text_i or not text_j:
                continue
            if _text_similarity(text_i, text_j) >= cutoff:
                cluster.append(j)
        if len(cluster) > 1:
            for idx in cluster:
                used.add(idx)
            clusters.append(cluster)

    return clusters


def validate_independence(rdir, hypothesis_id=None):
    rdir = _resolve(rdir)   # accept a refledger slug (r_xxxx) or an absolute path, like the spine CLI
    ledger_path = os.path.join(rdir, "ledger.jsonl")
    if not os.path.exists(ledger_path):
        return {"pass": False, "error": f"No ledger.jsonl in {rdir}"}

    rows = _read_jsonl(ledger_path)
    hypotheses = [r for r in rows if r.get("kind") == "hypothesis"]

    if not hypotheses:
        return {"pass": False, "error": "No hypotheses in ledger"}

    if hypothesis_id:
        hyps = [h for h in hypotheses if h.get("hypothesis_id") == hypothesis_id]
        if not hyps:
            return {"pass": False, "error": f"Hypothesis {hypothesis_id} not found"}
    else:
        hyps = hypotheses

    results = []
    all_pass = True

    for hyp in hyps:
        hid = hyp["hypothesis_id"]
        stakes = hyp.get("stakes", "") or "low"

        tri = triangulate(rdir, hid)

        # Predictions live in predictions.jsonl, NOT ledger.jsonl (the spine's digest reads them there too).
        # Reading them from `rows` (ledger) found 0 and falsely flagged no-falsifiable-prediction. Use the spine's
        # own _distinct_pred_count so the distinct/raw counts match what digest's alpha_label sees exactly.
        pred_rows = [r for r in _read_jsonl(os.path.join(rdir, "predictions.jsonl")) if r.get("kind") == "prediction"]
        predictions = [p for p in pred_rows if p.get("hypothesis_id", "") == hid]
        distinct_preds = _distinct_pred_count(predictions)
        raw_preds = len(predictions)

        label = alpha_label(tri, stakes=stakes, distinct_predictions=distinct_preds, raw_predictions=raw_preds)

        confirming_signals = [s for s in tri.get("signals", []) if s.get("polarity") == "confirms"]
        echo_clusters = _detect_echo_clusters(confirming_signals)

        host_dist = Counter(s.get("host", "") for s in confirming_signals if s.get("host"))
        dominant_host = host_dist.most_common(1)[0] if host_dist else ("", 0)
        concentration_warning = dominant_host[1] / max(len(confirming_signals), 1) > 0.5 if confirming_signals else False

        issues = list(label.get("reasons", []))
        if echo_clusters:
            issues.append(f"echo-clusters({len(echo_clusters)})")
        if concentration_warning:
            issues.append(f"host-concentration({dominant_host[0]}={dominant_host[1]}/{len(confirming_signals)})")

        has_disconfirm = tri.get("disconfirming", 0) > 0

        passed = label.get("alpha", False) and not echo_clusters and not concentration_warning
        if not passed:
            all_pass = False

        results.append({
            "hypothesis_id": hid,
            "thesis": hyp.get("thesis", "")[:80],
            "stakes": stakes,
            "pass": passed,
            "label": label["label"],
            "independent_hosts": tri.get("independent_confirming_hosts", 0),
            "modalities": tri.get("confirming_modalities", []),
            "confirming": tri.get("confirming", 0),
            "distinct_claims": tri.get("confirming_distinct_claims", 0),
            "disconfirming": tri.get("disconfirming", 0),
            "has_disconfirm": has_disconfirm,
            "echo_clusters": len(echo_clusters),
            "predictions": distinct_preds,
            "issues": issues,
            "warning": label.get("warning", ""),
        })

    return {"pass": all_pass, "hypotheses": results}


def main():
    parser = argparse.ArgumentParser(description="Validate independence and echo detection")
    parser.add_argument("run_dir", help="Path to refledger run directory")
    parser.add_argument("--hypothesis", help="Specific hypothesis ID to validate")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    result = validate_independence(args.run_dir, args.hypothesis)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result.get("error"):
        print(f"[ERROR] {result['error']}")
    else:
        for h in result.get("hypotheses", []):
            status = "PASS" if h["pass"] else "FAIL"
            print(f"[{status}] {h['label']} | {h['thesis']}")
            print(f"  hosts={h['independent_hosts']} mods={h['modalities']} "
                  f"confirm={h['confirming']}(distinct={h['distinct_claims']}) "
                  f"disconfirm={h['disconfirming']} predictions={h['predictions']}")
            if h.get("issues"):
                print(f"  issues: {', '.join(h['issues'])}")
            if h.get("warning"):
                print(f"  WARNING: {h['warning']}")
    sys.exit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
