---
name: evidence-budget
description: >-
  Data-shape definitions, evidence budget table by stakes level, video/OCR decision protocol,
  and minimum quality gates for leesearch-alpha investigations.
metadata:
  type: reference
---

# Evidence budget and data-shape floor

Read this file when planning the shape matrix (loop step 2) or when `check_shapes.py` flags a shape gap.
(Note: refledger's `digest` stamp knows modality/host/echo/prediction only — it does NOT enforce the shape
budget below. `check_shapes.py` is what emits `missing-<shape>`.)

## Data shapes defined (shape = artifact type, not source type)

| Shape | What it IS | What it ISN'T |
|---|---|---|
| **unstructured** | News articles, blog posts, community threads, long-form text fetched as HTML/text | A URL list; a search snippet without the actual page |
| **semi-structured** | PDF extractions, dashboard screenshots with labeled values, table captures (not raw HTML), analyst report tables | A news article that happens to mention a number |
| **structured** | CSV/JSON/API response with typed fields from an official source (DART, KIPRIS, NTIS, exchange filings, patent DBs) | JSON you hand-assembled from news text — that's unstructured repackaged |
| **video/audio** | Actually-watched content: frame samples (`farm_sample_frames`) + ASR transcript or caption text | A YouTube URL listed in findings; a thumbnail screenshot |
| **OCR** | Text extracted from image-based documents: scanned PDFs, infographics, screenshots with embedded text | A regular PDF that has selectable text (that's semi-structured) |

**The shape comes from the artifact, not the source.** A gov page fetched as HTML = unstructured. The same page's
table extracted to `.csv` = structured. Earn the shape by producing the artifact.

## Budget table by stakes

| Stakes | Total candidates | Required shapes | Per-shape minimum |
|---|---|---|---|
| **low** | 12–20 | unstructured + 1 other | ≥3 items each |
| **med** | 30–50 | unstructured + semi + structured | ≥3 items each |
| **high** | 50–100 | ALL five shapes | ≥5 items each |

- "candidates" = genuine (non-dangling) `record_finding` calls across ALL shapes, not just web hits.
- One-item shapes are checkbox compliance, not real diversity.
- `check_shapes.py` flags `missing-<shape>(N<min)` when a required shape is below its floor.
- The upper end of the candidate range is ADVISORY — over-collecting is not a failure (quality, not volume, is
  the agent's judgment). Only the floor (`budget_min`) and per-shape minimums gate the PASS.

**This table is mechanically enforced.** Run `python check_shapes.py <run_dir>` — it reads the ledger, gates at
the HIGHEST declared `--stakes` among the run's hypotheses (or a `--stakes` override; `stakes-undeclared` if
neither), skips dangling findings, and exits 1 with `missing-<shape>(N<min)` for any unmet floor. Don't eyeball
the budget; run the gate.

## Video/audio/OCR decision protocol (not optional-by-default)

Video is not "nice to have" — for most topics, relevant video exists. The protocol:

1. **SEARCH first** — YouTube/platform search for the topic. Takes 30 seconds.
2. **If relevant results exist** (they almost always do for med/high stakes):
   - Capture via `farm_evidence_run` + `farm_sample_frames` for visual evidence
   - For spoken content: use `leesearch-video-heavy` (refcap whisper ASR) or `leesearch-video-light` (captions)
   - Register frames and transcript as findings with the video shape
3. **If genuinely no results** after searching: mark "searched, not material" in the shape plan with the search query used.
4. **"I didn't look" ≠ "not material."** Skipping the search is a shape violation.

OCR follows the same logic: if the domain involves reports, filings, or infographics (most do), search for
image-based documents before marking OCR as unnecessary.

## Minimum quality gates

These gates apply at `digest` time. A finding that fails a gate is not counted toward the shape minimum.

- **cite-or-fail**: every finding must have a verbatim `--quote` from fetched bytes. No quote = not counted.
- **independence**: findings from the same eTLD+1 host count as 1 for triangulation (but still count individually for shape budgets).
- **polarity balance**: at least 1 `disconfirms` or `neutral` finding per hypothesis (pure confirmation = echo chamber).
- **artifact presence**: the shape is earned by the artifact, not the claim. "I found a CSV" without the CSV registered = unstructured, not structured.

## Gate limitations — what the deterministic gates CANNOT prove (QA-validated, 2026-06-09)

A 20-scenario full-stack QA + independent audit confirmed the two-layer design: the deterministic gates
(`check_shapes.py` / `validate_independence.py`) prove STRUCTURE; an independent ADVERSARIAL AUDIT proves
GENUINENESS. The gates alone are necessary but NOT sufficient. Measured gaps the gates cannot catch:

- **Structured PROVENANCE (only ~36% of `structured` findings were genuine in QA).** `check_shapes` classifies a
  finding as `structured` by artifact `type` (json/csv) — it CANNOT tell a real API/DB/filing extraction from news
  numbers hand-packed into JSON ("structured-in-disguise"). The gate passes both. YOU (and the audit) must verify a
  structured finding came from an official DB host (DART/KIPRIS/NTIS/exchange/customs), NOT the same host as a news
  article you already cited. Repackaging the same numbers into json is unstructured wearing a costume.
- **Video genuineness (gate is STRICTER than human judgment).** The `video` shape requires the AV modality
  (`transcript`/`audio`/`video` type) — i.e. you CONSUMED the spoken/temporal content. A bare frame screenshot
  (`type=image`) counts as `semi-structured`, NOT `video`. Auditors counted frame-sampling as "genuine video" ~71%
  of the time; the gate counted it ~6%. Both are defensible — just know the gate's bar: a YouTube URL or a thumbnail
  is never `video`; only a real transcript/caption (or registered frames) is.
- **Truth.** `cite-or-fail` proves a quote EXISTS in the bytes, not that the bytes are correct. The gates never
  judge whether the pick is *actually* alpha — that is the agent's + the adversarial audit's call.

Takeaway: run the gates to filter structure, THEN run an independent (ideally cross-model) audit for genuineness.
A gate PASS is a floor, not a verdict.
