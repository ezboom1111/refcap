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
last_verified: 2026-06-09
---

# leesearch-alpha — public, continuous ALPHA discovery (router leaf)

> Canonical source (versioned in the refcap repo). Deployed copies: `~/.claude/skills/leesearch-alpha/` and
> `~/.codex/skills/leesearch-alpha/`. Mechanics: refcap `refledger.py` Rank-7 (`set_hypothesis` / `record_finding`
> with `polarity` / `triangulate` / `predict`) + `ALPHA_PLAYBOOK.md`. YOU (the host agent) do the inference; the
> code persists nouns + counts only. **Spine = bones (deterministic guards), model = brain (assembly + judgment).**

## Reference files (read on demand — not all needed every run)
| File | When to read | What's inside |
|---|---|---|
| `evidence-budget.md` | Step 2 (planning shapes) | Data-shape definitions, budget table by stakes, video/OCR protocol, quality gates |
| `recon-remediation.md` | After `digest` shows RECON | RECON reasons, remediation prescriptions, pass termination rules |
| `signal-taxonomy.md` | Step 3 (collecting signals) | Public signal TYPE taxonomy by domain |
| `patterns/consensus-delta.md` | Step 0 (합의 앵커) | How to identify the consensus answer and measure your delta |
| `patterns/cross-source-triangulation.md` | Step 4 (triangulate) | Independent host verification, echo detection, cross-modal corroboration |
| `patterns/shape-extraction.md` | Step 2-3 (planning + collecting) | Practical how-to: DART→csv, YouTube→frames, PDF→semi-structured |

## 알파란 무엇인가 (4다리 — 이걸로 판단하라)

**알파 = 비합의(non-consensus) + 조립(assembly) + 반증가능(falsifiable) + 소멸(decay).** 그럴듯한 요약이 아니다.

1. **비합의** — 남들 답과 *달라야* 한다. **알파 = (내 결론) − (모두가 이미 아는 뻔한/브랜드 답).** 합의 기준선이 없으면 비합의를 잴 수 없다 → 패스 0에서 뻔한 답을 먼저 적는다. ("…총정리/순위 TOP-N" 기사를 받아쓰면 그건 *합의*지 알파 아님.)
2. **조립** — 하나로는 희미하나 다각도로 보면 거대한 신호. 아무도 안 엮는 **공개 파편의 조합.** 엣지는 *접근*이 아니라 *조립*. ← LLM의 비교우위(흩어진 방대한 텍스트를 읽고 동시 보유; 인간은 무명 기록 50개를 안 엮는다).
3. **반증가능** — `predict(resolve_by)`로 박아 **시간이 채점**(비순환 oracle, Brier). "서사"와 알파를 가르는 증명선.
4. **소멸/타이밍** — 알파는 *이르다*. priced-in 되면 사라짐 → `decay`가 "언제 먹나".

핵심 판별: **수렴(convergence)보다 놀라움(surprise).** 모두가 같이 날 거라 *예상하는* 신호 조합은 알파 아님. 아무도 안 잇는 둘이 알파.

## The loop (general — parameterize by thesis, not keywords)
0. **합의 앵커** — 먼저 "이 질문의 뻔한/브랜드 답"을 1줄로 적어라(`frontier note` 또는 thesis `--decay`에). 알파는 그 **델타**다. 뻔한 답을 못 적으면 비합의 측정 불가 = 멈추고 테제 재설정. *(See `patterns/consensus-delta.md` for the procedure.)*
1. **Declare a falsifiable THESIS** (`set_hypothesis ... --stakes low|med|high`): the SIGNATURE of the hidden X
   ("hidden powerhouse = {public signal A + B + C converge non-obviously}"). Any domain. **Declare `--stakes` up
   front — it gates EFFORT, not modality**: a `high` thesis the digest later finds at RECON shape gets a loud
   EFFORT-SHORTFALL warning.
2. **Plan the shape matrix BEFORE collecting.** Read `evidence-budget.md` for stakes-based requirements and shape
   definitions. List which data shapes are required and identify at least one concrete source per shape.
   **Write the plan as a `frontier_open` note before gathering.** Do not start collecting until you have a source
   for each required shape — "web search only, fix later" is how you get stuck in RECON loops.
   *(See `patterns/shape-extraction.md` for practical extraction methods per shape.)*
3. **Collect across ALL planned shapes** — interleave, don't serialize. Each `record_finding(hypothesis_id,
   polarity=confirms|disconfirms|neutral)` with a verbatim quote (cite-or-fail). Individually unconvincing is fine.
   **The shape comes from the artifact, not the source**: a gov page fetched as HTML = unstructured; the same page's
   table extracted to `.csv` = structured. Earn the shape by producing the artifact.
4. **`triangulate(hypothesis_id)`** — REPORTS independent convergence (distinct host AND modality among confirming
   signals, netted against disconfirming) + `confirming_distinct_claims` (string-near-identical echoes collapsed).
   YOU judge if it's decisive AND **surprising**; code sets no threshold.
   *(See `patterns/cross-source-triangulation.md` for echo detection and independence verification.)*
5. **Register a FALSIFIABLE `predict(hypothesis_id, ..., resolve_by)`** — the preemptive bet. Don't double-submit:
   a same-deadline near-IDENTICAL re-`predict` is auto-flagged `near_duplicate_of` and dropped from the `distinct`
   count (a re-forecast with a *different* `resolve_by` is genuine, not a dup).
6. **Refine / iterate** — open leads + missing legs via `frontier_open(hypothesis_id)`; next pass adds more PUBLIC
   fragments → re-`triangulate` → convergence GROWS or a leg gets cleanly DISCONFIRMED. Keep digging.

**Before trusting the stamp, run the deterministic self-check** (the spine is threshold-free by design; the
shape-budget + echo/independence policy lives in these skill-layer validators, NOT in refledger):
```bash
python check_shapes.py $SLUG              # shape budget by stakes (≥3/shape; missing-* = which shape to earn)
python validate_independence.py $SLUG     # ≥3 independent hosts, echo-cluster + host-concentration detection
```
Both exit 1 on failure with the specific gap. A `digest` `[ALPHA]` that fails either validator is NOT alpha —
treat it as RECON and read `recon-remediation.md`. (The validators catch what the spine's advisory label can't:
the per-shape ≥3 floor and press-release echo clusters.)

**After `digest` + self-check pass:** read the stamp. `[ALPHA]` → adversarial review below → seal. `[RECON]` → read
`recon-remediation.md` for the prescription per reason, run one more pass (max +2). If stuck, ask the human.

## 적대적 반증 (alpha 출하 전 필수 — 교차모델이면 최강)
조립이 끝나면 **독립 패스가 그 알파를 REFUTE 시도**한다: "이 결론을 무너뜨릴 공개 증거는? 합의가 사실 맞지 않나? 신호들이 같은 출처의 에코 아닌가? 더 단순한 설명은?"
- **교차모델로 하라**: 당신이 Claude면 Codex(또는 신선한 무맥락 서브에이전트)에게 반박을 시키고 vice versa — *같은 모델의 자기검증은 편향*. 독립 시각 = 비순환(블라인드 저지 원리).
- 반증을 **살아남으면 ALPHA**, 깨지면 RECON/kill. **깨끗한 public DISCONFIRM은 SUCCESS**(꿈의 다리 하나를 제거 = 더 정직한 픽).

## Invocation (refcap CLI — the loop is fully shell-drivable)
```bash
SLUG=$(python refledger.py open "<investigation goal>")
HID=$(python refledger.py hypothesis $SLUG "<thesis>" --signature "<pattern>" --decay "consensus=<뻔한답>; decays when <priced-in>" --stakes high | jq -r .hypothesis_id)
python refledger.py finding $SLUG "<signal>" OBSERVED $AID --quote "<verbatim>" --hypothesis $HID --polarity confirms
python refledger.py triangulate $SLUG $HID          # convergence REPORT (distinct host AND modality + distinct_claims)
python refledger.py predict $SLUG "<falsifiable claim>" 0.6 --by 2027-06-30 --hypothesis $HID
python refledger.py digest $SLUG                     # SUMMARY.md surfaces 가설+삼각측량+예측 + an ALPHA/RECON stamp
python check_shapes.py $SLUG                          # deterministic shape-budget gate (exit 1 = shape gap)
python validate_independence.py $SLUG                 # deterministic independence/echo gate (exit 1 = thin/echoed)
```
Then seal the load-bearing PUBLIC bytes through the farm cite-or-fail gate (browser-agent-mcp-farm).

## Invariants
- **LOGIN/MEMBER EXCLUDED.** Public-only = general + reproducible + ToS-clean.
- **Surprise + survive-refutation, not just convergence.** N개가 수렴해도 *뻔하면* 알파 아님.
- **독립성 ≥3, self 제외.** 2-host 수렴(특히 1개가 주체 자신의 페이지)은 ALPHA 아님.
- **Wall escalation**: `JS_WALL` → farm RENDER; `BOT_WALL` → stop; `LOGIN_WALL` → excluded; `DOWNLOAD_ONLY` → local parse.
- **EARN the missing data shape** — `RECON: missing-*` tells you which shape to earn. Read `evidence-budget.md`.
- **cite-or-fail.** Only fetched bytes + verbatim quote. gate=OK proves quote EXISTS, not truth.
- **Two-brain.** Code = nouns + counts. "Is this alpha / why hidden / when does it decay" = YOU.
- **Continuous = the validation engine.** Every pick registers a `predict`; resolve over weeks/months.
- **Stakes gate EFFORT.** A single-modality 1-pass scrape of a published roundup is RECON, not alpha.
- **Don't out-volume a weak input.** Conclusion's grade = grade of its load-bearing input.
