---
name: leesearch
description: >-
  Lee's unified research front-door (이지범's personal research router). Invoke this FIRST whenever the user
  asks to research / investigate / 조사 / 트렌드 분석 anything and wants traceable, farm-verifiable conclusions.
  It does NOT gather by itself — it CLASSIFIES the task and dispatches to the right executor skill
  (leesearch-video-light, leesearch-video-heavy, or the farm lenses market-scan / product-planning /
  deep-browser-research), then makes the load-bearing claims tamper-evident through the browser-agent-mcp-farm
  cite-or-fail gate. Use this as the single deterministic entry point so research is never left to ad-hoc
  skill-picking. Say "leesearch <goal>" to force it.
when_to_use: >-
  Any research / investigation / trend-reading request where you want one reliable front-door that routes to
  the correct gathering skill and guarantees farm-verified, cited conclusions — especially when unsure which
  research skill fits.
---

# leesearch — research front-door (router)

> Canonical source (versioned in the refcap repo). Deployed copies live at `~/.claude/skills/leesearch/`
> and `~/.codex/skills/leesearch/` for Claude Code and Codex respectively.

You (the host agent) are the dispatcher. This skill is the **decision tree**; the leaves do the gathering.
Pick exactly ONE executor per source, run it, then seal the load-bearing claims through the farm gate.

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
   저평가 / 남들 모르는 / 선제적 알파) → **`leesearch-alpha`** (thesis-driven, PUBLIC-only weak-signal triangulation +
   a falsifiable prediction, refined across passes; login EXCLUDED). Use when the answer is an INFERENCE from many
   scattered public clues, not a lookup.

## Invariants (every route)
- **One skill per source.** Never run light + heavy on the same clip.
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
