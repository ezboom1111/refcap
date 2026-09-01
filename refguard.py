#!/usr/bin/env python
# refguard - soft-block detection + value validation. HARDENED v2 (after Codex 2nd review 2026-09-01).
#
# v1 bugs fixed (reproduced by adversarial probe before this rewrite):
#   - false-positive block: a challenge marker as a bare substring flagged `blocked` even on a normal
#     article where the content selector HIT. FIX: markers are scored WITH selector evidence — if the
#     content selector hit, a marker in the body is treated as content, not a wall.
#   - HTTP 404/410/500 were merged into anti-bot `blocked`. FIX: HTTP errors get their own `http_error`
#     verdict, distinct from an anti-bot wall (403 stays ambiguous -> suspect unless a marker co-occurs).
#   - "non-throwing" was violated: a bad reject_regex raised re.error. FIX: every field is guarded;
#     an invalid regex / bytes html / hostile cookie becomes an ISSUE, never an exception.
#   - NaN/inf passed min/max. FIX: non-finite numbers are flagged, not silently in-range.
#   - max_empty_ratio only checked when required=True. FIX: checked whenever the rule specifies it.
#
# NOTE on scope: reject_regex is a KNOWN-JUNK DENYLIST, not a general wrong-target proof. Real
# wrong-target 0 needs stable id/URL, row cardinality, and cross-field invariants; `unique`/`min_rows`
# are first steps, but this module does not claim to guarantee correctness of extracted values.
#
# stdlib only. Non-throwing by contract (a guard must never crash the pipeline it protects).
import math
import re
from html.parser import HTMLParser  # noqa: F401 (reserved for future marker-position scoring)

_CHALLENGE_MARKERS = (
    "just a moment", "checking your browser", "access denied", "errors.edgesuite.net",
    "pardon our interruption", "captcha-delivery.com", "sec-if-cpt-container",
    "unusual traffic", "are you a robot", "verify you are human", "please enable cookies",
)
_JS_WALL_MARKERS = (
    "enable javascript", "javascript is required", "requires javascript", "javascript to run this app",
)
_TINY_BODY = 3000


def detect_softblock(html="", status=200, cookies=None, selector_hit=None, tiny_body=_TINY_BODY):
    """Return {blocked, verdict, signals, body_len}.

    verdict: blocked | http_error | js_wall | empty_shell | suspect | ok | weak_ok
    Precedence is content-aware and FALSE-POSITIVE-SAFE:
      - a selector HIT means content was extracted, so a challenge marker in the body is content, not a wall
      - an un-passed Akamai sensor cookie is a network-level block regardless of content
      - HTTP errors are `http_error` (not conflated with an anti-bot wall); 403 is ambiguous
    `blocked` is True only for a genuine anti-bot wall or an empty shell — not for http_error/js_wall/suspect.
    """
    try:
        html = "" if html is None else (html if isinstance(html, str) else html.decode("utf-8", "replace")
                                        if isinstance(html, (bytes, bytearray)) else str(html))
    except Exception:  # noqa: BLE001
        html = ""
    low = html.lower()
    body_len = len(html)
    signals = []

    marker = next((m for m in _CHALLENGE_MARKERS if m in low), None)
    if marker:
        signals.append(f"challenge:{marker}")
    js_wall = next((m for m in _JS_WALL_MARKERS if m in low), None)
    if js_wall:
        signals.append(f"js-wall:{js_wall}")
    tiny = body_len < tiny_body
    if tiny:
        signals.append(f"tiny-body:{body_len}")

    abck_unpassed = False
    try:
        if cookies and hasattr(cookies, "get"):
            abck = cookies.get("_abck")
            if abck and "~-1~" in str(abck):
                abck_unpassed = True
                signals.append("akamai:_abck-unpassed")
    except Exception:  # noqa: BLE001 - hostile cookie mapping must not crash the guard
        signals.append("cookie-scan-error")

    is_http_err = isinstance(status, int) and status >= 400
    if is_http_err:
        signals.append(f"http-{status}")

    # --- precedence ---
    if abck_unpassed:
        verdict, blocked = "blocked", True
    elif is_http_err and status in (404, 410):
        verdict, blocked = "http_error", False           # content genuinely absent, not a wall
    elif is_http_err and status >= 500:
        verdict, blocked = "http_error", False
    elif is_http_err and status == 403:
        verdict, blocked = ("blocked", True) if (marker or selector_hit is False) else ("suspect", False)
    elif is_http_err:  # other 4xx
        verdict, blocked = "http_error", False
    elif selector_hit is True:
        verdict, blocked = "ok", False                    # content extracted -> marker (if any) is content
    elif marker and (tiny or selector_hit is False):
        verdict, blocked = "blocked", True                # marker on a shell / no content -> real wall
    elif marker:
        verdict, blocked = "suspect", False               # marker on a normal-size body, content unknown
    elif js_wall:
        verdict, blocked = "js_wall", False               # recoverable render, not a block
    elif selector_hit is False and tiny:
        verdict, blocked = "empty_shell", True
    elif selector_hit is False:
        verdict, blocked = "suspect", False
    else:
        verdict, blocked = "weak_ok", False               # small size alone never blocks

    return {"blocked": blocked, "verdict": verdict, "signals": signals, "body_len": body_len}


def _coerce_num(v, as_int):
    s = str(v).replace(",", "").strip()
    return int(s) if as_int else float(s)


def validate_values(rows, schema, min_rows=None):
    """Validate scraped rows against a per-field schema. Returns a list of issue strings; NEVER raises.

    schema[field]: type ("int"|"float"|"str"), required (bool), max_empty_ratio (0..1),
                   min/max (numeric), allow_uniform (bool), reject_regex (str, known-junk denylist),
                   unique (bool, flag duplicate values), min_uniform_n (int, default 10).
    min_rows: table-level minimum row count (cardinality guard).
    """
    issues = []
    if not rows:
        return ["no rows to validate"]
    n = len(rows)
    if min_rows is not None and n < min_rows:
        issues.append(f"[_table] only {n} rows < min_rows {min_rows}")

    for field, rule in (schema or {}).items():
        try:
            vals = [(_r.get(field) if isinstance(_r, dict) else None) for _r in rows]
            present = [v for v in vals if v is not None and str(v).strip() != ""]
            empty_ratio = 1.0 - (len(present) / n)

            if "max_empty_ratio" in rule or rule.get("required"):
                limit = rule.get("max_empty_ratio", 0.0)
                if empty_ratio > limit:
                    issues.append(f"[{field}] empty ratio {empty_ratio:.0%} exceeds max {limit:.0%}")

            t = rule.get("type")
            if t in ("int", "float"):
                coerced, bad = [], 0
                for v in present:
                    try:
                        coerced.append(_coerce_num(v, t == "int"))
                    except (ValueError, TypeError):
                        bad += 1
                if bad:
                    issues.append(f"[{field}] {bad}/{len(present)} values not coercible to {t}")
                nonfinite = [c for c in coerced if not math.isfinite(c)]
                if nonfinite:
                    issues.append(f"[{field}] {len(nonfinite)} non-finite value(s) (NaN/inf)")
                finite = [c for c in coerced if math.isfinite(c)]
                lo, hi = rule.get("min"), rule.get("max")
                if lo is not None:
                    out = [c for c in finite if c < lo]
                    if out:
                        issues.append(f"[{field}] {len(out)} value(s) < min {lo} (e.g. {out[:3]})")
                if hi is not None:
                    out = [c for c in finite if c > hi]
                    if out:
                        issues.append(f"[{field}] {len(out)} value(s) > max {hi} (e.g. {out[:3]})")
            elif t == "str":
                nonstr = [v for v in present if not isinstance(v, str)]
                if nonstr:
                    issues.append(f"[{field}] {len(nonstr)} value(s) not str")

            rej = rule.get("reject_regex")
            if rej:
                try:
                    rx = re.compile(rej, re.IGNORECASE)
                    hits = [v for v in present if rx.search(str(v))]
                    if hits:
                        issues.append(f"[{field}] known-junk: {len(hits)} value(s) match /{rej}/ (e.g. {hits[:3]})")
                except re.error as e:
                    issues.append(f"[{field}] invalid reject_regex /{rej}/: {e}")

            if rule.get("unique"):
                seen, dups = set(), 0
                for v in present:
                    k = str(v)
                    if k in seen:
                        dups += 1
                    seen.add(k)
                if dups:
                    issues.append(f"[{field}] {dups} duplicate value(s) (expected unique)")

            if not rule.get("allow_uniform"):
                min_u = rule.get("min_uniform_n", 10)
                if len(present) >= min_u and len({str(v) for v in present}) == 1:
                    issues.append(f"[{field}] all {len(present)} values identical ('{present[0]}') — selector may grab a fixed element")
        except Exception as e:  # noqa: BLE001 - a guard must never crash its pipeline
            issues.append(f"[{field}] validation error: {type(e).__name__}: {e}")

    return issues


if __name__ == "__main__":  # pragma: no cover
    import json, sys
    print(json.dumps(detect_softblock(sys.stdin.read()), ensure_ascii=False, indent=2))
