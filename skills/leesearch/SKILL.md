---
name: leesearch
description: >-
  Lee's unified research front-door (이지범's personal research router). Invoke this FIRST whenever the user
  asks to research / investigate / 조사 / 트렌드 분석 anything and wants traceable, farm-verifiable conclusions.
  It is the dispatcher. For ordinary research it classifies the task and dispatches each source to the right
  executor skill (leesearch-video-light, leesearch-video-heavy, or the farm lenses market-scan /
  product-planning / deep-browser-research). For hidden-alpha research it switches to alpha-fusion mode:
  multiple source legs, multiple data shapes, one executor per source, and a cite-or-fail gate on the
  load-bearing claims. Say "leesearch <goal>" to force it.
when_to_use: >-
  Any research / investigation / trend-reading request where you want one reliable front-door that routes to
  the correct gathering skill and guarantees farm-verified, cited conclusions — especially when unsure which
  research skill fits.
---

# leesearch — research front-door (router)

> Canonical source (versioned in the refcap repo). Deployed copies live at `~/.claude/skills/leesearch/`
> and `~/.codex/skills/leesearch/` for Claude Code and Codex respectively.

You (the host agent) are the dispatcher. This skill is the **decision tree**; the leaves do the gathering.
For ordinary research, pick exactly ONE executor per source, run it, then seal the load-bearing claims through
the farm gate. For hidden-alpha research, do **not** collapse the whole task to one leaf: run **Alpha Fusion
Mode** below. The invariant is one executor **per source**, not one executor for the whole investigation.

## Routing decision tree
1. **Target is a video / short-form clip?**
   - **YouTube + served captions, and you just need cheap trend numbers / the spoken gist / a list-guide's
     items** → **`leesearch-video-light`** (caption-first, free APIs, no download, no ASR).
   - **No captions / foreign-language VO / TikTok·Instagram·Reels / non-YouTube / a deep resumable
     multi-source dig** → **`leesearch-video-heavy`** (refcap local whisper ASR, audio-separation, OCR,
     frame sampling + a resumable ledger).
2. **Competitor / pricing / market-size?** → **`market-scan`** (farm lens; corroborated across independent domains).
3. **User-pain / feature-gap / requirement / voice-of-customer?** → **`product-planning`** (farm lens).
4. **Generic web page / PDF / dashboard / long article (not video, not market/product)?** → **`deep-browser-research`**.
5. **Just need a tamper-evident bundle of pages you already know?** → drive **`browser-agent-mcp-farm`** directly.
6. **Want the NON-OBVIOUS / hidden / mispriced / underrated answer — not the obvious brand answer?** (숨은 꿀 /
   저평가 / 남들 모르는 / 선제적 알파) → **Alpha Fusion Mode** below (NOT just `leesearch-alpha` alone). The thesis
   loop lives in `leesearch-alpha`; the source fan-out lives HERE. Do not collapse alpha to a single leaf.

## Alpha Fusion Mode (hidden / underrated / mispriced requests)
`leesearch-alpha` owns the thesis loop (hypothesis → findings → triangulate → predict → digest).
This router owns the **source fan-out**: which data shapes to open, which executor handles each source.
Run BOTH together. Do not stamp ALPHA from a single-leaf web-only investigation.

1. **Declare the consensus baseline** (합의 앵커). Write the obvious/brand answer first; alpha = delta from that.
2. **Open a source matrix.** For each data shape, ACTIVELY SEARCH for sources before deciding relevance:
   - **unstructured** (required): news, community posts, long articles, reviews.
   - **semi-structured** (required for med/high): PDF, tables, dashboards, screenshots, transcripts.
   - **structured** (required for med/high): API/CSV/JSON/extracted rows from official databases, filings, patents.
   - **video/audio** (default: search, then decide): Do a YouTube/platform search for the topic FIRST. If relevant
     videos exist (they almost always do), capture at least one via `farm_evidence_run` + `farm_sample_frames`. Only
     mark "not material" AFTER searching and finding nothing relevant — "I didn't look" is not "not material."
   - **OCR** (when documents are image-based): scanned PDFs, infographics, screenshots with text.
3. **Dispatch one executor per source** (invariant: one executor per source, not one per investigation):
   - YouTube with captions → `leesearch-video-light`
   - YouTube without captions / non-YouTube / ASR needed → `leesearch-video-heavy`
   - Market numbers → `market-scan`; user pain → `product-planning`; long web/PDF → `deep-browser-research`
   - Known pages → `browser-agent-mcp-farm` directly.
4. **Per-shape minimums by stakes** (evidence budget lives in `leesearch-alpha`; reference it, don't duplicate here).
   The alpha skill defines candidate counts (low 12-20, med 30-50, high 50-100) and shape requirements.
   Key rule: each required shape must have ≥3 items — one-item shapes are checkbox compliance, not real diversity.
5. **Stop gates.** Do not stamp ALPHA unless: 3+ independent eTLD+1 hosts, 1+ disconfirming/refutation pass,
   1+ falsifiable `predict(resolve_by)`, cite-or-fail on load-bearing claims, and ALL required shapes present.
   Missing shape → `RECON(<missing-shape>)` with the specific next pass to run.

## 소스/플랫폼 선택 (트래픽·점유율 기반 · 라이브 · 자가갱신 — 고정 목록 금지)
**영원한 플랫폼은 없다.** 스킬에 "틱톡/X/IG/유튜브…" 고정 리스트를 박으면 *그 순간 늙는다* — 새 서비스가 떠도 구시대를 뒤진다. 그래서 이 스킬은 **목록(DATA)을 담지 않고 찾는 법(METHOD)만** 담는다:
1. **런타임 발견** — 조사 시작 시 "현재 이 **도메인·지역(locale)**에서 트래픽/점유율 상위 플랫폼·소스"를 LIVE로 발견. 랭킹 소스 **≥2개를 교차**(방문자/검색량/MAU/점유율 통계), 수치는 **cite-or-fail**. 단일 랭킹 사이트도 박지 마라 — 그것도 늙는다 → 일반 검색으로 현재 랭킹을 *발견*해 삼각측량.
2. **날짜 캐시 + TTL** — 발견 결과를 captured-at과 함께 ledger(또는 `<project>/cache/sources.json`)에 저장. 다음 런은 **TTL(기본 ~30일, 트렌드면 더 짧게 — half-life 참조) 내면 재사용, 지나면 자동 재발견.**
3. **top-N + locale 라우팅** — 상위 N개 + 지역 보정으로 어느 플랫폼을 어느 executor(위 트리)로 보낼지 결정. **새 플랫폼이 랭킹에 들면 자동 편입, 죽은 건 자동 탈락.**
4. **우아한 강등** — 전용 추출기 없는 신규 플랫폼도 farm 범용 캡처(스크린샷/텍스트/HTML)로 잡힌다 — 안 보이는 게 아니라 덜 풍부할 뿐.
5. **트렌드 전파 역할은 *역할*로, *고정 순위* 아님** — "원발→증폭→종착"의 역할 구조(예: 숏폼 원발 → 릴스/숏츠 증폭 → 롱폼 종착, X=실시간 담론)는 heuristic이니 **현재 점유율로 매 런 재확인**(과거 숫자 받아쓰기 금지). locale별 차이도 라이브로(예: 한국은 글로벌과 점유율이 다름).

> **"매번 CLI 켜서 스킬 업글?" — 아니.** 업데이트 = **캐시 만료 → 자동 재발견**. 플랫폼이 바뀌어도 스킬은 그대로(METHOD 불변), DATA만 라이브로 갱신. 수동 스킬 수정은 *찾는 법*이 바뀔 때만. (선택: `/schedule` 루틴으로 랭킹 캐시 주기적 예열.)

## Invariants (every route)
- **One skill per source.** Never run light + heavy on the same clip.
- **No frozen platform/source list.** Discover top sources by live traffic/share (≥2 triangulated, cited); cache
  dated with a TTL; re-discover on staleness. Hardcode only structural primitives, never *which platforms matter*.
- **Seal the load-bearing few, not everything.** Register exact bytes → `farm_add_claim` (anchor = verbatim
  quote) → `farm_run_claim_gate` → `farm_export_bundle`. The farm is the VERIFIER, never the understanding
  engine. (An MCP server cannot call skills — YOU dispatch and YOU drive the farm tools.)
- **gate=OK ≠ true.** cite-or-fail proves a quote exists in registered bytes, not that the bytes are correct.
  Surface low-quality / unverifiable citations; corroborate the highest-stakes number across INDEPENDENT domains.
- **An honest gap beats a guess.** If no route reaches the answer, say so.

## Map (who owns what)
| route | skill | owner |
|---|---|---|
| light video | `leesearch-video-light` → wraps `youtube-research` | personal / farm impl |
| heavy video | `leesearch-video-heavy` (refcap stack) | personal |
| market | `market-scan` | farm (shared) |
| product | `product-planning` | farm (shared) |
| generic web | `deep-browser-research` | personal |
| hidden alpha | `leesearch-alpha` (refcap Rank-7 + ALPHA_PLAYBOOK) | personal |
| evidence gate | `browser-agent-mcp-farm` | farm (shared) |

Farm skills keep their neutral names (shared, Apache-2.0); `leesearch-*` is the personal front-door layer on top.

## 출력 폴더링 계약 (필수 — 평면 덤프 금지, gstack처럼 스며들게)
한 조사 = **하나의 프로젝트 루트** 아래로 *전부* 들어간다. run마다 최상위 형제 폴더를 새로 만들지 마라(그게 174MB·50개 형제 mess의 원인이었다). 계약:
```
<project>/                     # 예: ~/Desktop/graduate school
├─ INDEX.md                    # 맵: 각 run이 뭔지 + reports 포인터 (조사 끝에 갱신)
├─ reports/                    # 사람이 읽는 합성 .md (결론·픽·alpha 리포트)
├─ inputs/                     # 사용자가 넣은 원본 (PDF 등)
├─ cache/                      # 비-연구물 (OCR 모델 tessdata 등 — 공유, run 아님)
├─ dcollection-artifacts/      # 구조화 수집(있으면)
└─ runs/
    ├─ farm/<entity>/<slug>/   # farm 캡처 번들 (entity=대학/기관; 많으면 그룹)
    └─ leesearch/<slug>/       # leesearch/refledger run
```
규칙: ① farm/leesearch run을 시작할 때 `base`(또는 runDir)를 **반드시 `<project>/runs/<tool>/...` 아래**로 줘라 — 절대 `<project>/<flat_name>`로 주지 마라. ② 합성 .md는 `reports/`에. ③ 원본 입력은 `inputs/`, 모델·캐시는 `cache/`. ④ 조사 끝에 `INDEX.md`를 갱신(또는 `python refledger.py digest`로 run별 SUMMARY). ⑤ OCR traineddata 같은 *공유 모델*은 연구 루트에 흩지 말고 `cache/tessdata/`(또는 사용자 공용 캐시)로. = 새 run이 *프로젝트에 스며든다*, 형제로 흩어지지 않는다.
