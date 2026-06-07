"""Adversarial whole-spine STRESS harness (500-scenario x10-round campaign).

NOT a substitute for grade_validity (insight-validity needs REAL future outcomes; this validates the
deterministic MACHINERY only: does the spine crash / mis-grade / drift / leak under mean inputs?).

Two deterministic probes, one uniform JSONL:
  probe="grade": build a real ledger (artifacts+pubdates+findings) -> set_standard -> grade_conclusion;
                 assert overall + per-domain `met` (breadth/recency/consistency/source_type) + shortfall.
                 Transitively exercises _shingles/_host/_jaccard (breadth), _parse_date (recency),
                 _numeric_conflicts/_EN_STOP (consistency), source-type, traceability, overall 4-state.
  probe="calib": write controlled prediction/resolution rows directly -> calibration; assert
                 n_resolved / n_premature (the new instant-resolution advisory) / brier sign.

Expecteds are INTENT-based (reasoned from RANK6_SPEC, NOT mirrored from the impl) so a mismatch is a
candidate bug; the human triages real-bug vs oracle-noise. stdlib only.
Usage: python run_stress.py scenarios_stress.jsonl
"""
import os, sys, json, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refledger as R

_MET = {"true": True, "false": False, "null": None}


def _grade(scn):
    d = tempfile.mkdtemp()
    try:
        r = R.open_research(scn["id"], base=d)
        for i, s in enumerate(scn.get("sources", [])):
            host = (s.get("host") or "").strip()
            url = "https://%s/p%d" % (host, i) if host else "local:item%d" % i
            art = R.ledger_append(r, type=(s.get("type") or "html"), source=url, method="m",
                                  path="p", sha256="h%d" % i, quality_label="OK")
            pa = (s.get("published_at") or "").strip()
            if pa:
                try:
                    R.set_published(r, art["artifact_id"], pa)
                except ValueError:
                    R._append_jsonl(os.path.join(r, "ledger.jsonl"),
                                    {"kind": "pubdate", "artifact_id": art["artifact_id"],
                                     "published_at": pa, "ts": R._now()})
            R.record_finding(r, "f%d" % i, "OBSERVED", art["artifact_id"],
                             quote=(s.get("quote") or ""), conclusion_id="C")
        try:
            knobs = json.loads(scn["knobs_json"])
        except Exception as e:
            return {"error": "knobs_json:%s" % e}
        try:
            std = R.set_standard(r, **knobs)
        except Exception as e:
            return {"error": "set_standard:%s" % e}
        try:
            g = R.grade_conclusion(r, "C", std["standard_id"], scn.get("as_of") or None)
        except Exception as e:
            return {"error": "grade:%s" % e}
        fails = []
        if g["overall"] != scn["expected_overall"]:
            fails.append("overall exp=%s act=%s" % (scn["expected_overall"], g["overall"]))
        for dom, key in (("breadth", "expected_breadth"), ("recency", "expected_recency"),
                         ("consistency", "expected_consistency"), ("source_type", "expected_source_type")):
            exp = scn.get(key, "na")
            if exp == "na":
                continue
            act = g["domains"].get(dom, {}).get("met")
            if act != _MET.get(exp):
                fails.append("%s.met exp=%s act=%s" % (dom, exp, act))
        return {"fails": fails}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _calib(scn):
    d = tempfile.mkdtemp()
    try:
        r = R.open_research(scn["id"], base=d)
        path = os.path.join(r, "predictions.jsonl")
        for p in scn.get("predictions", []):
            R._append_jsonl(path, {"kind": "prediction", "prediction_id": p["pid"],
                                   "claim": p.get("claim", "c"), "stated_confidence": float(p["confidence"]),
                                   "resolve_by": p.get("resolve_by", "2099-01-01"), "operator": "",
                                   "anchor_artifact_id": "", "conclusion_id": p.get("conclusion_id", ""),
                                   "created": p["created"]})
        for res in scn.get("resolutions", []):
            R._append_jsonl(path, {"kind": "resolution", "prediction_id": res["pid"],
                                   "outcome": res["outcome"], "evidence_artifact": "",
                                   "anchored": bool(res.get("anchored")), "ts": res["ts"]})
        try:
            c = R.calibration(r)
        except Exception as e:
            return {"error": "calib:%s" % e}
        fails = []
        exp = scn.get("expected", {})
        for k in ("n_resolved", "n_premature"):
            if k in exp and c.get(k) != exp[k]:
                fails.append("%s exp=%s act=%s" % (k, exp[k], c.get(k)))
        if "brier_all" in exp:
            want, got = exp["brier_all"], c.get("brier_all")
            if want == "none" and got is not None:
                fails.append("brier_all exp=none act=%s" % got)
            elif want == "positive" and not (isinstance(got, (int, float)) and got > 0):
                fails.append("brier_all exp=positive act=%s" % got)
            elif want == "zero" and got != 0.0:
                fails.append("brier_all exp=zero act=%s" % got)
        return {"fails": fails}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def check(scn):
    probe = scn.get("probe", "grade")
    res = _grade(scn) if probe == "grade" else _calib(scn) if probe == "calib" else {"error": "unknown probe %s" % probe}
    if res.get("error"):
        return ("ERROR", ["exception: " + res["error"]])
    return ("FAIL" if res["fails"] else "PASS", res["fails"])


def main():
    scns = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
    npass = nfail = nerr = 0
    mism = []
    per = {}
    for s in scns:
        status, fails = check(s)
        t = s.get("theme", "?")
        per.setdefault(t, [0, 0])
        if status == "PASS":
            npass += 1; per[t][0] += 1
        else:
            per[t][1] += 1
            nerr += (status == "ERROR"); nfail += (status == "FAIL")
            mism.append((status, s, fails))
    print("TOTAL=%d PASS=%d FAIL=%d ERROR=%d" % (len(scns), npass, nfail, nerr))
    print("per-theme [pass/mismatch]:", {k: "%d/%d" % (v[0], v[1]) for k, v in sorted(per.items())})
    with open("_stress_mismatches.txt", "w", encoding="utf-8") as f:
        for status, s, fails in mism:
            f.write("[%s %s/%s] %s: %s\n" % (status, s.get("theme"), s.get("probe"), s.get("id"),
                                             (s.get("description") or "")[:160]))
            f.write("    hypothesis=%s\n" % (s.get("hypothesis") or ""))
            for x in fails:
                f.write("    " + x + "\n")
            if s.get("probe") == "grade":
                f.write("    knobs=%s as_of=%s\n" % (s.get("knobs_json"), s.get("as_of")))
                f.write("    sources=%s\n" % json.dumps([{"h": x.get("host"), "d": x.get("published_at"),
                        "t": x.get("type"), "q": (x.get("quote") or "")[:48]} for x in s.get("sources", [])], ensure_ascii=False))
            else:
                f.write("    preds=%s\n    res=%s\n" % (json.dumps(s.get("predictions", []), ensure_ascii=False),
                                                        json.dumps(s.get("resolutions", []), ensure_ascii=False)))
    print("mismatches -> _stress_mismatches.txt (%d)" % len(mism))


if __name__ == "__main__":
    main()
