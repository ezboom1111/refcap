#!/usr/bin/env python
"""check_shapes.py — deterministic shape-budget validator for leesearch-alpha investigations.

Reads a ledger.jsonl run directory and checks whether the evidence shapes meet the declared
stakes level's budget (as defined in evidence-budget.md).

The quota is an ADVISORY signal by default: the report is printed, gaps are labeled, but the
exit code is 0. Rationale (measured, 2026-06): a hard exit-1 floor Goodharts — agents repackaged
news text as JSON to fill the `structured` slot (~36% genuine), so the gate bought confidence,
not evidence. Genuineness comes from provenance + an independent adversarial audit, not counts.
`--strict` restores exit-1 gating for callers with an external contract (CI, cross-agent runbooks).
A missing/unreadable ledger is an operator error and exits 1 in BOTH modes.

Usage:
    python check_shapes.py <run_dir>                  # advisory: report + exit 0 (auto-detect stakes)
    python check_shapes.py <run_dir> --strict         # hard gate: exit 1 on any unmet floor
    python check_shapes.py <run_dir> --stakes high    # override stakes level
    python check_shapes.py <run_dir> --json            # machine-readable output
"""
import os, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from refledger import _read_jsonl, _host, _resolve, _MODALITY_CLASS

SHAPE_MAP = {
    # Keyed on the RAW `type` stored on artifacts (html/json/pdf/image/transcript/…), which is what
    # ledger_append persists and _MODALITY_CLASS reads — NOT the EVIDENCE_KIND labels (page_html/…). Using the
    # EVIDENCE_KIND vocabulary here silently misclassified json→unstructured (the measured bug this fixes).
    "html": "unstructured", "md": "unstructured", "txt": "unstructured", "text": "unstructured",
    "json": "structured", "csv": "structured",
    "pdf": "semi-structured",
    # The video SHAPE means you CONSUMED the temporal/spoken content (transcript/audio). A bare frame screenshot
    # (type=image) does NOT prove that — it counts as semi-structured (a labeled-value capture). This deliberately
    # catches the "YouTube URL + frame grab, ASR failed" checkbox-compliance failure the verification run found.
    "transcript": "video", "audio": "video", "video": "video",
    "image": "semi-structured",
    "ocr": "ocr",
}

BUDGET = {
    "low":  {"total": (12, 20), "required": {"unstructured"}, "min_per_shape": 3},
    "med":  {"total": (30, 50), "required": {"unstructured", "semi-structured", "structured"}, "min_per_shape": 3},
    "high": {"total": (50, 100), "required": {"unstructured", "semi-structured", "structured", "video", "ocr"}, "min_per_shape": 5},
}


def _classify_shape(artifact):
    atype = (artifact.get("type", "") or "").lower()
    if atype in SHAPE_MAP:
        return SHAPE_MAP[atype]
    # Fall back to the spine's canonical modality map, then to the file extension, then prose.
    mod = _MODALITY_CLASS.get(atype, "")
    mod_to_shape = {"web": "unstructured", "structured": "structured", "document": "semi-structured",
                    "av": "video", "image": "semi-structured"}
    if mod in mod_to_shape:
        return mod_to_shape[mod]
    ext = os.path.splitext(artifact.get("source", ""))[1].lower()
    if ext in (".pdf", ".xlsx", ".xls"):
        return "semi-structured"
    if ext in (".csv", ".json"):
        return "structured"
    return "unstructured"


def check_shapes(rdir, stakes_override=None):
    rdir = _resolve(rdir)   # accept a refledger slug (r_xxxx) or an absolute path, like the spine CLI
    ledger_path = os.path.join(rdir, "ledger.jsonl")
    if not os.path.exists(ledger_path):
        return {"pass": False, "error": f"No ledger.jsonl in {rdir}"}

    rows = _read_jsonl(ledger_path)
    arts = {r["artifact_id"]: r for r in rows if r.get("kind") == "artifact"}
    findings = [r for r in rows if r.get("kind") == "finding"]
    # Last row WINS per hypothesis_id (stakes is mutable metadata, re-appended) — mirror digest()'s hyps_latest,
    # NOT hypotheses[-1] which would pick a later UNRELATED thesis's stakes.
    hyps_latest = {}
    for r in rows:
        if r.get("kind") == "hypothesis":
            hyps_latest[r["hypothesis_id"]] = r

    issues = []
    _RANK = {"low": 0, "med": 1, "high": 2}
    if stakes_override in BUDGET:
        stakes = stakes_override
        stakes_source = "override"
    elif hyps_latest:
        # Conservative: among DISTINCT theses, gate at the HIGHEST declared stakes (an unspecified '' floors to low).
        stakes = max((h.get("stakes") or "low" for h in hyps_latest.values()),
                     key=lambda s: _RANK.get(s, 0))
        stakes = stakes if stakes in BUDGET else "low"
        stakes_source = "hypothesis"
    else:
        # No hypothesis declared and no override → effort cannot be gated. Surface it LOUDLY (don't silently PASS
        # a high-stakes dig that forgot set_hypothesis); default the budget to low only to still report shapes.
        stakes = "low"
        stakes_source = "undeclared"
        issues.append("stakes-undeclared(no-hypothesis,no-override)")

    budget = BUDGET[stakes]

    shape_counts = {}
    dangling = 0
    for f in findings:
        aid = f.get("artifact_id", "")
        if aid not in arts:
            # Dangling anchor (artifact row missing) — the spine's verify() already fails on this. Do NOT let it
            # masquerade as a real 'unstructured' artifact and inflate the floor into a fabricated PASS.
            dangling += 1
            continue
        shape = _classify_shape(arts[aid])
        shape_counts[shape] = shape_counts.get(shape, 0) + 1

    total = sum(shape_counts.values())   # genuine (non-dangling) findings only
    total_min, total_max = budget["total"]

    if dangling:
        issues.append(f"dangling-findings({dangling})")
    if total < total_min:
        issues.append(f"total-candidates({total}<{total_min})")

    for req_shape in sorted(budget["required"]):
        count = shape_counts.get(req_shape, 0)
        if count < budget["min_per_shape"]:
            issues.append(f"missing-{req_shape}({count}<{budget['min_per_shape']})")

    passed = len(issues) == 0
    return {
        "pass": passed,
        "stakes": stakes,
        "stakes_source": stakes_source,
        "total_findings": total,
        "dangling_findings": dangling,
        # NOTE: budget_min is the enforced floor. The upper end (total_max) is ADVISORY — over-collecting is not a
        # failure (thoroughness isn't punished; quality, not volume, is the agent's call), so it never sets pass=False.
        "budget_min": total_min,
        "budget_max_advisory": total_max,
        "min_per_shape": budget["min_per_shape"],
        "shape_counts": shape_counts,
        "required_shapes": sorted(budget["required"]),
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="Check evidence shape budget")
    parser.add_argument("run_dir", help="Path to refledger run directory")
    parser.add_argument("--stakes", choices=["low", "med", "high"], help="Override stakes level")
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 on unmet floors (default: advisory — report only, exit 0)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    result = check_shapes(args.run_dir, args.stakes)
    result["mode"] = "strict" if args.strict else "advisory"
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result.get("error"):
        print(f"[ERROR] {result['error']}")
    else:
        status = "PASS" if result["pass"] else ("FAIL" if args.strict else "ADVISORY-GAP")
        print(f"[{status}] stakes={result['stakes']}({result['stakes_source']}) "
              f"findings={result['total_findings']} floor={result['budget_min']} "
              f"(max~{result['budget_max_advisory']})")
        print(f"  shapes: {result['shape_counts']}")
        if result.get("issues"):
            print(f"  issues: {', '.join(result['issues'])}")
        if not result["pass"] and not args.strict:
            print("  (advisory mode: gaps reported, not gated -- genuineness comes from provenance + "
                  "adversarial audit, not counts; use --strict to hard-gate)")
    if result.get("error"):
        sys.exit(1)   # wrong path / unreadable ledger = operator error in both modes
    sys.exit(0 if (result["pass"] or not args.strict) else 1)


if __name__ == "__main__":
    main()
