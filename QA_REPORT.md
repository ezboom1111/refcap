# refcap 리서치-스파인 — 116 시나리오 QA/QC 리포트 (2026-06-06)

방법: 10 카테고리 병렬 에이전트가 실제 코드(refledger.py)를 **읽고 파이썬 probe로 재현**해 116 시나리오 생성 +
현재 커버리지 정직 판정. 비정형33 / 반정형33 / 정형31 / mixed19 = "모든 데이터 상황" 커버.
자기집계: covered 32 / partial 37 / gap 47. 종합 에이전트가 **추측 아닌 실측**으로 진짜 결함 vs 설계한계를 분리.

## ✅ 발견 후 *수정*한 진짜 코드결함 9 (TDD 재현→수정, test_scenarios.py 17 테스트)
| # | 결함 (실측) | 수정 |
|---|---|---|
| ① | json ingest 분기가 `quality_label='OK'` 하드코딩 → 에러봉투/malformed/rate-limit JSON이 false-OK로 봉인 | `json_quality()` 추가(MALFORMED/API_ERROR/EMPTY) + ingest(json)에 적용 + BAD_QUALITY 포함 |
| ② | `_read_jsonl`이 잘린 마지막 줄에 JSONDecodeError → **verify/digest/plan/ingest 전체 brick** (최고영향) | tolerant skip (부분줄 무시) — 단일 크래시가 전체를 멈추지 않음 |
| ④ | verify가 **삭제된 캡처파일을 못 잡아 ok=true 거짓통과** | `os.path.exists` 가드 제거 → `unverifiable`로 분류 → ok=false |
| ⑤ | sha256=None 등록 artifact가 tamper검출에서 영구 제외 | `unverifiable`로 분류 → ok=false |
| ⑥ | parse_timed가 refcap `[s-e]`만 인식 → **실제 WebVTT/SRT는 빈세그→UNKNOWN** | `_parse_vtt_srt()` 추가 (`-->` 감지 시 실 VTT/SRT 파싱) |
| ⑦ | detect_type 과다매칭: `/api` substring→json(github.com/api/docs), host substring→video(채널/프로필) | host 파싱: `api.*` 호스트만 json, 비디오는 *비디오 PATH*(/watch·v=·/shorts 등) 요구 |
| ⑧ | audio(.mp3)/csv 미지원 → unknown(미등록) | `.mp3/.wav/...→audio`, `.csv→csv` 추가 |
| ⑨ | `_http_get` SSRF·사이즈캡 부재 (169.254.169.254 메타데이터, 50GB OOM) | 사설/loopback/link-local IP 거부 + 50MB 캡 |
| ⑩ | `# transcript FAILED` 헤더 → UNKNOWN(∉BAD_QUALITY, 경고회피) | FAILED 감지 → `EXTRACT_FAILED`(∈BAD_QUALITY) |
| ⑪ | frontier `visited` dead-path (reduce는 있으나 writer 없음 → 항상 빈 리스트) | `frontier_visit()` writer + CLI `visit` 추가 |

## ✅ "미룬" 4개도 끝까지 수정 (사용자: "과투자라 단정 말고 측정/실행하라")
처음 "$0 단일사용자엔 과투자"라며 미뤘으나 — 측정해보니 *진짜 문제였음*(또 단정이 틀림). 전부 수정(test_scenarios.py +3 테스트, 총 42 GREEN):
| # | 결함 | 수정 + 측정 |
|---|---|---|
| ③ | dedupe TOCTOU race (20스레드→arts=4) | `_LOCK`(in-proc) + `_file_lock`(cross-proc, OS-released) → **arts=1** 단언 |
| op-10 | 부분쓰기/디스크full → 줄 손상 | atomic append(전체 줄 1회 write + fsync) + tolerant read(②) |
| op-09 | **O(N²) dedupe** (매 append 전체 ledger 재파싱) | **측정: 1000 append 17.65s**(57/s)=실제 느림 → size-무효화 key 캐시 → **1.70s(590/s), ~10x** |
| adv-05 | path traversal (../../Windows/win.ini 지문화) | `_path_ok()`(시스템 디렉터리 denylist) + ingest 로컬경로 거부 |

## 📋 *수정 안 함* — 의도된 정직한 설계한계 (버그 아님, 원칙1·4)
코드는 **깊이-0 라우터 + "거짓말 못하게"만** 판정하고, *의미판단*은 에이전트/farm에 위임. 이게 설계:
- **화자귀속** (누가 말했나) — 전사 바이트엔 없음. cite-or-fail=앵커링≠정확성.
- **모순탐지** (9,900 vs 19,900 둘 다 통과), **가짜 corroboration**(동일 artifact 2회=2소스 위장), **도메인 독립성**(신디케이트) — 의미판단, 에이전트 몫.
- **fabrication-at-capture** ('열린 지붕'): 환각 전사(gate=OK)에서 뽑은 quote도 cite-or-fail 통과. 유일 방어=상류 coverage_gate 캡처전 라벨. cite-or-fail은 *정확성이 아니라 앵커링*만 증명.
- **prompt injection** in fetched content — web_quality=OK로 등록만. 방어=에이전트가 본문을 *데이터로* 취급(RUNBOOK 규율) + 하류 farm 게이트.
- **외국어 VO** (lang=ko 고정), **위조 gate=OK** (sha는 바이트불변만, 라벨진위 아님) — 정직히 한계 표시.
- **TikTok/IG 자동취득** — ToS상 *의도적 미구현*.

## 결론
116 시나리오 중 **진짜 코드결함 9개를 실측·수정**(39 테스트 GREEN, 회귀 0). 나머지 gap 대부분은 *코드에 의미판단을 박지 않는다*는 설계 사상의 정직한 표현. QA/QC가 입증: 척추의 *결정론 바닥*(해시·앵커·tolerant·integrity)은 견고화됐고, *판단*은 에이전트에 남는다.
