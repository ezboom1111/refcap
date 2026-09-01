#!/usr/bin/env python
# refopt - opt-out signal resolver for lawful gathering (leesearch P1 code contract).
#
# Resolves a URL's crawl / AI-use opt-out posture from the signals a polite gatherer must
# respect BEFORE fetching content, into a FAIL-VISIBLE state:
#
#     allowed | disallowed | conditional | unknown
#
# Design invariants (Codex adversarial review 2026-09-01):
#   1. FAIL-VISIBLE, never fail-silent-allow. A fetch/parse failure is `unknown`, NOT `allowed`.
#      The competitor's check_robots() returned allowed=True on error (fail-open) — we don't.
#   2. Signals combine, they don't collapse to one. A page can be robots-allowed yet carry an
#      RSL license (=conditional) or a TDM reservation (=conditional). Disallow wins over all.
#   3. RSL is detected, not interpreted here. RSL adds a single `License: <absoluteURL>` line to
#      robots.txt pointing to an EXTERNAL XML that holds the real terms (rslstandard.org, verified
#      2026-09-01 -> facts.registry F-003). We surface license_urls; parsing that XML's vocabulary
#      (ai-train/ai-input/...) is deferred until the spec is read (do NOT invent it here).
#   4. llms.txt is NON-STANDARD and is NOT a legal opt-out. We never treat it as one.
#
# stdlib only. Network is INJECTED (a `fetch` callable) so tests are hermetic (no live HTTP).
import re
from urllib.parse import urlsplit, unquote

# --- status constants -------------------------------------------------------
ALLOWED = "allowed"
DISALLOWED = "disallowed"
CONDITIONAL = "conditional"
UNKNOWN = "unknown"

# noai-family tokens seen in <meta name="robots"> / X-Robots-Tag (data, not a legal claim on their own)
_NOAI_TOKENS = ("noai", "noimageai", "noml")
_META_ROBOTS_RE = re.compile(
    r"""<meta\b[^>]*\bname\s*=\s*["']?(?:robots|x-robots-tag)["']?[^>]*\bcontent\s*=\s*["']([^"']*)["']""",
    re.IGNORECASE,
)
# TDMRep: <meta name="tdm-reservation" content="1"> (W3C TDM Reservation Protocol)
_META_TDM_RE = re.compile(
    r"""<meta\b[^>]*\bname\s*=\s*["']?tdm-reservation["']?[^>]*\bcontent\s*=\s*["']?\s*1\s*["']?""",
    re.IGNORECASE,
)


def parse_robots(text, user_agent="*"):
    """Parse robots.txt into the record that applies to `user_agent`.

    Returns {rules: [(kind, path)], crawl_delay: float|None, license_urls: [str]}.
    `rules` preserves order; entries are ("allow"|"disallow", path). RSL `License:` directives
    are collected globally (they are not UA-scoped in the spec's robots.txt integration).
    Longest-match with Allow-over-Disallow is applied by `_path_allowed`.
    """
    ua = user_agent.lower()
    groups = []           # list of {agents:set, rules:[...], crawl_delay}
    cur = None
    license_urls = []
    last_line_was_agent = False

    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if ":" not in line:
            continue
        field, value = line.split(":", 1)
        field = field.strip().lower()
        value = value.strip()

        if field == "license" and value:
            # RSL: License: <absoluteURL> -> external XML. Global, not UA-scoped.
            license_urls.append(value)
            continue
        if field == "user-agent":
            if cur is None or not last_line_was_agent:
                cur = {"agents": set(), "rules": [], "crawl_delay": None}
                groups.append(cur)
            cur["agents"].add(value.lower())
            last_line_was_agent = True
            continue
        last_line_was_agent = False
        if cur is None:
            continue
        if field in ("allow", "disallow"):
            cur["rules"].append((field, value))
        elif field == "crawl-delay":
            try:
                cur["crawl_delay"] = float(value)
            except ValueError:
                pass

    # pick the most specific matching group: exact UA match beats "*"; else "*".
    chosen = None
    for g in groups:
        if ua in g["agents"]:
            chosen = g
            break
    if chosen is None:
        for g in groups:
            if "*" in g["agents"]:
                chosen = g
                break
    rules = chosen["rules"] if chosen else []
    crawl_delay = chosen["crawl_delay"] if chosen else None
    return {"rules": rules, "crawl_delay": crawl_delay, "license_urls": license_urls}


def _path_allowed(rules, path):
    """robots.txt precedence: the longest matching rule wins; Allow beats Disallow on a tie.
    Empty Disallow ('Disallow:') means allow-all for that group. Returns True/False."""
    if not path:
        path = "/"
    best = None  # (length, kind)
    for kind, pat in rules:
        if kind == "disallow" and pat == "":
            continue  # empty disallow = no restriction
        if _robots_match(pat, path):
            length = len(pat)
            if best is None or length > best[0] or (length == best[0] and kind == "allow"):
                best = (length, kind)
    if best is None:
        return True
    return best[1] == "allow"


def _robots_match(pattern, path):
    """robots.txt path match with * wildcard and $ end-anchor (Google/RFC 9309 style)."""
    if pattern == "":
        return False
    anchored_end = pattern.endswith("$")
    pat = pattern[:-1] if anchored_end else pattern
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in pat)
    regex = "^" + regex + ("$" if anchored_end else "")
    return re.match(regex, path) is not None


def scan_noai(html="", headers=None):
    """Return the set of noai-family / TDM signals present in meta tags or headers.
    Pure detection — no legal conclusion here (resolve_optout combines them)."""
    signals = set()
    headers = headers or {}
    hay_headers = " ".join(f"{k}: {v}" for k, v in headers.items()).lower()
    html_l = html or ""

    # TDMRep: meta or tdm-reservation header
    if _META_TDM_RE.search(html_l) or "tdm-reservation: 1" in hay_headers or "tdm-reservation:1" in hay_headers:
        signals.add("tdmrep")
    # noai-family in <meta robots> / X-Robots-Tag content
    contents = [m.lower() for m in _META_ROBOTS_RE.findall(html_l)]
    xrobots = headers.get("X-Robots-Tag") or headers.get("x-robots-tag") or ""
    contents.append(str(xrobots).lower())
    joined = " ".join(contents)
    for tok in _NOAI_TOKENS:
        if re.search(rf"\b{re.escape(tok)}\b", joined):
            signals.add(tok)
    return signals


def resolve_optout(url, fetch, user_agent="*", page_html="", page_headers=None):
    """Resolve the opt-out posture for `url`.

    `fetch(robots_url) -> str` returns robots.txt text, or raises / returns None on failure.
    `page_html` / `page_headers` are OPTIONAL already-captured page signals (meta/headers); pass
    them when known so a page-level TDM/noai reservation is honored even if robots is clean.

    Returns {status, signals: [...], reasons: [...], license_urls: [...], crawl_delay}.
    FAIL-VISIBLE: any robots fetch/parse failure yields status `unknown` (never `allowed`).
    """
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    path = unquote(parts.path) or "/"
    # robots.txt matching is on path+query (RFC 9309): a `$` anchor must sit at the true
    # end of the request target, so `/*.pdf$` must NOT match `/a/b.pdf?x=1`.
    match_target = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
    signals = []
    reasons = []
    license_urls = []
    crawl_delay = None

    robots_ok = False
    try:
        text = fetch(robots_url)
        if text is None:
            reasons.append("robots.txt fetch returned no content")
        else:
            parsed = parse_robots(text, user_agent)
            license_urls = list(parsed["license_urls"])
            crawl_delay = parsed["crawl_delay"]
            robots_ok = True
            if not _path_allowed(parsed["rules"], match_target):
                signals.append("robots-disallow")
                reasons.append(f"robots.txt Disallow matches {path} for UA {user_agent}")
    except Exception as e:  # noqa: BLE001 - fetch may raise anything; treat all as unknown
        reasons.append(f"robots.txt fetch/parse error: {type(e).__name__}: {e}")

    # page-level reservations (independent of robots)
    page_sigs = scan_noai(page_html, page_headers)
    if "tdmrep" in page_sigs:
        signals.append("tdmrep")
        reasons.append("TDM reservation present (tdm-reservation)")
    noai_hit = sorted(s for s in page_sigs if s in _NOAI_TOKENS)
    if noai_hit:
        signals.append("noai-meta")
        reasons.append(f"noai-family meta/header: {', '.join(noai_hit)}")
    if license_urls:
        signals.append("rsl-license")
        reasons.append(f"RSL License directive -> external XML (fetch to read terms): {', '.join(license_urls)}")

    # combine into fail-visible status
    if "robots-disallow" in signals:
        status = DISALLOWED
    elif not robots_ok:
        status = UNKNOWN  # could not read robots -> not 'allowed'
    elif any(s in signals for s in ("rsl-license", "tdmrep", "noai-meta")):
        status = CONDITIONAL
    else:
        status = ALLOWED
        reasons.append("robots readable, path allowed, no license/TDM/noai signal")

    return {
        "status": status,
        "signals": signals,
        "reasons": reasons,
        "license_urls": license_urls,
        "crawl_delay": crawl_delay,
    }


if __name__ == "__main__":  # pragma: no cover - tiny manual smoke
    import sys
    import urllib.request

    def _live_fetch(u):
        req = urllib.request.Request(u, headers={"User-Agent": "refopt-smoke"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode("utf-8", "replace")

    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com/"
    import json
    print(json.dumps(resolve_optout(target, _live_fetch), ensure_ascii=False, indent=2))
