---
name: leesearch
description: >-
  Lee's research route-table (이지범's personal layer). Invoke when research conclusions must be
  TRACEABLE / RE-VERIFIABLE (farm-sealed bundle, cited numbers that survive scrutiny, alpha picks,
  resumable multi-source digs) — or when unsure which research executor fits. Do NOT invoke for a
  quick lookup or casual question: answer those with native search/research directly, no ceremony.
  Operating principle: GATHER with the host's native abilities (search, deep-research, consented
  browser), SEAL the load-bearing few claims through the browser-agent-mcp-farm gate. Say
  "leesearch <goal>" to force it.
when_to_use: >-
  Research where the output feeds a real decision, document, or dispute — i.e. it needs cited,
  hash-verifiable evidence or a resumable ledger. For throwaway questions, skip this and answer natively.
last_verified: 2026-06-10
---

# leesearch — route table (not a router)

> Canonical source (versioned in the refcap repo). Deployed copies live at `~/.claude/skills/leesearch/`
> and `~/.codex/skills/leesearch/`. You (the host agent) are the brain — this file is a map plus
> locale-specific facts you cannot infer. Classification is YOUR judgment, not a decision tree's.

**Operating principle: 수집은 네이티브, 봉인은 farm.** Gather with whatever is cheapest and best
(native web search / deep-research, consented browser, free APIs). Then seal only the load-bearing
few claims: register exact bytes → `farm_add_claim` (anchor = verbatim quote) → `farm_run_claim_gate`
→ `farm_export_bundle` (auto-verified on export). The farm is the VERIFIER, never the understanding engine.

## Intent lock before focused capture / alpha

Before any **focused 탐색**, trend read, competitor/price scrape, design/UI teardown, or Alpha Fusion
run, first lock the user's intent. Do **not** capture every modality just because the farm can.
If the request does not make the target decision and evidence shape obvious, ask 2-4 concise
questions before gathering.

Lock these fields:
- `decision_needed`: what the answer will be used for (alpha pick, price compare, design teardown,
  user-pain mining, trend watch, source verification, etc.).
- `target_scope`: entity/product/person/place, geography/language, time horizon, and must-include /
  must-exclude sources.
- `evidence_shapes`: which modalities matter: text/HTML, structured prices/API fields, UI screenshot
  or layout, OCR/image text, video frames, served captions/transcript, audio/ASR, map/place state, or
  byte-faithful BYO.
- `success_criteria`: what would count as useful, surprising, or decision-changing.
- `boundaries`: login/profile permission, BYO allowance, and anti-bot/paywall/CAPTCHA refusal line.
- `do_not_close_yet`: set true when this is active research/planning and the outcome is not ready.
- `closeout_hook`: what future signal would close the work as useful, abandoned, adopted, refuted,
  or still pending.
- `lifecycle_hint`: how the run should be treated if it goes quiet. Inferred lifecycle states are
  draft-only hints (`likely_closed`, `dormant`, `resurfaced`, `outcome_candidate`) and must not
  auto-apply canon success/failure.

Default behavior when the user does not answer:
- For T0/T1 low-risk work, continue with explicit provisional assumptions and label gaps.
- For Alpha Fusion, do not stamp `ALPHA` from an under-specified intent. Mark it `RECON(<gap>)`
  until the missing intent/evidence shape is resolved.
- For visual/audio/video/design claims, do not infer from text-only capture. Route to screenshots,
  OCR/frame sampling, served captions, or `leesearch-video-heavy` as appropriate.
- If the user gives `closeout_hook` / `lifecycle_hint`, preserve it in the run report or closeout
  draft. Let `loop lifecycle-hints` / vault closeout tooling score stale/resurfaced candidates;
  do not turn lifecycle hints into durable skill rules.
- When using `browser-agent-mcp-farm` directly, pass the lock into the run (`--intent`,
  `--intent-scope`, `--intent-shapes`, `--success-criteria`, `--intent-boundaries`). The farm now
  consumes this soft lock: `ui_screenshot` / `ocr_image_text` / `map_place_state` force browser full
  capture instead of tier-0 HTTP/cache replay, and OCR falls back to the page screenshot when no frame
  screenshots exist. Search-result surfaces also emit `search_result_candidates` with ranked titles,
  URLs, matched query terms, and screenshot-presence signals. Each run also emits
  `search_strategy_plan` search arms (current surface, cross-check, visual/review/community/video
  leads, dissent probe) and, when candidates exist, a `candidate_deepening_ledger` that selects a
  small follow-up queue. Read those artifacts before opening more destinations; if the plan shows
  underspecified intent or the ledger cannot choose between visual/audio/price/design/alpha goals,
  ask the user instead of widening blindly. For a completed farm search run, use
  `node .\dist\cli.js search-followups --run-dir <runDir>` to write a bounded plan/outcome ledger;
  add `--execute` only when deliberate follow-up capture is wanted. Add `--child-final-claim-gate`
  only when the child run's generated claims should be proof-gated; otherwise child runs are
  exploratory collection. This is not a platform crawler.

## Primary content completion rule

When the user asks to analyze content, strategy, BM, UI/UX, marketing, trend, alpha, or "what is
useful here", do not count landing/profile/watch/search pages as deep reading. First translate the
intent into content units, then either capture the matching primary artifact or mark the source as
`URL_ONLY` / blocked and do not claim analysis.

Minimum primary artifacts:
- spoken video/audio: `TRANSCRIPT` from served captions or ASR;
- visual video/shorts/demo/chart: timestamped frame screenshots and, when text matters, `FRAME_OCR`;
- thumbnail/image/design/UI/layout: screenshot or image artifact, with OCR/visual inspection when
  text or layout carries the claim;
- social/community: target post/thread/replies `THREAD_TEXT`, not just a profile/feed page;
- article/blog/page: main body `PAGE_TEXT`, not only title/meta/search result;
- paper/report: relevant section `PDF_TEXT` or page body text;
- API/market/price/trend data: `API_SCHEMA` for capability claims and `TIMESERIES`/snapshots for
  behavior-over-time claims;
- code/notebook/strategy rule: `CODE_READ` plus the concrete rule/config/function if it drives the
  conclusion.

This is a completion check, not a platform harness. Use it to keep the agent from stopping at cheap
page text when the user's decision depends on primary content.

## Large-run source registry (anti-overclaim, not a harness)

For any request that asks for many sources (`30+`, `100+`, "trend", "alpha", "비정형/정형/반정형",
multi-platform, multi-modal, or resumable digging), create or update a lightweight source registry
before synthesis when practical. This can be `<project>/cache/source_registry.jsonl`, a run-local
ledger, or a project-specific intake script. Discovery still comes from native search, public APIs,
user seeds, and platform exploration; the registry only dedupes, records status, and keeps the model
from rereading the same source.

Minimum fields: `url`, `query_or_seed`, `source_platform`, `source_type`, `evidence_state`, `status`,
`duplicate_of`, `blocker_or_rejected_reason`, `next_probe`.

Use these evidence states when reporting coverage:
- `URL_ONLY`: link/title/result only.
- `PAGE_TEXT`: page body/article text read.
- `PDF_TEXT`: PDF/body text extracted.
- `THREAD_TEXT`: public thread/comments read.
- `TRANSCRIPT`: served captions or ASR transcript read.
- `FRAME_OCR`: image/video frame or screenshot OCR inspected.
- `API_SCHEMA`: API docs/schema inspected.
- `TIMESERIES`: structured rows/snapshots collected.
- `CODE_READ`: code/notebook/config read.
- `SEALED`: load-bearing bytes gated by farm.

Strict wording rule: source type is not evidence. A YouTube URL is not `TRANSCRIPT`; an API docs page
is not `TIMESERIES`; a social URL is not `THREAD_TEXT`. Say `URL_ONLY scanned`, `PAGE_TEXT read`,
`TRANSCRIPT read`, `FRAME_OCR inspected`, `TIMESERIES collected`, or `SEALED gated` as applicable.
Never claim "watched/read/analyzed the video/thread/API data" from source labels alone.

Keep exploration alive: for alpha/trend work, leave budget for wildcard, dissent, failure-story,
origin-trace, and adjacent-market leads. The registry prevents duplicate work and overclaiming; it
does not rank truth, choose the alpha, or become canon.

## Report closeout contract

For T1/T2 multi-source reports, show trust status before final conclusions. Keep this visible and
short; it is a state board, not a scoring engine.

- `Run State`: `DISCOVERY_ONLY` / `PARTIAL_READ` / `DEEP_READ` / `QA_PASSED` / `SEALED`.
- `Evidence Coverage`: counts by `evidence_state` (`URL_ONLY`, `PAGE_TEXT`, `TRANSCRIPT`, `SEALED`,
  etc.).
- `Trust Boundary`: label cited support as `internal_memory`, `registry_*`, `sealed_farm`, or
  `unsupported`.
- `Claim x Evidence Matrix`: map the load-bearing 3-7 claims to source_registry entries and mark
  whether the evidence state is sufficient.
- `Not Claimable Yet`: list conclusions blocked by `URL_ONLY`, missing transcript, missing
  timeseries, blocked source, or unsealed evidence.
- `Top 3 Deepening Candidates`: state why it matters, current evidence_state, minimum promotion
  step, and whether BYO/profile is optional if blocked.

Do not use numeric confidence, source-quality, or alpha scores unless the user explicitly asks.
Prefer visible evidence states and short sufficiency labels.

## Route table

| Source / need | Executor |
|---|---|
| YouTube **with** served captions, cheap trend numbers / spoken gist | `youtube-research` (caption-first, free APIs, no download, no ASR) |
| Quantitative **time-series** need (velocity / decay of anything trackable) | `refcap/trendwatch.py` (standalone collector utility, NOT part of this skill's ceremony — see its docstring) |
| Video **without** captions / foreign VO / TikTok·IG·non-YouTube / deep resumable dig | `leesearch-video-heavy` (refcap: whisper ASR, OCR, frames, resumable ledger) |
| Competitor / pricing / market-size numbers | farm directly with the `market_scan` claim types (see farm SKILL.md "Lens claim types") — corroborate across independent eTLD+1 domains |
| User-pain / feature-gap / voice-of-customer | farm directly with the `product_planning` claim types (same section) |
| Generic web / PDF / dashboard / long article | native gather (deep-research, WebSearch/WebFetch, `claude-in-chrome`) → seal load-bearing claims via farm. For a full gather→refute→seal→verify pass in one shot, run the `sealed-research` workflow (`Workflow({scriptPath: "~/.claude/workflows/sealed-research.js", args: {question, projectDir}})`) |
| Pages you already know, need tamper-evident bundle | `browser-agent-mcp-farm` directly (`farm_evidence_run`) |
| Hidden / underrated / mispriced ("숨은 꿀 / 저평가 / 선제적 알파") | **Alpha Fusion**: `leesearch-alpha` owns the thesis loop (hypothesis → findings → triangulate → predict → digest); YOU fan out sources across data shapes. Never stamp ALPHA from a single-leaf web-only run |

**Invariant: one executor per source** (never light + heavy on the same clip), not one executor per investigation.

## Effort ladder (token/thinking efficiency = accuracy devices PROPORTIONAL to stakes, never ceremony)

Pick the tier by what the answer feeds — and name the tier you picked in one line:
- **T0 quick** (throwaway question): answer natively, cite links inline. No farm, no run dir, no ledger.
- **T1 standard** (default when this skill is invoked): gather natively; for every LOAD-BEARING claim,
  cross-check across **≥2 independent sources** (same press release echoed = 1 source) and run one
  cheap refutation pass ("what would make this wrong?"). Cite links. Still no farm unless T2 triggers.
- **T2 sealed** (output feeds a decision / document / dispute / share): T1 + register exact bytes and
  gate the load-bearing few (`farm_add_claim` → `farm_run_claim_gate {strictProvenance:true}` →
  `farm_export_bundle`), or run the `sealed-research` workflow for the whole pass.

Accuracy mechanisms are tier-independent METHOD, not domain features: independent-source collapsing,
refutation before reporting, byte-grounded quotes (never paraphrase a number you'll cite), honest gaps
("찾지 못함" beats a guess). Escalate a tier mid-run the moment a number becomes load-bearing; never
run T2 ceremony on a T0 question.

## Alpha Fusion notes (the rest lives in `leesearch-alpha`)

- Declare the consensus baseline first; alpha = delta from it.
- If the user's goal could mean different alphas (price, design, distribution, creator momentum,
  product gap, sentiment, media/audio signal), ask before collecting. The edge depends on the
  decision, not on grabbing more bytes.
- Open a shape matrix (unstructured / semi / structured / video-audio / OCR — defined in
  `leesearch-alpha/evidence-budget.md`). For video: SEARCH first (30s), then judge materiality —
  "I didn't look" ≠ "not material". Capture only what is actually material.
- Shape/candidate budgets are **ADVISORY signals, not hard gates** (`check_shapes.py` warns by
  default; `--strict` restores exit-1 for when an external contract demands it). The measured
  failure mode of hard quotas: news repackaged as JSON to fill the `structured` slot (~36% genuine
  in QA). Genuineness comes from provenance + an independent adversarial audit, not from counts.
- ALPHA stamp still requires: 3+ independent eTLD+1 hosts, ≥1 disconfirming pass, ≥1 falsifiable
  `predict(resolve_by)`, cite-or-fail on load-bearing claims. Otherwise label `RECON(<gap>)`.

## 소스 선택 — METHOD only, no frozen lists

**영원한 플랫폼은 없다.** This file holds *how to find* sources, never *which platforms matter*:
- **트렌드/플랫폼 의존 조사일 때만** "현재 이 도메인·지역 상위 플랫폼"을 LIVE로 발견 (랭킹 소스 ≥2 교차,
  수치 cite-or-fail). 플랫폼이 답과 무관한 조사(가격 정책, 단일 기업 분석 등)에는 이 선행 사이클을 붙이지 마라.
- 발견 결과는 captured-at + TTL(~30일, 트렌드면 짧게)로 `<project>/cache/sources.json`에 캐시; 만료 시 재발견.
- 전파 역할 구조(원발→증폭→종착)는 heuristic — 현재 점유율로 재확인, 과거 숫자 받아쓰기 금지.

## 한국 소스 벽 (측정 2026-06-09 · 벽은 변함 — 막히면 재측정)

- **Acquisition tiers**: farm은 source별 가장 싼 viable tier를 고른다
  (`official_api → feed → http_fetch → model_extract → profile → headed → byo_capture`).
  anti-bot/로그인 소스는 `headed_only` — farm은 자율로 뚫지 않는다 (lawful-refusal, 설계).
  **http_fetch가 403/빈껍데기면 멈추지 마라** → `profile`(동의된 로그인 세션) 또는 `byo_capture`
  (네가 실브라우저로 캡처, farm이 바이트 검증). 자율 봇/CAPTCHA 우회 금지.
- **리뷰 조사**: 벽 낮은 소스부터 — 앱스토어 리뷰(공식 API), 커머스 리뷰, 무로그인 커뮤니티,
  지도 리뷰, 유튜브 리뷰영상(→heavy). 네이버 PLACE 리뷰는 farm `naver_place_apollo` 추출기로 잡히지만
  **BLOG 본문은 iframe(PostView)이라 빈 껍데기** → profile/byo로 iframe 본문까지, 카페=로그인=profile 전용.
  해법은 "네이버를 뚫어라"가 아니라 "접근가능 소스 다변화 + 벽은 profile/byo".
- **소셜/로그인벽 (클래스로 다뤄라)**: 자율 tier는 프로필 META만 줌 — 본문은 동의 브라우저
  (Claude=`claude-in-chrome`, 일반=headed/profile)로 보고 farm이 검증(=byo_capture). 동의 브라우저
  자체의 도메인 allowlist에 막히면(네이버가 그랬다) human byo나 대체원으로. 크리에이터 추세는
  cross-platform 삼각측량 + 공개 분석 사이트로 보강.

## Invariants (every route)

- **Seal the load-bearing few, not everything.** Casual questions never enter the farm.
- **gate=OK ≠ true.** cite-or-fail proves the quote exists in registered bytes, not that the bytes
  are correct. Corroborate the highest-stakes number across INDEPENDENT domains.
- **Anti-bot/login = profile/byo_capture, never autonomous bypass.** A "403, 1–3 originals" result
  on a walled source means the run skipped profile/byo — not that the answer is unreachable.
- **An honest gap beats a guess.**

## 출력 폴더링 계약 (필수 — 평면 덤프 금지)

한 조사 = **하나의 프로젝트 루트** 아래로 전부 (run마다 최상위 형제 폴더 금지 — 174MB·50형제 mess의 원인):
```
<project>/
├─ INDEX.md                    # 맵: 각 run이 뭔지 + reports 포인터 (조사 끝에 갱신)
├─ reports/                    # 사람이 읽는 합성 .md
├─ inputs/                     # 사용자 원본
├─ cache/                      # 비-연구물 (sources.json, tessdata 등 공유 캐시)
└─ runs/
    ├─ farm/<entity>/<slug>/   # farm 캡처 번들
    └─ leesearch/<slug>/       # leesearch/refledger run
```
규칙: ① run의 `base`/runDir는 반드시 `<project>/runs/<tool>/...` 아래. ② 합성 .md는 `reports/`.
③ 끝에 `INDEX.md` 갱신(또는 `python refledger.py digest`). ④ 공유 모델/캐시는 `cache/`로.
