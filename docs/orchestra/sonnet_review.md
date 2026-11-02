# 검증팀 Sonnet 검토 (P0) — 판정: 수정 후 통과
pytest 42 통과. 아래는 HTTP 재현 근거가 있는 지적.

| # | 심각도 | 위치 | 내용 |
|---|---|---|---|
| 1-1/5-1 | 상 | api/bags.py:15, listings.py:18, orders.py:31,36 | JSON Infinity가 gt=0 통과 → 응답 직렬화 500. 리스팅이 이미 commit돼 이후 GET /v1/listings 영구 500. allow_inf_nan=False 필요 |
| 1-2 | 중 | api/deps.py:11, get_or_404 | 거대 정수 id/헤더 → sqlite OverflowError 500 (401/404여야) |
| 1-3 | 중 | api/ratings.py:39-41 | rated 판정을 평가 '대상' 기준으로 구현 → hauler가 공장·재활용을 평가하면 둘 다 평가 안 했는데 rated |
| 1-4 | 중 | api/orders.py:174-186 | 검사 무게 40kg인데 정산은 100kg 기준, 인계서 received_kg와 모순 |
| 1-5~1-8 | 하 | bags/listings/orders | 역할 403 순서, 판매된 마대 재등급, 마대 동시 리스팅 보호 없음, rated 후 인계서 덮어쓰기 |
| 2-1/2-2 | 상 | tests/conftest.py:13 | conftest가 app을 먼저 import → 인수 테스트의 DATABASE_URL 설정이 늦음 → 디스크 masdae.db 사용, StaticPool 버그 못 잡음. 블랙박스 아님 |
| 2-3 | 중 | test_trade_* | fake_run_flow가 등급 로직 복제 |
| 3-1 | 중 | gates.py:10,19 | 한글 수사("삼십 퍼센트", "두 배") 숫자 검사 통과 |
| 3-2~3-4 | 하 | gates.py, _common.py | 전화번호 형식 일부 누락, LLM 문장이 law 근거 상속, 모름→없음 휴리스틱 |
| 4-1 | 상 | economics.py:22-29 | 판매 수입을 '잡색 압축품(생활계 혼합) 매입가, VAT 포함·물류비 제외'로 산업 자투리에 적용, 단서·assumption 근거 없음 → 과대 |
| 4-2 | 중 | economics.py, pricing.py | '수입 > 소각비' 비교 자체가 어색(소각비는 절감액). 압축·운송·선별비 누락 미표시 |
| 4-3 | 중 | pricing.py:21 | 이 마대 적용 가격을 level=fact로 표시 |
| 4-4 | 중 | calc.py:27,31,39 | 위험 재질 영문 정확 일치만 → '오일' 섞인 마대가 B등급 통과증 |
| 4-5 | 하 | calc.py:31 | 반올림 후 임계 비교 → 0.94996이 A |
| 4-6/4-7 | 하 | listings.py, economics.py | 다른 재질 마대 한 리스팅, 소각재 포함/제외 구분 문구 없음 |
| 4-8 | 중 | api/listings.py:50, bundling.py | nearby_listings에 좌표가 없어 묶음 추천이 실제 경로에서 항상 0건(단위 테스트는 좌표 직접 주입) |
| 5-2 | 중 | api/companies.py:29 | 누구나 operator로 가입·승인 가능 → 허가 확인 무의미 |
| 5-3 | 중 | llm/ollama.py, runner.py | 무응답 Ollama면 호출마다 최대 120초, 실패 후에도 재시도 (미확인) |
| 5-4 | 중 | main.py:39-41 | health의 llm.available이 실제 도달 여부 아님 |
| 5-5/5-6/5-7 | 하 | ratings/orders/agents | UNIQUE 충돌 500, pickup·inspect 동시 이중 통과, agent-runs 인증 없음 |
| 6 | 하 | flows/agents/main/trace | 통합 대기용 방어 코드·예외 삼키기 정리 가능, pricing sale_low/high 중복 |

좋은 점: 선착순 조건부 UPDATE, 상태표 한 곳, 등급 계산 한 곳, LLM off/mock 테스트, 게이트가 근거 없는 주장·미등록 법 id·금지 표현 차단, 소각비 출처 정직 표기.
우선 수정: ① Infinity 차단 ② 인수 테스트 블랙박스화 ③ economics 문구·근거 정정 ④ bundling 좌표 연결 ⑤ 위험 재질 우회·반올림.
