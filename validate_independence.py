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
from refledger import _read_jsonl, _host, triangulate, alpha_label, _MODALITY_CLASS

MIN_INDEPENDENT_HOSTS = 3
MIN_MODALITIES = 2


def _detect_echo_clusters(signals):
    """Detect signals that are likely echoes of the same press release / wire service.
    Groups by similar text content and flags clusters > 2 with same-day timestamps."""
    from datetime import datetime

    clusters = []
    used = set()
    for i, s in enumerate(signals):
        if i in used:
            continue
        cluster = [i]
        text_i = s.get("text", "")[:100].lower()
        for j, t in enumerate(signals):
            if j <= i or j in used:
                continue
            text_j = t.get("text", "")[:100].lower()
            if not text_i or not text_j:
                continue
            overlap = len(set(text_i.split()) & set(text_j.split())) / max(len(text_i.split()), 1)
            if overlap > 0.6:
                cluster.append(j)
        if len(cluster) > 1:
            for idx in cluster:
                used.add(idx)
            clusters.append(cluster)

    return clusters


def validate_independence(rdir, hypothesis_id=None):
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

        predictions = [r for r in rows if r.get("kind") == "prediction" and r.get("hypothesis_id") == hid]
        distinct_preds = len(set(p.get("claim", "") for p in predictions))
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
