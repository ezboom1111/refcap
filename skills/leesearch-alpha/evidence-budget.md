---
name: evidence-budget
description: >-
  Data-shape definitions, evidence budget table by stakes level, video/OCR decision protocol,
  and minimum quality gates for leesearch-alpha investigations.
metadata:
  type: reference
---

# Evidence budget and data-shape floor

Read this file when planning the shape matrix (loop step 2) or when `digest` flags a shape gap.

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

- "candidates" = `record_finding` calls across ALL shapes, not just web hits.
- One-item shapes are checkbox compliance, not real diversity.
- `digest` flags `RECON: missing-<shape>` when a required shape has <3 items.

**This table is mechanically enforced.** Run `python check_shapes.py <run_dir>` — it reads the ledger, infers
stakes from the hypothesis (or `--stakes` override), and exits 1 with `missing-<shape>(N<min)` for any unmet
floor. Don't eyeball the budget; run the gate.

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
