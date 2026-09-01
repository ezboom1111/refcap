#!/usr/bin/env python
# refacquire - the acquisition FACADE for the safety pipeline (leesearch P0-1, PARTIAL).
#
# STATUS (honest, per Codex 3rd review 2026-09-01): this is currently an ADVISORY facade. The real
# production path `refledger.ingest()` still fetches via `_http_get` and does NOT route through here,
# so these gates are enforced ONLY for callers that choose to use acquire(). Wiring the production
# ingest path through a strict gateway (and making registry/schema required, catching fetch/parser
# exceptions, stopping on `suspect`) is OPEN work — see reports/codex-review3.md. Do not claim
# "enforced" until refledger.ingest (or the public entrypoint) is routed through it.
#
# When used, this module is the single entrypoint that orders, fail-visible, so a routed caller's
# wrong result cannot be promoted past a gate:
#
#   (registry freshness) -> opt-out -> fetch -> soft-block -> parse -> validate -> evidence_state
#
# Network + parsing are INJECTED (leesearch gathers natively); this module owns only the ORDER and
# the STOP conditions. Every stop is explicit in `evidence_state` + `gate`, never a silent proceed.
import refopt
import refguard
from collections import namedtuple

PageResponse = namedtuple("PageResponse", ["status", "content_type", "body", "cookies"])
AcquireResult = namedtuple("AcquireResult",
                           ["ok", "evidence_state", "gate", "optout", "softblock", "rows", "issues", "reasons"])


def page_response(body, status=200, content_type="text/html", cookies=None):
    return PageResponse(status=status, content_type=content_type, body=body, cookies=cookies or {})


def _norm_page(p):
    if isinstance(p, PageResponse):
        return p
    if isinstance(p, str):
        return page_response(p)
    if not (hasattr(p, "body") or hasattr(p, "text")):
        return None   # degenerate object: no body -> fetch_invalid, never default to empty ok
    return PageResponse(
        status=getattr(p, "status", getattr(p, "status_code", 200)),
        content_type=getattr(p, "content_type", "text/html"),
        body=getattr(p, "body", getattr(p, "text", "")),
        cookies=getattr(p, "cookies", {}) or {},
    )


def acquire(url, *, fetch_robots, fetch_page, parser, schema=None, user_agent="*",
            selector_hit=None, registry_check=None, allow_conditional=False, min_rows=None):
    """Run one URL through the enforced safety pipeline. Returns AcquireResult (never raises for
    control flow; a stop is a value, not an exception).

    - fetch_robots(robots_url) -> refopt.RobotsResponse | str | None
    - fetch_page(url)          -> PageResponse | str | duck-typed. Called ONLY if opt-out permits.
    - parser(body)             -> list[dict]. Called ONLY if not blocked.
    - schema                   -> refguard.validate_values schema. If issues, rows are NOT promoted.
    - registry_check()         -> optional list[str] freshness warnings (non-blocking, surfaced).
    """
    reasons = []
    if registry_check is not None:
        try:
            for w in (registry_check() or []):
                reasons.append(f"registry: {w}")
        except Exception as e:  # noqa: BLE001
            reasons.append(f"registry check error: {type(e).__name__}: {e}")

    # 1) opt-out gate — content is not fetched unless this permits it.
    opt = refopt.resolve_optout(url, fetch_robots, user_agent=user_agent)
    reasons.extend(opt["reasons"])
    if opt["status"] == refopt.DISALLOWED:
        return AcquireResult(False, "refused_optout", "optout", opt, None, None, None, reasons)
    if opt["status"] == refopt.UNKNOWN:
        return AcquireResult(False, "undecidable_optout", "optout", opt, None, None, None, reasons)
    # allow_conditional must be a LITERAL True. A truthy non-bool (e.g. the string "false") must NOT be
    # read as consent — an override is a deliberate boolean decision, not any truthy value.
    if opt["status"] == refopt.CONDITIONAL and allow_conditional is not True:
        if allow_conditional not in (False, None):
            reasons.append(f"allow_conditional must be True to consent; got {allow_conditional!r} -> treated as no consent")
        return AcquireResult(False, "needs_consent", "optout", opt, None, None, None, reasons)

    # 2) fetch (only now). fetch/parse exceptions are STATES, not crashes (fail-visible).
    try:
        page = _norm_page(fetch_page(url))
    except Exception as e:  # noqa: BLE001
        return AcquireResult(False, "fetch_error", "fetch", opt, None, None, None, reasons + [f"fetch error: {type(e).__name__}: {e}"])
    if page is None or not isinstance(page.body, (str, bytes, bytearray)):
        return AcquireResult(False, "fetch_invalid", "fetch", opt, None, None, None, reasons + ["fetch returned no usable body"])

    # 3) soft-block gate — parser is not called if this blocks.
    sb = refguard.detect_softblock(page.body, status=page.status, cookies=page.cookies,
                                   selector_hit=selector_hit)
    if sb["blocked"]:
        return AcquireResult(False, "blocked", "softblock", opt, sb, None, None, reasons + [f"softblock: {sb['verdict']}"])
    if sb["verdict"] == "http_error":
        return AcquireResult(False, "http_error", "softblock", opt, sb, None, None, reasons + [f"http {page.status}"])
    if sb["verdict"] == "js_wall":
        return AcquireResult(False, "js_wall", "softblock", opt, sb, None, None, reasons + ["js render required"])
    suspect = sb["verdict"] == "suspect"
    if suspect:
        reasons.append(f"softblock suspect: {sb['signals']}")

    # 4) parse
    try:
        rows = parser(page.body)
    except Exception as e:  # noqa: BLE001
        return AcquireResult(False, "parse_error", "parse", opt, sb, None, None, reasons + [f"parse error: {type(e).__name__}: {e}"])
    if not rows:
        return AcquireResult(False, "parse_empty", "parse", opt, sb, [], None, reasons + ["parser returned no rows"])

    # 5) validate — rows are NOT promoted if there are issues. No schema (None OR empty dict) => nothing was
    # checked => ok_unvalidated, never a plain validated `ok`. An empty {} validates zero fields, so treating
    # it as a pass would promote unchecked rows (junk included) as if validated.
    if not schema:
        state = "ok_unvalidated" if not suspect else "suspect"
        return AcquireResult(not suspect, state, None if not suspect else "softblock", opt, sb, rows, [],
                             reasons + ["no (or empty) schema -> validation not run"])
    issues = refguard.validate_values(rows, schema, min_rows=min_rows)
    if issues:
        return AcquireResult(False, "validation_failed", "validate", opt, sb, rows, issues, reasons + issues)

    # A suspect soft-block that still parsed+validated is flagged (ok=False), not silently promoted.
    if suspect:
        return AcquireResult(False, "ok_suspect", "softblock", opt, sb, rows, [], reasons + ["validated but soft-block suspect — agent must confirm"])
    return AcquireResult(True, "ok", None, opt, sb, rows, [], reasons + ["all gates passed"])


if __name__ == "__main__":  # pragma: no cover
    print("refacquire: import and call acquire(); it enforces optout->fetch->softblock->parse->validate.")
