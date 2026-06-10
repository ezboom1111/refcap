---
name: recon-remediation
description: >-
  RECON diagnosis reasons, remediation prescriptions per reason, and pass termination rules
  for leesearch-alpha investigations that fail to reach ALPHA grade.
metadata:
  type: reference
---

# RECON remediation

Read this file when `digest` stamps `[RECON]`, when `validate_independence.py` exits 1, OR when
`check_shapes.py` reports advisory `missing-*` gaps you judge material (it no longer hard-gates by default).
The **Reason** column below is the EXACT substring the validators emit in their `issues` list — match on that
substring (counts in parens vary, e.g. `thin-independence(1<3)`), then apply the prescription.

## RECON reasons and prescriptions

These appear in the `issues` list emitted by `check_shapes.py` (shape budget) and `validate_independence.py`
(independence/echo). The parenthesised counts are dynamic; match the prefix.

| Reason (issues substring) | Emitter | What it means | Remediation (next pass) |
|---|---|---|---|
| `missing-structured(N<M)` | check_shapes | <min structured artifacts (CSV/JSON/API from official DBs) | Query DART, KIPRIS, NTIS, exchange APIs, patent DBs. Extract to typed file. Don't repackage news numbers into JSON. |
| `missing-semi-structured(N<M)` | check_shapes | <min semi-structured artifacts (PDF tables, dashboard captures) | Find analyst reports, government dashboards, financial statements. Extract labeled tables/values. |
| `missing-video(N<M)` | check_shapes | <min video artifacts despite relevant content existing | YouTube/platform search → `farm_evidence_run` + `farm_sample_frames` + ASR/captions. Register frames + transcript. |
| `missing-ocr(N<M)` | check_shapes | <min OCR artifacts when the domain involves image-based docs | Find scanned PDFs, infographics, presentation slides. Extract text via OCR tools. |
| `total-candidates(N<M)` | check_shapes | total genuine findings below the stakes floor | Collect more across the missing shapes (not more of the same). |
| `dangling-findings(N)` | check_shapes | findings whose artifact row is missing from the ledger | Re-register the cited bytes; the spine's `verify()` also fails on these. |
| `stakes-undeclared(...)` | check_shapes | no hypothesis declared and no `--stakes` override → effort can't be gated | Run `set_hypothesis ... --stakes` first (loop step 1), or pass `--stakes`. |
| `single-modality` | validate_independence | confirming findings span <2 modality classes | Diversify shapes per the budget table in `evidence-budget.md`. |
| `thin-independence(N<M)` | validate_independence | <M independent eTLD+1 hosts among confirming findings | Find sources from different organizations/domains. Same-org mirror sites don't count. |
| `echo-clusters(N)` | validate_independence | N clusters of near-identical findings (press-release echo) | Find primary sources, not derivative coverage. Check bylines and dates. |
| `host-concentration(host=K/T)` | validate_independence | >50% of confirming findings from one host | Spread across more independent domains; the dominant host is over-weighted. |
| `echoed-claims(N->M)` | validate_independence (via spine) | N raw confirming claims collapse to M distinct (copy-paste echoes) | Replace echoes with genuinely distinct sources. |
| `no-falsifiable-prediction` | validate_independence (via spine) | no distinct `predict()` tied to the thesis | Register a `predict(... --by <date>)` — the falsifiable bet. |

**Advisory signals (NOT in the `issues` list — surfaced elsewhere):**
- **`has_disconfirm: false`** (a boolean field in `validate_independence` output) — zero `disconfirms` findings. Not a hard gate, but a pure-confirmation thesis is weak: actively search counter-evidence ("why might this be wrong?").
- **`warning: "HIGH-STAKES EFFORT SHORTFALL"`** (the `warning` field, not `issues`) — stakes=high but an egregious convergence/quality miss. Increase candidate count + shape coverage to match the declared stakes.
- **digest `[RECON: ...]` stamp** — refledger's own advisory label (modality/host/echo/prediction only; it does NOT know the shape budget — that's `check_shapes.py`'s job).

## Pass termination rules

- **Max +2 remediation passes** after the initial RECON diagnosis. If still RECON after pass +2, escalate to the human.
- Each remediation pass must target the specific RECON reason, not repeat the same search.
- A pass that adds 0 new findings toward the missing shape = stop immediately (the source doesn't exist for this topic).
- If remediation succeeds (shape now met), re-run `digest` — it may surface a different RECON reason.
- **Clean RECON is acceptable.** Not every thesis has alpha. A well-documented "searched everywhere, consensus holds" is a valid outcome — stamp it and move on.
