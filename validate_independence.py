#!/usr/bin/env python
"""validate_independence.py — deterministic independence + echo validator for leesearch-alpha.

Checks that triangulation meets alpha criteria: ≥3 independent hosts, no echo clusters,
cross-modal corroboration. Exits 0 = pass, 1 = fail.

Usage:
    python validate_independence.py <run_dir>
    python validate_independence.py <run_dir> --hypothesis <hid>   # specific hypothesis
    python validate_independence.py <run_dir> --json
"""
import os, sys, re, json, argparse
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from refledger import (_read_jsonl, _host, triangulate, alpha_label, debunk_label, _MODALITY_CLASS, _resolve,
                       _distinct_pred_count, _jaccard, _shingles, _NEAR_DUP_SIM, _SHINGLE_K,
                       _CJK_STOP, _EN_STOP)

MIN_INDEPENDENT_HOSTS = 3
MIN_MODALITIES = 2


def _sig_tokens(text):
    """Significant content tokens — REPLICATES _shingles' filter exactly (drop stopwords + <4-char ascii words) so
    the unigram-fallback path below stays consistent with the spine's shingle tokenization."""
    out = []
    for w in re.findall(r"[^\W\d_]{2,}", (text or "").lower(), re.UNICODE):
        if w in _CJK_STOP or w in _EN_STOP:
            continue
        if not w.isascii() or len(w) >= 4:
            out.append(w)
    return out


def _text_similarity(a, b):
    """SYMMETRIC near-identity score. Order-independent and length-fair — unlike the old `intersection /
    len(text_i)` which keyed the denominator on whichever signal came first.

    Uses the spine's 3-gram shingle Jaccard for normal-length texts (precise; topically-similar-but-INDEPENDENT
    findings don't falsely cluster). BUT _shingles emits 1-tuples for <K significant tokens and K-grams otherwise,
    and a 1-tuple set can NEVER intersect a K-gram set — so a 2-token vs 3-token near-duplicate would score 0.0
    and silently slip through. When EITHER side is below K tokens, fall back to a word-SET Jaccard (also symmetric),
    which is the right granularity for such short texts."""
    ta, tb = _sig_tokens(a), _sig_tokens(b)
    if len(ta) < _SHINGLE_K or len(tb) < _SHINGLE_K:
        return _jaccard(set(ta), set(tb))
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
    # Last row WINS per hypothesis_id (the agent may re-declare a thesis, appending a 2nd row) — mirror digest()'s
    # hyps_latest. Iterating raw rows evaluated the SAME hypothesis twice (measured in QA: duplicate rows).
    hyps_latest = {}
    order = []
    for r in rows:
        if r.get("kind") == "hypothesis":
            hid = r["hypothesis_id"]
            if hid not in hyps_latest:
                order.append(hid)
            hyps_latest[hid] = r

    if not hyps_latest:
        return {"pass": False, "error": "No hypotheses in ledger"}

    if hypothesis_id:
        if hypothesis_id not in hyps_latest:
            return {"pass": False, "error": f"Hypothesis {hypothesis_id} not found"}
        order = [hypothesis_id]

    results = []
    skipped = []
    evaluated = 0
    all_pass = True

    for hid in order:
        hyp = hyps_latest[hid]
        stakes = hyp.get("stakes", "") or "low"

        tri = triangulate(rdir, hid)

        # A hypothesis with ZERO findings is an UNUSED/draft declaration, not a failing alpha — skip it from the
        # pass decision (measured in QA: a leftover dead-stub hypothesis dragged an otherwise-ALPHA run to RECON).
        if tri.get("n_signals", 0) == 0:
            skipped.append({"hypothesis_id": hid, "thesis": hyp.get("thesis", "")[:80], "reason": "no-findings"})
            continue

        # Predictions live in predictions.jsonl, NOT ledger.jsonl (the spine's digest reads them there too).
        # Reading them from `rows` (ledger) found 0 and falsely flagged no-falsifiable-prediction. Use the spine's
        # own _distinct_pred_count so the distinct/raw counts match what digest's alpha_label sees exactly.
        pred_rows = [r for r in _read_jsonl(os.path.join(rdir, "predictions.jsonl")) if r.get("kind") == "prediction"]
        predictions = [p for p in pred_rows if p.get("hypothesis_id", "") == hid]
        distinct_preds = _distinct_pred_count(predictions)
        raw_preds = len(predictions)

        mode = hyp.get("mode", "discover")
        if mode == "debunk":
            label = debunk_label(tri, stakes=stakes, distinct_predictions=distinct_preds, raw_predictions=raw_preds)
        else:
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

        evaluated += 1
        if mode == "debunk":
            # echo / host-concentration are ADVISORY for a debunk (a provenance debunk legitimately rests on one
            # authoritative investigation restated by fact-checkers) — surfaced in `issues`, but only the verdict
            # decides PASS. A debunk PASSES when it RESOLVED (CONFIRMED-FALSE or CONFIRMED-TRUE).
            passed = label.get("resolved", False)
        else:
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

    # The run PASSES only if at least one hypothesis was actually evaluated (had findings) AND all evaluated passed.
    # A run with only dead-stub hypotheses (no findings anywhere) is RECON, not a vacuous PASS.
    run_pass = all_pass and evaluated > 0
    return {"pass": run_pass, "hypotheses": results, "skipped_no_findings": skipped, "evaluated": evaluated}


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
