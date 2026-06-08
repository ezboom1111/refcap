---
name: cross-source-triangulation
description: >-
  Independent host verification, echo detection, and cross-modal corroboration procedures
  for leesearch-alpha triangulation (loop step 4).
metadata:
  type: reference
---

# Cross-source triangulation pattern

## When to use
Loop step 4, when running `triangulate(hypothesis_id)` and judging whether convergence is genuine.

## Independence verification

1. **eTLD+1 rule.** Two findings from `news.example.com` and `blog.example.com` = 1 independent source, not 2. The code reports distinct hosts; YOU check if they're truly independent organizations.

2. **Self-exclusion.** If your thesis is about Company X, findings from Company X's own website/blog/press releases don't count toward independence. They're the subject's self-report, not independent verification.

3. **Minimum independence.** ALPHA requires ≥3 independent eTLD+1 hosts among confirming findings. 2-host convergence (especially when one is the subject itself) is RECON.

## Echo detection

Press releases and wire services create echo clusters — the same content republished verbatim across 20 sites looks like 20 independent confirmations but is really 1.

1. **Check publication dates.** If 5+ articles appeared within 24 hours with nearly identical text, they're echoing a single source (usually a press release or wire service).

2. **Check bylines.** "Staff reporter" or no byline + identical text = wire echo.

3. **Check the `confirming_distinct_claims` count.** The code collapses string-near-identical claims. If your 15 findings collapse to 3 distinct claims, you have 3 pieces of evidence, not 15.

4. **Trace to primary.** Find the original source being echoed. That's your 1 real finding; the echoes are noise.

## Cross-modal corroboration

The strongest triangulation: the same fact confirmed by DIFFERENT data shapes.

- Financial filing (structured) + analyst report (semi) + news article (unstructured) all confirming the same number = strong.
- Three news articles (all unstructured) from different sites = moderate (same shape, so could be same wire source).
- A video interview (video) where the CEO states a number that matches the filing = very strong (hard to fake across modalities).

Prioritize cross-modal over same-modal convergence when judging whether triangulation is decisive.
