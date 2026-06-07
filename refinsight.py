#!/usr/bin/env python
# refinsight - layer-3 EXTRACTIVE insight benchmark SCORER (Rank-4 of the insight-accuracy R&D).
# stdlib only, farm import 0 (neutrality), sibling of refbench(layer1)/test_refledger(layer2).
#
# WHAT: scores DERIVED values the agent produced against externally-checkable GOLD (official-API numbers,
# on-screen prices, list items, settled facts). NON-CIRCULAR: gold is a real fact a human/free-API settles in
# seconds, NOT an LLM-judge (rejected by the R&D - circular when judge==researcher). The AGENT runs the
# research and produces a results map {task_id: value}; this module ONLY scores (don't-code-the-brain).
#
# HONEST: the headline is EXTRACTIVE pass-rate (verbatim-checkable facts only) - a REGRESSION TRIPWIRE, never
# "insight accuracy" unqualified (synthesis/contradiction/recall are the hard part, not scored here). Ships
# AFTER the cheaper non-circular signals (calibration rank-1, capture-ceiling rank-2) per the red-team: a
# self-authored benchmark Goodharts and rots, so it carries anti-gaming armor - held-out split, poison cards
# (a planted trap the agent must NOT match - it must explicitly abstain), freshness expiry on captured_at, and
# a STABLE-fact headline so drift-prone counts don't fire a phantom regression.
#
# KNOWN LIMITS (a tripwire, not a proof): text matching is word-boundary substring - it does NOT understand
# NEGATION ("founded NOT in 2009" still matches gold "2009"); keep gold values specific. CJK gold falls back to
# plain substring (no \b in CJK). A non-answer is NOT an abstention (a poison card is 'caught' only if the agent
# actually answered AND abstained - silence is dodging, not detecting).
#
# CARD: {task_id, question, answer_kind(settled-fact|list-item|api-number|on-screen-price|count),
#        gold_value, gold_source_url, tolerance(num kinds), stable(bool), holdout(bool), poison(bool),
#        captured_at(YYYY-MM-DD), ttl_days}. Gold bootstraps for free from normal use (every official-API
# number / on-screen price the agent already registers is a pre-anchored gold candidate).
import json, re, datetime, argparse

_NUM = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?(?:[eE][+-]?\d+)?")   # commas as thousands-groups; allows 1e6
_NUMERIC_KINDS = {"api-number", "on-screen-price", "count"}
_MISSING = object()                       # distinguishes 'agent never answered' from an explicit abstention


def _num(v):
    m = _NUM.search(str(v))
    if not m:
        return None
    try:
        return float(m.group().replace(",", ""))
    except ValueError:
        return None


def _norm(s):
    return re.sub(r"\s+", " ", str(s).strip().lower())


def is_abstain(answer):
    """An EXPLICIT 'I don't know' - NOT a missing answer (see _MISSING) and NOT a wrong answer."""
    return answer is None or _norm(answer) in ("", "unknown", "abstain", "n/a", "none", "모름", "확인불가")


def _matches_text(gold, answer):
    g, a = _norm(gold), _norm(answer)
    if not g:
        return False
    if g.isascii():   # word-boundary so gold '9' != '1999' and '2009' != '12009' (CJK has no \b -> substring)
        return re.search(r"(?<!\w)" + re.escape(g) + r"(?!\w)", a) is not None
    return g in a


def card_passes(card, answer):
    """One card's pass/fail. answer may be the _MISSING sentinel (agent never responded).
    poison: passes IFF the agent ANSWERED and explicitly abstained (silence is dodging, not detecting).
    numeric kinds: |answer - gold| <= tolerance. settled-fact/list-item: word-boundary substring of gold."""
    if card.get("poison"):
        return answer is not _MISSING and is_abstain(answer)
    if answer is _MISSING or is_abstain(answer):
        return False
    if card.get("answer_kind") in _NUMERIC_KINDS:
        a, g = _num(answer), _num(card.get("gold_value"))
        return a is not None and g is not None and abs(a - g) <= float(card.get("tolerance", 0) or 0)
    return _matches_text(card.get("gold_value"), answer)


def _expired(card, today):
    ca, ttl = card.get("captured_at"), card.get("ttl_days")
    if ca is None or ttl is None:               # explicit None (so ttl_days=0 reaches the comparison)
        return False
    try:
        d = datetime.datetime.strptime(str(ca)[:10], "%Y-%m-%d").date()
        return (today - d).days > int(float(ttl))
    except (ValueError, TypeError):
        return False


def _valid(c):
    return bool(c.get("task_id") and c.get("answer_kind") and c.get("gold_value") is not None)


def score(cards, results, today=None):
    """cards: list of card dicts. results: {task_id: agent_answer}. today: datetime.date (defaults to UTC).
    Returns the scorecard. Reports, never gates (the agent/human reads it; a pass-rate DROP = a real regression).
    Malformed cards (missing task_id/answer_kind/gold_value) are EXCLUDED and counted in n_invalid (not silent)."""
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    invalid = [c for c in cards if not _valid(c)]
    rows = []
    for c in (c for c in cards if _valid(c)):
        ans = results.get(c["task_id"], _MISSING)
        rows.append({"task_id": c["task_id"], "kind": c.get("answer_kind", ""),
                     "stable": bool(c.get("stable")), "poison": bool(c.get("poison")),
                     "holdout": bool(c.get("holdout")), "expired": _expired(c, today),
                     "answered": c["task_id"] in results, "passed": card_passes(c, ans)})

    def rate(rs):
        rs = [r for r in rs if not r["expired"]]
        return round(sum(r["passed"] for r in rs) / len(rs), 4) if rs else None

    live_nonpoison = [r for r in rows if not r["expired"] and not r["poison"]]
    poison = [r for r in rows if r["poison"] and not r["expired"]]          # expired poison excluded (like all rates)
    held = [r for r in live_nonpoison if r["holdout"]]
    pr_dev = rate([r for r in live_nonpoison if not r["holdout"]])
    pr_held = rate(held)
    return {
        "n_cards": len(cards), "n_invalid": len(invalid), "n_scored": sum(r["answered"] for r in rows),
        "n_expired": sum(r["expired"] for r in rows), "n_live": len(live_nonpoison), "n_holdout_live": len(held),
        "extractive_pass_rate": rate(live_nonpoison),
        "stable_fact_pass_rate": rate([r for r in live_nonpoison if r["stable"]]),  # <- the regression-tripwire headline
        "pass_rate_by_kind": {k: rate([r for r in live_nonpoison if r["kind"] == k])
                              for k in sorted({r["kind"] for r in live_nonpoison})},
        "poison_caught_rate": (round(sum(r["passed"] for r in poison) / len(poison), 4) if poison else None),
        "holdout_gap": (round(pr_dev - pr_held, 4) if (pr_dev is not None and pr_held is not None) else None),
        "note": "EXTRACTIVE pass-rate (verbatim-checkable facts only) - a regression tripwire, NOT 'insight accuracy'.",
    }


def load_cards(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("cards"), list):
        return data["cards"]
    raise ValueError(f"{path}: expected a JSON list of cards or an object with a 'cards' list (got {type(data).__name__})")


def main():
    ap = argparse.ArgumentParser(description="refinsight - extractive insight benchmark scorer (agent runs, this scores)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("score"); ps.add_argument("cards"); ps.add_argument("results")
    sub.add_parser("questions").add_argument("cards")   # BLIND run: emit only task_id+question
    a = ap.parse_args()
    cards = load_cards(a.cards)
    if a.cmd == "questions":
        print(json.dumps([{"task_id": c.get("task_id"), "question": c.get("question")} for c in cards], ensure_ascii=False, indent=2))
        return
    with open(a.results, encoding="utf-8") as f:
        results = json.load(f)
    print(json.dumps(score(cards, results), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
