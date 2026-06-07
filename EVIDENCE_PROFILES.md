# 증거-기준 평가표 (의도별 프로파일 가이드)

이건 **사람이 읽고 복사·수정하는 가이드**다 (코드가 읽는 기본값이 *아니다* — 그건 gyeongju 임계값트리 금지). 너의 *의도*에 맞는 프로파일을 골라 `set_standard --knobs`로 *해소된 숫자*를 박으면, `grade`가 그 평가표대로 채점하고 루프는 **MEETS까지** 돈다. 주제마다 숫자는 *네가 확정*한다.

> **최신성(recency)은 OPTIONAL이다.** `max_age_days`를 빼면 채점 안 함. `fatal_domains`에 `recency`를 안 넣으면 멈춤에 영향 0. **과거·정설·장기 조사엔 recency를 *안 건다*** — 시스템은 최신을 강요하지 않는다. "유기적"의 핵심이 이것.

## 도메인 한눈에
- `min_independent_sources` = **물량**(붕괴 후 *독립* 소스 수) · `min_distinct_hosts` = 독립 도메인 수
- `max_age_days` = **최신성**(가장 최신 발행물의 나이 상한; *생략 가능*) · `min_dated_fraction` = 날짜 보유 비율
- `dup_similarity` = 신디케이트/복사본 붕괴 임계 · `min_distinct_source_types` = 소스 종류 다양성(html/json/transcript)
- `required_modalities` = **모달리티 커버리지 강제** = 선언한 *클래스가 각각* 존재해야 함 (web/structured/document/av/image). *카운트가 아니라 특정 클래스 요구* → **"웹 4개"로는 절대 통과 못 함**(영상·1차문서·정형이 0이면 SHORTFALL). 텍스트 편향을 코드가 막는 레버.
- `fatal_domains` = **무엇이 치명(SHORTFALL을 강제)인가** = 너의 의도의 핵심 (breadth/recency/consistency/source_type/**modality**). modality·source_type은 *downgrade-only*(단독으론 MEETS 못 만듦 — 반드시 breadth 등 arithmetic 도메인과 함께).

---

## 1. breaking-trend — 속보·실시간 트렌드 (최신성 지배)
```json
{"min_independent_sources":2,"min_distinct_hosts":2,"max_age_days":1,"min_dated_fraction":1.0,"dup_similarity":0.4,"fatal_domains":["breadth","recency"]}
```
*언제*: "지금 뜨는 사운드/밈/이슈". 하루만 지나도 stale. 발행일 필수.

## 2. trend-momentum — 며칠~몇주 트렌드
```json
{"min_independent_sources":3,"min_distinct_hosts":2,"max_age_days":14,"min_dated_fraction":0.7,"dup_similarity":0.4,"fatal_domains":["breadth","recency"]}
```
*언제*: "이 트렌드 2주 내 정점?" 같은 마케팅 타이밍. recency를 `predict/resolve/calib`와 묶어 검증.

## 3. market-size / competitive — 시장규모·경쟁 (물량+무충돌 지배, 수개월 허용)
```json
{"min_independent_sources":3,"min_distinct_hosts":3,"max_age_days":180,"min_dated_fraction":0.5,"fatal_domains":["breadth","consistency"]}
```
*언제*: 시장 크기·가격·점유율. 최신성은 넉넉(180일), 대신 **독립 3+ 도메인 교차검증 + 모순 없음**이 치명.

## 4. fact-check — 사실 확인 (진실은 빨리 안 만료)
```json
{"min_independent_sources":2,"min_distinct_hosts":2,"max_age_days":365,"fatal_domains":["breadth","consistency"]}
```
*언제*: 바이럴 주장 검증. 2-소스 규칙 + 모순 없음. 신디케이트 경고(`syndication_suspected`)를 꼭 확인 — 같은 통신사 기사 3개 재게재는 *1소스*.

## 5. ★ historical / longitudinal — 과거·장기 추세 (recency 미게이트)
```json
{"min_independent_sources":3,"min_distinct_hosts":3,"fatal_domains":["breadth","consistency"]}
```
*언제*: "2019년 매출", "10년간 추세", 정설/연혁. **`max_age_days` 자체를 뺀다** → recency는 UNGRADED, 멈춤에 영향 0. 물량+독립+무충돌만 본다. 과거가 핵심이면 *최신을 요구하지 않는 게 정답*.
- *특정 과거 시점 기준*으로 채점하려면: `grade $SLUG C1 $STD --as-of 2020-01-01` (그날 기준으로 나이 계산).
- *주의(정직한 한계)*: `published_at`은 콘텐츠 *발행일*이지 *다루는 시기*가 아니다. "2019를 다룬 2024년 분석"은 발행일 2024 → 이건 코드가 자동 구분 못 함. "그 과거 시기를 실제로 커버하나"는 *네 판단*(finding에 명시). 향후 'period-coverage' 도메인 후보.

## 6. academic / deep-synthesis — 학술·심층 종합 (넓은 triangulation, 나이 매우 관대)
```json
{"min_independent_sources":4,"min_distinct_hosts":3,"min_distinct_source_types":2,"max_age_days":1825,"min_dated_fraction":0.5,"fatal_domains":["breadth"]}
```
*언제*: 리터러처 리뷰·방법론. 독립 4+ 소스, 소스 종류 2+(논문 json + 페이지 html 등), 5년까지 허용.

## 7. idea-building / marketing-concept — 아이디어·기획 (다양성+신선도 균형)
```json
{"min_independent_sources":3,"min_distinct_hosts":3,"min_distinct_source_types":2,"max_age_days":90,"min_dated_fraction":0.5,"fatal_domains":["breadth","source_type"]}
```
*언제*: 아이템 기획·콘셉트 발굴. *다양한 종류*의 소스(트렌드+리뷰+경쟁사)에서 넓게. source_type을 치명으로 = 한 우물만 파는 걸 막음.

## 8. ★ primary-source / institutional — 1차자료·기관 리서치 (모달리티 커버리지 강제)
```json
{"min_independent_sources":3,"min_distinct_hosts":3,"required_modalities":["structured","document"],"fatal_domains":["breadth","modality"]}
```
*언제*: 정부·공공기관·1차자료가 핵심인 조사 (정책, 기관 성과, 연구비/과제 DB, 통계). **`required_modalities`로 정형(structured: 정부 CSV/JSON/API)+1차문서(document: PDF 공시·요강)를 *강제***. 뉴스/블로그(web)만으로는 breadth가 차도 modality SHORTFALL → *2차 텍스트로 슬쩍 후퇴 불가*. 영상 증언이 핵심이면 `"av"` 추가.
- *왜*: 내(에이전트)가 텍스트/웹서치로 만족하고 멈추는 편향을 **게이트가 강제로 막음** — 1차 정형/문서가 0이면 초록불이 안 뜬다.
- *벽=공개*: 1차 모달리티가 JS/로그인 벽에 막히면 그 클래스가 `missing`으로 남아 modality SHORTFALL → 커버리지 구멍이 *가시화*된다(은밀한 2차 후퇴가 grade에 드러남). 벽은 라벨(BOT_WALL/LOGIN)로 보존하고 video-heavy/OCR로 우회.

---

## 루프 사용 (어느 프로파일이든)
```bash
STD=$(python refledger.py standard $SLUG --knobs '<위 JSON>' | python -c "import sys,json;print(json.load(sys.stdin)['standard_id'])")
# gather -> grade -> SHORTFALL이면 부족분(어느 도메인)만 더 채워 -> 재grade -> MEETS까지
python refledger.py grade $SLUG <conclusion_id> $STD
```
- **물량 부족** → `breadth` SHORTFALL → 독립 소스 더 (같은 도메인 복사본은 안 셈).
- **최신성 부족**(켰을 때) → `recency` SHORTFALL → 더 최신 출처. *과거 조사면 애초에 안 켠다*.
- **품질=종합**: 물량(breadth)+독립(distinct_hosts)+무충돌(consistency)+추적(traceability) 전부 *선언한 fatal*에서 MET여야 MEETS.

## 정직한 천장
이 평가표는 **충분성**(물량·독립·최신·무충돌이 *선언한 바*를 충족)을 채점하지 **진실**은 아니다(열린 지붕). `eff_n`은 독립성의 *상한*(paraphrase+새 호스트엔 뚫림). MEETS = "잘 뒷받침+감사가능"이지 "맞다"가 아니다. 행마다 `sufficiency_not_truth=true`로 명시된다.
