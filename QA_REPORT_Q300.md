# Rank-6 grade 층 — 300 정량 시나리오 QA/QC (2026-06-07)

방법: 12-영역 병렬 에이전트가 *결정론적* `grade_conclusion`을 겨냥해 300 시나리오 생성 — band별 **많이(above 37) / 적정(at 31) / 조금(below 70) / 경계(edge 123) / 무효(invalid 39)**, 각 시나리오에 *독립 reasoned 기대값*. 하니스 `run_q300.py`가 각 시나리오의 ledger를 만들어 **실제 grade에 300개 실행** → expected vs actual *기계 비교*.

> 앞선 도메인-QA는 *설계-커버리지 산문*이었지만(라이브 리서치는 실행 불가), grade는 *결정론적 코드*라 **300개를 실제로 돌려 PASS/FAIL을 *측정***한다 — vibe 아닌 기계 검증.

## 결과: 300 실행 → 진짜 코드결함 2개 적출·수정
**PASS(exact) 266 / 34 mismatch** → triage:

### 진짜 코드결함 2개 (수정, TDD)
| 결함 | 수정 |
|---|---|
| **[BUG] non-list `fatal_domains`** (예: `fatal_domains=5`) → grade가 `set(5)` → **크래시**. set_standard는 경고만 하고 통과시킴 | grade에 `isinstance(list)` 가드 → 비-list는 fatal 비움 → UNGRADED(선언시 이미 `fatal_domains_not_list` 경고). bare-string도 같이 안전화. |
| **[FALSE-CONFLICT]** `_numeric_conflicts`가 공통 *filler 단어*("according"/"which"/...)로 거짓 모순 생성 → consistency가 *fatal*일 때 **잘못된 SHORTFALL** (이제 grade에 이빨이 있어 중요) | `_EN_STOP`(영어 filler 집합) 추가, `_CJK_STOP`처럼 토큰에서 제외. 단위어(percent 등)는 유지 — 실제 모순(CPI 3% vs 4%) 신호. |

### 나머지 ~32 = oracle 오류 (코드는 정확, 에이전트 기대가 틀림)
- 대부분: `consistency`를 `null`로 기대 → 실제 코드는 *항상* `met=(무모순)` 계산(consistency엔 knob 없음=항상 advisory 계산, 의도된 동작). overall은 다 맞음.
- 일부: `strptime`이 비-제로패딩 날짜(`2026-6-1`)를 *거부할 거라* 오판 → 실제 Python strptime은 lenient 파싱(정상·더 견고).
- **★ 핵심 invariant 전부 코드 정확**: meets-not-on-unverified(declared_unverified만으론 MEETS 불가)·breadth(eff/distinct_hosts)·recency(age 경계·dated_fraction)·overall(fatal_domains 4-state) — 19/8/5건 "실패"가 전부 consistency/recency 도메인 *오라벨*이고 overall은 일치.

**수정 후: ERROR=0, 128 단위테스트 GREEN(신규 2).**

## band별 검증된 것
- **많이/적정/조금**: `eff==bar` vs `bar-1`, `min_distinct_hosts` 게이트, 호스트·subdomain(news.naver.com→naver.com)·co.kr(3-label 유지) 붕괴, dup-Jaccard tau 경계 — 정확.
- **recency**: `age==max_age` vs `+1`, `dated_fraction` 게이트, future/absent/garbage 날짜 — 정확(lenient 파싱 포함).
- **overall**: fatal_domains 조합(없음→UNGRADED, carrier 부재→UNKNOWN, 비-arith만→UNGRADED), 무효/비일관 standard의 `standard_warnings` — 정확.

## 결론
grade의 *정량 수치 경계*를 300개 실행으로 검증, 진짜 결함 2개(non-list 크래시·filler 거짓모순)를 실측·수정. 나머지는 oracle 노이즈로 *코드 정확성 재확인*. 재현: `python run_q300.py scenarios_q300.jsonl` (하니스+시나리오 보존).
