---
name: leesearch
description: >-
  Lee's research route-table (이지범's personal layer). Invoke when research conclusions must be
  TRACEABLE / RE-VERIFIABLE (farm-sealed bundle, cited numbers that survive scrutiny, alpha picks,
  resumable multi-source digs) — or when unsure which research executor fits. Do NOT invoke for a
  quick lookup or casual question you can answer from knowledge: answer those natively, no ceremony.
  BUT reading a specific login-walled social post (X thread/long-form, TikTok, Instagram) — even ONE,
  even casual — is NOT a native lookup: native fetch silently truncates (~280 chars) or bot-gates and
  the agent flails (measured 2026-07-20: casual login-wall reads failed ~43%, one burned 5 dead
  attempts while the installed opencli adapter sat unused). Check this route-table's adapter tier
  first for those. Operating principle: GATHER with the host's native abilities (search, deep-research,
  consented browser) + opencli adapters for login-walled sources, SEAL the load-bearing few claims
  through the browser-agent-mcp-farm gate. Say "leesearch <goal>" to force it.
when_to_use: >-
  Research where the output feeds a real decision, document, or dispute — i.e. it needs cited,
  hash-verifiable evidence or a resumable ledger. For throwaway questions, skip this and answer natively.
last_verified: 2026-09-01
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

## 병렬 대량 수집 프로토콜 (실측 2026-07-18~19, 832건 런 — 3웨이브 재발·소비 확정)

30건+ 수집은 서브에이전트 팬아웃으로. 규칙은 전부 실사고에서 나왔다:

- **각 에이전트는 결과를 `<project>/runs/<slug>/` JSON 파일로 직접 Write한다** — 에이전트의 최종
  텍스트 응답은 메인에 전달되지 않아 유실된다(실사고 1회 후 3웨이브 확정 경로). 메인에는
  SendMessage 요약만 보낸다.
- 파일 계약: `{items:[{url, source_platform, evidence_state, ...}]}` — source_registry 스키마
  그대로. 메인이 merge→dedupe 후에만 합성한다(생파일 순서 주의: 큐레이트본보다 raw 덤프를 먼저
  merge하면 레지스트리가 오염된다 — 실사고 1회).
- **URL_ONLY 침전 법칙**: 대량 스윕은 blog 55%·youtube 61%·reddit 62%가 URL_ONLY로 남는다(832건
  실측). 합성에서 URL_ONLY 행 인용 금지, 심층 읽기는 후보선정 2차 패스로 분리하라.
- `blocker_or_rejected_reason`을 **수집 시점에** 기록하라 — 832건 런은 0건 기록해 벽 지도를
  사후 복원해야 했다.
- **정보재 평가 배선 (실측 2026-07-20 — sweep을 채점 모델에 먹여라)**: 수집은 discovery지만
  거기서 멈추면 engagement 줄세우기로 오도된다(별점·조회수 ≠ 신뢰성·신선도). 정보재 평가 모델은
  이미 vault에 있다 = `loop quality`(src=신뢰성/발행자, fresh=신선도[published_at 우선], corr=검증/반증,
  creative_span=알파성격). **자기발전 아님(실측 2026-07-20)**: QUALITY_WEIGHTS는 손튜닝 상수, `loop eval`은
  판단 IC를 **측정만** 하고 가중치를 자동 갱신 안 함 — outcome→weight 루프는 코드에 안 닫혀 있고(사람 단계)
  아직 미실행. 통합 리랭크는 실증됨(4후보 실채점: freshness가 llm_wiki 1.0 > claude-obsidian 0.44 > Karpathy
  0.19로 별점 오도를 교정). 단 전부 저점(31~39)·weak provenance = 미검증 discovery라 모델이 과claim 거부. 배선:
  ① **수집 시점에** `source_platform`·`published_at`(captured_at 아님)·`evidence_state`를 각 아이템에 찍어라.
  ② discovery 끝나면 **survivor만**(전부 아님) draft 노트로 승격 → `loop quality`가 채점.
  ③ load-bearing 숫자는 farm 봉인(T2) → outcome이 나면 settle → 채점자 재보정.
  즉 **평가는 leesearch-alpha가 아니라 `loop quality`가 한다**(alpha=비자명 엣지 추출 전용 부분집합).

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
| YouTube **with** served captions, cheap trend numbers / spoken gist | `youtube-research` (caption-first, free APIs, no download, no ASR). ⚠️ YouTube는 로그인벽 아님 — 공개 검색·자막·채널통계는 Data API/yt-dlp/json3가 최저가. `opencli youtube`(전부 cookie)는 로그인 전용 표면(내 피드·시청기록·구독)에만 쓴다, 공개 데이터엔 쓰지 마라 |
| Quantitative **time-series** need (velocity / decay of anything trackable) | `refcap/trendwatch.py` (standalone collector utility, NOT part of this skill's ceremony — see its docstring) |
| Video **without** captions / foreign VO / TikTok·IG·non-YouTube / deep resumable dig | `leesearch-video-heavy` (refcap: whisper ASR, OCR, frames, resumable ledger) |
| **로그인벽·플랫폼 데이터 읽기** (X·TikTok·IG·LinkedIn·논문·금융·트렌드 등 174 어댑터) — 특히 **반복** 수집 | `opencli <site> <cmd>` (어댑터 티어, 1회 학습→LLM 0콜; 근육 인벤토리 참조). 무로그인으로 되면 그쪽 먼저(계정 리스크 0), 1회성·시각 판단은 claude-in-chrome. 바이트는 farm 등록으로 검증. **소스가 막히면(429 등) 여기서 멈추지 말고 독립 소스로 폴백**(예: arxiv→openalex) — 그 판단이 이 표의 존재 이유다 |
| Competitor / pricing / market-size numbers | farm directly with the `market_scan` claim types (see farm SKILL.md "Lens claim types") — corroborate across independent eTLD+1 domains |
| User-pain / feature-gap / voice-of-customer | farm directly with the `product_planning` claim types (same section) |
| Generic web / PDF / dashboard / long article | native gather (deep-research, WebSearch/WebFetch, `claude-in-chrome`) → seal load-bearing claims via farm. For a full gather→refute→seal→verify pass in one shot, run the `sealed-research` workflow (`Workflow({scriptPath: "~/.claude/workflows/sealed-research.js", args: {question, projectDir}})`) |
| Pages you already know, need tamper-evident bundle | `browser-agent-mcp-farm` directly (`farm_evidence_run`) |
| Hidden / underrated / mispriced ("숨은 꿀 / 저평가 / 선제적 알파") | **Alpha Fusion**: `leesearch-alpha` owns the thesis loop (hypothesis → findings → triangulate → predict → digest); YOU fan out sources across data shapes. Never stamp ALPHA from a single-leaf web-only run |

**Invariant: one executor per source** (never light + heavy on the same clip), not one executor per investigation.

### 로컬 근육 인벤토리 (dev PC 실측 2026-07-07 — 여기 없는 설치도구는 호스트가 놓친다, 설치/제거 시 이 표를 갱신)

> ⚠ **시효 있는 사실은 registry에 산다**(도구 버전·플랫폼 API 정책·스텔스 티어 건강 — 레코드별 TTL):
> 기계 소스 `facts.registry.json` + loader `refcap/reffreshness.py`(만료/미발효/미검증/손상 판정, stale를
> fresh로 재라벨 안 함), 사람용 뷰 `facts.registry.md`. 이 표는 "무엇을 왜 쓰나"(method)만 담고,
> 버전 숫자·정책 날짜가 어긋나면 registry가 최신이다. (스텔스 티어: curl_cffi·patchright·nodriver=healthy /
> camoufox·FlareSolverr=degraded / puppeteer-stealth=dead — registry 참조.)

| Need | 근육 (전부 설치·스모크 통과) |
|---|---|
| 기사/블로그 본문 정제 (html→본문 텍스트) | `trafilatura.extract(html)` |
| JS 렌더링 SPA → 마크다운 | `crawl4ai` AsyncWebCrawler — **브라우저 티어**, http_fetch·URL변형 실패 후에만 |
| RSS/Atom 수신·파싱 | `feedparser` |
| PDF/DOCX/PPTX/XLSX → 마크다운 (표·스캔) | `docling` DocumentConverter |
| 소셜 이미지 갤러리+메타 대량 | `gallery-dl` (공개=무로그인; 심화=버너쿠키+저속, 계정리스크) |
| 영상/오디오/자막/메타 다운로드 | `yt-dlp` (TikTok 공개영상 무로그인 확정경로 · 실 JS런타임 필요 — 버전·런타임은 `facts.registry.md`) |
| 이미지/프레임 OCR **한국어** | `rapidocr_onnxruntime` RapidOCR — easyocr 대신 쓸 것(한국어 CER 약함) |
| TLS 지문 403 돌파 | `curl_cffi` — ⚠ 한글 사용자명 PC는 CA 경로 버그: `CURL_CA_BUNDLE=C:/Users/Public/cacert.pem` 지정 필요 |
| 무인 브라우저 CLI (모델 불문, a11y-tree 텍스트) | `agent-browser` 0.31.1 — 데몬 미다운로드(24/7 소비자 생기면 `agent-browser install`) |
| **반복** 로그인벽 수집 (사이트→결정론 CLI 어댑터, 1회 학습→LLM 0콜 재실행) | `opencli` 1.8.6 (공급망 감사 2026-07-20 통과: 피시홈 0·확장 localhost-only·쿠키 스코프 강제. **수칙**: 공식 내장 어댑터만(어댑터=Node 코드 자동실행)·`plugin install` 금지·유휴 시 데몬 종료·전용 Chrome 프로필 권장. Browser Bridge 확장 필요. 어댑터 제작·수리 노하우는 자동주입 스킬 대신 패키지 내 `node_modules/@jackwener/opencli/skills/` 6종을 필요할 때 읽어라 — 기능은 CLI 자체문서(`opencli list`, `browser --help`)로 100% 사용 가능 실측. **A/B 실측 통과 2026-07-20**: X 장문 전문+답글 7.9s·LLM 0콜 — oEmbed 164자 잘림·동의브라우저 미연결 대비 유일 완전 경로) |

벽/빈껍데기 페이지 에스컬레이션 순서(싼 것부터): **①known KR 레시피**(네이버 블로그=`m.blog`/`PostView` URL,
아래 표) → **②insane-search 엔진**(unknown/harder 벽: 위장그리드+WAF프로파일+per-host 학습) → **③**`curl_cffi`
단발 → crawl4ai/farm headed → profile/byo.

> **이음매 — 자동/동의 경계선**(성격이 바뀌는 한 지점): **①②③+crawl4ai**까지는 "데이터가 어디 있나"를
> 찾는 단계라 **자동 진행**한다(사이트가 나를 막은 게 아니라 데이터 위치가 다를 뿐). `profile`·`byo_capture`·
> headed 로그인은 **"상대가 나를 식별·거절한"** 뒤의 단계다 — 이 경계를 넘을 때만 사용자 동의/판단을 받고,
> 자율 봇·CAPTCHA 우회는 넘어서도 금지(lawful-refusal). 통지는 "도메인당 한 번"이 아니라 이 경계를 넘을 때다.

- **insane-search 엔진 (vendored engine-only, 감사 2026-07-07 통과)**: `refcap/vendor/insane-search/`에서
  `python -m engine <URL> [--json] [--device mobile] [--trace]`. SSRF가드+프롬프트인젝션탐지+로컬학습 내장,
  플러그인 껍데기(phone-home·config주입)는 **의도적 제외**. **사각지대(실측)**: url_transforms가 `www.X→m.X`·apex만이라
  `blog.naver.com→m.blog.naver.com`(3-label) 변환을 **못 함**(설계상 도메인-불문 규칙만, 사이트명 참조 금지 →
  네이버 특화는 엔진이 아니라 이 라우트 ①에 산다). ⚠️ **insane-search가 블로그를 못 하는 게 아니다** — 실측 2026-07-14:
  데스크톱 `blog.naver.com/<id>/<logNo>`를 주면 17회 전부 `challenge`(껍데기 2938B)로 헛돎, 그러나 `m.blog.naver.com/<id>/<logNo>`를
  주면 `ok:true`로 **본문 224KB 확보**(`--device mobile`은 host를 안 바꿔 무효). → **규칙: 네이버 블로그는 fetcher에 넘기기 전에
  라우트 ①이 데스크톱→m.blog/PostView로 먼저 정규화**하라. 정규화 후엔 http_fetch(①, 최저가)가 이기고, 필요 시 insane-search도 됨.
  데스크톱 URL을 insane-search에 그대로 던지지 마라(17회 낭비). insane-search는 X/Reddit/Coupang 등 미지 벽·위장그리드가 필요할 때.
  (근거·A/B: [[2026-07-07-acquisition-tools-install-execution]] · 블로그 실측: [[2026-07-14-capture-insane-search-naver]])

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

- **(벽 지도 갱신 2026-07-19, 832건 랜드스케이프 런 실측)** github/paper/HN/release = 네이티브
  심층률 63~100% 고수율 경로. X는 x-archive 우회 포함 URL_ONLY만 나옴 — 예산 낭비 경로로 취급.
  YouTube는 yt-dlp json3 서빙 자막 우선(ASR 불필요 — 이 런의 TRANSCRIPT 11건 전부 이 경로).
- **(X 레시피 실측 2026-07-20)** 공개 X 포스트 무로그인 경로: ①`publish.twitter.com/oembed?url=<포스트URL>`
  ②`cdn.syndication.twimg.com/tweet-result?id=<id>&token=<base36((id/1e15)·π)에서 0과 . 제거>`
  ③서드파티 프록시 `api.fxtwitter.com/<user>/status/<id>`(장문 note_tweet 완본 반환·display_text_range로
  잘림 자가검증 가능하나 **감사 안 된 남의 서버 경유** — throwaway 읽기만, load-bearing 금지).
  ①②는 **장문이 ~280자에서 잘리고 스레드 후속타래도 안 나옴**. **완전·감사 경로는 opencli twitter
  thread/search(인증세션)** — 장문 전문·답글·지표까지, 2026-07-20 A/B 통과.
- **발견층 실측(8각도 트라이얼 2026-07-20)**: leesearch 발동은 프레이밍 의존적 — 결정/자료 프레이밍
  3/3 발동, casual/모호("뭐래·뭐 떠") 7/7 미발동(설명의 "quick=native"를 충실히 따름). 이건 대체로
  올바른 설계다(casual에 의례 강제 금지 = 효율). 유일 잔여 위험 = **결정용인데 casual하게 프레이밍된**
  로그인벽 읽기가 감사 안 된 프록시(fxtwitter)로 샐 때. 스킬 본문에 "로그인벽은 quick 아님"을 박아도
  casual은 본문을 안 열어 무력함이 실측됨 — 이 seam의 하드 봉인은 훅뿐(재발 시). throwaway 읽기의
  프리랜싱은 용인, load-bearing이면 fxtwitter 금지·어댑터/farm 경유.

- **Acquisition tiers**: farm은 source별 가장 싼 viable tier를 고른다
  (`official_api → feed → http_fetch → model_extract → profile → headed → byo_capture`).
  anti-bot/로그인 소스는 `headed_only` — farm은 자율로 뚫지 않는다 (lawful-refusal, 설계).
  **http_fetch가 403/빈껍데기면 멈추지 마라** → `profile`(동의된 로그인 세션) 또는 `byo_capture`
  (네가 실브라우저로 캡처, farm이 바이트 검증). 자율 봇/CAPTCHA 우회 금지.
- **Opt-out 신호(수집 전, agent 행동 규칙 — 코드 아님)**: robots.txt만 보지 말고 `License:` 지시자
  (RSL — 외부 XML URL을 가리키고 실제 조건은 그 XML에 있음)·TDMRep·`noai`류 메타도 함께 보라. 상태를
  `allowed | disallowed | conditional | unknown`으로 명시하라(fail-visible — 못 읽으면 "allowed" 아님).
  EU는 opt-out 신호를 놓치고 수집하면 저작권 예외가 소멸한다(GPAI 의무). ⚠️ `llms.txt`(비표준)를 법적
  opt-out으로 취급 금지 — 공식 RSL과 구분. RSL 세부 어휘·검증 상태는 `facts.registry.md` F-003.
  **구현**: `refcap/refopt.py` `resolve_optout(url, fetch)` — robots(status/content-type·path+query·
  UA product-token·Allow오버라이드·`*`/`$`)·RSL `License:`·TDMRep·noai를 `allowed|disallowed|
  conditional|unknown`으로 해석(fail-visible: 로그인HTML·403·5xx=unknown, 404=allow-all; 테스트 23).
  라이선스 XML 본문 파싱은 스펙 확인 후(F-003) — 지금은 license_urls만 노출.
  **강제 배선**: `refcap/refacquire.py acquire()`가 optout→fetch→softblock→parse→validate를 순서대로
  STOP-게이트로 강제한다(disallowed/unknown=fetch 금지, conditional=동의 게이트). helper를 직접
  부르지 말고 이 진입점을 통해라 — 그래야 게이트가 실제로 걸린다.
- **네이버 공식 API 상태**: 검색(블로그·뉴스·카페·지식iN) API는 유지되나 **쇼핑·책·전문자료
  코퍼스는 종료**(2026 API HUB 이전) — 가격비교를 공식 API로 뽑으려 시간 낭비 말 것. 현재 상태·날짜는
  `facts.registry.md` F-002가 최신(플랫폼 정책은 시효 있음).
- **리뷰 조사**: 벽 낮은 소스부터 — 앱스토어 리뷰(공식 API), 커머스 리뷰, 무로그인 커뮤니티,
  지도 리뷰, 유튜브 리뷰영상(→heavy). ⚠️ 네이버 PLACE: farm `naver_place_apollo`는 Place
  **엔트리(목적지) 추출기**이지 리뷰 본문 추출기가 아니며, 감사 실측(2026-07-20) 결과 프로덕션
  미배선(테스트만 임포트하는 죽은 모듈)이다 — PLACE 리뷰 본문 경로는 재실측 전 미확정으로 취급하라.
  **BLOG 본문**: 데스크톱 `blog.naver.com/<id>/<logNo>`는 iframe(mainFrame) 껍데기(한글 ~4청크)지만,
  `m.blog.naver.com/<id>/<logNo>` 또는 `blog.naver.com/PostView.naver?blogId=<id>&logNo=<logNo>`로
  **URL만 바꾸면 본문이 http_fetch로 그대로 나온다** (실측 2026-07-07: 모바일 571·PostView 1337 한글청크,
  curl_cffi 불필요·plain GET도 200). 포스트 발견은 `rss.blog.naver.com/<id>.xml`(50 item). → 블로그 본문은
  **profile/byo 불필요, 모바일/PostView URL 변형 = http_fetch 티어**. 카페=로그인=profile 전용(이건 유효).
  해법은 "네이버를 뚫어라"가 아니라 "접근가능 소스 다변화 + URL변형 우선, 남은 벽만 profile/byo".
- **소셜/로그인벽 (클래스로 다뤄라)**: 자율 tier는 프로필 META만 줌 — 본문은 동의 브라우저
  (Claude=`claude-in-chrome`, 일반=headed/profile)로 보고 farm이 검증(=byo_capture). 동의 브라우저
  자체의 도메인 allowlist에 막히면(네이버가 그랬다) human byo나 대체원으로. 크리에이터 추세는
  cross-platform 삼각측량 + 공개 분석 사이트로 보강.
  **반복성으로 실행자를 가른다(2026-07-20)**: 같은 로그인벽 소스를 주기적으로 긁는 워크로드는
  `opencli` 어댑터(위 근육 표, 1회 학습→결정론 재실행) → 바이트는 farm 등록으로 검증. 1회성·시각
  판단은 기존대로 claude-in-chrome. 무로그인으로 되는 소스는 언제나 그쪽 먼저(계정 리스크 0).
  한 소스에 실행자 하나 — opencli 어댑터가 있는 소스에 claude-in-chrome을 겹치지 마라.
  **어댑터 커버리지는 명령 단위로 확인하라(실측 2026-07-20)**: opencli twitter는 `thread/article/search`로
  개별 포스트 본문까지 되지만, opencli **tiktok/instagram은 user/search/trending(계정·검색·트렌드) 위주**라
  **"특정 영상/릴스 1건 내용 읽기" 명령이 없다** — 개별 공개 영상은 `yt-dlp`, 개별 시각/릴스는
  claude-in-chrome이 맞는 실행자. `opencli list`로 그 사이트가 실제 가진 cmd를 먼저 봐라.

## Invariants (every route)

- **Seal the load-bearing few, not everything.** Casual questions never enter the farm.
- **gate=OK ≠ true.** cite-or-fail proves the quote exists in registered bytes, not that the bytes
  are correct. Corroborate the highest-stakes number across INDEPENDENT domains.
- **HTTP 200 ≠ 성공, "무언가 반환" ≠ 옳음.** `refcap/refguard.py detect_softblock`은 챌린지/빈셸/
  Akamai 미통과를 판별하되 **selector가 hit하면 마커가 있어도 콘텐츠로 취급**(정상 기사 오탐 제거),
  HTTP 4xx/5xx는 `http_error`로 anti-bot과 분리, JS-wall은 렌더 승격으로 분리. `validate_values`는
  type/range/empty/**non-finite(NaN)**/uniform/`unique`/min_rows + reject_regex(**known-junk 데닐리스트 —
  wrong-target 증명이 아님**) 검사, non-throwing. 이 순서를 강제하는 진입점은 `refcap/refacquire.py
  acquire()`(blocked=parse 금지, validation issue=미승격, 각 STOP은 `evidence_state`로 명시). 자가치유·
  greedy 셀렉터는 늘 무언가 반환하므로 값 검증이 필수(실측: `reports/scrapling-experiment.md`).
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
