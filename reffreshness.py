#!/usr/bin/env python
# reffreshness - the loader that makes facts.registry.json a REAL per-record freshness registry
# (leesearch P0-2). Answers Codex 2nd review's "cosmetic registry / no loader" charge.
#
# It NEVER re-labels last-known-good as fresh: an expired or unverified record stays that way until a
# real re-observation updates observed_at (there is no --fix that fakes freshness here). Missing file
# or corrupt/invalid records surface as issues, not as silent `fresh`.
#
# freshness per record:
#   pending   : effective_at is in the future (cite as "announced", not a current fact)
#   unverified: status in {unverified, partially-verified} (do not hard-code downstream)
#   stale     : observed_at + ttl_days < today (TTL passed -> re-verify before relying)
#   fresh     : within TTL and verified
#   corrupt   : record failed schema/date validation
# stdlib only.
import json
import os
from datetime import date, datetime, timezone

_REQUIRED = ("id", "claim", "status", "source_refs", "observed_at", "ttl_days", "scope")
_VALID_STATUS = {"observed", "announced", "effective", "degraded", "dead", "partially-verified", "unverified"}
_UNVERIFIED_STATUS = {"unverified", "partially-verified"}
_UNHEALTHY_STATUS = {"dead", "degraded"}   # a tool marked dead/degraded is unusable even while within TTL

DEFAULT_REGISTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "skills", "leesearch", "facts.registry.json")


def _parse_date(s):
    return datetime.strptime(str(s).strip(), "%Y-%m-%d").date()


def load_registry(path=DEFAULT_REGISTRY):
    """Load + validate. Returns (records, issues). A missing/corrupt file yields ([], [issue...])."""
    issues = []
    if not os.path.exists(path):
        return [], [f"registry missing: {path}"]
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return [], [f"registry unreadable: {type(e).__name__}: {e}"]
    if not isinstance(data, dict):
        return [], [f"registry root must be an object, got {type(data).__name__}"]
    records = data.get("records")
    if not isinstance(records, list):
        return [], ["registry has no 'records' list"]

    seen_ids = set()
    valid = []
    for i, r in enumerate(records):
        if not isinstance(r, dict):
            issues.append(f"record #{i} is not an object")
            continue
        missing = [k for k in _REQUIRED if k not in r]
        if missing:
            issues.append(f"record #{i} ({r.get('id', '?')}) missing fields: {missing}")
            continue
        rid = r["id"]
        if not isinstance(rid, str) or not rid.strip():
            issues.append(f"record #{i}: id must be a non-empty string")
            continue
        if rid in seen_ids:
            issues.append(f"duplicate id: {rid}")
            continue
        seen_ids.add(rid)
        # status must be a STRING before set membership — a list status raised TypeError: unhashable type.
        if not isinstance(r["status"], str):
            issues.append(f"{rid}: status must be a string, got {type(r['status']).__name__}")
            continue
        if r["status"] not in _VALID_STATUS:
            issues.append(f"{rid}: invalid status '{r['status']}'")
            continue
        if not isinstance(r["claim"], str) or not r["claim"].strip():
            issues.append(f"{rid}: claim must be a non-empty string")
            continue
        if not isinstance(r["source_refs"], list) or not r["source_refs"]:
            issues.append(f"{rid}: source_refs must be a non-empty list")
            continue
        # each source_ref must be a real non-empty string — a [null]/[""] list was clean-loading before.
        if any(not isinstance(s, str) or not s.strip() for s in r["source_refs"]):
            issues.append(f"{rid}: source_refs items must be non-empty strings")
            continue
        if not isinstance(r["scope"], str) or not r["scope"].strip():
            issues.append(f"{rid}: scope must be a non-empty string")
            continue
        try:
            observed = _parse_date(r["observed_at"])
            if r.get("effective_at"):
                _parse_date(r["effective_at"])
        except (ValueError, TypeError):
            issues.append(f"{rid}: unparseable date (observed_at/effective_at)")
            continue
        # bool is an int subclass -> reject explicitly so ttl_days:true can't slip through
        if isinstance(r["ttl_days"], bool) or not isinstance(r["ttl_days"], int) or r["ttl_days"] <= 0:
            issues.append(f"{rid}: ttl_days must be a positive int")
            continue
        valid.append(r)
    return valid, issues


def evaluate(records, today=None):
    """Classify each record's freshness. Pure — does not mutate records or touch disk."""
    today = today or datetime.now(timezone.utc).date()
    out = []
    for r in records:
        observed = _parse_date(r["observed_at"])
        eff = _parse_date(r["effective_at"]) if r.get("effective_at") else None
        age = (today - observed).days
        if age < 0:
            fresh = "corrupt"
            reason = f"observed_at {observed.isoformat()} is in the future ({-age}d) -> data error / fake stamp"
        elif eff and eff > today:
            fresh = "pending"
            reason = f"effective_at {eff.isoformat()} is future ({(eff - today).days}d) -> cite as announced"
        elif r["status"] in _UNVERIFIED_STATUS:
            fresh = "unverified"
            reason = f"status {r['status']} -> do not hard-code downstream"
        elif age >= r["ttl_days"]:
            fresh = "stale"
            reason = f"age {age}d >= ttl {r['ttl_days']}d -> re-verify"
        else:
            fresh = "fresh"
            reason = f"age {age}d < ttl {r['ttl_days']}d"
        out.append({"id": r["id"], "freshness": fresh, "reason": reason, "status": r["status"]})
    return out


def registry_check(path=DEFAULT_REGISTRY, today=None):
    """Adapter for refacquire's registry_check hook: return non-blocking warning strings for
    load issues + any record that is stale/pending/unverified/corrupt, AND any record whose status
    is dead/degraded (unusable regardless of freshness — otherwise a recently-observed dead tool is
    machine-silent). Empty list == all fresh AND healthy."""
    records, issues = load_registry(path)
    warnings = list(issues)
    by_id = {r["id"]: r for r in records}
    for e in evaluate(records, today):
        rec = by_id.get(e["id"], {})
        if e["freshness"] != "fresh":
            warnings.append(f"{e['id']} [{e['freshness']}]: {e['reason']}")
        elif rec.get("status") in _UNHEALTHY_STATUS:
            warnings.append(f"{e['id']} [{rec['status']}]: within TTL but health is {rec['status']} -> unusable")
    return warnings


if __name__ == "__main__":  # pragma: no cover
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows cp949 consoles choke on non-ASCII otherwise
    except Exception:  # noqa: BLE001
        pass
    recs, iss = load_registry()
    status_by_id = {r["id"]: r["status"] for r in recs}
    for e in evaluate(recs):
        # show status alongside freshness so a `dead` tool isn't misread as usable just because it's `fresh`
        print(f"{e['freshness']:10s} status={status_by_id.get(e['id'],'?'):18s} {e['id']:26s} {e['reason']}")
    for i in iss:
        print("ISSUE:", i)
