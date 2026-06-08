---
name: leesearch-alpha
description: >-
  Lee's ALPHA-discovery branch (이지범's personal alpha router leaf). Invoke when the user wants the NON-OBVIOUS,
  preemptive edge — "find the hidden / mispriced / underrated X that others miss", "숨은 꿀 / 저평가 / 남들 모르는".
  Unlike plain research (which retrieves documented facts), this ASSEMBLES scattered PUBLIC fragments into an
  inference no single source states, registers a FALSIFIABLE prediction, and KEEPS digging across passes until
  convergence or decay. Login/member data is EXCLUDED (not general, ToS-grey, not the edge — the edge is ASSEMBLY,
  not access). General: works for hidden companies / researchers / labs / trends, not one domain. Say
  "leesearch-alpha <thesis>" to force it. Backed by refcap's Rank-7 alpha layer + ALPHA_PLAYBOOK.
when_to_use: >-
  Any "find the hidden/underrated/mispriced X by assembling public clues" request — where the answer is an
  inference from many weak public signals, not a lookup, and you want a falsifiable, continuously-refined,
  reproducible (public-only) alpha pick rather than the obvious brand answer.
---

# leesearch-alpha — public, continuous ALPHA discovery (router leaf)

> Canonical source (versioned in the refcap repo). Deployed copies: `~/.claude/skills/leesearch-alpha/` and
> `~/.codex/skills/leesearch-alpha/`. Mechanics: refcap `refledger.py` Rank-7 (`set_hypothesis` / `record_finding`
> with `polarity` / `triangulate` / `predict`) + `ALPHA_PLAYBOOK.md`. YOU (the host agent) do the inference; the
> code persists nouns + counts only.

Alpha = a non-obvious, preemptive conclusion that NO single source states, inferred by assembling **public**
fragments others do not combine. The edge is in the ASSEMBLY. Use this when "the obvious answer is the brand
answer" and the real pick is hidden in scattered public records.

## The loop (general — parameterize by thesis, not keywords)
1. **Declare a falsifiable THESIS** (`set_hypothesis ... --stakes low|med|high`): the SIGNATURE of the hidden X
   ("hidden powerhouse = {public signal A + B + C converge non-obviously}"). E.g. labs/companies/researchers/
   trends — any domain. **Declare `--stakes` up front — it gates EFFORT, not modality** (stakes contract invariant):
   a `high` thesis the digest later finds at RECON shape gets a loud EFFORT-SHORTFALL warning.
2. **Gather WEAK public signals** by signal-type (see taxonomy), each `record_finding(hypothesis_id, polarity=
   confirms|disconfirms|neutral)` with a verbatim quote (cite-or-fail). Individually unconvincing is fine.
3. **`triangulate(hypothesis_id)`** — REPORTS independent convergence (distinct host AND modality among confirming
   signals, netted against disconfirming) + `confirming_distinct_claims` (string-near-identical echoes collapsed —
   copy-paste of one signal from 2 hosts ≠ 2 independent claims). YOU judge if it's decisive; code sets no threshold.
4. **Register a FALSIFIABLE `predict(hypothesis_id, ..., resolve_by)`** — the preemptive bet, resolved by a future
   public outcome. This is what makes it alpha (early + falsifiable) and seeds grade_validity (N→20). Don't double-
   submit: a same-deadline near-IDENTICAL re-`predict` is auto-FLAGGED `near_duplicate_of` and excluded from the
   digest's `distinct` count (a re-forecast with a *different* `resolve_by` is genuine, not a dup).
5. **Refine / iterate** — open leads + missing legs via `frontier_open(hypothesis_id)`; next pass adds more PUBLIC
   fragments → re-run `triangulate` → convergence GROWS or a leg gets cleanly DISCONFIRMED. Keep digging.

## Invocation (refcap CLI — the loop is fully shell-drivable)
```bash
SLUG=$(python refledger.py open "<investigation goal>")
HID=$(python refledger.py hypothesis $SLUG "<thesis>" --signature "<pattern>" --decay "<why-hidden/when-decays>" --stakes high | jq -r .hypothesis_id)
# ingest a PUBLIC source -> register -> tag a weak signal to the thesis:
python refledger.py finding $SLUG "<signal>" OBSERVED $AID --quote "<verbatim>" --hypothesis $HID --polarity confirms
python refledger.py triangulate $SLUG $HID          # convergence REPORT (distinct host AND modality + distinct_claims)
python refledger.py predict $SLUG "<falsifiable claim>" 0.6 --by 2027-06-30 --hypothesis $HID
python refledger.py digest $SLUG                     # SUMMARY.md surfaces 가설+삼각측량+예측 + an ALPHA/RECON stamp
```
Then seal the load-bearing PUBLIC bytes through the farm cite-or-fail gate (browser-agent-mcp-farm).

## PUBLIC (login-free) source taxonomy
- **(a) 수주/funding concentration**: NTIS public project facets · 나라장터 g2b 낙찰결과(OpenAPI) · 알리오 · 국정감사 자료
- **(b) tech-transfer**: Google Patents / KIPRIS public co-assignee · 기술이전 공시 · 산학 MOU 보도자료
- **(c) magnitude**: 공시(대학알리미 값은 뉴스/PDF 미러) · DART · BK21 공개명단
- **(d) output**: 벤처확인 공시 · 창업/스핀오프(뉴스·DART) · Scholar/DBpia 공개 인용·공저 · 졸업생 진로(홈피) · 학회 임원
- Generalize: for companies → DART·특허·채용·뉴스; for trends → 검색량·발행일·creator 이동.

## Invariants
- **LOGIN/MEMBER EXCLUDED from the path.** 김박사넷 별점 · 블라인드 · 회원 카페 · 로그인 detail = out of scope (not a
  lead, not "ask the user"). Public-only = general + reproducible + ToS-clean. Login-edge is *access*, not alpha.
- **Wall escalation** (web_quality label): `JS_WALL` → farm browser RENDER (login-free); `BOT_WALL` → stop / reroute
  (no bypass); `LOGIN_WALL` → excluded; `DOWNLOAD_ONLY` → download + local parse. Never silently retreat to 2차 text.
- **Convergence, not a single source.** Rank by how many INDEPENDENT public signal-types + modalities converge.
- **cite-or-fail.** Only fetched bytes + verbatim quote. A clean public DISCONFIRM (a dream leg killed) is a SUCCESS.
- **Two-brain.** Code = nouns + counts (triangulate). "Is this alpha / why hidden / when does it decay / where to
  dig next" = YOU. No threshold in code.
- **Continuous = the validation engine.** Every pick registers a `predict`; resolving them over weeks/months is how
  the system earns the right to claim its alpha is real (grade_validity at N≥20).
- **Stakes gate EFFORT; recon ≠ alpha.** The digest stamps each thesis **ALPHA** or **RECON** mechanically from the
  alpha layer's OWN definition (≥2 modalities, no echoed claims, net independent convergence, ≥1 falsifiable
  predict). A single-modality 1-pass scrape of a *published roundup* is **RECON, not alpha** — the digest says so,
  and at `--stakes high` it adds an EFFORT-SHORTFALL warning. Do NOT label a low-effort recon as an alpha pick.
  (This is why the real failure mode is rarely "input grade too low" and usually **stopping at pass 1 + an obvious
  thesis** — a roundup article titled "…총정리" is the OPPOSITE of an assembled-from-fragments edge.)
- **Don't out-volume / out-polish a weak input.** A fired cite-or-fail gate on a low-grade page (gate=OK on a news
  headline) certifies the quote exists, NOT that it's authoritative — it makes weak look verified. For a `high`
  stakes pick, escalate to the structured-authority modality (NTIS/DART/공시/PDF) before sealing, don't pad the
  news leg. The conclusion's grade = the grade of its load-bearing input; more findings/words can't raise it.
