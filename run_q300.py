"""One-off QA harness: build each of the 300 quantitative scenarios into a real ledger, run the REAL
grade_conclusion, and compare to the independently-reasoned expected. A mismatch = a candidate bug (code-vs-intent).
Targets the Rank-6 grader's quantitative math across above/at/below-bar + edges. stdlib only.
Usage: python run_q300.py scenarios_q300.jsonl
"""
import os, sys, json, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refledger as R

_MET = {"true": True, "false": False, "null": None}


def build_and_grade(scn):
    d = tempfile.mkdtemp()
    try:
        r = R.open_research(scn["id"], base=d)
        for i, s in enumerate(scn.get("sources", [])):
            host = (s.get("host") or "").strip()
            url = f"https://{host}/p{i}" if host else f"local:item{i}"   # empty host => urlparse hostname None => _host ""
            art = R.ledger_append(r, type=(s.get("type") or "html"), source=url, method="m",
                                  path="p", sha256="h%d" % i, quality_label="OK")
            pa = (s.get("published_at") or "").strip()
            if pa:
                try:
                    R.set_published(r, art["artifact_id"], pa)
                except ValueError:
                    # garbage/unparseable date: write the pubdate row DIRECTLY to exercise grade's _parse_date robustness
                    R._append_jsonl(os.path.join(r, "ledger.jsonl"),
                                    {"kind": "pubdate", "artifact_id": art["artifact_id"], "published_at": pa, "ts": R._now()})
            R.record_finding(r, "f%d" % i, "OBSERVED", art["artifact_id"], quote=(s.get("quote") or ""), conclusion_id="C")
        try:
            knobs = json.loads(scn["knobs_json"])
        except Exception as e:
            return {"error": "knobs_json:%s" % e}
        try:
            std = R.set_standard(r, **knobs)
        except Exception as e:
            return {"error": "set_standard:%s" % e}
        try:
            return R.grade_conclusion(r, "C", std["standard_id"], scn.get("as_of") or None)
        except Exception as e:
            return {"error": "grade:%s" % e}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def check(scn):
    g = build_and_grade(scn)
    if isinstance(g, dict) and g.get("error"):
        return ("ERROR", ["exception: " + g["error"]])
    fails = []
    if g["overall"] != scn["expected_overall"]:
        fails.append("overall expected=%s actual=%s" % (scn["expected_overall"], g["overall"]))
    for dom, key in (("breadth", "expected_breadth"), ("recency", "expected_recency"), ("consistency", "expected_consistency")):
        exp = scn.get(key, "na")
        if exp == "na":
            continue
        actual = g["domains"].get(dom, {}).get("met")
        if actual != _MET.get(exp):
            fails.append("%s.met expected=%s actual=%s" % (dom, exp, actual))
    return ("FAIL" if fails else "PASS", fails)


def main():
    scns = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
    npass = nfail = nerr = 0
    mism = []
    per_area = {}
    for s in scns:
        status, fails = check(s)
        a = s.get("area", "?")
        per_area.setdefault(a, [0, 0])
        if status == "PASS":
            npass += 1; per_area[a][0] += 1
        else:
            per_area[a][1] += 1
            if status == "ERROR":
                nerr += 1
            else:
                nfail += 1
            mism.append((status, s, fails))
    print("TOTAL=%d PASS=%d FAIL=%d ERROR=%d" % (len(scns), npass, nfail, nerr))
    print("per-area [pass/mismatch]:", {k: "%d/%d" % (v[0], v[1]) for k, v in sorted(per_area.items())})
    with open("_q300_mismatches.txt", "w", encoding="utf-8") as f:
        for status, s, fails in mism:
            f.write("[%s %s/%s] %s: %s\n" % (status, s.get("area"), s.get("band"), s.get("id"), (s.get("description") or "")[:140]))
            for x in fails:
                f.write("    " + x + "\n")
            f.write("    knobs=%s as_of=%s nsrc=%d\n" % (s.get("knobs_json"), s.get("as_of"), len(s.get("sources", []))))
            f.write("    sources=%s\n" % json.dumps([{"h": x.get("host"), "d": x.get("published_at"), "q": (x.get("quote") or "")[:40], "t": x.get("type")} for x in s.get("sources", [])], ensure_ascii=False))
    print("mismatches -> _q300_mismatches.txt (%d)" % len(mism))


if __name__ == "__main__":
    main()
