# leesearch — facts.registry (시효 있는 사실, 레코드별 TTL)

> **SKILL.md는 METHOD(시효 없음: 라우팅·사다리·에스컬레이션)만 담는다. 시효 있는 사실은 여기 산다.**
> 도구 버전·플랫폼 API 정책·스텔스 티어 건강처럼 몇 주면 썩는 것들. 각 레코드는 자기 날짜·TTL·status를
> 가진다(파일 전체 `last_verified` 하나로는 서로 다른 TTL을 만료 못 시킨다 — Codex 리뷰 2026-09-01).
>
> **⚙ 기계 소스는 `facts.registry.json`이다(이 .md는 사람용 뷰).** loader `refcap/reffreshness.py`가
> 레코드별로 `fresh|stale|pending|unverified|corrupt`를 판정하며 **stale를 fresh로 재라벨하지 않는다**.
> `refacquire.acquire(registry_check=reffreshness.registry_check)`로 배선되면 stale/pending/미검증
> 사실이 수집 결과에 경고로 표면화된다. (`python reffreshness.py`로 현재 판정 표를 볼 수 있다.)
>
> **status**: `observed`(직접 관측) · `announced`(발표됨, 미발효) · `effective`(발효/시행 중) ·
> `degraded`/`dead`(도구 상태) · `partially-verified` · `unverified`(스킬 hard-code 금지).
> **읽는 법(에이전트=소비자)**: 라우팅 판단 전에 관련 레코드를 보라. `effective_at`가 미래면 "예고"로만
> 쓰고, TTL 지난 레코드는 재확인 전까지 약한 근거로 취급. registry가 SKILL 본문과 어긋나면 registry가 최신.
> **갱신**: 재측정한 사람이 해당 레코드의 날짜·status만 바꾼다. 자동 probe는 미도입(P3) — 지금은 수동.

세부 근거·재검증 로그: `refcap/research/crawling-skill-update-2026-08/reports/facts-ledger.md`.

---

## 스텔스/안티봇 티어 건강 (군비경쟁 — 분기마다 재측정)

| 티어 | status | observed_at | 메모 |
|---|---|---|---|
| `curl_cffi` | `healthy` | 2026-09-01 | HTTP/3 지문 추가(v0.15). 최저가 안티봇 티어(브라우저 전) |
| `patchright` | `healthy` | 2026-09-01 | Playwright 무변경 스텔스 드롭인. 기존 farm 워커에 무코드 업그레이드 경로 |
| `nodriver` | `healthy` | 2026-09-01 | v0.50.1, undetected-chromedriver 후계. 경량 스텔스 브라우저 |
| `camoufox` | `degraded` | 2026-09-01 | README가 ~1년 유지보수 공백 자인 → **신뢰 금지**, 복구 입증 후 재평가 |
| `FlareSolverr` | `degraded` | 2026-09-01 | captcha 솔버 전멸(README 경고) → "solver"에서 "레거시 쿠키 하베스터"로 강등 |
| `puppeteer-stealth` | `dead` | 2026-09-01 | 2025-02 폐기, 이제 탐지됨. 쓰지 마라 |

## 로컬 도구 버전·상태 (근육 인벤토리의 시효 부분)

| 도구 | status | observed_at | 사실 |
|---|---|---|---|
| `yt-dlp` | `effective` | 2026-09-01 | **실 JS런타임 강제**(Deno 2.3+/Node 22+, Bun 폐기, Python 3.11 권장). 최신 2026.08.19. video-heavy 경로는 런타임 핀 필요 |
| `gallery-dl` | `effective` | 2026-09-01 | 개발이 **Codeberg로 이전**(GitHub=미러). 릴리스 워칭은 Codeberg repo |
| `agent-browser` | `observed` | 2026-07-07 | 0.31.1 CLI 설치. 데몬 미다운로드(24/7 소비자 생기면 `agent-browser install`) — ⚠ 버전 재확인 필요(2개월 경과) |
| `opencli` | `observed` | 2026-07-20 | 1.8.6, 공급망 감사 통과. 반복 로그인벽 어댑터 티어 — ⚠ 버전 재확인 필요 |

## 플랫폼 정책·법 (F-xxx = facts-ledger 대응)

| id | status | observed/effective | 사실 |
|---|---|---|---|
| F-001 Cloudflare | `announced` | effective 2026-09-15 | 2026-09-15부터 광고 페이지 mixed-use 크롤러 기본 차단 + Pay Per Use(HTTP 402 + Ed25519 서명 신원). 범위=신규·기존무료 고객 기본값. **오늘 미발효 → "예고"로만 인용, 이후 실측.** 2025-07 원문은 private beta·날짜없음(현재벽 아님) |
| F-002 네이버 API HUB | `effective` | 2026-06-25~ | Search/Trend/Shopping Insight를 네이버클라우드 API HUB로 이관, **쇼핑·책·전문자료 검색 종료**(가격비교 공식통로 닫힘). 블로그·뉴스·카페·지식iN 검색 유지. 신규는 HUB 콘솔. 구조 다소스 교차 / 정확한 컷오프 날짜는 1소스 |
| F-003 RSL opt-out | `partially-verified` | 2025-12~ | robots.txt에 `License: [XML URL]` 지시자 한 줄, 실제 조건은 외부 XML. opt-out 파서는 robots `License:` 감지→XML fetch가 정확한 경로. AI-usage 타입 어휘(ai-all 등)는 XML 스펙 미확인. **llms.txt(비표준)를 법적 opt-out으로 취급 금지** |

## 봇 트래픽 지형 (인용 시 창 기간 명시 필수)

| id | status | observed_at | 사실 |
|---|---|---|---|
| bot-majority | `observed` | 2026-06 | 봇이 HTML 트래픽 57.5%로 사상 첫 과반(Cloudflare Radar). crawl-to-refer는 측정 창마다 수십 배 변동 — 수치 인용 시 창 기간·소스 명시 |
