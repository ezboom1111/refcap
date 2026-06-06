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
               "BOT_WALL", "LOGIN_WALL", "PAYWALL", "EMPTY", "HTTP_ERROR",
               "API_ERROR", "MALFORMED", "EXTRACT_FAILED"}
_BOT_MARKERS = ("captcha", "cloudflare", "unusual traffic", "are you a robot", "verify you are human",
                "enable javascript", "checking your browser", "automated requests")
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


def record_finding(rdir, text, label, artifact_id, quote="", locator="", confidence="med"):
    """Local cite-or-fail: a finding MUST anchor to a registered artifact, else refuse.
    `quote` = the VERBATIM span from the artifact that grounds the claim (NOT the claim text - the farm
    gate rejects a claim whose anchor text is not literally in the cited bytes; learned e2e). `locator` =
    where (cue=N | char=a..b | frame=<file>) for cue/frame anchors that need no quote."""
    path = os.path.join(rdir, "ledger.jsonl")
    ids = {r["artifact_id"] for r in _read_jsonl(path) if r.get("kind") == "artifact"}
    if artifact_id not in ids:
        raise ValueError(f"dangling anchor: artifact_id {artifact_id!r} not in ledger")
    f = {"kind": "finding", "artifact_id": artifact_id, "text": text, "label": label,
         "quote": quote, "locator": locator, "confidence": confidence, "ts": _now()}
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


def predict(rdir, claim, confidence, resolve_by, operator="", anchor_artifact_id=""):
    """Record a FALSIFIABLE forecast. confidence in [0,1] = stated P(claim is true). resolve_by = the date
    by which reality should settle it. operator = the falsifiable condition (e.g. peaks_within / price_lte /
    count_gte). anchor_artifact_id (optional) = the basis evidence at forecast time (validated vs the ledger
    if given). Append-only, no dedupe (a re-forecast is a new prediction)."""
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
    # predictions are append-only with NO dedupe, so the id need not be stable/derived (unlike artifact ids).
    pid = "p_" + sha256_bytes(f"{claim}|{operator}|{resolve_by}|{now}|{os.urandom(8).hex()}".encode("utf-8"))[:12]
    row = {"kind": "prediction", "prediction_id": pid, "claim": claim, "stated_confidence": c,
           "resolve_by": resolve_by, "operator": operator, "anchor_artifact_id": anchor_artifact_id,
           "created": now}
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
    for pid, p in preds.items():
        res = latest.get(pid)
        if not res or res.get("outcome") not in ("hit", "miss"):
            continue
        y = 1.0 if res["outcome"] == "hit" else 0.0
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
    return {"n_predictions": n, "n_resolved": len(resolved),
            "resolution_rate": round(len(resolved) / n, 3) if n else 0.0,
            "brier_all": ba, "brier_anchored": banch,
            "brier_divergence": (round(ba - banch, 4) if (ba is not None and banch is not None) else None),
            "reliability_buckets": buckets,
            "worst_bucket_gap": max((x["gap"] for x in buckets), default=None)}


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
    return {"ok": not dangling and not mismatch and not unverifiable, "dangling_anchors": dangling,
            "hash_mismatch": mismatch, "unverifiable": unverifiable, "low_quality_citations": low_q}


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
                           cwd=HERE, timeout=900, check=False)
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
        ql = web_quality(body, http_status=status) if t == "html" else json_quality(body, http_status=status)
        return ledger_append(rdir, type=t, source=target, method="refledger/fetch",
                             path=dest, canonical_path=dest, sha256=sha256_file(dest),
                             quality_label=ql, note=note)
    if t == "transcript":
        segs, quality = parse_timed(target if os.path.exists(target) else "")
        canon = target + ".segments.json"
        if segs:
            with open(canon, "w", encoding="utf-8") as _fh:
                _fh.write(canonical_json(segs))
        sha = sha256_file(canon if segs else target)
        return ledger_append(rdir, type="transcript", source=target, method="register",
                             path=target, canonical_path=(canon if segs else target),
                             sha256=sha, quality_label=quality, note=note)
    # image / text / pdf: register as-is; the AGENT reads it (vision for images, text for the rest)
    sha = sha256_file(target) if os.path.exists(target) else None
    return ledger_append(rdir, type=t, source=target, method="register", path=target,
                         canonical_path=target, sha256=sha, quality_label="UNKNOWN",
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
        L.append(f"- [{a['type']}] {a['source']}  (gate={a.get('quality_label')}, sha={a.get('sha256','')[:12]})")
    L.append(f"\n## findings (OBSERVED first)")
    for f in sorted(finds, key=lambda x: x["label"]):
        L.append(f"- ({f['label']}) {f['text']}  <-{f['artifact_id']}@{f.get('locator')}")
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
    pf.add_argument("--confidence", default="med")
    po = sub.add_parser("frontier"); po.add_argument("rdir"); po.add_argument("op", choices=["open", "close", "note", "visit", "state"])
    po.add_argument("item", nargs="?", default=""); po.add_argument("--kind", default="question"); po.add_argument("--reason", default="")
    for c in ("verify", "digest", "plan"):
        sub.add_parser(c).add_argument("rdir")
    pp = sub.add_parser("predict"); pp.add_argument("rdir"); pp.add_argument("claim"); pp.add_argument("confidence")
    pp.add_argument("--by", required=True, dest="resolve_by"); pp.add_argument("--operator", default=""); pp.add_argument("--anchor", default="")
    prs = sub.add_parser("resolve"); prs.add_argument("rdir"); prs.add_argument("prediction_id")
    prs.add_argument("outcome", choices=["hit", "miss", "unresolved"]); prs.add_argument("--evidence", default="")
    sub.add_parser("calib").add_argument("rdir")
    a = ap.parse_args()
    if a.cmd == "open":
        print(os.path.basename(open_research(a.goal)))   # print the ASCII slug, not the Korean path
        return
    rd = _resolve(a.rdir)
    if a.cmd == "ingest":
        print(json.dumps(ingest(rd, a.target, a.note), ensure_ascii=False))
    elif a.cmd == "finding":
        print(json.dumps(record_finding(rd, a.text, a.label, a.artifact_id, a.quote, a.locator, a.confidence), ensure_ascii=False))
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
        print(json.dumps(predict(rd, a.claim, a.confidence, a.resolve_by, a.operator, a.anchor), ensure_ascii=False))
    elif a.cmd == "resolve":
        print(json.dumps(resolve(rd, a.prediction_id, a.outcome, a.evidence), ensure_ascii=False))
    elif a.cmd == "calib":
        print(json.dumps(calibration(rd), ensure_ascii=False))


if __name__ == "__main__":
    main()
