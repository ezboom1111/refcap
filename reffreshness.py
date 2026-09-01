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
        if rid in seen_ids:
            issues.append(f"duplicate id: {rid}")
            continue
        seen_ids.add(rid)
        if r["status"] not in _VALID_STATUS:
            issues.append(f"{rid}: invalid status '{r['status']}'")
            continue
        try:
            _parse_date(r["observed_at"])
            if r.get("effective_at"):
                _parse_date(r["effective_at"])
        except (ValueError, TypeError):
            issues.append(f"{rid}: unparseable date (observed_at/effective_at)")
            continue
        if not isinstance(r["ttl_days"], int) or r["ttl_days"] <= 0:
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
        if eff and eff > today:
            fresh = "pending"
            reason = f"effective_at {eff.isoformat()} is future ({(eff - today).days}d) — cite as announced"
        elif r["status"] in _UNVERIFIED_STATUS:
            fresh = "unverified"
            reason = f"status {r['status']} — do not hard-code downstream"
        elif age >= r["ttl_days"]:
            fresh = "stale"
            reason = f"age {age}d >= ttl {r['ttl_days']}d — re-verify"
        else:
            fresh = "fresh"
            reason = f"age {age}d < ttl {r['ttl_days']}d"
        out.append({"id": r["id"], "freshness": fresh, "reason": reason, "status": r["status"]})
    return out


def registry_check(path=DEFAULT_REGISTRY, today=None):
    """Adapter for refacquire's registry_check hook: return non-blocking warning strings for
    load issues + any record that is stale/pending/unverified/corrupt. Empty list == all fresh."""
    records, issues = load_registry(path)
    warnings = list(issues)
    for e in evaluate(records, today):
        if e["freshness"] != "fresh":
            warnings.append(f"{e['id']} [{e['freshness']}]: {e['reason']}")
    return warnings


if __name__ == "__main__":  # pragma: no cover
    recs, iss = load_registry()
    for e in evaluate(recs):
        print(f"{e['freshness']:10s} {e['id']:26s} {e['reason']}")
    for i in iss:
        print("ISSUE:", i)
