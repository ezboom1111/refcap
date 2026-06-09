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
    elif result.get("error"):
        print(f"[ERROR] {result['error']}")
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
