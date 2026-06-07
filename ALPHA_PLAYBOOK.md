# ALPHA PLAYBOOK — 공개 파편 조립으로 알파를 *계속* 찾아나가는 일반 방법론 (2026-06-07)

알파 = *아무 단일 소스도 진술하지 않은* 비-자명·선제적 결론을, **남들이 조립하지 않는 *공개* 파편들**에서 추론. 이건 grad-school 전용이 아니라 **"숨은/저평가된 X를 공개 파편 조립으로 발굴"** 하는 *모든* 문제에 쓰는 일반 루프(숨은 기업·저평가 연구자·떠오르는 트렌드·과소평가 자산).

## 0. 제1원칙 — 로그인/회원 데이터는 알파 경로에서 *제외*
- **EXCLUDED (추구·저장·lead화 금지)**: 김박사넷 별점/한줄평, 블라인드, 취준 카페 회원글, NTIS 연구자 로그인 detail, 유료/멤버 전용.
- *왜*: (a) **범용 불가**(유저/주제마다 인증 다름 → 재현·일반화 안 됨), (b) ToS-회색(자동로그인·계정생성 금지), (c) **엣지가 아님** — 그건 *접근권한*이지 *조립*이 아니다. 알파는 *공개인데 흩어진 걸 조립*하는 데서 나온다. login에 기대면 "남들이 못 보는"이 아니라 "내가 권한 있는"이 됨.
- login-라벨 신호 = *out of scope* (사용자에게 "로그인해줘"도 아님 — 아예 경로 밖).

## 1. 일반 알파 루프 (주제로 파라미터화 — 도메인 무관)
```
thesis  = 시그니처 선언 (set_hypothesis): "숨은 X = {공개신호 A + B + C가 비-자명하게 수렴}"
gather  = 공개 신호유형별 fan-out (아래 2번 택소노미), 각 신호 record_finding(hypothesis_id, polarity)
triangulate(H) = 독립(distinct host AND modality) 수렴 REPORT  ← 단일소스 아님
judge   = 에이전트: 수렴이 결정적인가? why-hidden? decay?  (코드 임계값 0)
predict = 반증가능 베팅 등록 (predict, hypothesis_id) → 미래 resolve로 검증 = 선제적 알파의 증명
refine/iterate  = 부족 레그/미특정 lead를 frontier_open → *다음 패스에서 더 공개 파편* → 재-triangulate (수렴 누적)
```

## 2. 공개(login-free) 알파 소스 택소노미 — 신호유형별
| 신호 | 공개 소스 (접근법) |
|---|---|
| **(a) 수주/자금 집중** | NTIS 공개 프로젝트 facet(ThSearchProjectList SSR) · 나라장터 g2b 용역 낙찰공고/결과 · 알리오 공기업 출연·발주 공시 · 국회 국정감사 자료(공개) |
| **(b) 기술이전** | Google Patents / KIPRIS 공개특허 co-assignee · 기술이전·사업화 공시 · 산학 MOU 보도자료 |
| **(c) 자금 규모** | 대학알리미 값(JS벽이면 뉴스/공시 PDF 미러) · BK21 공개 명단 · DART 공시(기술지주·산학) |
| **(d) 아웃풋** | 벤처확인기업 공시 · 창업/스핀오프 뉴스 · 졸업생 진로(홈피) · Google Scholar/DBpia 공개 인용·공저 · 학회 임원 명단 |
- 벽 만나면(JS): farm/Chrome *렌더*(공개페이지). **로그인 벽이면 멈추고 *다른 공개 소스로 우회*** (그 사실을 라벨로 남김, lead 아님).

## 3. 연속(continuous) — "계속 탐구하고 찾아나가는 단계"
- **1회가 아니라 누적**: append-only ledger에 패스마다 공개 신호를 더 쌓고 `triangulate` 재실행 → *수렴이 자란다*(net_independent↑, modality 다양성↑ = 확신↑).
- **standing 알파 프런티어**: 미특정 lead(예: 서울과기대↔한수원 공동출원 PI), 결손 레그(송종순 b-특허)를 `frontier_open(hypothesis_id)`로 *지속*. 세션 넘어 계속 판다.
- **예측 누적 = 검증 엔진**: 매 픽마다 `predict(hypothesis_id)` → N이 쌓여 N≥20에서 grade_validity가 "선제적 알파가 실제로 맞나"를 채점(R4). *연속 탐구 자체가 검증 데이터를 만든다.*
- **decay 추적**: 각 thesis의 decay(언제 priced-in)를 적어두고, 만료 전 resolve.

## 4. 범용성 + 규율
- **도메인 무관**: 위 루프·택소노미는 thesis만 바꾸면 숨은 기업·연구자·트렌드에 그대로. grad-school은 instance #1.
- **cite-or-fail**: 공개라도 *fetch한 바이트 + verbatim 인용*만. 메모리 진술 금지.
- **two-brain**: 코드는 noun+count(triangulate), "알파인가/왜숨었나/언제끝나나/다음 어디 팔까"는 에이전트.
- **공개라서 재현가능**: 누구나 같은 공개 소스로 검증 가능 = 알파의 신뢰성. (login 기반은 검증 불가 = 알파 아님.)
