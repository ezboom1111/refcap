# Whole-spine ADVERSARIAL stress campaign — 500 scenarios (2026-06-07)

User ask: "/loop 500 x10 — is this skill appropriate? generate 50, verify, fix, repeat." Reframed honestly:
a loop validates **mechanism robustness** (does the spine crash / mis-grade / drift?), NOT **insight-validity**
(grade_validity needs REAL future outcomes, N>=20 — un-loopable). This campaign is the former.

## Method
10 themed adversarial agents (878k tokens) each wrote 50 scenarios targeting a different surface + the
session's new code (`_shingles` `_EN_STOP`, `n_premature`, `conclusion_id`). Expecteds reasoned from INTENT
(RANK6_SPEC), then executed through the REAL spine via `run_stress.py` (two deterministic probes: `grade`
= full ledger->grade_conclusion across breadth/recency/consistency/source_type/overall; `calib` =
predict/resolve->calibration incl. n_premature). 500 valid lines, 0 malformed, 0 dup ids.

## Result: 500 run -> 2 REAL bugs found + fixed (TDD)
First run: 498 PASS / 2 FAIL. After fixes: residual 3 "fails" all benign (see below). **0 real regressions.**

| Real bug | Surface | Fix |
|---|---|---|
| **IP-literal false collapse** — `_host` applied eTLD+1 (last-2-labels) to raw IPv4, so `1.2.3.4` & `9.8.3.4` both -> `3.4` -> falsely collapse -> UNDER-count breadth independence | `_host` (independence) | `ipaddress.ip_address(h)` guard returns the IP whole (eTLD+1 is meaningless for IPs). stdlib, already imported. |
| **decimal/int false conflict** — `3.0` vs `3` kept as distinct strings `{3.0}!={3}` -> false numeric conflict -> false SHORTFALL (realistic: "3.0%" vs "3%") | `_numeric_conflicts` (consistency) | `_canon_num` normalizes to numeric VALUE (`3.0`==`3`, `1,234`==`1234`; whole values render without `.0`). Mechanical only; agent still adjudicates. |

## Residual 3 "fails" — all benign (triaged)
- `g2_009`, `g2_027` (IP): expected SHORTFALL because the agent **pinned the OLD buggy collapse**; the fix
  correctly makes distinct IPs distinct (MEETS). The fix is right; the pin is now stale. = fix working.
- `g4_007` (`1e6` vs `2e6`): ORACLE ERROR — 1e6 (1M) and 2e6 (2M) are genuinely different values, so the
  conflict IS correct. The agent mislabeled it a "false-conflict trap." Code is right. (Sci-notation
  tokenization is imperfect but produces no wrong OUTCOME in realistic cases; `_NUM_RE` left unchanged on
  purpose — the strategic review flagged its divergence from refinsight `_num` as intentional.)

## Per-theme (post-fix): 8 grade + 2 calib themes, 497/500 clean
`G1_independence_filler 50/0 · G2_host_collapse 48/2(IP pins) · G3_recency_dates 50/0 ·
G4_consistency_conflict 49/1(1e6 oracle) · G5_overall_fatal 50/0 · G6_standard_coherence 50/0 ·
G7_source_type 50/0 · G8_combined_realistic 50/0 · C9_calibration_math 50/0 · C10_premature_honesty 50/0`

## Verdict on "is the skill appropriate?" (mechanism dimension)
The deterministic kernel held up under 500 mean/adversarial inputs: the recency 4-state, overall fatal-domain
rollup, host clustering (subdomain/co.kr/multi-suffix/www/echo/empty), source-type, standard coherence, and
the new n_premature/conclusion_id surfaces were all correct. Two genuine edge bugs (raw-IP host, decimal
conflict) found + fixed. This is the 4th QA campaign; the real-bug rate keeps dropping (116->9, 300->2,
300->2, 500->2) = the mechanism is converging. **What a loop CANNOT validate stays open: whether a MEETS
grade actually tracks reality (grade_validity, needs real resolved predictions over weeks/months).** That is
the binding constraint, and it is DATA-gated, not code-gated. Repro: `python run_stress.py scenarios_stress.jsonl`.
