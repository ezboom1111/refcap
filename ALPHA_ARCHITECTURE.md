# ALPHA 아키텍처 — leesearch 생태계를 "검색기"에서 "알파 추론기"로 (2026-06-07)

## 갭 (왜 이게 필요한가)
연구엔 3층: **검색**(documented된 것)→**집계**(교차검증·충분성)→**알파**(아무 소스도 진술 안 한 *비-자명·선제적* 결론을 *흩어진 약한 조각*에서 추론/예측). 지금 시스템은 1~2층은 강한데 **3층(알파)에서 멈춘다**. 원인=신념 아니라 *비용경사+조기만족+침묵후퇴+가설/조립 장치 부재*의 창발. 알파는 (a) 소스 *사이*의 빈틈·모순·부재에 살고, (b) *비싼/벽 뒤 데이터*(남들이 안 보는 것)에 살고, (c) *여러 약신호의 조립*에 산다.

> 핵심 통찰: **내가 지은 척추(corroboration+predict)는 이미 *알파-삼각측량 엔진*이다.** 갭은 도구가 아니라 — 그걸 *FACT 검증*에만 쓰고 *INFERENCE 추론*에 안 겨눴다는 것. 그래서 알파 아키텍처 = 새 거대 시스템이 아니라 *기존 엔진을 추론에 겨누는 얇은 레이어 + 벽뚫기 데이터 획득*.

## R1 — 알파 커널 [BUILT, commit 이번 턴, 140 tests green]
새 noun 최소화: **signal = `hypothesis_id`+`polarity` 태그가 붙은 기존 finding**(cite-or-fail 유지, 노운 안 늘림).
- `set_hypothesis(thesis, signature, decay)` — 반증가능 *가설* 선언(NOUN). signature=패턴, decay=왜숨었나/언제 끝나나.
- `record_finding(..., hypothesis_id, polarity)` — polarity ∈ {confirms, disconfirms, neutral}. *약한 조각*을 가설에 태그.
- `triangulate(hypothesis_id)` — **독립 수렴만 REPORT**: confirming/disconfirming 수, *독립*(distinct eTLD+1 host AND modality) confirming 수, modality 다양성, net_independent. **임계값 0**(알파인지·decay는 에이전트 판단 = two-brain 경계 유지).
- `predict(..., hypothesis_id)` — 가설에 *반증가능 예측*을 묶음 = 선제적 알파가 *나중에 resolve로 검증*(비순환). **불용 중이던 Rank-1을 비로소 소비** = 5번(검증) 전진.

### 알파 루프 (에이전트가 돈다)
```
1. set_hypothesis(thesis, signature)   # "비플래그십 + 단일공기업 단독공급 + 공동특허 + 집중아웃풋" 시그니처
2. 신호 수집 (alt-data, 벽 뚫어서):    # NTIS 연구자별·특허 co-assignee·창업·배치·김박사넷 — 각각 약함
   record_finding(..., hypothesis_id=H, polarity=confirms|disconfirms)
3. triangulate(H)                       # 독립 약신호가 몇 개 수렴? (단일소스 아님)
4. 에이전트 판단: 수렴이 결정적인가? why_hidden? decay?  (코드 안 정함)
5. predict(..., hypothesis_id=H)        # 반증가능 베팅 등록 -> 몇 주/달 뒤 resolve로 검증
```

## R2 — 벽뚫기 에스컬레이션 (alt-data 획득) [NEXT, hunt가 요구한 모양대로]
알파는 *남들이 안 보는 데이터*에 있는데 그게 정확히 내가 후퇴하던 벽(JS/로그인). 자동 에스컬레이션 필요:
- **WebFetch JS벽 → farm/Chrome 브라우저 렌더** (공개 JS페이지: NTIS 연구자별·academyinfo 값·김박사넷 공개·하이브레인넷). 지금은 수동 — *루프에 "JS벽 감지→브라우저 렌더" 분기*를 표준화.
- **공식 Open API + serviceKey** (data.go.kr·KOSIS·KISTI 15138962·KETEP) = 정형 데이터 *최선책*. 키는 사용자 발급(무료).
- **DOWNLOAD_ONLY → 로컬 파싱** (BK21 CSV; PDF는 이미 pdftotext로 실증).
- **로그인 벽**(블라인드·김박사넷 별점·에타) = **자동로그인 금지**(ToS/계정). 사용자 인증 세션→내가 읽기, 또는 공개분만 + LOGIN 라벨.
- 코드 변화 최소: 런북 규칙(이미 13번)에 더해, ingest가 `quality_label=JS_WALL`을 주면 *farm 브라우저 재시도*를 권고하는 얇은 헬퍼(선택). 두뇌-인-코드 아님(메커니즘만).

## R3 — leesearch-alpha 서브스킬 [PLAN/SPEC]
leesearch 라우터에 **알파 브랜치** 추가: 사용자가 "숨은 알파/저평가 발굴/남들이 모르는" 의도면 → `leesearch-alpha`가 *알파 루프*(R1)를 오케스트레이트(가설→신호유형별 fan-out→triangulate→predict→decay). 기존 `leesearch-video-*`와 동렬. 위임만(MCP는 스킬호출 불가=에이전트가 description으로 선택). 정본=refcap 레포, ~/.claude + ~/.codex 양쪽.

## R4 — grade_validity (5번 검증) [PLAN, hunt로 예측 쌓인 뒤]
알파/등급이 *현실과 맞는지*는 아직 미검증(N=1 toy). 이제 predict에 conclusion_id+hypothesis_id 조인키가 *준비됨*. grade_validity = grade×outcome (또는 thesis×outcome) 2×2 비순환 오라클(MEETS/고신뢰 가설이 실제로 더 맞나, Wilson 하한, N≥20까지 unvalidated). **데이터-게이트**(코드 ~25줄, 단 *실제 resolved 예측 ≥10~20개* 먼저). → 알파 루프를 실제로 돌릴수록 채워짐.

## R5 — 신호 IC/decay 스코어 [DEFER]
신호유형별 *정보계수*(어느 신호가 실제로 예측력 있나)·decay 정량화 = signal-engineer 영역. **resolved 예측이 쌓이기 전엔 짓지 마라**(검토 경고: caller 없는 축 금지). triangulate의 net_independent로 충분, IC는 데이터 쌓인 뒤.

## leesearch 생태계 갭 (현재 부족한 것)
| 갭 | 상태 | 다음 |
|---|---|---|
| 알파 가설/삼각측량 레이어 | ✅ BUILT (R1) | hunt 신호를 적재 |
| 벽뚫기(JS/API/다운로드) 표준 분기 | ⚠️ 수동 | R2: 브라우저 에스컬레이션 표준화 |
| leesearch-alpha 라우팅 브랜치 | ❌ 없음 | R3: 서브스킬 |
| 예측 검증 오라클(grade_validity) | ❌ 미구현(데이터 0) | R4: 예측 쌓고 → 짓기 |
| 신호 IC/decay 정량 | ❌ 의도적 보류 | R5: 데이터 후 |
| CLI 노출(hypothesis/triangulate) | ❌ Python API만 | 소소 follow-up |

## 규율 (과잉금지 — 검토 반영)
- **USE→배워서→짓기**: alpha hunt(실행)가 *아키텍처가 뭘 요구하는지* 드러낸 뒤 R2~를 짓는다. R1 커널만 *지금* 지은 건 (a) 알파의 정의적 primitive라 모양이 안 변하고 (b) 불용 Rank-1을 *소비*해 검증(5번)을 전진시키기 때문 — 검토의 "caller 있을 때만 / 검증 enabler"를 통과(sample_n과 달리 demanding task=hunt가 *지금* 요구).
- **새 adequacy 축 금지**(검토 biggest-risk): triangulate는 게이지가 아니라 *소비 레이어*. 임계값 0 유지.
- **두뇌-인-코드 0**: 코드는 noun+count, "알파인가/얼마나 숨었나/언제 끝나나"는 에이전트.
