#!/usr/bin/env python
# refledger - the research-agent SPINE. NOT a brain: the brain is the AGENT (Claude Code / hermes).
# This is the thin, disk-bound shared working-memory + the entrance to a deterministic evidence gate.
#
# DESIGN PHILOSOPHY (verified by 2 red-team rounds vs real refcap/farm/hermes code):
#   1. Don't code the brain - the agent decides WHAT to investigate. Code persists NOUNS (artifact,
#      finding, frontier-entry) and only judges whether evidence is real (exists+unchanged); the agent
#      performs VERBS (choose, ask, stop, adapt).  Litmus: "does this decision change per topic?" -> agent.
#   2. ingest() is a DEPTH-0 router (extension/scheme only). NEVER content-based branching/scoring/
#      thresholds (that path produced the gyeongju degeneracy false-positive). Source strategy = prose runbook.
#   3. Differentiator is NOT a feature (hermes can bolt on a ledger) but an ARCHITECTURAL STANCE: small TCB,
#      neutrality (refledger imports farm 0), and the upstream coverage_gate's pre-capture honesty.
#   4. cite-or-fail proves anchoring (quote exists in bytes), NOT correctness. Fabrication-at-capture is the
#      open roof; the only real defense is the upstream coverage_gate label, which we PRESERVE (ledger.note /
#      quality_label) and WARN on, but never silently bless.
#
# stdlib only. farm import 0 (neutrality). Korean-path safe (ascii dir leaf + utf-8 + ensure_ascii=False).
import os, sys, json, re, hashlib, datetime, argparse, subprocess, urllib.request, urllib.parse, ipaddress, socket, threading, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
# capture-quality labels that make a citation UNTRUSTWORTHY -> verify warns + farm_plan tags [WARN].
# audio side comes from refrecord.coverage_gate; web side from web_quality() below. Both label a MEASURED
# capture FAILURE (no-speech / bot-wall / empty), NOT a content-type judgement (that stays the agent's).
BAD_QUALITY = {"NO_SPEECH_OR_MASKED", "SILENT", "COVERAGE_GAP", "LOW_CONFIDENCE", "DEGENERATE",
               "BOT_WALL", "JS_WALL", "LOGIN_WALL", "PAYWALL", "EMPTY", "HTTP_ERROR",
               "API_ERROR", "MALFORMED", "EXTRACT_FAILED"}
_BOT_MARKERS = ("captcha", "cloudflare", "unusual traffic", "are you a robot", "verify you are human",
                "checking your browser", "automated requests")   # genuine bot challenge -> do NOT bypass (ToS)
_JS_MARKERS = ("enable javascript", "javascript is required", "requires javascript",   # SPA shell -> ESCALATE to a
               "javascript to run this app")   # browser render (login-free, ToS-clean, recoverable); NOT a bot wall
_LOGIN_MARKERS = ("sign in to continue", "log in to view", "please log in", "members only",
                  "로그인 후", "로그인이 필요", "login required")
_PAYWALL_MARKERS = ("subscribe to read", "subscribers only", "for subscribers", "유료 회원", "구독해야")
EVIDENCE_KIND = {"html": "page_html", "json": "structured_data", "image": "frame_screenshot",
                 "ocr": "ocr_text", "text": "structured_data", "transcript": "transcript_cue",
                 "video": "transcript_cue"}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_LOCK = threading.Lock()   # serializes ledger writes within a process (the realistic 'agent parallel-calls' race)


@contextlib.contextmanager
def _file_lock(rdir):
    """Best-effort cross-PROCESS advisory lock (OS-released on death -> no stale deadlock). Pairs with the
    in-process _LOCK so concurrent ledger_append (op-03 TOCTOU race) can't double-register a logical_key."""
    f = open(os.path.join(rdir, ".ledger.lock"), "a+")
    held = False
    try:
        try:
            import fcntl; fcntl.flock(f.fileno(), fcntl.LOCK_EX); held = True
        except ImportError:
            try:
                import msvcrt; f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1); held = True
            except Exception:
                pass
        yield
    finally:
        if held:
            try:
                import fcntl; fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except ImportError:
                try:
                    import msvcrt; f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
        f.close()


_DENY = [os.environ.get("SystemRoot", r"C:\Windows"), r"C:\Program Files", r"C:\Program Files (x86)",
         "/etc", "/sys", "/proc", "/boot", "/root", "/dev"]


def _path_ok(p):
    """Refuse registering a path that resolves into a system directory (path-traversal / sensitive-file
    fingerprinting into a bundle). adversarial-05. Normal artifact paths (refs/, research/) pass."""
    try:
        ap = os.path.normcase(os.path.abspath(p))
    except Exception:
        return False
    for d in _DENY:
        try:
            dn = os.path.normcase(os.path.abspath(d))
        except Exception:
            continue
        if ap == dn or ap.startswith(dn + os.sep):
            return False
    return True


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str, buf: int = 65536) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(buf), b""):
            h.update(chunk)
    return h.hexdigest()


# ---- canonical transcript (FIX1: real WebVTT + segments-only hash; FIX3: run-metadata never hashed) ----
_LINE = re.compile(r"^\[\s*([\d.]+)-\s*([\d.]+)\]\s*(.*)$")
_GATE = re.compile(r"gate=([A-Z_]+)")
_VTT_TIMING = re.compile(r"(\d\d):(\d\d):(\d\d)[.,](\d+)\s*-->\s*(\d\d):(\d\d):(\d\d)[.,](\d+)")


def _parse_vtt_srt(text):
    """Parse a REAL WebVTT ('00:00:00.000 -->') or SRT ('00:00:03,000' + index) into segments.
    Scenario QA found parse_timed only knew refcap's '[ s- e]' format, so real .vtt/.srt -> [] -> UNKNOWN."""
    def secs(h, m, s, frac):
        return int(h) * 3600 + int(m) * 60 + int(s) + (int(frac) / (10 ** len(frac)) if frac else 0)
    segs = []
    for block in re.split(r"\n\s*\n", text):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        ti = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if ti is None:
            continue
        m = _VTT_TIMING.search(lines[ti])
        if not m:
            continue
        start = secs(*m.group(1, 2, 3, 4)); end = secs(*m.group(5, 6, 7, 8))
        txt = " ".join(lines[ti + 1:]).strip()
        if txt:
            segs.append({"start": round(start, 2), "end": round(end, 2), "text": txt})
    return segs


def parse_timed(text_or_path):
    """transcript -> ([{start,end,text}], quality_label). Handles refcap's '[ s- e]' format AND real
    WebVTT/SRT. Strips header/timestamp noise so the VO text alone is registered/anchored. A '# ... FAILED'
    extract header -> EXTRACT_FAILED (a bad capture, so verify warns instead of silently UNKNOWN)."""
    text = text_or_path
    if "\n" not in text_or_path and os.path.exists(text_or_path):
        with open(text_or_path, encoding="utf-8") as _fh:
            text = _fh.read()
    if "-->" in text:                                   # a real WebVTT/SRT, not refcap's bracket format
        return _parse_vtt_srt(text), "UNKNOWN"
    quality = "UNKNOWN"
    segs = []
    for line in text.splitlines():
        if line.startswith("#"):
            if "FAILED" in line:
                quality = "EXTRACT_FAILED"              # corrupt/undecodable capture -> BAD_QUALITY
            m = _GATE.search(line)
            if m:
                quality = m.group(1)
            continue
        m = _LINE.match(line)
        if m:
            segs.append({"start": round(float(m.group(1)), 2),
                         "end": round(float(m.group(2)), 2), "text": m.group(3).strip()})
    return segs, quality


def to_vtt(segs) -> str:
    def ts(s):
        h = int(s // 3600); m = int((s % 3600) // 60); sec = s % 60
        return f"{h:02d}:{m:02d}:{sec:06.3f}"
    out = ["WEBVTT", ""]
    for sg in segs:
        out.append(f"{ts(sg['start'])} --> {ts(sg['end'])}")
        out.append(sg["text"]); out.append("")
    return "\n".join(out)


def canonical_json(segs) -> str:
    # deterministic identity: segments only, rounded, no run metadata -> same VO => same hash across runs
    return json.dumps([{"start": s["start"], "end": s["end"], "text": s["text"]} for s in segs],
                      ensure_ascii=False)


def web_quality(text, http_status=None, min_chars=200, wall_chars=1500):
    """Pre-capture quality label for a fetched page/text — the web analogue of refrecord.coverage_gate.
    Detects CAPTURE FAILURE (the agent fetched a wall/empty/error, not real content) so a finding citing
    such a source is WARNED (redteam's 'real next high-value': cite-or-fail can't stop fabrication, but
    labeling a bad capture upstream reduces it). CRITICAL (measured live, same lesson as the gyeongju
    degeneracy false-positive): a wall is SPARSE - a 1.2MB real article that merely MENTIONS 'captcha'
    once is NOT a bot wall. So wall labels fire ONLY when visible content is below wall_chars; content-rich
    pages are OK regardless of a passing marker. Rule-based on sparsity + failure signatures, never a
    content-type classifier."""
    if http_status is not None and int(http_status) >= 400:
        return "HTTP_ERROR"
    low = text.lower()
    visible = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()  # strip html tags for length
    if len(visible) >= wall_chars:
        return "OK"                                                       # content-rich -> real content
    # sparse: a wall / empty page. classify by failure signature.
    if any(m in low for m in _BOT_MARKERS):
        return "BOT_WALL"
    if any(m in low for m in _JS_MARKERS):
        return "JS_WALL"          # sparse SPA shell -> escalate to a browser render (login-free); distinct from a bot challenge
    if any(m in low for m in _LOGIN_MARKERS):
        return "LOGIN_WALL"
    if any(m in low for m in _PAYWALL_MARKERS):
        return "PAYWALL"
    if len(visible) < min_chars:
        return "EMPTY"
    return "OK"                                                           # short but real, no failure marker


def json_quality(text, http_status=None):
    """Quality label for a fetched JSON/structured body — the json analogue of web_quality (scenario QA
    found the json ingest branch hardcoded 'OK', so error-envelopes / malformed / rate-limit JSON were
    sealed as OK). Detects MALFORMED / API_ERROR / EMPTY so verify warns on a citation to a bad capture."""
    if http_status is not None and int(http_status) >= 400:
        return "HTTP_ERROR"
    try:
        obj = json.loads(text)
    except Exception:
        return "MALFORMED"
    low = text.lower()
    if isinstance(obj, dict) and any(k in obj for k in ("error", "errors")):
        return "API_ERROR"
    if any(m in low for m in ("rate limit", "rate_limit", "unusual traffic", "quota exceeded", "captcha")):
        return "API_ERROR"
    if obj in ([], {}, None, ""):
        return "EMPTY"
    return "OK"


# ---- research dir + ledger/frontier (2 append-only files; findings folded into ledger via kind) ----
def open_research(goal: str, base: str = None):
    base = base or os.path.join(HERE, "research")
    slug = "r_" + hashlib.sha256(goal.encode("utf-8")).hexdigest()[:10]   # ascii leaf (Windows/farm safe)
    rdir = os.path.join(base, slug)
    os.makedirs(rdir, exist_ok=True)
    meta = os.path.join(rdir, "meta.json")
    if not os.path.exists(meta):
        with open(meta, "w", encoding="utf-8") as _fh:
            json.dump({"goal": goal, "slug": slug, "created": _now()}, _fh, ensure_ascii=False, indent=2)
    return rdir


def _read_jsonl(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as fh:
        for l in fh:
            l = l.strip()
            if not l:
                continue
            try:
                rows.append(json.loads(l))
            except json.JSONDecodeError:
                continue   # tolerate a truncated/partial last line from a crash mid-write (else it bricks ALL ops)
    return rows


def _append_jsonl(path, row):
    # write the COMPLETE line in one call + fsync -> minimizes the partial-line window on crash/ENOSPC
    # (and _read_jsonl tolerates any partial leftover). op-10.
    line = json.dumps(row, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass


_KEYCACHE = {}   # rdir -> (ledger_size_bytes, set_of_logical_keys). MEASURED: re-reading the whole ledger
                 # for the dedupe check on every append is O(N^2) (1000 appends = 17.6s); the cache makes
                 # sequential appends O(1). Invalidated by ledger byte-size change (catches cross-process writes).


def _logical_keys(rdir, path):
    try:
        size = os.path.getsize(path)
    except OSError:
        return set()
    c = _KEYCACHE.get(rdir)
    if c and c[0] == size:
        return c[1]
    keys = {r.get("logical_key") for r in _read_jsonl(path) if r.get("kind") == "artifact"}
    _KEYCACHE[rdir] = (size, keys)
    return keys


def ledger_append(rdir, **row):
    """Append an artifact. Dedupe by LOGICAL key (source|method), NOT content sha256 (FIX3: derived
    artifacts like whisper transcripts are non-deterministic, so same clip => different bytes).
    Read-check-append under a lock (op-03 race) + a size-invalidated key cache (op-09 O(N^2) -> O(1))."""
    path = os.path.join(rdir, "ledger.jsonl")
    logical = row.get("logical_key") or f"{row.get('source')}|{row.get('method')}"
    with _LOCK, _file_lock(rdir):
        if logical in _logical_keys(rdir, path):
            for r in _read_jsonl(path):    # dedupe HIT (rare) -> read once to return the existing row
                if r.get("kind") == "artifact" and r.get("logical_key") == logical:
                    return r
        aid = "a_" + sha256_bytes(logical.encode("utf-8"))[:16]   # STABLE id (survives re-ingest)
        art = {"kind": "artifact", "artifact_id": aid, "logical_key": logical, "ts": _now(), **row}
        _append_jsonl(path, art)
        c = _KEYCACHE.get(rdir)            # keep the cache warm (avoid a re-read next append)
        if c:
            c[1].add(logical)
            try:
                _KEYCACHE[rdir] = (os.path.getsize(path), c[1])
            except OSError:
                _KEYCACHE.pop(rdir, None)
        return art


def record_finding(rdir, text, label, artifact_id, quote="", locator="", confidence="med", corroborated_by=None, conclusion_id="", hypothesis_id="", polarity=""):
    """Local cite-or-fail: a finding MUST anchor to a registered artifact, else refuse.
    `quote` = the VERBATIM span from the artifact that grounds the claim (NOT the claim text - the farm
    gate rejects a claim whose anchor text is not literally in the cited bytes; learned e2e). `locator` =
    where (cue=N | char=a..b | frame=<file>) for cue/frame anchors that need no quote. `corroborated_by` =
    artifact_ids this finding claims to be CORROBORATED by (Rank-3: verify mechanically checks their sources
    span >=2 distinct hosts, so a same-domain '2 sources' fake-independence is surfaced)."""
    path = os.path.join(rdir, "ledger.jsonl")
    ids = {r["artifact_id"] for r in _read_jsonl(path) if r.get("kind") == "artifact"}
    if artifact_id not in ids:
        raise ValueError(f"dangling anchor: artifact_id {artifact_id!r} not in ledger")
    cb = list(corroborated_by or [])
    for aid in cb:
        if aid not in ids:
            raise ValueError(f"dangling corroboration: artifact_id {aid!r} not in ledger")
    if polarity not in ("", "confirms", "disconfirms", "neutral"):   # Rank-7: a signal's stance toward a thesis
        raise ValueError(f"polarity must be confirms/disconfirms/neutral, got {polarity!r}")
    f = {"kind": "finding", "artifact_id": artifact_id, "text": text, "label": label, "quote": quote,
         "locator": locator, "confidence": confidence, "corroborated_by": cb, "conclusion_id": conclusion_id,
         "hypothesis_id": hypothesis_id, "polarity": polarity, "ts": _now()}
    _append_jsonl(path, f)
    return f


def frontier_open(rdir, item, kind="question", reason=""):
    _append_jsonl(os.path.join(rdir, "frontier.jsonl"),
                  {"op": "open", "item": item, "kind": kind, "reason": reason, "ts": _now()})


def frontier_close(rdir, item, reason=""):
    _append_jsonl(os.path.join(rdir, "frontier.jsonl"),
                  {"op": "close", "item": item, "reason": reason, "ts": _now()})


def frontier_note(rdir, item, reason=""):
    _append_jsonl(os.path.join(rdir, "frontier.jsonl"),
                  {"op": "note", "item": item, "reason": reason, "ts": _now()})


def frontier_visit(rdir, item, reason=""):
    # record a source as visited (for the agent's dedupe-of-attention). frontier_state already reduces
    # 'visit' -> visited; scenario QA found the writer was missing (visited was a permanently-empty dead path).
    _append_jsonl(os.path.join(rdir, "frontier.jsonl"),
                  {"op": "visit", "item": item, "reason": reason, "ts": _now()})


def frontier_state(rdir):
    """Reduce the event log -> state. Code only persists+reduces; it NEVER prioritizes/pops (that's the
    agent's judgement - a priority function would be the brittle threshold-tree the thesis forbids)."""
    open_, closed, visited = [], [], []
    for e in _read_jsonl(os.path.join(rdir, "frontier.jsonl")):
        it = e["item"]
        if e["op"] == "open" and it not in open_:
            open_.append(it)
        elif e["op"] == "close":
            if it in open_:
                open_.remove(it)
            if it not in closed:
                closed.append(it)
        elif e["op"] == "visit" and it not in visited:
            visited.append(it)
    return {"open": open_, "closed": closed, "visited": visited}


# ---- prediction-outcome calibration (Rank-1 of the insight-accuracy R&D) ---------------------------
# Layer-(3) INSIGHT accuracy (do the CONCLUSIONS match reality) needs a NON-CIRCULAR oracle: a falsifiable
# forecast scored against a FUTURE real-world outcome the model cannot author at forecast time (unlike a
# self-graded fixture, which Goodharts, or an LLM-judge, which is circular when judge==researcher). Code
# only persists the forecast/outcome NOUNS + does arithmetic (Brier, reliability) = no threshold, no content
# branch, no judge (so it does NOT reintroduce the gyeongju threshold-tree). The AGENT forecasts and
# adjudicates the outcome (VERBS). Sharpening (adversarial-verify): a resolution may cite an OBSERVED+anchored
# evidence artifact so the hit/miss is itself auditable BYTES; calib then splits Brier(all) vs Brier(anchored)
# to surface self-serving unanchored grades.
_OUTCOMES = {"hit", "miss", "unresolved"}


def predict(rdir, claim, confidence, resolve_by, operator="", anchor_artifact_id="", conclusion_id="", hypothesis_id=""):
    """Record a FALSIFIABLE forecast. confidence in [0,1] = stated P(claim is true). resolve_by = the date
    by which reality should settle it. operator = the falsifiable condition (e.g. peaks_within / price_lte /
    count_gte). anchor_artifact_id (optional) = the basis evidence at forecast time (validated vs the ledger
    if given). Append-only: a genuine re-forecast (same claim, DIFFERENT resolve_by) is preserved as a new row.
    An accidental near-IDENTICAL re-submit (same claim+resolve_by+hypothesis) is FLAGGED via near_duplicate_of
    (advisory) but NOT dropped — so "predict N" can't silently inflate (the real hidden-gem-natl bug)."""
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        raise ValueError(f"confidence must be a number in [0,1], got {confidence!r}")
    if not (0.0 <= c <= 1.0):
        raise ValueError(f"confidence must be in [0,1], got {c}")
    if anchor_artifact_id:
        ids = {r["artifact_id"] for r in _read_jsonl(os.path.join(rdir, "ledger.jsonl")) if r.get("kind") == "artifact"}
        if anchor_artifact_id not in ids:
            raise ValueError(f"dangling anchor: artifact_id {anchor_artifact_id!r} not in ledger")
    now = _now()
    # collision-proof id via urandom (NOT a pre-read filesize, which TOCTOU-races under concurrent predicts).
    # predictions stay append-only, so the id need not be stable/derived (unlike artifact ids).
    pid = "p_" + sha256_bytes(f"{claim}|{operator}|{resolve_by}|{now}|{os.urandom(8).hex()}".encode("utf-8"))[:12]
    # ADVISORY near-duplicate flag: a same-deadline + same-hypothesis re-submit whose claim is near-IDENTICAL to an
    # earlier one (3-gram Jaccard >= cutoff). FLAG only — the row is still appended (a different resolve_by => genuine
    # re-forecast => not flagged). Surfaces the inflation that made hidden-gem-natl report "predict 3" for a true 2.
    dup_of = ""
    sc = _shingles(claim)
    for r in _read_jsonl(os.path.join(rdir, "predictions.jsonl")):
        if (r.get("kind") == "prediction" and r.get("resolve_by") == resolve_by
                and r.get("hypothesis_id", "") == hypothesis_id
                and _jaccard(sc, _shingles(r.get("claim", ""))) >= _NEAR_DUP_SIM):
            dup_of = r["prediction_id"]; break
    row = {"kind": "prediction", "prediction_id": pid, "claim": claim, "stated_confidence": c,
           "resolve_by": resolve_by, "operator": operator, "anchor_artifact_id": anchor_artifact_id,
           "conclusion_id": conclusion_id, "hypothesis_id": hypothesis_id, "near_duplicate_of": dup_of,
           "created": now}   # join keys: grade_validity + alpha thesis
    _append_jsonl(os.path.join(rdir, "predictions.jsonl"), row)
    return row


def resolve(rdir, prediction_id, outcome, evidence_artifact=""):
    """Close a prediction with a real-world OUTCOME (hit/miss/unresolved). Latest resolution per id wins.
    evidence_artifact (optional) = a registered artifact that an OBSERVED finding anchors to -> makes the
    hit/miss auditable BYTES, not the agent's bare word (anchored=True). The agent still adjudicates."""
    if outcome not in _OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(_OUTCOMES)}, got {outcome!r}")
    ppath = os.path.join(rdir, "predictions.jsonl")
    if prediction_id not in {r["prediction_id"] for r in _read_jsonl(ppath) if r.get("kind") == "prediction"}:
        raise ValueError(f"unknown prediction_id {prediction_id!r}")
    anchored = False
    if evidence_artifact:
        rows = _read_jsonl(os.path.join(rdir, "ledger.jsonl"))
        if evidence_artifact not in {r["artifact_id"] for r in rows if r.get("kind") == "artifact"}:
            raise ValueError(f"evidence artifact {evidence_artifact!r} not in ledger")
        if not any(r.get("kind") == "finding" and r.get("artifact_id") == evidence_artifact
                   and r.get("label") == "OBSERVED" for r in rows):
            raise ValueError(f"evidence artifact {evidence_artifact!r} has no OBSERVED finding to ground the resolution")
        anchored = True
    row = {"kind": "resolution", "prediction_id": prediction_id, "outcome": outcome,
           "evidence_artifact": evidence_artifact, "anchored": anchored, "ts": _now()}
    _append_jsonl(ppath, row)
    return row


def calibration(rdir):
    """Reduce predictions.jsonl -> Brier score + 5-bucket reliability table + resolution_rate. REPORTS, never
    judges (the agent reads it). Non-circular: the oracle is a future outcome the model couldn't author.
    Honest scope: scores only the falsifiable forecast-shaped slice of insight; descriptive synthesis is not
    measured here, and it is meaningful only after N>=~20 resolved."""
    rows = _read_jsonl(os.path.join(rdir, "predictions.jsonl"))
    preds = {r["prediction_id"]: r for r in rows if r.get("kind") == "prediction"}
    latest = {}                                  # prediction_id -> latest resolution (append-ordered; last wins)
    for r in rows:
        if r.get("kind") == "resolution" and r.get("prediction_id") in preds:
            latest[r["prediction_id"]] = r
    resolved = []                                # (p, y, anchored) over hit/miss only
    n_premature = 0                              # resolved at/before the forecast was made = not a future oracle (toy/smoke)
    for pid, p in preds.items():
        res = latest.get(pid)
        if not res or res.get("outcome") not in ("hit", "miss"):
            continue
        if res.get("ts", "") <= p.get("created", ""):   # instant resolution (ts<=created) = suspect non-oracle (toy/smoke);
            n_premature += 1                            # ADVISORY only - NOT excluded from Brier. Code reports the mechanical
        y = 1.0 if res["outcome"] == "hit" else 0.0     # fact; the AGENT discounts it when judging readiness (don't-code-the-brain).
        resolved.append((float(p.get("stated_confidence", 0.0)), y, bool(res.get("anchored"))))

    def _brier(rs):
        return round(sum((p - y) ** 2 for p, y, _ in rs) / len(rs), 4) if rs else None

    buckets = []
    for b in range(5):
        inb = [r for r in resolved if min(int(r[0] * 5), 4) == b]
        if inb:
            mc = sum(r[0] for r in inb) / len(inb)
            hr = sum(r[1] for r in inb) / len(inb)
            rng = f"[{b / 5.0:.1f},{(b + 1) / 5.0:.1f}{']' if b == 4 else ')'}"
            buckets.append({"range": rng, "n": len(inb), "mean_confidence": round(mc, 3),
                            "hit_rate": round(hr, 3), "gap": round(abs(mc - hr), 3)})
    ba, banch = _brier(resolved), _brier([r for r in resolved if r[2]])
    n = len(preds)
    return {"n_predictions": n, "n_distinct_predictions": _distinct_pred_count(preds.values()),
            "n_resolved": len(resolved), "n_premature": n_premature,
            "resolution_rate": round(len(resolved) / n, 3) if n else 0.0,
            "brier_all": ba, "brier_anchored": banch,
            "brier_divergence": (round(ba - banch, 4) if (ba is not None and banch is not None) else None),
            "reliability_buckets": buckets,
            "worst_bucket_gap": max((x["gap"] for x in buckets), default=None)}


# ---- layer-1/3 advisory analysis (Rank 2/3 of the insight-accuracy R&D) ----------------------------
def _levenshtein(a, b):
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _cer(hyp, ref):
    ref = ref or ""
    return round(_levenshtein(hyp or "", ref) / len(ref), 4) if ref else 0.0


def measure_capture_error(rdir, artifact_id, hyp_span, truth_span):
    """Rank-2: put a NUMBER on layer-1 capture fidelity = CER(machine span vs a short HUMAN-keyed truth span).
    cite-or-fail proves a quote EXISTS in bytes; this measures whether the bytes are CORRECT - the open roof
    cite-or-fail provably cannot touch. Code computes+appends the number; the AGENT (runbook) decides if it is
    material and caps the finding to INFERRED (NO hardcoded ceiling = no threshold-tree). CER only (char-level;
    word segmentation is language-specific)."""
    if not (truth_span or "").strip():
        raise ValueError("truth_span must be non-empty; CER is undefined without a human reference")
    ids = {r["artifact_id"] for r in _read_jsonl(os.path.join(rdir, "ledger.jsonl")) if r.get("kind") == "artifact"}
    if artifact_id not in ids:
        raise ValueError(f"unknown artifact_id {artifact_id!r}")
    row = {"kind": "capture_measure", "artifact_id": artifact_id, "cer": _cer(hyp_span, truth_span), "ts": _now()}
    _append_jsonl(os.path.join(rdir, "ledger.jsonl"), row)
    return row


# Curated common-traffic multi-label suffixes ACROSS REGIONS (not one country). A snapshot + NOT exhaustive: the
# canonical source is the Public Suffix List (bundle it if exhaustive correctness is needed). Kept small (small-TCB)
# but de-skewed so non-Anglo/EA orgs (a.com.mx, b.com.sg) don't FALSELY collapse to the bare suffix and read as the
# "same org" (which would under-count independent hosts / mis-fire fake-corroboration). This is a STRUCTURAL DNS
# primitive (low-churn), NOT the traffic-driven SOURCE SELECTION (that is live-discovered in the skill, never frozen).
_MULTI_SUFFIX = {
    "co.kr", "or.kr", "ne.kr", "go.kr", "re.kr", "pe.kr", "ac.kr",                     # KR (ac.kr: snu.ac.kr != ac.kr)
    "co.uk", "org.uk", "ac.uk", "gov.uk", "co.jp", "ne.jp", "or.jp", "go.jp", "ac.jp",  # UK / JP
    "com.au", "net.au", "org.au", "gov.au", "edu.au", "co.nz", "com.cn", "co.in",      # AU / NZ / CN / IN
    "com.br", "com.mx", "com.ar", "com.co",                                            # LatAm
    "com.sg", "com.hk", "com.tw", "com.my", "co.id", "co.th", "com.ph", "com.vn",      # SE / E Asia
    "co.za", "com.tr", "co.il", "com.ua", "com.sa",                                    # Africa / MENA / EE
}


def _host(url):
    """Registrable domain (eTLD+1), www-stripped, with a small frozen multi-label-suffix table so a subdomain
    (news.bbc.co.uk reduces to bbc.co.uk, not co.uk) collapses to its org and a same-org 'corroboration' is caught.
    NOT a full Public Suffix List (not stdlib); covers common multi-label ccTLDs across regions (see _MULTI_SUFFIX),
    not one country (subdomain fake-independence)."""
    h = (urllib.parse.urlparse(str(url)).hostname or "").lower()
    if h.startswith("www."):
        h = h[4:]
    try:
        return ipaddress.ip_address(h).compressed   # raw IP literal: eTLD+1 is meaningless (1.2.3.4 != 9.8.3.4)
    except ValueError:
        pass
    parts = h.split(".")
    if len(parts) <= 2:
        return h
    return ".".join(parts[-3:]) if ".".join(parts[-2:]) in _MULTI_SUFFIX else ".".join(parts[-2:])


_NUM_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")   # comma only as a thousands group (so '1,2,3' = three numbers)


def _canon_num(tok):
    """Canonical numeric VALUE so 3.0==3 and 1,234==1234 (display formatting != a real disagreement); whole values
    render without a trailing .0 (9900 stays '9900'). Falls back to the raw (comma-stripped) string if unparseable.
    Mechanical normalization only; the agent adjudicates."""
    t = tok.replace(",", "")
    try:
        f = float(t)
        return str(int(f)) if f == int(f) else repr(f)
    except (ValueError, OverflowError):
        return t
_CJK_STOP = {"입니다", "이다", "한다", "합니다", "됩니다", "있다", "없다", "에서", "에게", "으로", "이고",
             "이며", "하는", "했다", "된다", "이라", "라고", "까지", "부터", "처럼", "보다", "예요", "에요",
             "이에요", "그리고", "하지만", "그러나", "또는", "이런", "저런", "그런"}
_EN_STOP = {"according", "reached", "posted", "reported", "including", "between", "during", "within", "around",
            "about", "after", "before", "their", "these", "those", "which", "while", "would", "could", "should",
            "there", "where", "when", "with", "from", "that", "this", "have", "been", "were", "will", "also",
            "into", "over", "than", "then", "them", "they", "your", "more", "most", "some", "such", "only",
            "very", "just", "like", "made", "make", "said", "says", "where", "what", "here", "still"}


def _numeric_conflicts(finds):
    """Rank-3 (narrow, ADVISORY): two findings that share an entity-ish word AND whose number sets differ.
    Surfaces a candidate contradiction for the agent (rule 4); it NEVER adjudicates which value is right, and
    is kept narrow (shared entity token + differing numbers) to avoid the cry-wolf nag the threshold-tree died of."""
    def toks(f):
        s = f.get("quote") or ""        # the VERBATIM bytes only (not the agent's claim text, which can share
        nums = {_canon_num(n) for n in _NUM_RE.findall(s)}        # a category label and false-flag distinct metrics)
        words = set()
        for w in re.findall(r"[^\W\d_]{2,}", s, re.UNICODE):
            wl = w.lower()
            if wl in _CJK_STOP or wl in _EN_STOP:
                continue                            # skip KR copulas + EN fillers (according/which/...) = false-conflict source
            if not wl.isascii() or len(wl) >= 4:    # CJK 2+ char = content token; ASCII needs 4+ (skip is/of/the)
                words.add(wl)
        return nums, words
    items = [(f, *toks(f)) for f in finds]
    out = []
    for i in range(len(items)):
        fi, ni, wi = items[i]
        for j in range(i + 1, len(items)):
            fj, nj, wj = items[j]
            if ni and nj and ni != nj and (wi & wj):
                out.append({"a": fi["artifact_id"], "b": fj["artifact_id"], "numbers": sorted(ni | nj)})
    return out


# ---- Rank-6 evidence-STANDARD layer: declare-then-check sufficiency grade (see RANK6_SPEC.md) -------
# The agent/user DECLARES the bar (kind='standard' row); code only COUNTS / date-diffs / host-clusters and
# GRADES (kind='conclusion_grade'). NO code-resident default bar (a grader-read default = the forbidden
# gyeongju threshold-tree). Grades SUFFICIENCY (enough recent, distinct-host, non-redundant, conflict-free
# corroboration vs the DECLARED bar) - NEVER TRUTH (fabrication-at-capture stays the open roof).
_STD_KNOBS = {"min_independent_sources", "min_distinct_hosts", "max_age_days", "min_dated_fraction",
              "dup_similarity", "fatal_domains", "min_distinct_source_types", "required_modalities"}
_ARITHMETIC_DOMAINS = {"breadth", "recency", "consistency"}   # carried by math over hash-pinned bytes
_GRADE_DOMAIN_NAMES = {"breadth", "recency", "consistency", "traceability", "source_type", "modality"}
# Mechanical artifact-TYPE -> modality CLASS (by file type only, NOT content - same anti-gyeongju rule as detect_type).
# Lets the agent DECLARE required_modalities so "4 web hosts" can't go MEETS while video/primary-doc coverage is 0.
_MODALITY_CLASS = {"html": "web", "md": "web", "txt": "web", "json": "structured", "csv": "structured",
                   "pdf": "document", "transcript": "av", "audio": "av", "video": "av", "image": "image"}
_SHINGLE_K = 3   # FIXED (code-owned, NOT per-topic); only the dup_similarity CUTOFF is agent-declared
_NEAR_DUP_SIM = 0.6   # ADVISORY near-IDENTITY cutoff (3-gram Jaccard) for distinct-counts + duplicate FLAGS.
                      # ADVISORY ONLY: it annotates/counts, NEVER gates a grade (grade collapse still uses the
                      # agent-declared dup_similarity — no hidden bar there). Catches accidental copy-paste
                      # re-submits; measured on the real hidden-gem-natl bug the dup pair scored 0.73 while
                      # genuinely-distinct forecasts scored 0.00, so 0.6 separates them with a wide margin.


def _parse_date(s):
    try:
        return datetime.datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _shingles(text):
    # reuse the CJK-aware tokenizer from _numeric_conflicts (so k/normalization can't smuggle topic-sensitivity);
    # word K-gram shingles of the quote bytes for near-DUPLICATE (string near-identity, NOT semantic similarity).
    toks = []
    for w in re.findall(r"[^\W\d_]{2,}", (text or "").lower(), re.UNICODE):
        if w in _CJK_STOP or w in _EN_STOP:   # MUST match _numeric_conflicts.toks (else EN fillers inflate Jaccard
            continue                          # -> false near-dup -> falsely collapses independent sources -> corrupts breadth)
        if not w.isascii() or len(w) >= 4:
            toks.append(w)
    if len(toks) < _SHINGLE_K:
        return frozenset((w,) for w in toks)   # 1-tuples: homogeneous with the K-gram tuples (else never intersect)
    return frozenset(tuple(toks[i:i + _SHINGLE_K]) for i in range(len(toks) - _SHINGLE_K + 1))


def _jaccard(a, b):
    if not a or not b:
        return 0.0
    u = len(a | b)
    return len(a & b) / u if u else 0.0


def _uf_components(items, edges):
    """Deterministic union-find component COUNT (order-independent; smaller id wins as root)."""
    parent = {x: x for x in items}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            lo, hi = (ra, rb) if ra < rb else (rb, ra)
            parent[hi] = lo
    return len({find(x) for x in items})


def _distinct_text_count(texts, tau=_NEAR_DUP_SIM):
    """ADVISORY count of DISTINCT items after collapsing near-IDENTICAL strings (union-find on 3-gram Jaccard).
    String near-identity hygiene (copy-paste echoes), NOT semantic dedup — paraphrase/semantic overlap stays the
    AGENT's call (don't-code-the-brain). Order-independent. Used only for surfaced counts, never to gate a grade."""
    items = list(range(len(texts)))
    if not items:
        return 0
    shg = {i: _shingles(texts[i]) for i in items}
    edges = [(i, j) for i in items for j in items if i < j and _jaccard(shg[i], shg[j]) >= tau]
    return _uf_components(items, edges)


def _distinct_pred_count(preds):
    """DISTINCT predictions after collapsing near-IDENTICAL claims within the SAME (resolve_by, hypothesis) group
    — a genuine re-forecast with a DIFFERENT deadline stays distinct. ADVISORY count, order-independent. `preds` is
    an iterable of prediction rows. Same rule as predict()'s near_duplicate_of flag, recomputed so it also catches
    rows written before the flag existed (back-compat)."""
    pl = list(preds)
    idx = list(range(len(pl)))
    if not idx:
        return 0
    shg = {i: _shingles(pl[i].get("claim", "")) for i in idx}
    edges = [(i, j) for i in idx for j in idx if i < j
             and pl[i].get("resolve_by") == pl[j].get("resolve_by")
             and pl[i].get("hypothesis_id", "") == pl[j].get("hypothesis_id", "")
             and _jaccard(shg[i], shg[j]) >= _NEAR_DUP_SIM]
    return _uf_components(idx, edges)


def set_published(rdir, artifact_id, published_at):
    """Rank-6: record the CONTENT publish date for an artifact (agent-supplied, declared_unverified) - distinct
    from the capture `ts`. Append-only kind='pubdate' row (capture_measure precedent). NEVER inferred from bytes."""
    ids = {r["artifact_id"] for r in _read_jsonl(os.path.join(rdir, "ledger.jsonl")) if r.get("kind") == "artifact"}
    if artifact_id not in ids:
        raise ValueError(f"unknown artifact_id {artifact_id!r}")
    if _parse_date(published_at) is None:
        raise ValueError(f"published_at must be YYYY-MM-DD, got {published_at!r}")
    row = {"kind": "pubdate", "artifact_id": artifact_id, "published_at": str(published_at), "ts": _now()}
    _append_jsonl(os.path.join(rdir, "ledger.jsonl"), row)
    return row


def set_standard(rdir, **knobs):
    """Rank-6: DECLARE the evidence bar for a conclusion (the agent's per-topic judgment). kind='standard' row,
    standard_id=sha256(canonical knobs). Unknown knob -> raise (typo guard); incoherent/malformed -> invalid_fields
    advisory. NO code-resident default: an omitted knob => that domain UNGRADED (never code-defaulted)."""
    bad = set(knobs) - _STD_KNOBS
    if bad:
        raise ValueError(f"unknown standard knobs: {sorted(bad)} (allowed: {sorted(_STD_KNOBS)})")
    invalid = []
    mis, mds = knobs.get("min_independent_sources"), knobs.get("min_distinct_hosts")
    if mis is not None and mds is not None and mds > mis:
        invalid.append("volume_bar_incoherent")             # distinct hosts can't exceed eff sources after collapse
    fd = knobs.get("fatal_domains")
    if fd is not None and not isinstance(fd, list):
        invalid.append("fatal_domains_not_list")            # e.g. a bare string from --knobs JSON
    elif fd is not None:
        if set(fd) - _GRADE_DOMAIN_NAMES:
            invalid.append("fatal_domains_unknown")         # a typo'd domain would force permanent UNKNOWN silently
        if set(fd) <= {"traceability", "source_type", "modality"}:
            invalid.append("fatal_set_trivial")             # no arithmetic-carried domain => vacuous/unverified bar
    ds = knobs.get("dup_similarity")
    if ds is not None and not (0 < float(ds) <= 1):
        invalid.append("dup_similarity_range")
    rm = knobs.get("required_modalities")
    if rm is not None and (not isinstance(rm, list) or set(rm) - set(_MODALITY_CLASS.values())):
        invalid.append("required_modalities_invalid")       # must be a list of known classes (web/structured/document/av/image)
    canon = json.dumps(knobs, ensure_ascii=False, sort_keys=True)
    row = {"kind": "standard", "standard_id": "std_" + sha256_bytes(canon.encode("utf-8"))[:12],
           "knobs": knobs, "invalid_fields": invalid, "ts": _now()}
    _append_jsonl(os.path.join(rdir, "ledger.jsonl"), row)
    return row


def grade_conclusion(rdir, conclusion_id, standard_id, as_of=None):
    """Rank-6: mechanically GRADE one conclusion's evidence SUFFICIENCY vs the DECLARED standard. standard_id is an
    EXPLICIT agent argument (validated; never a 'latest/only' fallback = a brain decision about which bar applies).
    overall (MEETS/SHORTFALL/UNKNOWN/UNGRADED) derives PURELY from the declared fatal_domains - no code-privileged
    domain. Deterministic. Grades sufficiency, NOT truth (sufficiency_not_truth=true)."""
    rows = _read_jsonl(os.path.join(rdir, "ledger.jsonl"))
    arts = {r["artifact_id"]: r for r in rows if r.get("kind") == "artifact"}
    stds = {r["standard_id"]: r for r in rows if r.get("kind") == "standard"}
    if standard_id not in stds:
        raise ValueError(f"unknown standard {standard_id!r}")
    knobs = stds[standard_id].get("knobs", {})
    if as_of is not None and _parse_date(as_of) is None:
        raise ValueError(f"as_of must be YYYY-MM-DD (or an ISO datetime), got {as_of!r}")
    supports = [r for r in rows if r.get("kind") == "finding" and r.get("conclusion_id") == conclusion_id]
    if not supports:
        raise ValueError(f"no findings carry conclusion_id {conclusion_id!r}")
    pub = {r["artifact_id"]: r.get("published_at") for r in rows if r.get("kind") == "pubdate" and r["artifact_id"] in arts}
    quote, aset = {}, []
    for s in supports:
        q = (s.get("quote") or "")[:200]
        for aid in [s["artifact_id"], *(s.get("corroborated_by") or [])]:
            if aid in arts:
                if aid not in aset:
                    aset.append(aid)
                if aid not in quote or len(q) > len(quote[aid]):   # longest quote per artifact (best near-dup signal)
                    quote[aid] = q
    aset.sort(key=lambda a: ((arts[a].get("sha256") or ""), a))    # determinism (order-independent grade)
    host = {a: _host(arts[a].get("source", "")) for a in aset}
    distinct_hosts = len({h for h in host.values() if h})
    tau = knobs.get("dup_similarity")
    shg = {a: _shingles(quote.get(a, "")) for a in aset}
    edges = []
    for i in range(len(aset)):
        for j in range(i + 1, len(aset)):
            a, b = aset[i], aset[j]
            if host[a] and host[a] == host[b]:
                edges.append((a, b)); continue
            if tau is not None and _jaccard(shg[a], shg[b]) >= float(tau):   # only dup_similarity gates (no hidden bar)
                edges.append((a, b))
    eff = _uf_components(aset, edges) if aset else 0
    mis, mds = knobs.get("min_independent_sources"), knobs.get("min_distinct_hosts")
    breadth_met = ((mis is None or eff >= mis) and (mds is None or distinct_hosts >= mds)) if (mis is not None or mds is not None) else None
    breadth = {"value": {"effective_sources": eff, "distinct_hosts": distinct_hosts, "n_supporting_artifacts": len(aset),
                         "syndication_suspected": distinct_hosts > eff},
               "bar": {"min_independent_sources": mis, "min_distinct_hosts": mds}, "met": breadth_met}
    max_age = knobs.get("max_age_days")
    asof = as_of or max((s.get("ts") for s in supports), default=_now())
    asof_d = _parse_date(asof)
    ages, n_dated, n_undated, future = [], 0, 0, []
    for a in aset:
        d = _parse_date(pub.get(a)) if pub.get(a) else None
        if d is None:
            n_undated += 1
            continue
        n_dated += 1
        if asof_d:
            age = (asof_d - d).days
            if age < 0:
                future.append({"artifact_id": a, "published_at": str(pub.get(a))})   # back-dated/anomalous
            else:
                ages.append(age)
    recency_met, rec_val = None, {"n_dated": n_dated, "n_undated": n_undated, "future_dated_artifacts": future}
    if max_age is not None:
        n_tot = len(aset)
        rec_val["dated_fraction"] = round((n_dated / n_tot) if n_tot else 0.0, 3)
        if n_dated == 0 or rec_val["dated_fraction"] < (knobs.get("min_dated_fraction") or 0) or not ages:
            recency_met = None                              # UNKNOWN (silent unless declared; cry-wolf armor)
        else:
            rec_val["freshest_age_days"] = min(ages)
            recency_met = min(ages) <= max_age
    recency = {"value": rec_val, "bar": {"max_age_days": max_age, "min_dated_fraction": knobs.get("min_dated_fraction")}, "met": recency_met}
    # CARVE-OUT (documented exception to RANK6_SPEC's "omit knob => UNGRADED"): consistency + traceability have NO
    # agent-tunable knob, so they compute UNCONDITIONALLY (bar:None, hard met) unlike the guarded breadth/recency/
    # source_type. They only affect `overall` if the agent lists them in fatal_domains.
    conf = _numeric_conflicts(supports)
    consistency = {"value": {"conflicts": len(conf)}, "bar": None, "met": (len(conf) == 0)}
    trace_ok = bool(aset) and all(arts[a].get("sha256") for a in aset)
    traceability = {"value": {"all_hashed": trace_ok}, "bar": None, "met": trace_ok}
    domains = {"breadth": breadth, "recency": recency, "consistency": consistency, "traceability": traceability}
    mst = knobs.get("min_distinct_source_types")
    if mst is not None:
        ntypes = len({arts[a].get("type", "") for a in aset})
        domains["source_type"] = {"value": ntypes, "bar": mst, "met": (ntypes >= mst), "basis": "declared_unverified"}
    rmod = knobs.get("required_modalities")
    if isinstance(rmod, list) and rmod:                     # DECLARED modality coverage: each required CLASS must be present
        present = sorted({_MODALITY_CLASS.get(arts[a].get("type", ""), "other") for a in aset})
        missing = [m for m in rmod if m not in present]    # NOT a count - forces SPECIFIC classes (text-only can't pass)
        domains["modality"] = {"value": {"present": present, "missing": missing}, "bar": {"required": sorted(set(rmod))},
                               "met": (not missing), "basis": "declared_unverified"}
    _fd = knobs.get("fatal_domains")
    fatal = set(_fd) if isinstance(_fd, list) else set()   # malformed fatal_domains (non-list) -> UNGRADED (warned at declare)
    shortfall = sorted(d for d in fatal if domains.get(d, {}).get("met") is False)
    unknown_fatal = sorted(d for d in fatal if domains.get(d, {}).get("met") is None)
    if not fatal:
        overall = "UNGRADED"
    elif shortfall:
        overall = "SHORTFALL"
    elif unknown_fatal:
        overall = "UNKNOWN"
    elif not (fatal & _ARITHMETIC_DOMAINS):
        overall = "UNGRADED"                                # MEETS may not rest on declared_unverified domains alone
    else:
        overall = "MEETS"
    grade = {"kind": "conclusion_grade", "conclusion_id": conclusion_id, "standard_id": standard_id,
             "overall": overall, "shortfall_reasons": shortfall, "domains": domains, "as_of": asof,
             "standard_warnings": stds[standard_id].get("invalid_fields", []),
             "sufficiency_not_truth": True, "recency_basis": "declared_date_unverified", "ts": _now()}
    _append_jsonl(os.path.join(rdir, "ledger.jsonl"), grade)
    return grade


# ---- Rank-7 ALPHA layer: thesis + weak-signal TRIANGULATION (assemble fragments others don't) ---------------
# Alpha = a non-obvious inference where MANY weak signals converge though no single source states it. A hypothesis
# is the agent's falsifiable THESIS; signals are just findings tagged hypothesis_id + polarity (no new noun). The
# agent ties a predict() to the thesis (so the bet is later resolved = non-circular). triangulate() REPORTS
# independent convergence (distinct host AND modality) - it NEVER judges "is this alpha" or sets a threshold; that
# judgment, the why-hidden, and the decay stay the agent's (code persists nouns + counts, like every other rank).
def set_hypothesis(rdir, thesis, signature="", decay="", stakes=""):
    """DECLARE a falsifiable alpha thesis. signature = the pattern in words; decay = why-hidden / when it stops
    being edge. stakes (''/low/med/high) = the agent's declared importance — it gates EFFORT, not modality: a
    high-stakes thesis that the digest finds at RECON shape (single-modality / echoed / no prediction) gets a loud
    EFFORT-SHORTFALL warning. NOUN only (the inference + resolution are the agent's, via tagged signals + predict())."""
    if not str(thesis).strip():
        raise ValueError("thesis must be non-empty")
    if stakes not in ("", "low", "med", "high"):
        raise ValueError(f"stakes must be one of low/med/high (or '' = unspecified), got {stakes!r}")
    hid = "hyp_" + sha256_bytes(str(thesis).encode("utf-8"))[:12]    # id = thesis hash only (stakes is mutable metadata)
    row = {"kind": "hypothesis", "hypothesis_id": hid, "thesis": thesis, "signature": signature,
           "decay": decay, "stakes": stakes, "ts": _now()}
    _append_jsonl(os.path.join(rdir, "ledger.jsonl"), row)
    return row


def triangulate(rdir, hypothesis_id):
    """Reduce the SIGNALS (findings tagged this hypothesis_id) into INDEPENDENT convergence. REPORTS only: the alpha
    core = how many CONFIRMING signals converge from DISTINCT eTLD+1 hosts AND distinct modality classes (the weak
    fragments others don't assemble), netted against disconfirming. The agent decides if convergence is decisive +
    estimates decay; code sets NO threshold (no brain-in-code)."""
    rows = _read_jsonl(os.path.join(rdir, "ledger.jsonl"))
    arts = {r["artifact_id"]: r for r in rows if r.get("kind") == "artifact"}
    sig = [r for r in rows if r.get("kind") == "finding" and r.get("hypothesis_id") == hypothesis_id]

    def _host_of(f):
        return _host(arts[f["artifact_id"]].get("source", "")) if f.get("artifact_id") in arts else ""

    def _mod_of(f):
        return _MODALITY_CLASS.get(arts[f["artifact_id"]].get("type", ""), "other") if f.get("artifact_id") in arts else "other"

    def _facets(pol):
        fs = [f for f in sig if f.get("polarity") == pol]
        hosts = {h for h in (_host_of(f) for f in fs) if h}
        return fs, hosts, {_mod_of(f) for f in fs}

    conf, chosts, cmods = _facets("confirms")
    disc, dhosts, _ = _facets("disconfirms")
    return {"hypothesis_id": hypothesis_id, "n_signals": len(sig),
            "confirming": len(conf), "disconfirming": len(disc),
            # distinct CLAIMS after collapsing near-IDENTICAL signal text (copy-paste echoes from >1 host inflate the
            # raw confirming count without adding independent information). Advisory; semantic paraphrase is the agent's.
            "confirming_distinct_claims": _distinct_text_count([f.get("text", "") for f in conf]),
            "disconfirming_distinct_claims": _distinct_text_count([f.get("text", "") for f in disc]),
            "independent_confirming_hosts": len(chosts), "confirming_modalities": sorted(cmods),
            "independent_disconfirming_hosts": len(dhosts),
            "net_independent": len(chosts) - len(dhosts),   # >0 = weak signals converge confirming (agent judges if decisive)
            "signals": [{"text": f.get("text"), "polarity": f.get("polarity"), "artifact_id": f.get("artifact_id"),
                         "host": _host_of(f), "modality": _mod_of(f)} for f in sig]}


# The alpha CONCEPT's default definition — domain/site/platform-NEUTRAL (names nothing perishable), and OVERRIDABLE
# by the agent/skill per `criteria` (like grade_conclusion's declared knobs). It is the definition of "alpha", not a
# hidden methodology baked immovably in the spine: pass criteria={...} to change the bar; the spine just REPORTS.
_ALPHA_CRITERIA = {"min_modalities": 2, "min_independent_hosts": 3, "require_net_positive": True,
                   "require_distinct_predict": True, "no_echoed_claims": True}
# min_independent_hosts: ALPHA needs corroboration breadth, not just 2 sources (measured: a 2-host pick — one being
# the subject's own page — passed [ALPHA] and the agent over-claimed "established finding"; judges flagged it).
# The CODE counts distinct hosts; "is one of them the subject itself?" is the agent's call (two-brain).


def alpha_label(tri, stakes="", distinct_predictions=None, raw_predictions=None, criteria=None):
    """ADVISORY mechanical label: is a thesis at ALPHA grade, or only RECON? Derives from an alpha definition
    (independent convergence across DISTINCT host AND modality, no echoed claims, a falsifiable prediction) that is
    AGENT-OVERRIDABLE via `criteria` (default `_ALPHA_CRITERIA`; no immovable methodology in the spine) + the
    agent-declared `stakes`. Code REPORTS the shape + a label; the agent still judges. `stakes` only sets how LOUD a
    shortfall is flagged. distinct_predictions / raw_predictions (optional) = DISTINCT vs total predictions tied to
    this thesis (raw > distinct => echoed re-submits). Structural fix for the hidden-gem-natl mislabel: a 1-modality
    single-burst run gets stamped RECON, so a low-effort recon can no longer masquerade as alpha in the digest."""
    c = {**_ALPHA_CRITERIA, **(criteria or {})}
    reasons = []
    nconf = tri.get("confirming", 0)
    if len(tri.get("confirming_modalities", [])) < c["min_modalities"]:
        reasons.append("single-modality" if nconf else "no-confirming-signals")
    cdc = tri.get("confirming_distinct_claims", nconf)
    if c["no_echoed_claims"] and cdc < nconf:
        reasons.append(f"echoed-claims({nconf}->{cdc})")
    if c["require_net_positive"] and tri.get("net_independent", 0) <= 0:
        reasons.append("no-net-independent-convergence")
    if nconf and tri.get("independent_confirming_hosts", 0) < c["min_independent_hosts"]:
        reasons.append(f"thin-independence({tri.get('independent_confirming_hosts', 0)}<{c['min_independent_hosts']})")
    if c["require_distinct_predict"] and distinct_predictions == 0:
        reasons.append("no-falsifiable-prediction")
    elif c["require_distinct_predict"] and raw_predictions is not None and distinct_predictions is not None and raw_predictions > distinct_predictions:
        reasons.append(f"echoed-predictions({raw_predictions}->{distinct_predictions})")
    shape = "ALPHA" if not reasons else "RECON"
    # The RECON *label* is always honest (any missed criterion). The LOUD high-stakes warning is reserved for an
    # EGREGIOUS shortfall — a quality/convergence miss BEYOND the often-unavoidable single-modality: when an
    # authority source is fetched as a page (its structured data not extracted) it registers as 'web', so
    # single-modality ALONE is frequently a capture artifact, not laziness (the agent's SKILL prescribes the remedy,
    # the spine doesn't). Gating the warning on host-COUNT instead would REOPEN the original failure (which had 4
    # same-type hosts + 1 modality), so we key on reason QUALITY, not host volume. Measured live: single-modality
    # fires near-universally when sources are JS-walled, so an unconditional warning would cry wolf.
    egregious = bool(set(reasons) - {"single-modality"})
    warning = "HIGH-STAKES EFFORT SHORTFALL" if (shape == "RECON" and stakes == "high" and egregious) else ""
    return {"label": shape, "alpha": shape == "ALPHA", "reasons": reasons, "warning": warning}


def verify(rdir):
    """Deliberately THIN: local dangling-anchor + tamper(rehash) check + low-quality-citation WARNING.
    NOT the farm gate (which does byte-in-quote semantic grounding). The real seal is the farm bridge."""
    rows = _read_jsonl(os.path.join(rdir, "ledger.jsonl"))
    arts = {r["artifact_id"]: r for r in rows if r.get("kind") == "artifact"}
    finds = [r for r in rows if r.get("kind") == "finding"]
    dangling = [f["artifact_id"] for f in finds if f["artifact_id"] not in arts]
    mismatch, unverifiable = [], []
    for a in arts.values():
        target = a.get("canonical_path") or a.get("path")
        if not a.get("sha256"):
            unverifiable.append(a["artifact_id"])          # no recorded hash -> can't attest (was: silently skipped)
        elif not target or not os.path.exists(target):
            unverifiable.append(a["artifact_id"])          # capture file gone -> can't re-hash (was: false ok=true)
        elif sha256_file(target) != a["sha256"]:
            mismatch.append(a["artifact_id"])
    low_q = [f["artifact_id"] for f in finds
             if arts.get(f["artifact_id"], {}).get("quality_label") in BAD_QUALITY]
    # --- advisory surfacers (Rank 2/3/5): REPORT, never adjudicate (ok stays = dangling/mismatch/unverifiable) ---
    cmeas = {}
    for r in rows:
        if r.get("kind") == "capture_measure":
            cmeas[r["artifact_id"]] = r.get("cer")                    # latest wins (append-ordered)
    capture_errors = {f["artifact_id"]: cmeas[f["artifact_id"]] for f in finds if f["artifact_id"] in cmeas}
    fake_corrob = []                                                  # rule 5: 'corroborated' but sources share a host
    for f in finds:
        cb = f.get("corroborated_by") or []
        if cb:
            hosts = {_host(arts.get(aid, {}).get("source", "")) for aid in [f["artifact_id"], *cb]}
            hosts.discard("")
            if len(hosts) < 2:
                fake_corrob.append(f["artifact_id"])
    # Rank-6 sufficiency grades (advisory; folded ONLY when >=1 declared standard exists; ok UNCHANGED)
    cg = {}
    if any(r.get("kind") == "standard" for r in rows):
        latest_g = {}
        for g in rows:
            if g.get("kind") == "conclusion_grade":
                latest_g[(g.get("conclusion_id"), g.get("standard_id"))] = g
        sf = [{"conclusion_id": g["conclusion_id"], "reasons": g["shortfall_reasons"]}
              for g in latest_g.values() if g["overall"] == "SHORTFALL"]
        graded = {g["conclusion_id"] for g in latest_g.values()}
        all_cids = {f.get("conclusion_id") for f in finds if f.get("conclusion_id")}
        cg = {"n_graded": len(latest_g), "n_shortfall": len(sf),
              "n_ungraded_conclusions": len(all_cids - graded), "shortfalls": sf}
    alpha_bad = [f["artifact_id"] for f in finds                     # Rank-7: an alpha SIGNAL resting on a walled/bad
                 if f.get("hypothesis_id") and arts.get(f["artifact_id"], {}).get("quality_label") in BAD_QUALITY]
    return {"ok": not dangling and not mismatch and not unverifiable, "dangling_anchors": dangling,
            "hash_mismatch": mismatch, "unverifiable": unverifiable, "low_quality_citations": low_q,
            "capture_errors": capture_errors, "fake_corroboration": list(dict.fromkeys(fake_corrob)),
            "numeric_conflicts": _numeric_conflicts(finds), "open_at_stop": frontier_state(rdir)["open"],
            "alpha_signals_on_bad_capture": list(dict.fromkeys(alpha_bad)),   # capture (login/JS-walled) -> suspect signal
            "conclusion_grades": cg}


def farm_plan(rdir):
    """Emit the ORDERED farm_* calls the AGENT executes (refledger never calls farm - neutrality).
    FIX2: if an artifact has no http(s) sourceUrl, emit NO transcript/evidence channel for it (local-seal
    only) - NEVER synthesize a file:// uri over a Korean home dir (which fails farm's uri validation)."""
    rows = _read_jsonl(os.path.join(rdir, "ledger.jsonl"))
    arts = {r["artifact_id"]: r for r in rows if r.get("kind") == "artifact"}
    finds = [r for r in rows if r.get("kind") == "finding"]
    calls, skipped, registered = [], [], set()
    for f in finds:
        a = arts.get(f["artifact_id"])
        if not a:
            skipped.append({"reason": "dangling", "artifact_id": f["artifact_id"]}); continue
        src = str(a.get("source", ""))
        if not (src.startswith("http://") or src.startswith("https://")):
            skipped.append({"reason": "no_source_url", "artifact_id": a["artifact_id"]}); continue
        if a["artifact_id"] not in registered:
            registered.add(a["artifact_id"])
            if a.get("type") in ("transcript", "video") and a.get("canonical_path", "").endswith(".vtt"):
                calls.append({"tool": "farm_register_transcript",
                              "args": {"runDir": rdir, "vttPath": a["canonical_path"], "sourceUrl": src,
                                       "captureMethod": "byo-refcap-asr", "capturedBy": "refcap/refledger"}})
            else:
                calls.append({"tool": "farm_register_evidence",
                              "args": {"runDir": rdir, "path": a.get("path"), "sourceUrl": src,
                                       "evidenceKind": EVIDENCE_KIND.get(a.get("type"), "structured_data")}})
        # anchor MUST point at verbatim bytes (e2e: claim text != cited bytes -> gate rejects).
        # prefer an explicit verbatim quote; else a cue/frame index (no quote needed); else fall back.
        ekind = EVIDENCE_KIND.get(a.get("type"), "structured_data")
        if f.get("quote"):
            anchor, ctype = {"type": "text_span", "quote": f["quote"]}, "text"
        elif f.get("locator", "").startswith("cue=") and f["locator"].split("=")[1].isdigit():
            anchor, ctype, ekind = {"type": "transcript_cue", "cueIndex": int(f["locator"].split("=")[1])}, "text", "transcript_cue"
        elif f.get("locator", "").startswith("frame="):
            anchor, ctype, ekind = {"type": "frame", "timestampSec": 0}, "visual", "frame_screenshot"
        else:
            anchor, ctype = {"type": "text_span", "quote": f["text"][:120]}, "text"
        warn = " [WARN low-quality source]" if a.get("quality_label") in BAD_QUALITY else ""
        calls.append({"tool": "farm_add_claim",
                      "args": {"runDir": rdir, "claim": f["text"] + warn, "claimType": ctype,
                               "evidenceKind": ekind, "artifactId": "<FILL: farm artifactId from register>",
                               "artifactSource": src, "anchor": anchor}})
    plan = {"research": os.path.basename(rdir), "calls": calls, "skipped": skipped,
            "then": ["farm_run_claim_gate(mode=final)", "farm_export_bundle"]}
    with open(os.path.join(rdir, "farm_plan.json"), "w", encoding="utf-8") as _fh:
        json.dump(plan, _fh, ensure_ascii=False, indent=2)
    return plan


# ---- ingest: DEPTH-0 router (extension/scheme only) ----
def detect_type(target: str) -> str:
    t = target.lower()
    host = urllib.parse.urlparse(t).hostname or "" if t.startswith("http") else ""
    # video: a real video PATH on a video host, or a video file ext (NOT just the host - a youtube
    # /@channel/about or instagram /p/<photo> is NOT a video; scenario QA found host-substring over-match).
    video_path = any(p in t for p in ("/watch", "v=", "/shorts/", "/reel", "/video/", "youtu.be/"))
    if t.endswith((".mp4", ".webm", ".mov", ".mkv")) or (any(h in host for h in ("youtube.com", "youtu.be", "tiktok.com", "instagram.com")) and video_path):
        return "video"
    if t.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
        return "image"
    if t.endswith((".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg")):
        return "audio"
    if t.endswith((".vtt", ".srt")):
        return "transcript"
    if t.endswith(".csv"):
        return "csv"
    if t.endswith(".pdf"):
        return "pdf"
    # json: a .json file or an api.* host (NOT any '/api' substring - github.com/api/docs is human HTML).
    if t.endswith(".json") or host.startswith("api."):
        return "json"
    if t.endswith((".txt", ".md")):
        return "text"
    if t.startswith("http"):
        return "html"
    return "unknown"


def _is_blocked_host(host):
    """Refuse SSRF targets: loopback / private / link-local (e.g. 169.254.169.254 cloud metadata)."""
    if not host:
        return True
    try:
        for fam, _, _, _, sa in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(sa[0])
            if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return True
    except Exception:
        return False   # unresolved -> let urlopen fail normally
    return False


def _http_get(url, dest, max_bytes=50_000_000):
    host = urllib.parse.urlparse(url).hostname
    if _is_blocked_host(host):                       # SSRF guard (scenario adversarial-03)
        raise ValueError(f"refused private/loopback/link-local host: {host}")
    req = urllib.request.Request(url, headers={"User-Agent": "refledger/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read(max_bytes + 1)                 # size cap (scenario adversarial-04: zip-bomb/50GB OOM)
        if len(data) > max_bytes:
            raise ValueError(f"response exceeds {max_bytes}-byte cap")
        status = getattr(r, "status", None) or (r.getcode() if hasattr(r, "getcode") else None)
    with open(dest, "wb") as f:
        f.write(data)
    return status


def ingest(rdir, target, note=""):
    """Download/extract -> hash -> register. The AGENT reads/understands the result (esp. images: Claude
    vision beats easyocr). Sequential subprocess calls only (never parallel -> 15GB OOM defense)."""
    t = detect_type(target)
    if not target.lower().startswith("http") and not _path_ok(target):   # local path into a system dir -> refuse
        return {"error": f"refused: path resolves into a system directory: {target}", "source": target}
    artdir = os.path.join(rdir, "art"); os.makedirs(artdir, exist_ok=True)
    if t == "unknown":
        return {"type": "unknown", "source": target, "needs_agent": True,
                "hint": "확장자/스킴으로 타입 판정 불가 - 에이전트가 적절한 추출기를 직접 고르라"}
    if t == "video":
        # delegate to the verified file-based pipeline (subprocess; cwd-relative ascii = Korean-path safe)
        script = "refauto.py" if target.startswith("http") else "refextract.py"
        try:
            subprocess.run([sys.executable, script, target, "--note", note] if script == "refextract.py"
                           else [sys.executable, script, target, note],
                           cwd=HERE, timeout=int(os.environ.get("REFCAP_INGEST_TIMEOUT_S", "2400")), check=False)
        except Exception as e:
            return {"error": f"video extract failed: {e}", "source": target}
        # find newest refs/<name>/transcript_timed.txt
        refs = os.path.join(HERE, "refs")
        cand = [os.path.join(refs, d, "transcript_timed.txt") for d in os.listdir(refs)
                if os.path.exists(os.path.join(refs, d, "transcript_timed.txt"))]
        if not cand:
            return {"error": "no transcript produced", "source": target}
        timed = max(cand, key=os.path.getmtime)
        outdir = os.path.dirname(timed)
        segs, quality = parse_timed(timed)
        vtt = os.path.join(outdir, "transcript.vtt")
        with open(vtt, "w", encoding="utf-8") as _fh:
            _fh.write(to_vtt(segs))
        # hash the CANONICAL_PATH file (the vtt) so verify can re-hash it; the vtt is deterministic
        # (same segments -> same WebVTT, no run metadata) so identity is preserved across runs.
        return ledger_append(rdir, type="transcript", source=target, method="refextract",
                             path=timed, canonical_path=vtt, sha256=sha256_file(vtt),
                             quality_label=quality, note=note)
    if t in ("html", "json"):
        ext = ".json" if t == "json" else ".html"
        dest = os.path.join(artdir, "art_" + sha256_bytes(target.encode())[:12] + ext)
        try:
            status = _http_get(target, dest)   # returns http status (or None)
        except Exception as e:
            return {"error": f"fetch failed: {e}", "source": target}
        with open(dest, encoding="utf-8", errors="replace") as _fh:
            body = _fh.read()
        if t == "json":
            ql = json_quality(body, http_status=status)
        else:
            # t == 'html', but detect_type is depth-0 (ext/scheme) and misses structured endpoints on
            # non-'api.' hosts (e.g. openapi.<host>, registry.npmjs.org, .../api/v2/... with no ext, any region).
            # MECHANICAL sniff (not a content classifier): if the fetched body parses as JSON,
            # label it via json_quality so API_ERROR/MALFORMED/EMPTY/rate-limit detection runs instead of
            # the HTML-tuned web_quality (which false-EMPTYs a valid array and false-OKs a >1500-char error).
            try:
                json.loads(body)
                is_json = True
            except Exception:
                is_json = False
            ql = json_quality(body, http_status=status) if is_json else web_quality(body, http_status=status)
        return ledger_append(rdir, type=t, source=target, method="refledger/fetch",
                             path=dest, canonical_path=dest, sha256=sha256_file(dest),
                             quality_label=ql, note=note)
    # remote already-served file of a register-only kind -> FETCH it first. The register-only branches below
    # sha256 a LOCAL path; a bare http(s) URL would otherwise register sha256=None = an empty UNVERIFIABLE shell
    # (QA-300 #1, the top cross-domain defect: arxiv PDFs, raw CHANGELOG.md, remote CSVs all broke). Reuses
    # _http_get's SSRF guard + 50MB cap; lawful ($0, already-served, no cookies/anti-bot); no content classifier
    # (quality stays UNKNOWN for binary/agent-read kinds; transcripts keep parse_timed's label) -> brain uncoded.
    local = target
    if target.lower().startswith("http") and t in ("transcript", "image", "text", "pdf", "csv", "audio"):
        ext = os.path.splitext(urllib.parse.urlparse(target).path)[1] or ("." + t)
        local = os.path.join(artdir, "art_" + sha256_bytes(target.encode())[:12] + ext)
        try:
            _http_get(target, local)
        except Exception as e:
            return {"error": f"fetch failed: {e}", "source": target}
    method = "refledger/fetch" if local != target else "register"
    if t == "transcript":
        segs, quality = parse_timed(local if os.path.exists(local) else "")
        canon = local + ".segments.json"
        if segs:
            with open(canon, "w", encoding="utf-8") as _fh:
                _fh.write(canonical_json(segs))
        sha = sha256_file(canon if segs else local)
        return ledger_append(rdir, type="transcript", source=target, method=method,
                             path=local, canonical_path=(canon if segs else local),
                             sha256=sha, quality_label=quality, note=note)
    # image / text / pdf / csv / audio: register as-is; the AGENT reads it (vision for images, text otherwise)
    sha = sha256_file(local) if os.path.exists(local) else None
    return ledger_append(rdir, type=t, source=target, method=method, path=local,
                         canonical_path=local, sha256=sha, quality_label="UNKNOWN",
                         note=note + (" | 에이전트가 직접 읽음(vision/text)" if t == "image" else ""))


def digest(rdir):
    rows = _read_jsonl(os.path.join(rdir, "ledger.jsonl"))
    arts = [r for r in rows if r.get("kind") == "artifact"]
    finds = [r for r in rows if r.get("kind") == "finding"]
    st = frontier_state(rdir)
    with open(os.path.join(rdir, "meta.json"), encoding="utf-8") as _fh:
        meta = json.load(_fh)
    L = [f"# RESEARCH DIGEST: {meta['goal']}", "", f"## 수집 증거 ({len(arts)})"]
    for a in arts:
        L.append(f"- [{a.get('type')}] {a.get('source')}  (gate={a.get('quality_label')}, sha={(a.get('sha256') or '')[:12]})")
    L.append(f"\n## findings (OBSERVED first)")
    for f in sorted(finds, key=lambda x: x["label"]):
        L.append(f"- ({f['label']}) {f['text']}  <-{f['artifact_id']}@{f.get('locator')}")
    pr = [r for r in _read_jsonl(os.path.join(rdir, "predictions.jsonl")) if r.get("kind") == "prediction"]
    hyps_latest = {}                                          # latest row per hid (stakes is mutable metadata; last wins)
    for r in rows:
        if r.get("kind") == "hypothesis":
            hyps_latest[r["hypothesis_id"]] = r
    if hyps_latest:                                           # Rank-7 alpha layer: thesis + weak-signal triangulation
        L.append(f"\n## 알파 가설 + 삼각측량 ({len(hyps_latest)})")
        for hid, h in hyps_latest.items():
            t = triangulate(rdir, hid)
            preds_h = [p for p in pr if p.get("hypothesis_id", "") == hid]   # per-thesis raw vs distinct predictions
            lab = alpha_label(t, stakes=h.get("stakes", ""),
                              distinct_predictions=_distinct_pred_count(preds_h), raw_predictions=len(preds_h))
            stamp = (f"[!{lab['warning']}] " if lab["warning"] else "") + "[" + lab["label"] + \
                    (": " + ", ".join(lab["reasons"]) if lab["reasons"] else "") + "]"
            L.append(f"- {h['thesis'][:90]}  [confirm {t['confirming']} (distinct {t['confirming_distinct_claims']}, "
                     f"독립호스트 {t['independent_confirming_hosts']}, modality {len(t['confirming_modalities'])}) "
                     f"/ disconfirm {t['disconfirming']} / net {t['net_independent']}]  {stamp}")
    if pr:
        cal = calibration(rdir)
        L.append(f"\n## 예측 ({len(pr)} 등록 · distinct {cal['n_distinct_predictions']} / resolved {cal['n_resolved']} "
                 f"/ premature {cal['n_premature']} / brier {cal['brier_all']})")
        for p in pr:
            dupmark = f"  (dup of {p['near_duplicate_of']})" if p.get("near_duplicate_of") else ""
            L.append(f"- (conf {p.get('stated_confidence')}, by {p.get('resolve_by')}) {(p.get('claim') or '')[:100]}{dupmark}")
    L.append(f"\n## 남은 frontier ({len(st['open'])})")
    for o in st["open"]:
        L.append(f"- [ ] {o}")
    out = os.path.join(rdir, "SUMMARY.md")
    with open(out, "w", encoding="utf-8") as _fh:
        _fh.write("\n".join(L) + "\n")
    return out


def _resolve(rdir_or_slug):
    """CLI passes the ASCII slug, never the Korean absolute path (Windows mangles Korean subprocess args
    - the exact seam the red team flagged). Resolve slug -> HERE/research/<slug>, CONFINED to the research
    root so a CLI slug like '../../etc' cannot escape (path-traversal — now exposed via predict/resolve/calib).
    A genuine absolute path (programmatic caller) passes through unchanged."""
    s = rdir_or_slug
    if os.path.isabs(s):
        return s
    root = os.path.normpath(os.path.join(HERE, "research"))
    norm = os.path.normpath(os.path.join(root, s))
    if norm != root and not norm.startswith(root + os.sep):
        raise ValueError(f"rdir escapes the research root: {s!r}")
    return norm


def main():
    ap = argparse.ArgumentParser(description="refledger - research-agent spine (agent drives, code persists)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("open").add_argument("goal")
    pi = sub.add_parser("ingest"); pi.add_argument("rdir"); pi.add_argument("target"); pi.add_argument("--note", default="")
    pf = sub.add_parser("finding"); pf.add_argument("rdir"); pf.add_argument("text"); pf.add_argument("label")
    pf.add_argument("artifact_id"); pf.add_argument("--quote", default=""); pf.add_argument("--locator", default="")
    pf.add_argument("--confidence", default="med"); pf.add_argument("--corroborated", nargs="*", default=[])
    pf.add_argument("--conclusion", default=""); pf.add_argument("--hypothesis", default=""); pf.add_argument("--polarity", default="")
    po = sub.add_parser("frontier"); po.add_argument("rdir"); po.add_argument("op", choices=["open", "close", "note", "visit", "state"])
    po.add_argument("item", nargs="?", default=""); po.add_argument("--kind", default="question"); po.add_argument("--reason", default="")
    for c in ("verify", "digest", "plan"):
        sub.add_parser(c).add_argument("rdir")
    pp = sub.add_parser("predict"); pp.add_argument("rdir"); pp.add_argument("claim"); pp.add_argument("confidence")
    pp.add_argument("--by", required=True, dest="resolve_by"); pp.add_argument("--operator", default=""); pp.add_argument("--anchor", default="")
    pp.add_argument("--conclusion", default=""); pp.add_argument("--hypothesis", default="")
    prs = sub.add_parser("resolve"); prs.add_argument("rdir"); prs.add_argument("prediction_id")
    prs.add_argument("outcome", choices=["hit", "miss", "unresolved"]); prs.add_argument("--evidence", default="")
    sub.add_parser("calib").add_argument("rdir")
    pm = sub.add_parser("measure"); pm.add_argument("rdir"); pm.add_argument("artifact_id")
    pm.add_argument("hyp_span"); pm.add_argument("truth_span")
    ppub = sub.add_parser("published"); ppub.add_argument("rdir"); ppub.add_argument("artifact_id"); ppub.add_argument("published_at")
    pstd = sub.add_parser("standard"); pstd.add_argument("rdir"); pstd.add_argument("--knobs", required=True, help="JSON object of declared knobs")
    pgr = sub.add_parser("grade"); pgr.add_argument("rdir"); pgr.add_argument("conclusion_id"); pgr.add_argument("standard_id"); pgr.add_argument("--as-of", default=None, dest="as_of")
    ph = sub.add_parser("hypothesis"); ph.add_argument("rdir"); ph.add_argument("thesis")   # Rank-7 alpha layer
    ph.add_argument("--signature", default=""); ph.add_argument("--decay", default="")
    ph.add_argument("--stakes", default="", choices=["", "low", "med", "high"])
    pt = sub.add_parser("triangulate"); pt.add_argument("rdir"); pt.add_argument("hypothesis_id")
    a = ap.parse_args()
    if a.cmd == "open":
        print(os.path.basename(open_research(a.goal)))   # print the ASCII slug, not the Korean path
        return
    rd = _resolve(a.rdir)
    if a.cmd == "ingest":
        print(json.dumps(ingest(rd, a.target, a.note), ensure_ascii=False))
    elif a.cmd == "finding":
        print(json.dumps(record_finding(rd, a.text, a.label, a.artifact_id, a.quote, a.locator, a.confidence, a.corroborated, a.conclusion, a.hypothesis, a.polarity), ensure_ascii=False))
    elif a.cmd == "frontier":
        if a.op == "state":
            print(json.dumps(frontier_state(rd), ensure_ascii=False))
        elif a.op == "open":
            frontier_open(rd, a.item, a.kind, a.reason)
        elif a.op == "close":
            frontier_close(rd, a.item, a.reason)
        elif a.op == "visit":
            frontier_visit(rd, a.item, a.reason)
        else:
            frontier_note(rd, a.item, a.reason)
    elif a.cmd == "verify":
        print(json.dumps(verify(rd), ensure_ascii=False))
    elif a.cmd == "digest":
        print(digest(rd))
    elif a.cmd == "plan":
        print(json.dumps(farm_plan(rd), ensure_ascii=False))
    elif a.cmd == "predict":
        print(json.dumps(predict(rd, a.claim, a.confidence, a.resolve_by, a.operator, a.anchor, a.conclusion, a.hypothesis), ensure_ascii=False))
    elif a.cmd == "resolve":
        print(json.dumps(resolve(rd, a.prediction_id, a.outcome, a.evidence), ensure_ascii=False))
    elif a.cmd == "calib":
        print(json.dumps(calibration(rd), ensure_ascii=False))
    elif a.cmd == "measure":
        print(json.dumps(measure_capture_error(rd, a.artifact_id, a.hyp_span, a.truth_span), ensure_ascii=False))
    elif a.cmd == "published":
        print(json.dumps(set_published(rd, a.artifact_id, a.published_at), ensure_ascii=False))
    elif a.cmd == "standard":
        print(json.dumps(set_standard(rd, **json.loads(a.knobs)), ensure_ascii=False))
    elif a.cmd == "grade":
        print(json.dumps(grade_conclusion(rd, a.conclusion_id, a.standard_id, a.as_of), ensure_ascii=False))
    elif a.cmd == "hypothesis":
        print(json.dumps(set_hypothesis(rd, a.thesis, a.signature, a.decay, a.stakes), ensure_ascii=False))
    elif a.cmd == "triangulate":
        print(json.dumps(triangulate(rd, a.hypothesis_id), ensure_ascii=False))


if __name__ == "__main__":
    main()
