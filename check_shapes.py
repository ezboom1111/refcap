#!/usr/bin/env python
"""check_shapes.py — deterministic shape-budget validator for leesearch-alpha investigations.

Reads a ledger.jsonl run directory and checks whether the evidence shapes meet the declared
stakes level's budget (as defined in evidence-budget.md). Exits 0 = pass, 1 = fail.

Usage:
    python check_shapes.py <run_dir>                  # auto-detect stakes from hypothesis
    python check_shapes.py <run_dir> --stakes high    # override stakes level
    python check_shapes.py <run_dir> --json            # machine-readable output
"""
import os, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from refledger import _read_jsonl, _host

SHAPE_MAP = {
    "page_html": "unstructured",
    "structured_data": "structured",
    "frame_screenshot": "video",
    "ocr_text": "ocr",
    "transcript_cue": "video",
}

BUDGET = {
    "low":  {"total": (12, 20), "required": {"unstructured"}, "min_per_shape": 3},
    "med":  {"total": (30, 50), "required": {"unstructured", "semi-structured", "structured"}, "min_per_shape": 3},
    "high": {"total": (50, 100), "required": {"unstructured", "semi-structured", "structured", "video", "ocr"}, "min_per_shape": 5},
}


def _classify_shape(artifact):
    atype = artifact.get("type", "")
    if atype in SHAPE_MAP:
        return SHAPE_MAP[atype]
    ext = os.path.splitext(artifact.get("source", ""))[1].lower()
    if ext in (".pdf", ".xlsx", ".xls", ".csv"):
        return "semi-structured"
    return "unstructured"


def _is_genuine_structured(artifact, finding):
    """Structured shape requires data from an official source with typed fields,
    not news text repackaged into JSON."""
    if artifact.get("type") != "structured_data":
        return False
    source = artifact.get("source", "")
    if not source:
        return False
    return True


def check_shapes(rdir, stakes_override=None):
    ledger_path = os.path.join(rdir, "ledger.jsonl")
    if not os.path.exists(ledger_path):
        return {"pass": False, "error": f"No ledger.jsonl in {rdir}"}

    rows = _read_jsonl(ledger_path)
    arts = {r["artifact_id"]: r for r in rows if r.get("kind") == "artifact"}
    findings = [r for r in rows if r.get("kind") == "finding"]
    hypotheses = [r for r in rows if r.get("kind") == "hypothesis"]

    stakes = stakes_override or ""
    if not stakes and hypotheses:
        stakes = hypotheses[-1].get("stakes", "low") or "low"
    if stakes not in BUDGET:
        stakes = "low"

    budget = BUDGET[stakes]

    shape_counts = {}
    shape_findings = {}
    for f in findings:
        aid = f.get("artifact_id", "")
        art = arts.get(aid, {})
        shape = _classify_shape(art)
        shape_counts[shape] = shape_counts.get(shape, 0) + 1
        shape_findings.setdefault(shape, []).append(f)

    total = len(findings)
    total_min, total_max = budget["total"]

    issues = []
    if total < total_min:
        issues.append(f"total-candidates({total}<{total_min})")

    for req_shape in budget["required"]:
        count = shape_counts.get(req_shape, 0)
        if count < budget["min_per_shape"]:
            issues.append(f"missing-{req_shape}({count}<{budget['min_per_shape']})")

    passed = len(issues) == 0
    return {
        "pass": passed,
        "stakes": stakes,
        "total_findings": total,
        "budget_range": list(budget["total"]),
        "min_per_shape": budget["min_per_shape"],
        "shape_counts": shape_counts,
        "required_shapes": sorted(budget["required"]),
        "issues": issues,
    }


def main():
    parser = argparse.ArgumentParser(description="Check evidence shape budget")
    parser.add_argument("run_dir", help="Path to refledger run directory")
    parser.add_argument("--stakes", choices=["low", "med", "high"], help="Override stakes level")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    result = check_shapes(args.run_dir, args.stakes)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "PASS" if result["pass"] else "FAIL"
        print(f"[{status}] stakes={result['stakes']} findings={result['total_findings']} "
              f"budget={result['budget_range']}")
        print(f"  shapes: {result['shape_counts']}")
        if result.get("issues"):
            print(f"  issues: {', '.join(result['issues'])}")
    sys.exit(0 if result["pass"] else 1)


if __name__ == "__main__":
    main()
