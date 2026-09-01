#!/usr/bin/env python
# refguard - soft-block detection + value validation for lawful gathering (leesearch P1).
#
# Clean-room: the CONCEPT is from the surveyed web-crawler (MIT) utils.py, but this code is
# written fresh. Two guards a gatherer needs so it never ships "N rows of garbage":
#
#   detect_softblock(html, status, cookies, selector_hit)
#     HTTP 200 != success. WAF/Akamai/Cloudflare answer 200 with a challenge page or an empty
#     shell. Flag it BEFORE parsing. FALSE-POSITIVE-SAFE: a small legitimate page is NOT a block
#     (require a positive block signal, not just a small body). A JS-wall ("enable javascript")
#     is NOT a bot-block — it is a recoverable render escalation, reported separately.
#
#   validate_values(rows, schema)
#     Catch the silent-wrong the Scrapling experiment surfaced (2026-09-01): a self-healing or
#     greedy selector "always returns something", so verify type/range/empty/uniform and
#     optionally reject known-junk (ads) = the wrong-target guard the plan's A/B was missing.
#
# stdlib only. Non-throwing (a guard must never crash the pipeline it protects).
import re

# --- soft-block ------------------------------------------------------------
# Positive block signals (case-insensitive substrings). A block needs ONE of these,
# or an empty-shell combination — never body-size alone (that would false-positive).
_CHALLENGE_MARKERS = (
    "just a moment",              # Cloudflare
    "checking your browser",      # Cloudflare / DDoS-GUARD
    "access denied",              # Akamai
    "errors.edgesuite.net",       # Akamai
    "pardon our interruption",    # PerimeterX
    "captcha-delivery.com",       # DataDome
    "sec-if-cpt-container",       # generic captcha container
    "unusual traffic",            # Google
    "are you a robot",
    "verify you are human",
    "please enable cookies",
)
# JS-wall markers: recoverable via browser render, NOT a bot-block.
_JS_WALL_MARKERS = (
    "enable javascript",
    "javascript is required",
    "requires javascript",
    "javascript to run this app",
)
_TINY_BODY = 3000  # bytes; only meaningful WITH another signal


def detect_softblock(html="", status=200, cookies=None, selector_hit=None, tiny_body=_TINY_BODY):
    """Return {blocked, verdict, signals, body_len}.

    verdict: blocked | js_wall | empty_shell | suspect | ok | weak_ok
    - blocked    : a challenge marker or an un-passed Akamai sensor cookie is present.
    - empty_shell: no marker, but tiny body AND the content selector did not hit (blocked-shaped).
    - js_wall    : a JS-required notice (recoverable by rendering; not a bot-block).
    - suspect    : selector expected but missed on a normal-size body (maybe wrong selector).
    - ok         : content selector hit.
    - weak_ok    : nothing suspicious, but no selector was provided to confirm content.
    FALSE-POSITIVE-SAFE: a small page with no marker and selector_hit True/None is NOT blocked.
    """
    html = html or ""
    low = html.lower()
    body_len = len(html)
    signals = []

    if isinstance(status, int) and status >= 400:
        signals.append(f"http-{status}")

    marker = next((m for m in _CHALLENGE_MARKERS if m in low), None)
    if marker:
        signals.append(f"challenge:{marker}")

    # Akamai _abck sensor: a value containing "~-1~" means NOT passed (still challenged).
    abck_unpassed = False
    if cookies:
        abck = cookies.get("_abck") if hasattr(cookies, "get") else None
        if abck and "~-1~" in str(abck):
            abck_unpassed = True
            signals.append("akamai:_abck-unpassed")

    js_wall = next((m for m in _JS_WALL_MARKERS if m in low), None)
    if js_wall:
        signals.append(f"js-wall:{js_wall}")

    tiny = body_len < tiny_body
    if tiny:
        signals.append(f"tiny-body:{body_len}")

    # verdict — precedence
    if marker or abck_unpassed or (isinstance(status, int) and status >= 400):
        verdict, blocked = "blocked", True
    elif js_wall:
        verdict, blocked = "js_wall", False           # recoverable render, not a block
    elif selector_hit is False and tiny:
        verdict, blocked = "empty_shell", True        # blocked-shaped: no content where expected
    elif selector_hit is False:
        verdict, blocked = "suspect", False           # normal body, selector missed -> maybe wrong selector
    elif selector_hit is True:
        verdict, blocked = "ok", False
    else:
        verdict, blocked = "weak_ok", False           # no selector to confirm; small size alone != block

    return {"blocked": blocked, "verdict": verdict, "signals": signals, "body_len": body_len}


# --- value validation ------------------------------------------------------
def validate_values(rows, schema):
    """Validate scraped rows against a per-field schema. Returns a list of issue strings (never raises).

    schema[field] keys (all optional):
      type          : "int" | "float" | "str"
      required      : bool  (field must be present and non-empty)
      max_empty_ratio: float 0..1 (fail if empty fraction exceeds)
      min / max     : numeric bounds (after type coercion)
      allow_uniform : bool  (skip the "all values identical" flag for this field)
      reject_regex  : str   (any value matching = wrong-target, e.g. r"광고|sponsored|\\bAd\\b")
      min_uniform_n : int   (how many rows before a uniform-value flag; default 10)
    """
    issues = []
    if not rows:
        return ["no rows to validate"]
    n = len(rows)
    for field, rule in (schema or {}).items():
        vals = [(_r.get(field) if isinstance(_r, dict) else None) for _r in rows]
        present = [v for v in vals if v is not None and str(v).strip() != ""]
        empty_ratio = 1.0 - (len(present) / n)

        if rule.get("required") and empty_ratio > rule.get("max_empty_ratio", 0.0):
            issues.append(f"[{field}] empty ratio {empty_ratio:.0%} exceeds max {rule.get('max_empty_ratio', 0.0):.0%}")

        t = rule.get("type")
        if t in ("int", "float"):
            bad = 0
            coerced = []
            for v in present:
                try:
                    num = int(str(v).replace(",", "")) if t == "int" else float(str(v).replace(",", ""))
                    coerced.append(num)
                except (ValueError, TypeError):
                    bad += 1
            if bad:
                issues.append(f"[{field}] {bad}/{len(present)} values not coercible to {t}")
            lo, hi = rule.get("min"), rule.get("max")
            if lo is not None:
                out = [c for c in coerced if c < lo]
                if out:
                    issues.append(f"[{field}] {len(out)} values < min {lo} (e.g. {out[:3]})")
            if hi is not None:
                out = [c for c in coerced if c > hi]
                if out:
                    issues.append(f"[{field}] {len(out)} values > max {hi} (e.g. {out[:3]})")

        rej = rule.get("reject_regex")
        if rej:
            rx = re.compile(rej, re.IGNORECASE)
            hits = [v for v in present if rx.search(str(v))]
            if hits:
                issues.append(f"[{field}] wrong-target: {len(hits)} value(s) match reject /{rej}/ (e.g. {hits[:3]})")

        if not rule.get("allow_uniform"):
            min_u = rule.get("min_uniform_n", 10)
            if len(present) >= min_u and len(set(str(v) for v in present)) == 1:
                issues.append(f"[{field}] all {len(present)} values identical ('{present[0]}') — selector may grab a fixed element")

    return issues


if __name__ == "__main__":  # pragma: no cover
    import json, sys
    print(json.dumps(detect_softblock(sys.stdin.read()), ensure_ascii=False, indent=2))
