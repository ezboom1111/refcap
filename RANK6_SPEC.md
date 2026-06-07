# Rank-6 증거-기준 층 — 개발 스펙 (2026-06-07)

출처: 61-에이전트 워크플로 = 5 표준조사(WebSearch 그라운딩: GRADE·PRISMA·Oxford CEBM·Bradford Hill·W3C PROV·C2PA·ISO/IEC 25012·Denzin triangulation·SIFT/IFCN) + **10라운드 경쟁/비평/창의/분석 토론** + 5축 적대검증(4 REVISE, 1 KEEP). 3.6M 토큰. 아래는 검증 sharpening까지 반영한 *빌드 청사진*.

## 닫는 갭
스파인은 *충분성*을 전혀 채점 안 함: 발행일 없음, 최소근거수 없음, 최신성 게이트 없음, 결론별 등급 없음. "이 결론 신뢰가능?"=에이전트의 강제 안 되는 vibe. Rank-6는 그걸 **선언된-바 vs 기계적-체크 등급**으로 감사가능하게 만듦.

## 핵심 원칙: DECLARE-THEN-CHECK (두뇌-인-코드 유지)
에이전트/사용자가 **바를 선언**, 코드는 **체크+카운트만**. 코드-내장 기본값 0(grader가 읽는 기본값=금지된 gyeongju). 바(에이전트)와 등급(코드)은 **분리된 두 명사**. 리트머스: "주제마다 바뀌나?→에이전트. count/date-diff/host-distinct/string-equality인가?→코드."

## 새 명사
- **published_at** (artifact-level, optional): 콘텐츠 발행일, 에이전트 공급, `recency_basis='declared_date_unverified'` 자가라벨. `ts`(캡처시각)와 다름. 제로-마이그레이션(`ledger_append(**row)`). 바이트에서 추론 금지.
- **conclusion_id** (finding-level, optional ''): 불투명 에이전트 그룹키. 유일한 비-제로-마이그레이션(record_finding 시그니처). **정확-문자열 그룹만** — 코드는 finding을 절대 군집 안 함. 없으면 채점 비가시.
- **kind='standard'** 행 (에이전트, `set_standard()`): 바. `standard_id=sha256(정규화 knobs)`. append-only=움직인 골대 가시.
- **kind='conclusion_grade'** 행 (코드, `grade_conclusion()`): 체크. 도메인별 {value,bar,met,slack}, overall 4상태, 핀된 standard_id, inline `sufficiency_not_truth=true`.

## 선언 knobs (전부 화이트리스트+closed; 생략⇒그 도메인 UNGRADED, 절대 기본값화 안 함)
`min_independent_sources` · `min_distinct_hosts`(가드: ≤sources) · `max_age_days` · `min_dated_fraction` · `dup_similarity`(Jaccard tau—에이전트 선언, 하드코딩 금지) · **`fatal_domains`**(어느 도메인 SHORTFALL이 overall SHORTFALL—코드가 특정 도메인 특권화 0; 가드: {traceability}만이면 invalid) · `min_distinct_source_types`(optional, 기존 `type` 필드 문자열-distinct만).

## 5 기계적 채점 도메인 (각각 표준에 명명)
| 도메인 | 표준 | 계산 |
|---|---|---|
| Currentness | ISO/IEC 25012 | date-diff(as_of, published_at), 4상태 |
| Breadth/Volume | GRADE imprecision | 유효 독립소스 수 (union-find) |
| Independence | Denzin triangulation | distinct `_host`(eTLD+1) 수 |
| Consistency | GRADE inconsistency | `_numeric_conflicts` 재사용 (boolean) |
| Traceability | W3C PROV / cite-or-fail | always-met (sha256 존재) |

## grade_conclusion(rdir, conclusion_id, standard_id, as_of=None) — 알고리즘 (sharpening 반영)
- **STEP 0 BIND**: `standard_id`는 **명시적 에이전트 인자**(predict 앵커처럼 존재검증, unknown이면 ValueError; "latest/only standard"로 폴백 절대 금지=어느 바가 적용되나=두뇌결정). standard_id를 등급에 핀.
- STEP 1 ASSEMBLE: supports = 이 conclusion_id의 findings → artifacts → corroborated_by union.
- **STEP 2 BREADTH = 두 개의 명시적 파티션**(검증 sharpening): (a) 독립성=eTLD+1 host 컴포넌트(튜너블 0); (b) echo=shingle-Jaccard near-dup, cutoff tau=선언된 dup_similarity. **3개 카운트 보고**: n_distinct_hosts(상한), n_after_echo_collapse(하한), gap='syndication 의심' 플래그. **고정 표현(코드소유, 비-주제별): shingle width k 핀 + `_numeric_conflicts`의 기존 CJK-aware 토크나이저 재사용**(k/정규화로 주제민감성 밀반입 차단). sort-stable 대칭 union-find(sha256,artifact_id 정렬)=순서무관 카운트(shuffle-20x 결정성 테스트). 빈 `_host`는 절대 all-to-1 붕괴 안 함(R9 치명버그)→declared_origin_only + breadth_basis 스탬프.
- STEP 3 RECENCY: support별 4상태(ABSENT/UNPARSEABLE/FUTURE→invalid/OK), strptime ~6줄 refinsight에서 **포팅**(two clocks, _expired 재사용 금지). dated_fraction<min_dated_fraction→UNKNOWN. n_undated=4번째 카운트(윈도 제외). eff_n_within_window=in-window 그룹만 breadth(stale-echo tell).
- STEP 4 CONSISTENCY: `_numeric_conflicts(supports)` BOOLEAN만.
- STEP 5 DEPTH/source_type(선언시): count만, 다운그레이드만 가능.
- STEP 6 TRACEABILITY = always-met.
- STEP 7 OVERALL 4상태(UNGRADED/UNKNOWN/SHORTFALL/MEETS), **선언된 fatal_domains에서만 유도**(코드 특권 도메인 0). 불변식: MEETS는 breadth AND recency가 *해시-핀된 artifact 위 arithmetic*으로 carried돼야; declared_unverified(depth/source_type)는 다운그레이드만. 출력=도메인별 **signed-slack 벡터**(스칼라/가중치 0=숨은 바 0) + ordered shortfall_reasons + not_assessed + **binding_domain(argmin relative slack, 명시적 total-order tiebreak: slack ASC, fatal-우선, canonical 도메인순 — 아니면 row hash 비결정)**.

## 데이터 조합 = 구조의 TABULATION, 절대 점추정 아님
코드가 median/가중값 내면=어느 숫자가 맞나 adjudicate=두뇌-인-코드(`_numeric_conflicts`가 이미 "NEVER adjudicates" 계약). 신디케이트 복사본 붕괴(union-find)→독립 컴포넌트+distinct type 카운트→numeric_conflicts→충돌시 양쪽 값 surface. SKIP: inverse-variance/I²/Dempster/Bayesian(없는 분산 필요/predict-calib 소관).

## 검증 = grade_validity(rdir) — 비순환 오라클
grade와 resolved prediction을 *둘 다* 가진(공유 conclusion_id) 결론에 대해: 2×2 grade×outcome, delta=hit_rate(MEETS)−hit_rate(SHORTFALL). predict/resolve/calibration 그대로 재사용. **sharpening**: (a) **신뢰도-층화 delta**(calibration 5버킷 내)로 "등급이 그냥 confidence 재진술"(confound) surface; (b) bare delta>0 대신 **Wilson/2-prop-z 하한>0 + 셀별 최소 k**; SHORTFALL 셀 얇으면 abstain(selection bias). N≥20까지 'unvalidated' 라벨로 출하.

## MVP (랭크순 — 이것부터)
1. **published_at** on artifacts (문서만, 코드 0).
2. **record_finding에 conclusion_id=''** (유일한 시그니처 변경, 하위호환).
3. **set_standard()** → kind='standard' (closed 화이트리스트, coherence 가드, standard_id 반환).
4. **grade_conclusion(rdir, conclusion_id, standard_id)** → kind='conclusion_grade' (~80 LOC: 2-파티션 breadth + recency + boolean consistency + fatal rollup + signed-slack). 핵심.
5. **verify**가 conclusion_grades 블록 fold(standard 행 ≥1일 때만); SUMMARY는 n_shortfall+fatal+n_ungraded만; `ok` UNCHANGED(advisory).
6. **grade_validity** (deferred-but-planned, N≥20까지 'unvalidated').
DEFER(#6 lift 후): claim_value, origin_id, sample_n, dual-consensus fusion, leave-one-out.

## 통합 (중복 0)
verify advisory 블록(ok 불변, fake_corroboration처럼). refinsight=TWO CLOCKS(strptime ~6줄 복사; published_at≠captured_at). predict/resolve/calibration=grade_validity가 그대로 재사용. farm import 0. CLI: standard/grade/gradevalidity 서브파서.

## 정직한 천장 (행마다 inline 자가라벨)
- *충분성*을 채점(선언된 바 대비 충분히 최신·distinct-host·비중복·무충돌 교차검증), **절대 진실 아님**. MEETS="잘 뒷받침+감사가능"이지 "맞다" 아님.
- fabrication-at-capture=열린 지붕(틀린 published_at=declared_unverified).
- eff_n=중복-바닥, 독립성의 *상한*(에이전트 작성 quote span 디덥이지 소스 바이트 아님; paraphrase+fresh-host에 뚫림; 같은 보도자료 인용한 진짜 독립 2소스를 과붕괴 가능).
- CIB/봇/astroturf 탐지 없음(단일사용자 IP/계정 그래프 0). 누락-체리픽 비기계화(분모만 surface).
- NOT ASSESSED(명명, 절대 위조 안 함): risk-of-bias·publication bias·indirectness·정확성/신뢰성·I²/Egger·OCEBM 소스등급.
- 검증은 영원히 abstain 가능(단일사용자가 N≥20 못 채울 수)=규율이지 입증된 오라클 아님을 정직히.
