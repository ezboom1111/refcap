---
name: signal-taxonomy
description: >-
  Public signal TYPE taxonomy for leesearch-alpha. Classifies observable signal types
  by domain to guide collection in loop step 3.
metadata:
  type: reference
---

# Signal TYPE taxonomy (public signals only)

Read this file when collecting findings (loop step 3) to ensure you're covering the right signal types for the domain.

## General signal types (domain-agnostic)

| Type | Examples | Shape |
|---|---|---|
| **regulatory** | Filings, patents, licenses, government approvals, compliance records | structured / semi |
| **financial** | Revenue, funding rounds, exchange filings, analyst estimates | structured |
| **operational** | Hiring patterns, office expansions, partnership announcements | unstructured |
| **technical** | Papers, GitHub repos, conference talks, patent claims | semi / video |
| **social** | Community sentiment, review trends, forum discussions | unstructured |
| **media** | News coverage, interviews, podcast mentions, YouTube features | unstructured / video |
| **market** | Market share data, competitor movements, industry reports | semi / structured |

## Domain-specific additions

**Tech/startup**: GitHub stars trajectory, npm downloads, job postings (tech stack reveals), API changelog frequency, developer conference mentions.

**Pharma/biotech**: Clinical trial registrations (ClinicalTrials.gov), FDA/MFDS filings, patent expiry cliffs, pipeline advancement signals, KOL presentation slides.

**Manufacturing/export**: HS code trade data (customs), factory capacity announcements, raw material price correlations, logistics route changes.

**Content/creator**: Platform analytics (Social Blade, PlayBoard), sponsorship deal signals, cross-platform migration patterns, audience demographic shifts.

**Government/policy**: Budget allocations (열린재정), audit reports (감사원), legislative calendar, public comment periods, grant program announcements.

## Using the taxonomy

1. Identify your thesis domain(s) from the list above.
2. For each signal type relevant to your thesis, identify at least one concrete source.
3. Map each source to a data shape (the artifact you'll produce, not just the source).
4. This becomes your shape matrix input for loop step 2.

The taxonomy is a **starting checklist**, not an exhaustive list. Novel signal types that don't fit any category are often the most valuable alpha signals.
