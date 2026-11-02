# P0 오케스트라 진행 기록 (2026-11-01)

| 순서 | 누가 | 한 일 | 결과 파일 |
|---|---|---|---|
| 1 | 지휘부 Opus | 계약서·harness.yaml·공통 타입·데이터 준비 | docs/ARCHITECTURE.md, harness/harness.yaml, backend/app/contracts.py |
| 2 | 분석팀 Sonnet A | 거래 서비스(주문·콜·인계서·가짜 결제·별점) | backend/app/{api,services,db}, tests/test_trade_scenario.py |
| 2 | 분석팀 Sonnet B | 앱 안 오케스트라(지휘 AI + 에이전트 7 + 게이트 + Ollama/Claude) | backend/app/{harness,agents,llm,tools}, harness/agents/*.md |
| 2 | 분석팀 Sol | 계약서만 보고 블라인드 인수 테스트 | tests/acceptance/, sol_acceptance_report.md |
| 3 | 지휘부 Opus | 통합(저장 칸 이름, 등급 계산 한 곳, 검사 순서 결정, 메모리 DB 버그) | ARCHITECTURE.md v0.1.1 |
| 4 | 검증팀 Sonnet·Sol | 서로 보지 않고 독립 검토 → 둘 다 "수정 후 통과" | sonnet_review.md, sol_review.md |
| 5 | 지휘부 Argon | 두 검토 대조·판정 "수정 후 통과", 필수 6 + 계약 4 | argon_verdict.md |
| 6 | 분석팀 Sonnet | 필수 6 + 위험 재질 한글(지휘부 추가) 수정, 회귀 테스트 | tests/test_*_fixes.py, ARCHITECTURE.md v0.1.2 |
| 7 | 검증팀 Sonnet | 독립 호출로 재확인 → **통과** (52 테스트, 인수 8) | — |

P1로 넘긴 것: 동시 요청 잠금, 한글 수사·국제 전화번호 게이트, 거대 정수 입력 500, 검사 무게 정산 조정, 취소 API, health의 실제 Ollama 확인, operator 가입 제한.

# QA·보완 라운드 기록 (2026-11-02)

| 순서 | 누가 | 한 일 | 결과 파일 |
|---|---|---|---|
| 1 | 검증팀 페르소나 6명(Sonnet 5, Sol 1) | 실제 PostgreSQL 서버에 사용자처럼 요청 → 문제 99건 | docs/qa/01~06, 10_종합.md |
| 2 | 사용자 | 운임 상한·±5% 정산·운영자 중재 결정, 배포 DB PostgreSQL | — |
| 3 | 지휘부 Opus | 계약 v0.2(8절) | docs/ARCHITECTURE.md |
| 4 | 분석팀 A·B + Sol | v0.2 구현 + 블라인드 인수 테스트 48개 | tests/acceptance/test_contract_v02.py |
| 5 | 검증팀 Sonnet / Sol | 재검사 "수정 필요" / 코드 검토 "반려" | docs/qa/20_v02_재검사.md, sol_v02_review.md |
| 6 | 지휘부 Opus | 계약 v0.3(9절) | docs/ARCHITECTURE.md |
| 7 | 분석팀 A·B + Sol | v0.3 구현 + 블라인드 인수 테스트 | tests/acceptance/test_contract_v03.py |
| 8 | 지휘부 Opus | 통합(템플릿 등급 글자, reasons 가리기, 카드 경로, 구 테스트 v0.3 맞춤, 공개 구성비 가리기) | — |
| 9 | 검증팀 Sonnet | 실제 HTTP 재검사 **통과** | docs/qa/30_v03_재검사.md |
| 10 | 지휘부 Argon | 최종 **통과** | argon_v03_verdict.md |

테스트: PostgreSQL 247 통과·1 건너뜀 / SQLite 238 통과·10 건너뜀(동시성은 PostgreSQL 전용).
남은 것(Argon): 시범 전 — 운영자 토큰·시범 계정, 프론트 이스케이프, Ollama 미리 올리기, CI에서 PostgreSQL 테스트. 외부 공개 전 — 실제 로그인, 요청 제한·CORS, 반송·처리 전환 법률 자문, 실제 PG.
