#!/usr/bin/env python
# refopt - opt-out signal resolver. HARDENED v2 (after Codex 2nd adversarial review, 2026-09-01).
#
# Resolves a URL's crawl / AI-use opt-out posture into a FAIL-VISIBLE state:
#     allowed | disallowed | conditional | unknown
#
# v1 bugs fixed (all reproduced by adversarial probe before this rewrite):
#   - login/challenge HTML returned as robots.txt parsed to 0 rules -> `allowed` (false-allow).
#     FIX: the fetch contract now carries HTTP status + content-type, so a non-200, or a 200 whose
#     content-type is not text/plain-ish, yields `unknown` — never `allowed`. (RFC 9309: robots.txt
#     404 == allow-all; 401/403/5xx == undecidable == unknown.)
#   - `GoodBot/1.0` did not match a `User-agent: GoodBot` group (exact-string match). FIX: match on
#     the crawler PRODUCT TOKEN (RFC 9309 §2.2.1), case-insensitive, most-specific group wins.
#   - `<meta content="noai" name="robots">` was missed (regex assumed name-before-content). FIX: meta
#     is parsed with the stdlib HTMLParser, attribute order/casing independent.
#
# fetch(robots_url) -> RobotsResponse(status:int, content_type:str, text:str) | None   (or raises).
# Use text_response(text) to adapt a plain-text/testing fetcher. stdlib only; network injected.
import re
from collections import namedtuple
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote

ALLOWED = "allowed"
DISALLOWED = "disallowed"
CONDITIONAL = "conditional"
UNKNOWN = "unknown"

RobotsResponse = namedtuple("RobotsResponse", ["status", "content_type", "text"])


def text_response(text, status=200, content_type="text/plain"):
    """Adapt a plain-text robots body (tests / simple callers) to the fetch contract."""
    return RobotsResponse(status=status, content_type=content_type, text=text)


_NOAI_TOKENS = ("noai", "noimageai", "noml")


class _MetaScanner(HTMLParser):
    """Collect <meta name=.. content=..> pairs regardless of attribute order/casing."""
    def __init__(self):
        super().__init__()
        self.metas = []  # list of (name_lower, content_lower)

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        d = {k.lower(): (v or "") for k, v in attrs}
        name = (d.get("name") or d.get("property") or d.get("http-equiv") or "").lower()
        content = (d.get("content") or "").lower()
        if name:
            self.metas.append((name, content))


def _meta_pairs(html):
    p = _MetaScanner()
    try:
        p.feed(html or "")
    except Exception:  # noqa: BLE001 - malformed HTML must never crash a guard
        pass
    return p.metas


def parse_robots(text, user_agent="*"):
    """Parse robots.txt; return {rules, crawl_delay, license_urls} for the group matching user_agent."""
    groups = []
    cur = None
    license_urls = []
    last_was_agent = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, value = line.split(":", 1)
        field = field.strip().lower()
        value = value.strip()
        if field == "license" and value:
            license_urls.append(value)
            continue
        if field == "user-agent":
            if cur is None or not last_was_agent:
                cur = {"agents": [], "rules": [], "crawl_delay": None}
                groups.append(cur)
            cur["agents"].append(value.lower())
            last_was_agent = True
            continue
        last_was_agent = False
        if cur is None:
            continue
        if field in ("allow", "disallow"):
            cur["rules"].append((field, value))
        elif field == "crawl-delay":
            try:
                cur["crawl_delay"] = float(value)
            except ValueError:
                pass

    chosen = _match_group(groups, user_agent)
    return {
        "rules": chosen["rules"] if chosen else [],
        "crawl_delay": chosen["crawl_delay"] if chosen else None,
        "license_urls": license_urls,
    }


def _product_token(user_agent):
    """RFC 9309 product token: text before '/' or whitespace, lowercased."""
    return re.split(r"[/\s]", (user_agent or "").strip(), 1)[0].lower()


def _match_group(groups, user_agent):
    """Most-specific matching group: a group agent token that is a case-insensitive prefix of the
    crawler product token wins by longest token; else the '*' group; else None."""
    product = _product_token(user_agent)
    ua_full = (user_agent or "").lower()
    best = None  # (specificity, group)
    star = None
    for g in groups:
        for tok in g["agents"]:
            if tok == "*":
                if star is None:
                    star = g
                continue
            if product == tok or product.startswith(tok) or ua_full.startswith(tok):
                if best is None or len(tok) > best[0]:
                    best = (len(tok), g)
    if best is not None:
        return best[1]
    return star


def _robots_match(pattern, path):
    if pattern == "":
        return False
    anchored = pattern.endswith("$")
    pat = pattern[:-1] if anchored else pattern
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in pat)
    return re.match("^" + regex + ("$" if anchored else ""), path) is not None


def _path_allowed(rules, path):
    if not path:
        path = "/"
    best = None  # (length, kind)
    for kind, pat in rules:
        if kind == "disallow" and pat == "":
            continue
        if _robots_match(pat, path):
            length = len(pat)
            if best is None or length > best[0] or (length == best[0] and kind == "allow"):
                best = (length, kind)
    return True if best is None else best[1] == "allow"


def scan_noai(html="", headers=None):
    """Return {tdmrep, noai...} signals from meta tags (order/casing independent) or headers."""
    signals = set()
    headers = headers or {}
    metas = dict(_meta_pairs(html))
    if metas.get("tdm-reservation", "").strip() == "1":
        signals.add("tdmrep")
    hdr_lower = {str(k).lower(): str(v).lower() for k, v in headers.items()}
    if hdr_lower.get("tdm-reservation", "").strip() == "1":
        signals.add("tdmrep")
    robots_content = " ".join(v for k, v in metas.items() if k in ("robots", "x-robots-tag"))
    xrobots = hdr_lower.get("x-robots-tag", "")
    joined = robots_content + " " + xrobots
    for tok in _NOAI_TOKENS:
        if re.search(rf"\b{re.escape(tok)}\b", joined):
            signals.add(tok)
    return signals


def _normalize_fetch(resp):
    """Accept a RobotsResponse, a bare str (legacy/testing), or None. Returns RobotsResponse|None."""
    if resp is None:
        return None
    if isinstance(resp, RobotsResponse):
        return resp
    if isinstance(resp, str):
        return text_response(resp)
    # duck-typed object with .status/.text
    status = getattr(resp, "status", getattr(resp, "status_code", 200))
    ctype = getattr(resp, "content_type", getattr(resp, "headers", {}).get("Content-Type", "text/plain")
                    if hasattr(resp, "headers") else "text/plain")
    text = getattr(resp, "text", "")
    return RobotsResponse(status=status, content_type=ctype, text=text)


def resolve_optout(url, fetch, user_agent="*", page_html="", page_headers=None):
    """Resolve opt-out posture. FAIL-VISIBLE: a robots read that cannot be trusted is `unknown`,
    never `allowed`. Returns {status, signals, reasons, license_urls, crawl_delay}."""
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    match_target = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
    path_for_msg = unquote(parts.path) or "/"
    signals, reasons, license_urls = [], [], []
    crawl_delay = None
    robots_ok = False

    try:
        resp = _normalize_fetch(fetch(robots_url))
        if resp is None:
            reasons.append("robots.txt fetch returned no content")
        elif resp.status == 404:
            robots_ok = True  # RFC 9309: no robots.txt == allow-all
            reasons.append("robots.txt 404 -> allow-all")
        elif resp.status in (401, 403) or resp.status >= 500 or resp.status != 200:
            reasons.append(f"robots.txt status {resp.status} -> undecidable")
        elif "html" in (resp.content_type or "").lower():
            reasons.append(f"robots.txt content-type '{resp.content_type}' is not text/plain -> not robots (likely a wall/login page)")
        else:
            parsed = parse_robots(resp.text, user_agent)
            license_urls = list(parsed["license_urls"])
            crawl_delay = parsed["crawl_delay"]
            robots_ok = True
            if not _path_allowed(parsed["rules"], match_target):
                signals.append("robots-disallow")
                reasons.append(f"robots.txt Disallow matches {path_for_msg} for UA {user_agent}")
    except Exception as e:  # noqa: BLE001
        reasons.append(f"robots.txt fetch/parse error: {type(e).__name__}: {e}")

    page_sigs = scan_noai(page_html, page_headers)
    if "tdmrep" in page_sigs:
        signals.append("tdmrep")
        reasons.append("TDM reservation present")
    noai_hit = sorted(s for s in page_sigs if s in _NOAI_TOKENS)
    if noai_hit:
        signals.append("noai-meta")
        reasons.append(f"noai-family: {', '.join(noai_hit)}")
    if license_urls:
        signals.append("rsl-license")
        reasons.append(f"RSL License directive -> external XML (fetch to read terms): {', '.join(license_urls)}")

    if "robots-disallow" in signals:
        status = DISALLOWED
    elif not robots_ok:
        status = UNKNOWN
    elif any(s in signals for s in ("rsl-license", "tdmrep", "noai-meta")):
        status = CONDITIONAL
    else:
        status = ALLOWED
        reasons.append("robots readable, path allowed, no license/TDM/noai signal")

    return {"status": status, "signals": signals, "reasons": reasons,
            "license_urls": license_urls, "crawl_delay": crawl_delay}


if __name__ == "__main__":  # pragma: no cover
    import sys, json, urllib.request

    def _live_fetch(u):
        req = urllib.request.Request(u, headers={"User-Agent": "refopt-smoke"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                ct = r.headers.get("Content-Type", "text/plain")
                return RobotsResponse(status=r.status, content_type=ct, text=r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            return RobotsResponse(status=e.code, content_type="", text="")

    target = sys.argv[1] if len(sys.argv) > 1 else "https://example.com/"
    # judgment UA and request UA are the SAME token now:
    print(json.dumps(resolve_optout(target, _live_fetch, user_agent="refopt-smoke"), ensure_ascii=False, indent=2))
