---
name: recon-remediation
description: >-
  RECON diagnosis reasons, remediation prescriptions per reason, and pass termination rules
  for leesearch-alpha investigations that fail to reach ALPHA grade.
metadata:
  type: reference
---

# RECON remediation

Read this file when `digest` stamps `[RECON]`, OR when `check_shapes.py` / `validate_independence.py` exit 1.
The reason strings below match those validators' output exactly (`missing-<shape>`, `single-modality`,
`low-independence`, `echo-clusters`, `host-concentration`). Match the reason and apply its prescription.

## RECON reasons and prescriptions

| Reason | What it means | Remediation (next pass) |
|---|---|---|
| `missing-structured` | <3 structured artifacts (CSV/JSON/API from official DBs) | Query DART, KIPRIS, NTIS, exchange APIs, patent DBs. Extract to typed file. Don't repackage news numbers into JSON. |
| `missing-semi-structured` | <3 semi-structured artifacts (PDF tables, dashboard captures) | Find analyst reports, government dashboards, financial statements. Extract labeled tables/values. |
| `missing-video` | <3 video artifacts despite relevant content existing | YouTube/platform search → `farm_evidence_run` + `farm_sample_frames` + ASR/captions. Register frames + transcript. |
| `missing-ocr` | <3 OCR artifacts when the domain involves image-based docs | Find scanned PDFs, infographics, presentation slides. Extract text via OCR tools. |
| `single-modality` | All findings from one data shape only | Diversify: add the missing shapes per the budget table in `evidence-budget.md`. |
| `low-independence` | <3 independent eTLD+1 hosts among confirming findings | Find sources from different organizations/domains. Same-org mirror sites don't count. |
| `no-disconfirm` | Zero `disconfirms` or `neutral` findings | Actively search for counter-evidence. "Why might this thesis be wrong?" |
| `echo-cluster` | Multiple findings trace to the same original source (press release echo) | Find primary sources, not derivative coverage. Check bylines and dates. |
| `effort-shortfall` | Stakes declared as high/med but effort matches low | Increase candidate count and shape coverage to match declared stakes. |

## Pass termination rules

- **Max +2 remediation passes** after the initial RECON diagnosis. If still RECON after pass +2, escalate to the human.
- Each remediation pass must target the specific RECON reason, not repeat the same search.
- A pass that adds 0 new findings toward the missing shape = stop immediately (the source doesn't exist for this topic).
- If remediation succeeds (shape now met), re-run `digest` — it may surface a different RECON reason.
- **Clean RECON is acceptable.** Not every thesis has alpha. A well-documented "searched everywhere, consensus holds" is a valid outcome — stamp it and move on.
