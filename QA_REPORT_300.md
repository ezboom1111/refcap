# refcap/leesearch — 300-시나리오 크로스도메인 QA/QC 리포트 (2026-06-07)

방법: 12 도메인(경영·여행·마케팅트렌드·쇼핑·경쟁·로컬·테크·금융·뉴스·학술·부동산법규·헬스푸드) 병렬 에이전트가
각 25 시나리오를 생성하며 **실제 코드(refledger.py·refinsight.py)와 스킬(leesearch/youtube-research SKILL.md)을 읽고**
라우팅·데이터경로·인사이트툴 적합성을 평가. JS 집계 → 갭 종합 → 진짜결함 적대검증(general-purpose 리뷰어). 16 에이전트.

> **정직한 범위**: 300개 *라이브* 리서치 실행이 아니라 **설계-커버리지 QA**(이 시스템이 이 요구를 *처리할 수 있나*).
> 라이브 정확도는 Rank-1 calib / Rank-4 refinsight가 실사용에서 누적 측정. 116-시나리오 캠페인과 동일 방식(그때 결함 9개).

## 커버리지 (300)
| | covered | partial | gap | design-limit | 실결함-시나리오 |
|---|---|---|---|---|---|
| 합계 | 142 | 129 | 29 | 141 | 29 |

- 데이터형태: 반정형 110 · mixed 66 · 정형 64 · 비정형 60.  난이도: adversarial 115 · deep 113 · simple 66.
- 라우팅: deep-browser-research 149 · video-heavy 49 · market-scan 44 · video-light 27 · **unclear-or-none 16** · farm 8 · product-planning 7.

## ✅ 발견→수정한 진짜 결함 (적대검증 FIX, TDD)
| # | 결함 (실측 재현) | 수정 |
|---|---|---|
| ① **[high · 최다 인용]** | 원격 http(s) **pdf/csv/txt/image/audio/transcript** URL이 register-only 분기로 가서 `sha256_file(URL) if os.path.exists(URL)`=False → **sha=None, 바이트 0 = 빈 unverifiable 셸**(arxiv PDF·raw CHANGELOG.md·원격 CSV 전부 깨짐) | register-only 직전에 http면 기존 `_http_get`(SSRF가드+50MB캡 재사용)으로 다운로드 후 로컬 등록. quality=UNKNOWN 유지(콘텐츠분류기 0=두뇌-인-코드 유지). 원격 transcript도 동일. |
| ② **[med]** | `detect_type` JSON 휴리스틱이 `.json`/`api.*`만 → 비-api 키드 엔드포인트(openapi.naver.com·dapi.kakao.com·registry.npmjs.org·data.go.kr)가 html로 오라우팅 → `json_quality`(API_ERROR/MALFORMED/rate-limit) 건너뜀, HTML튜닝 web_quality가 JSON을 오라벨 | html 분기에서 **기계적 json.loads sniff**: 본문이 JSON으로 파싱되면 json_quality, 아니면 web_quality. depth-0 유지(`/api` substring 과매칭 재발 0 — HTML은 파싱 실패). |

**③ [DESIGN-LIMIT — 수정 거부]**: `detect_type`가 비-YT/틱톡/IG 영상 *페이지* URL(vimeo/bilibili/douyin)을 html로 반환 = 증상은 실재하나 제안된 "video 반환" 수정은 **유해**(refauto/yt-dlp 자동다운로드 유발 = ToS 위반). 현재 'html'이 *의도된 ToS 안전장치*. 무수정. (적대검증이 잘못된 "수정"을 걸러낸 사례.)

## 📋 확정 설계한계 (천장 — 버그 아님, 받아들일 것)
- **fabrication-at-capture = 열린 지붕**: cite-or-fail=추적이지 진실 아님(포토샵 스샷·환각 ASR 숫자도 게이트 통과). 방어=상류 품질라벨 + 에이전트 교차확인.
- **품질게이트 sparsity 맹점**: web/json_quality는 visible<1500자일 때만 wall 라벨 → *콘텐츠 풍부한 페이월/로그인 teaser*(Statista/Crunchbase)나 JS-rich-but-empty 셸은 OK 오라벨 → 에이전트 규칙2/3가 load-bearing(정직 라벨이 *유일하게* 미끄러지는 지점). "뚱뚱한 벽" 탐지는 콘텐츠분류기=gyeongju 퇴화 재발이라 코드로 못 닫음.
- JS렌더/인터랙티브(SPA·맵·라이브가격)=stdlib urllib 미도달(farm 브라우저 경로는 deep-browser-research로 존재) · ToS벽(틱톡/IG/페이월) 미우회 · 거래(예약/결제) 범위밖 · 외국어 ASR(lang=ko 핀=모델천장) · PDF 텍스트추출 미구현(에이전트 vision) · 모순/사실독립성/종합 판정은 에이전트(don't-code-the-brain). 교차-호스트 신디케이션(연합뉴스 wire 3사 재게재)은 호스트독립성만으론 못 잡음=에이전트 규칙5.

## 유연성 평결 (정직)
라우팅은 **거의 항상 정확**(라우터가 엉뚱한 leaf로 거의 안 보냄). 실패는 *바이트 도달*이고 대부분 **정직**(BOT_WALL/LOGIN_WALL/PAYWALL/EMPTY 라벨 또는 거절)이지 날조 아님. 인사이트 사다리(predict/calib·CER·fake_corroboration·numeric_conflicts·refinsight)가 전 도메인 adversarial 케이스에 깔끔히 매핑. partial+gap 170개 중 **141개가 의도된 설계한계**.
- **강한 도메인**: 학술(원격PDF 수정 후 gap 0)·경쟁/뉴스(교차검증·호스트독립성)·테크/금융(HTML/JSON 소스일 때).
- **정직하게 약함(=의도된 천장)**: 마케팅트렌드/쇼핑(틱톡/IG·상거래 가격그리드가 ToS벽/JS) — 구조적 천장이지 코드약점 아님.
- **고친 약점**: 위 ①②(원격파일·키드API) = 가장 흔한 요청을 covered→unverifiable로 만들던 기계적 결함.

## 결론
300 시나리오 중 진짜 코드결함 **2개 실측·수정**(원격파일 fetch · JSON sniff), 1개는 ToS 안전장치로 *수정 거부*. **105 테스트 GREEN**(신규 7, ResourceWarning=error, 회귀 0). 나머지 갭 대부분은 *don't-code-the-brain / ToS / 열린지붕*의 정직한 표현. 라우팅·정직성은 견고, 약점은 reach(벽/JS/거래=의도)뿐. 원시 300 시나리오는 `SCENARIOS_300.jsonl`.
