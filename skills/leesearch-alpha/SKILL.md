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
> code persists nouns + counts only. **Spine = bones (deterministic guards), model = brain (assembly + judgment).**

## 알파란 무엇인가 (4다리 — 이걸로 판단하라)

**알파 = 비합의(non-consensus) + 조립(assembly) + 반증가능(falsifiable) + 소멸(decay).** 그럴듯한 요약이 아니다.

1. **비합의** — 남들 답과 *달라야* 한다. **알파 = (내 결론) − (모두가 이미 아는 뻔한/브랜드 답).** 합의 기준선이 없으면 비합의를 잴 수 없다 → 패스 0에서 뻔한 답을 먼저 적는다. ("…총정리/순위 TOP-N" 기사를 받아쓰면 그건 *합의*지 알파 아님.)
2. **조립** — 하나로는 희미하나 다각도로 보면 거대한 신호. 아무도 안 엮는 **공개 파편의 조합.** 엣지는 *접근*이 아니라 *조립*. ← LLM의 비교우위(흩어진 방대한 텍스트를 읽고 동시 보유; 인간은 무명 기록 50개를 안 엮는다).
3. **반증가능** — `predict(resolve_by)`로 박아 **시간이 채점**(비순환 oracle, Brier). "서사"와 알파를 가르는 증명선.
4. **소멸/타이밍** — 알파는 *이르다*. priced-in 되면 사라짐 → `decay`가 "언제 먹나".

핵심 판별: **수렴(convergence)보다 놀라움(surprise).** 모두가 같이 날 거라 *예상하는* 신호 조합은 알파 아님. 아무도 안 잇는 둘이 알파.

## The loop (general — parameterize by thesis, not keywords)
0. **합의 앵커** — 먼저 "이 질문의 뻔한/브랜드 답"을 1줄로 적어라(`frontier note` 또는 thesis `--decay`에). 알파는 그 **델타**다. 뻔한 답을 못 적으면 비합의 측정 불가 = 멈추고 테제 재설정.
1. **Declare a falsifiable THESIS** (`set_hypothesis ... --stakes low|med|high`): the SIGNATURE of the hidden X
   ("hidden powerhouse = {public signal A + B + C converge non-obviously}"). Any domain. **Declare `--stakes` up
   front — it gates EFFORT, not modality**: a `high` thesis the digest later finds at RECON shape gets a loud
   EFFORT-SHORTFALL warning.
2. **Plan the shape matrix BEFORE collecting.** Check your stakes level (Evidence budget below). List which data
   shapes are required and identify at least one concrete source per shape:
   - unstructured: which news/community/review sites to search?
   - semi-structured: which PDF reports, tables, dashboards, or transcripts to capture?
   - structured: which API/DB/filing system to extract from? (DART, patent DB, Google Trends, etc.)
   - video/audio (med/high): what YouTube/platform search query to run?
   **Write the plan as a `frontier_open` note before gathering.** Do not start collecting until you have a source
   for each required shape — "web search only, fix later" is how you get stuck in RECON loops.
3. **Collect across ALL planned shapes** — interleave, don't serialize. Each `record_finding(hypothesis_id,
   polarity=confirms|disconfirms|neutral)` with a verbatim quote (cite-or-fail). Individually unconvincing is fine.
   **The shape comes from the artifact, not the source**: a gov page fetched as HTML = unstructured; the same page's
   table extracted to `.csv` = structured. Earn the shape by producing the artifact.
4. **`triangulate(hypothesis_id)`** — REPORTS independent convergence (distinct host AND modality among confirming
   signals, netted against disconfirming) + `confirming_distinct_claims` (string-near-identical echoes collapsed).
   YOU judge if it's decisive AND **surprising**; code sets no threshold.
5. **Register a FALSIFIABLE `predict(hypothesis_id, ..., resolve_by)`** — the preemptive bet. Don't double-submit:
   a same-deadline near-IDENTICAL re-`predict` is auto-flagged `near_duplicate_of` and dropped from the `distinct`
   count (a re-forecast with a *different* `resolve_by` is genuine, not a dup).
6. **Refine / iterate** — open leads + missing legs via `frontier_open(hypothesis_id)`; next pass adds more PUBLIC
   fragments → re-`triangulate` → convergence GROWS or a leg gets cleanly DISCONFIRMED. Keep digging.

## Evidence budget and data-shape floor
Alpha is not a web-only lookup. It is a cross-shape assembly of public evidence. These are minimum effort gates by
`--stakes`; if the public corpus is genuinely smaller, write that as a RECON limitation with evidence of the search.

| stakes | candidate items | required shapes | per-shape minimum |
|---|---:|---|---:|
| `low` | 12-20 | 2+ shapes | 3 items each |
| `med` | 30-50 | unstructured + semi-structured + structured | 5 items each |
| `high` | 50-100 | unstructured + semi-structured + structured + video/audio (see below) | 5 items each |

### Data shapes defined (by artifact type, not source prestige)
- **unstructured**: HTML page, news article, blog post, forum thread, community review. An official gov page fetched
  as HTML is still unstructured until you extract rows/fields.
- **semi-structured**: PDF report, HTML table with extracted rows, dashboard screenshot with labeled values, video
  transcript/captions (.vtt/.srt), captured page with structured lists.
- **structured**: `.json`/`.csv` extracted from API, database query result, DART/EDGAR filing fields, patent metadata,
  Google Trends export, financial metrics from a data provider. Numbers quoted in a news article do NOT count as
  structured — the article is unstructured; extract the numbers into a structured artifact to count.
- **video/audio**: YouTube video captured via `farm_evidence_run` + `farm_sample_frames`, podcast episode, webinar
  recording, ASR transcript from `leesearch-video-heavy`. Capturing a YouTube page URL counts ONLY if you actually
  read the captured text/captions/frames — a bare URL capture with no content extraction is not video evidence.

### Video/audio/OCR decision protocol (not optional-by-default)
For `med` and `high` stakes:
1. **Search first, decide after.** Do a YouTube/platform search for the topic. Most topics have relevant video.
2. **If relevant videos exist** (and they almost always do): capture at least one via `farm_evidence_run(url)` →
   `farm_sample_frames(url, seconds=[...])` → read the captured text + frame screenshots → `record_finding` with
   verbatim quotes from the video page or transcript.
3. **If no relevant videos exist after searching**: record "video: searched [query], no material results" in the
   ledger. This is legitimate — "searched and found nothing" ≠ "didn't search."
4. **OCR**: required when load-bearing evidence is in scanned documents, infographics, or screenshot-only sources.
   Use `farm_evidence_run` to capture, then read the extracted text. Not required when all text sources are
   machine-readable.

### Minimum quality gates
- 3+ independent eTLD+1 hosts, excluding the subject's own page/press release.
- 1+ disconfirming or adversarial-refutation pass recorded before finalizing.
- 1+ falsifiable `predict(..., resolve_by)` attached to the thesis.
- cite-or-fail passes for the load-bearing claims; gate=OK proves quote presence, not truth.
- ALL required data shapes present with per-shape minimums met.
- Any missing shape → `RECON(<missing-shape>)`, not ALPHA.

## 패스 종료 프로토콜 (digest 후 — RECON으로 *조용히* 끝내지 마라)
`digest`의 스탬프를 읽고:
- **[ALPHA]** → 적대적 반증 1회(아래) → 살아남으면 farm 게이트로 봉인, 끝.
- **[RECON: <이유>]** → 이유별 처방(아래)을 **한 패스 더** 수행(최대 +2 패스). 각 미해소 이유를 `frontier_open`으로 기록(휘발 방지·resumable) → `digest` 재실행 → 위로.
- 한도 도달 OR 벽(JS/BOT/LOGIN/DOWNLOAD)으로 *진짜* 못 닿으면 → 멈추되 **사람에게 구체적 다음 결정을 권유**: "RECON(<이유>). ① <처방>을 한 패스 더 돌릴까요 ② recon-grade로 수용·봉인 ③ 테제 변경. 어느 것?"
- **금지**: RECON을 ALPHA처럼 보고 / NEXT를 비운 채 종료 / 사람에게 다음 수를 안 권하고 끝.

이유 → 처방 (처방은 스킬이 소유; 스핀은 보고만):
| RECON 이유 | 처방 (한 패스 더) |
|---|---|
| `single-modality` | 다른 모달리티 클래스 1개+ 확보: 추출 데이터를 `.json/.csv`(structured), 문서를 `.pdf`, 전사를 `.vtt`로 `ingest`. 같은 web 페이지만 더 모으면 안 늘어남 |
| `missing-structured` | 관청/공시/API에서 수치를 `.json`/`.csv`로 추출. 뉴스 기사 속 숫자 인용 ≠ structured — 원본 DB/API 접근 |
| `missing-semi-structured` | PDF 보고서 캡처, HTML 테이블 추출, 영상 자막 `.vtt` 획득, 대시보드 스크린샷+값 추출 |
| `missing-video` | YouTube/플랫폼 검색 → `farm_evidence_run` + `farm_sample_frames` → 자막/프레임 읽기 → finding 등록. 검색 후 무관하면 "searched [query], not material" 기록 |
| `echoed-claims` | 복붙 에코를 독립 호스트/다른 모달리티의 증거로 교체·통합 |
| `echoed-predictions` | 중복 예측 제거 — 서로 다른 falsifiable 예측만 |
| `no-net-independent-convergence` | 독립 호스트 확증 추가, 또는 반증이 우세하면 가설 약화/폐기 |
| `thin-independence(<3)` | 독립 호스트(eTLD+1)를 ≥3개로 확보. **주체 자신의 페이지·보도자료는 독립 코로보 아님** — 2-host(특히 1개가 주체)는 "확립"이 아니라 후보 |
| `no-falsifiable-prediction` | `resolve_by` 있는 `predict` 1개+ 등록 |
| `no-confirming-signals` | findings를 `--hypothesis`로 연결했는지 확인(현재 0건) |

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
```
Then seal the load-bearing PUBLIC bytes through the farm cite-or-fail gate (browser-agent-mcp-farm).

## 공개(login-free) 신호-TYPE 택소노미 — TYPE은 영속, 소스는 라이브로 발견
신호의 **TYPE**(아래)이 durable하다. 구체적 사이트는 *예시*일 뿐 — 도메인/지역별 **현재 권위 소스를 라이브로 발견**하라(고정 가정 금지; leesearch의 트래픽 기반 소스 선택과 동일 원리).
- **(a) 수주/funding 집중** — 정부 R&D 과제 facet · 공공조달 낙찰 OpenAPI · 공기업 경영공시 · 국정감사 자료 *(KR 예: NTIS·나라장터·알리오)*
- **(b) tech-transfer** — 특허 공동출원/공동양수인 · 기술이전 공시 · 산학 MOU *(예: Google Patents·KIPRIS)*
- **(c) magnitude** — 공시·재무공시 *(예: 대학알리미·DART)*
- **(d) output** — 벤처/창업 공시 · 스핀오프 · 공개 인용·공저 · 졸업생 진로 · 학회 임원
- Generalize: 기업 → 재무공시·특허·채용·뉴스; trends → 검색량·발행일·creator 이동.

## Invariants
- **LOGIN/MEMBER EXCLUDED.** 별점 사이트 · 회원 카페 · 로그인 detail = out of scope (not a lead). Public-only =
  general + reproducible + ToS-clean. Login-edge is *access*, not alpha.
- **Surprise + survive-refutation, not just convergence.** N개가 수렴해도 *뻔하면* 알파 아님. 독립 적대 패스를 통과해야 alpha.
- **독립성 ≥3, self 제외.** 2-host 수렴(특히 1개가 *주체 자신*의 페이지/보도자료)은 ALPHA 아님 — 깔끔해 보이는 "글로벌 1위·>90% 점유" 류 단일출처 주장이 정확히 여기서 걸린다(측정됨). 코드는 호스트만 세니, "그중 하나가 주체 자신인가"는 네가 판단.
- **Wall escalation** (web_quality label): `JS_WALL` → farm browser RENDER (login-free); `BOT_WALL` → stop / reroute
  (no bypass); `LOGIN_WALL` → excluded; `DOWNLOAD_ONLY` → download + local parse. Never silently retreat to 2차 text.
- **EARN the missing data shape** (don't stamp single-modality RECON and stop). See "Evidence budget and data-shape
  floor" above for per-shape minimums. Shape is defined by ARTIFACT TYPE: an official HTML page is `unstructured`
  until you extract rows/fields into `.json`/`.csv` (→ structured) or save a PDF/screenshot (→ semi-structured).
  `RECON: missing-*` tells you exactly which shape to earn next — see the RECON remediation table.
- **cite-or-fail.** Only fetched bytes + verbatim quote. gate=OK proves the quote EXISTS in bytes, not that it's true.
- **Two-brain.** Code = nouns + counts (triangulate) + a label against an OVERRIDABLE definition. "Is this alpha /
  why hidden / when does it decay / where to dig / what's the remedy" = YOU. No immovable methodology in the spine.
- **Continuous = the validation engine.** Every pick registers a `predict`; resolving them over weeks/months earns
  the right to claim the alpha is real (grade_validity at N≥20).
- **Stakes gate EFFORT.** A single-modality 1-pass scrape of a published roundup is RECON, not alpha. At `--stakes
  high`, 50-100 candidate public evidence items and the three-shape floor are the expected effort unless the public
  corpus is demonstrably smaller.
- **Don't out-volume / out-polish a weak input.** The conclusion's grade = the grade of its load-bearing input;
  more findings/words can't raise it. For high stakes, escalate to a structured-authority modality before sealing.
