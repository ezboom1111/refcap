# refcap — 콘텐츠 레퍼런스 & 멀티소스 리서치 척추

[![CI](https://github.com/ezboom1111/refcap/actions/workflows/ci.yml/badge.svg)](https://github.com/ezboom1111/refcap/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](#요구-사항)
[![License: Source-Available](https://img.shields.io/badge/License-Source--Available_(view--only)-lightgrey.svg)](./LICENSE)

> *refcap is a personal content-reference + multi-source research toolkit: an append-only,
> cite-or-fail research ledger (stdlib-only Python) plus local media extraction (whisper ASR,
> vocal separation, OCR, frame sampling) and a falsifiable-alpha hypothesis loop. It is a
> **neutral** evidence stack — it imports `browser-agent-mcp-farm` exactly **0** times.*

숏폼/영상 레퍼런스를 "왜 터졌는지" 프레임 단위로 분해하려던 도구에서 출발해,
**모든 종류의 멀티소스 리서치를 지탱하는 증거 척추**로 자란 개인 툴킷입니다.
`leesearch` 스킬군(범용 리서치 라우트 테이블 · 알파 발굴 · 헤비 영상 분석)의
로컬 실행 계층이며, 결론을 지탱하는 주장은 등록된 바이트에 앵커되지 않으면
기록 자체가 거부됩니다(cite-or-fail).

## 30초 요약

| 질문 | 답 |
| --- | --- |
| 어떤 문제를 푸나? | 여러 소스와 긴 미디어를 조사할 때 출처·미해결 질문·판단 근거가 세션 사이에서 유실되는 문제 |
| 무엇을 만들었나? | 표준 라이브러리만 쓰는 append-only 증거 원장, 재개 가능한 조사 frontier, 미디어 추출 파이프라인, 반증 가능한 가설·예측 루프 |
| 무엇을 강제하나? | finding의 인용문이 등록된 바이트에 실제로 존재해야 하며, 원본이 바뀌면 SHA-256 재검증이 실패함 |
| 무엇을 보장하지 않나? | 인용이 존재한다는 사실은 보장하지만 그 인용이나 결론이 참이라는 사실은 보장하지 않음 |
| 어떻게 검증했나? | stdlib `unittest` 269개와 네 차례 적대적 QA 코퍼스를 저장소에 함께 공개 |

가장 빠른 코드 검토 경로는 [`refledger.py`](./refledger.py) →
[`test_refledger.py`](./test_refledger.py) →
[`RESEARCH_RUNBOOK.md`](./RESEARCH_RUNBOOK.md) 순서입니다. 전체 자동 검증은 다음
한 줄로 재현할 수 있습니다.

```bash
python -m unittest discover -p "test_*.py"
```

## 핵심 입장: 두뇌는 에이전트, 코드는 척추

이 저장소의 아키텍처는 기능 목록이 아니라 **입장**입니다
(`refledger.py` 헤더와 `RESEARCH_RUNBOOK.md`에 원문):

1. **두뇌를 코드에 박지 않는다.** "이 결정이 주제마다 달라지나?" → 그렇다면
   에이전트가 정한다. 코드는 명사(artifact/finding/frontier)를 영속화하고
   "증거가 진짜인가(존재+불변+캡처품질)"만 판정한다. 에이전트가 동사
   (고르다·묻다·멈추다·적응하다)를 수행한다.
2. **ingest는 깊이-0 라우터.** 확장자/스킴만 본다. 내용 기반 분기·점수·
   임계값을 코드에 넣지 않는다 — 그 길로 갔다가 실측 오탐(경주 degeneracy
   false-positive)을 만들고 철회한 이력이 커밋에 남아 있다.
3. **차별점은 기능이 아니라 입장**: 작은 TCB + 중립성(farm import 0).
   다른 에이전트 메모리와 경쟁하지 않고 *그 위에 얹는 증거 레이어*.
4. **cite-or-fail은 앵커링만 증명한다** — 인용문이 바이트에 존재한다는 것.
   *정확성이 아니다.* 환각 전사도 게이트는 통과한다. 진짜 방어는 캡처 *이전*
   품질 라벨(coverage_gate: `NO_SPEECH`/`BOT_WALL`/`DEGENERATE` 등)이며,
   저품질 출처 인용은 verify가 경고한다 — 침묵으로 축복하지 않는다.
5. **don't-hoard**: 원본 미디어는 해시만 남기고 삭제. 원장에는 추출물과
   지문만.

## 구성 요소

### 척추 — `refledger.py` (stdlib only, farm import 0)

디스크 기반 공유 작업기억 + 결정론적 증거 게이트 입구. 한 파일, 표준
라이브러리만 사용. CLI 서브커맨드:

```
open · ingest · finding · frontier(open/close/note/visit/state) · verify · digest · plan
hypothesis(--mode discover|debunk) · triangulate · predict · resolve · calib
measure · published · standard · grade
```

- **append-only 원장**: 산출물 등록(SHA-256), 앵커된 finding
  (`OBSERVED`/`INFERRED`/`UNKNOWN` 라벨), 재개 가능한 frontier(미방문 질문/
  소스 큐) — 중단된 조사를 다음 세션이 이어받는다.
- **finding은 앵커 없으면 거부**: `--quote`는 전사/페이지 바이트에 *그대로
  있는* 인용구여야 한다. 해석(claim)과 인용(quote)의 분리가 강제된다.
- **`verify`**: dangling 앵커 + 변조(재해시) + 저품질 인용 경고.
- **`plan`**: 고가치 finding을 [browser-agent-mcp-farm](https://github.com/ezboom1111/browser-agent-mcp-farm)의
  변조 증거 번들로 봉인하기 위한 `farm_plan.json`(실행할 `farm_*` MCP 호출
  목록)을 **생성만** 한다 — 실행은 에이전트 몫. refledger는 farm을 호출하지
  않는다(중립성).
- 동시성: 프로세스 내 락 + OS advisory 파일락으로 병렬 에이전트 호출의
  이중 등록(TOCTOU)을 차단. 한국어 경로 안전(ascii 슬러그 + UTF-8).

### 로컬 미디어 추출 계층

| 모듈 | 역할 |
| --- | --- |
| `refauto.py` | URL → yt-dlp 다운로드 → refextract 풀 파이프라인 자동화 (ToS-회색인 yt-dlp를 farm 밖 **이 한 지점에 격리**) |
| `refextract.py` | 녹화된 레퍼런스 영상(mp4) → 에이전트가 읽을 수 있는 증거(스마트 프레임 + 타임드 전사) |
| `refrecord.py` | 데스크톱 오디오 자율 캡처(WASAPI loopback) → 타임드 전사, 커버리지 게이트로 경화 |
| `refsep.py` | Demucs 보컬 분리(BGM 아래 깔린 음성 복구) |
| `refocr.py` | 프레임의 burned-in 텍스트 OCR → whisper의 동적 initial_prompt로 사용(음차 오류 감소) |
| `colorprofile.py` | 프레임에서 정량 컬러/룩 프로파일(Pillow만 사용) |
| `refdiscover.mjs` | 유튜브 니치별 레퍼런스 선별 — 절대 조회수가 아니라 최신성 윈도 안 **속도(views/day)** 로 랭킹 |
| `refbench.py` / `refinsight.py` | 전사 단계 내부 벤치마크 / 추출적 인사이트 채점기 — LLM-judge를 순환성 때문에 기각하고 사람이 수초에 확정 가능한 gold + 함정 카드(poison card)로 채점 |
| `tabcap-extension/` | Chrome MV3 확장 — 활성 탭의 오디오+비디오를 로컬 `.webm`으로 녹화(업로드·네트워크 0). 음소거 스크린샷이 못 듣는 VO 숏폼용 |

무거운 도구(whisper, yt-dlp, Demucs, ffmpeg)는 **서브프로세스로 순차 실행**
(15GB OOM 방어)되며 척추의 의존성이 아닙니다.

### 트렌드 시계열 — `trendwatch.py`

결정론적 유튜브 트렌드 스냅샷 수집기 + 속도/반감기 리포트. 고정 워치리스트
추적과 **차트 모드**(일일 인기 차트를 모집단으로 적재 → 진입/이탈/churn/체류
통계)를 분리 — 워치리스트는 늙지만 차트는 늙지 않는다는 실측 판단이 설계에
반영되어 있습니다. Windows 작업 스케줄러로 일일 자동 수집.

### 알파 계층 — 반증 가능한 가설 루프

`hypothesis → finding(앵커) → triangulate → predict(resolve_by 기한) → resolve`
루프로, "숨은/저평가 X"를 공개 조각의 **조립**으로 추론하고 반증 가능한
예측으로 등록합니다. 쌍둥이 **debunk 모드**(`--mode debunk`)는 유행 주장을
반증 명제로 박아 1차 소스와 대조합니다.

- `ALPHA_PLAYBOOK.md` / `ALPHA_ARCHITECTURE.md` — 운영 계약. **ALPHA 스탬프는
  다섯 조건 전부**를 요구합니다(`_ALPHA_CRITERIA`): ①확증 신호가 **2종 이상
  모달리티**(web/structured/document/av/image — "웹 4개"로는 절대 통과 못 함:
  텍스트 편향을 코드가 막는 레버) ②독립 eTLD+1 ≥3곳 ③**순-독립 수렴**(확증
  독립출처 > 반증 독립출처) ④에코 아닌 고유 주장(복붙 에코는 확증 수에서
  실격) ⑤반증 가능한 predict ≥1. 하나라도 미달이면 미달 사유를 나열한
  `RECON`으로 강등됩니다(예: `[RECON: single-modality, thin-independence(2<3)]`).
  기준 자체도 에이전트가 `criteria=`로 덮어쓸 수 있습니다 — "알파의 *정의*이지
  척추에 박제된 방법론이 아니다"(코드 주석).
- `check_shapes.py` — 증거 형태(정형/비정형/영상 등) 예산 검증
  (기본은 경고 — 하드 쿼터가 "뉴스를 JSON로 재포장"을 유발한 실측 후 완화).
- `validate_independence.py` — 소스 독립성/에코(같은 보도자료 재탕) 검증.
- `harvest_corrections.py` — 과거 런의 교정 패턴 수확 → 다음 런의 체크리스트.

### 계보정·충분성 레이어

- **예측 계보정**: `predict → resolve → calib`가 Brier 점수와 신뢰도 버킷
  테이블을 누적합니다 — "리서치가 좋아지고 있는가"를 감이 아니라 적중률로
  채점합니다. 피드백이 가장 느린 레이어라 *먼저* 켜라는 것이 운영 수칙.
- **충분성 등급**: `standard / published / grade` — 에이전트가 기준을
  선언하고(**DECLARE-THEN-CHECK**) 코드는 체크+카운트만 합니다. 최신성·폭·
  독립성·일관성·추적성·모달리티 6개 도메인이 GRADE·Denzin triangulation·
  W3C PROV·ISO/IEC 25012 같은 외부 표준에 명시적으로 사상되어 있고, 코드
  내장 기본값은 0입니다. 등급은 신호이지 게이트가 아닙니다("grade ≠ gate";
  기본은 안 매김 — 캐주얼 조회에 학술 루브릭을 들이대지 않음). 상황별
  `--knobs` 프로파일 쿡북은 `EVIDENCE_PROFILES.md`.

### 콘텐츠 분석 프레임워크 — `FRAMEWORK.md`

숏폼이 "왜 터졌는지"를 후킹·촬영·편집·리텐션 등 23개 크래프트 레이어로
분해하는 절차서. 모든 줄에 **OBSERVED / INFERRED / UNKNOWN** 라벨과
[timestamp]/[frame] 근거를 강제 — "어떤 영상에도 맞는 말이면 지워라"가
규율입니다.

### vendored 획득 엔진 — `vendor/insane-search/`

벽 있는 페이지(위장 그리드·WAF)용 fetch 엔진의 **engine-only** 벤더링
(원저작 [fivetaku/insane-search](https://github.com/fivetaku/insane-search),
MIT — `vendor/insane-search/LICENSE`·`PROVENANCE.md`로 귀속, 커밋 핀 고정):
SSRF 가드(사설/루프백/메타데이터 IP + DNS 리바인딩 방어) + 프롬프트 인젝션
탐지 + per-host 학습(로컬 JSON만, 네트워크 0) 내장. phone-home·원격 설정
주입이 가능한 플러그인 껍데기는 감사(2026-07-07, ~4,000줄 전수) 후
**의도적으로 제외**하고 엔진만 편입 — "유용한 DNA는 흡수하고 래퍼는 버린다".

### 스킬 정본 — `skills/`

`leesearch`(리서치 라우트 테이블) · `leesearch-alpha`(알파 발굴) ·
`leesearch-video-heavy`(헤비 영상 분석) 스킬의 **정본이 이 저장소에서 버전
관리**되고, `deploy_skills.ps1`/`.sh`로 `~/.claude/skills/`와
`~/.codex/skills/`에 md5 검증 미러링됩니다(멱등; `--check`는 드리프트 시
exit 1 — CI/pre-commit 가드용). `.githooks/pre-commit`이 스킬 변경 시 배포
드리프트와 코어 변경 시 스킬 신선도(`check_skill_staleness.py`,
`last_verified` TTL)를 경고합니다 — 소스·배포본·신선도를 한 몸으로 유지.
스킬 본문의 운영 원칙 한 줄: **"수집은 네이티브, 봉인은 farm."**

## 리서치 루프 (요약)

전체 절차서는 `RESEARCH_RUNBOOK.md`. 골자:

```bash
SLUG=$(python refledger.py open "<조사 목표 한 문장>")
python refledger.py frontier $SLUG open "구글: <검색어>" --kind question   # 시드
python refledger.py ingest $SLUG "<url-or-file>" --note "<맥락>"           # 등록+해시+품질라벨
python refledger.py finding $SLUG "<해석>" OBSERVED <artifact> \
    --quote "<바이트에 그대로 있는 인용구>"                                # 앵커 없으면 거부
python refledger.py verify $SLUG     # dangling/변조/저품질 점검
python refledger.py plan $SLUG       # farm 봉인 계획 생성(실행은 에이전트가 farm MCP로)
python refledger.py digest $SLUG     # 사람용 SUMMARY.md
```

멈춤·라우팅·다음 소스 선택은 전부 에이전트의 판단입니다 — 코드는 상태
(`frontier state`)와 카운트만 노출합니다.

## 검증

- 테스트 **269개, 14개 모듈** — `python -m unittest discover -p "test_*.py"`
  → OK(약 22초, stdlib `unittest`만).
- **적대적 QA 캠페인 4회**가 시나리오 코퍼스·하네스째 커밋되어 있습니다
  (`QA_REPORT*.md`, `SCENARIOS*.jsonl`, `run_q300.py`/`run_stress.py`):
  116 시나리오 → 실버그 9건 수정, 300 → 2건, 정량 300 실행 → 2건,
  적대 스트레스 500 → 2건. **회차마다 실버그 발생률이 떨어지는 수렴 곡선
  (116→9, 300→2, 300→2, 500→2)** 이 검증 메커니즘 자체의 성적표입니다.
  루프가 검증할 수 없는 것 — MEETS 등급이 실제 현실을 추적하는가
  (grade_validity) — 은 숨기지 않고 데이터-게이트로 열어둔 채 문서화되어
  있습니다.
- 설계는 **실코드 레드팀 2회**(farm·hermes 실물과 대조)를 거쳐 출하됐고,
  이후 수정도 실측 근거를 커밋에 남깁니다 — 과장을 발견하면 철회 커밋을
  남기는 것까지 포함해서(예: "'자기발전' 과장 철회 — 실측"). QA가 제안한
  "수정"을 해로워서 기각한 기록도 있습니다(vimeo/bilibili를 `video`로
  라우팅하면 yt-dlp 자동 다운로드 = ToS 위반 → 기각).

## 안전·ToS 경계

- 안티봇/CAPTCHA 우회 없음, TikTok/IG 자동 획득·쿠키 주입 없음(ToS).
  봇 챌린지는 `BOT_WALL`로 라벨하고 멈춥니다; JS 셸은 합법적 브라우저 렌더로
  승격할 *수 있는* 상태로만 분류합니다.
- 시크릿은 env로만(파일 커밋 금지 — gitignore에 패턴 봉인).
- 원본 미디어 비축 금지(don't-hoard): 해시와 추출물만 보존.

## 요구 사항

- Python 3.9+ (개발·테스트 환경은 3.12.10) — 척추(`refledger.py`)·
  `trendwatch.py`·검증 스크립트·테스트 269개 전부 **표준 라이브러리만으로**
  동작합니다.
- 선택(미디어 추출 시, 전부 지연 import — 없으면 해당 추출기만 비활성):
  `faster-whisper`, `torch`+`demucs`, `numpy`, `easyocr`, `Pillow`,
  `soundcard`(WASAPI 루프백); 외부 바이너리 `ffmpeg`/`ffprobe`, `yt-dlp`;
  vendored 엔진용 `curl_cffi`·`PyYAML`; `refdiscover.mjs`용 Node.
- 플랫폼: 척추는 크로스플랫폼, 데스크톱 오디오 캡처(`refrecord`)는
  Windows(WASAPI) 전용.
- 봉인(선택): [browser-agent-mcp-farm](https://github.com/ezboom1111/browser-agent-mcp-farm)
  MCP 서버 — `plan`이 생성한 호출 목록을 에이전트가 실행할 때만 필요.

## farm과의 관계

refcap과 farm은 **의도적으로 분리된 두 저장소**입니다: refcap은 이해·조립·
가설의 척추(두뇌는 에이전트), farm은 변조 증거 봉인·검증의 게이트(결정론
코드). refcap이 farm을 import하는 횟수는 0이고, 연결점은 `plan`이 출력하는
JSON 하나뿐입니다. 이 중립성 자체가 설계 원칙 3번입니다 — 증거 레이어는
특정 실행기에 묶이지 않아야 재사용됩니다.

## 라이센스

**소스공개 — 열람·평가 전용** ([LICENSE](./LICENSE)). © 2026 이지범, all
rights reserved. 포트폴리오 열람과 저자의 작업을 평가하기 위한 무수정 로컬
실행만 허용되며, 그 외의 사용·복제·수정·재배포는 사전 서면 허가 없이
금지됩니다(문의: ezboom1111@gmail.com).
`vendor/insane-search/`는 원저작자(fivetaku)의 **MIT** 라이센스를 따르며
`vendor/insane-search/LICENSE`·`PROVENANCE.md`로 귀속을 유지합니다.
