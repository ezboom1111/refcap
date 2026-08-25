# refcap

**Personal content-reference + multi-source research toolkit** — the research spine behind the
`leesearch` skill family. A neutral, externally-auditable **evidence kernel**: local extraction
(whisper ASR · audio separation · OCR · frame sampling), an append-only research ledger with a
resumable frontier, and cite-or-fail evidence sealing through an external Merkle-bundle gate.

> 에이전트 리서치의 "증거 척추". 호스트 에이전트(Claude Code 등)가 **뇌**(판단·분해·중단 결정)를 맡고,
> refcap은 **척추**(원장·출처·바이트 앵커링)만 맡는다. 증거 봉인 게이트(farm)는 별도 MCP 서버이며,
> 이 레포는 farm을 import하지 않는다(farm-import-0, 중립성).

## 설계 철학 한 줄

코드는 **명사**(artifact, finding, frontier-entry)를 보존하고, 증거가 진짜인지(존재·불변·품질 라벨)만
판정한다. **동사**(무엇을 고르고, 언제 멈추고, 어떻게 적응할지)는 전부 에이전트의 몫이다.
리트머스: *"이 결정이 주제마다 달라지는가?"* → 그렇다면 에이전트의 일이지, 코드의 일이 아니다.

## 구성

| 경로 | 역할 |
|------|------|
| `refledger.py` | 추가 전용(append-only) 리서치 원장 + 재개 가능한 frontier + cite-or-fail 호출 계획(`farm_plan.json`) 생성. stdlib만 사용 |
| `refextract.py` · `refsep.py` · `refocr.py` · `refrecord.py` | 로컬 추출 스택 — whisper ASR, 오디오 분리, OCR, 프레임 샘플링/캡처 |
| `refinsight.py` · `refbench.py` · `refbench2.py` | 인사이트 정확도 레이어 (Rank 1–6: 예측-결과 캘리브레이션, 캡처 상한, 모순/독립성 검증, 리콜, 추출 벤치, 증거 충분성 루프) |
| `ALPHA_PLAYBOOK.md` · `ALPHA_ARCHITECTURE.md` | Rank-7 알파 레이어 — 흩어진 공개 단서를 조립해 반증 가능한 예측으로 등록·정산 |
| `FRAMEWORK.md` | 숏폼 콘텐츠 23항목 분해 프레임워크 (모든 판단에 OBSERVED / INFERRED / UNKNOWN 라벨 강제) |
| `trendwatch.py` · `refdiscover.mjs` | 트렌드 스냅샷 · 소스 발굴 |
| `tabcap-extension/` | 크롬 탭 캡처 확장 (수동 레퍼런스 수집 입구) |
| `skills/` | `leesearch` 스킬 패밀리 — 라우트 테이블 + heavy path 계약서 |
| `vendor/insane-search/` | fetch-escalation 엔진 (MIT, engine-only 벤더링 — `PROVENANCE.md` 참조) |
| `SCENARIOS*.jsonl` · `QA_REPORT*.md` | 자체 QA — 300문항 크로스도메인 + 스트레스 시나리오와 그 리포트 |

## 정직한 경계 (over-market 금지)

cite-or-fail이 증명하는 것은 **"이 인용이 등록된 바이트 안에 존재한다"** 까지다 —
바이트 자체(예: ASR 전사)가 옳다는 증명이 아니다. 캡처 시점의 오전사가 열린 지붕이며,
유일한 상류 방어는 캡처 전 NO_SPEECH/DEGENERATE 품질 라벨링이다.
"전사 검증됨"이라고 주장하지 않는다. 이 한계는 숨기지 않고 사용자에게 표면화한다.

## 라우팅 (light vs heavy)

- 자막 있는 YouTube · 값싼 트렌드 수치 → **light path** (`youtube-research`: 공식 API + 서빙된 자막, 다운로드/ASR 없음)
- 자막 없음 · 외국어 VO · YouTube 밖(TikTok/IG) · 심층 멀티소스 → **heavy path** (이 레포의 로컬 추출 + 원장)
- 소스당 정확히 하나의 경로만. 결론의 하중을 받는 주장은 양쪽 모두 동일한 farm cite-or-fail 게이트로 봉인.

## 기록

2026-06-06 시작, 약 한 달간 56커밋. 문서 곳곳의 절대 경로는 개인 작업 환경 기준이다.
