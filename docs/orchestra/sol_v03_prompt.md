너는 분석팀 멤버 Sol이다. 계약서 v0.3용 블라인드 인수 테스트를 쓴다.
읽을 것: docs/ARCHITECTURE.md (9절이 8절보다, 8절이 앞 절보다 우선), backend/app/contracts.py, harness/harness.yaml, docs/qa/20_v02_재검사.md, docs/orchestra/sol_v02_review.md. backend/app/ 구현 파일은 열지 말 것.
할 일: backend/tests/acceptance/test_contract_v03.py 하나만 새로 쓴다(실행 안 해도 됨). 기존 test_contract_v02.py가 v0.3과 충돌하면(보류 금액 공식, treat 정산 칸, return 후 마대, /health 모델명, /harness 카드, agent-runs 접근) 고치지 말고 v03 파일 맨 위 주석에 "v02 파일과 달라진 점: …"으로 목록만 적는다.
- app import 전에 os.environ.setdefault("DATABASE_URL","sqlite://"), LLM_PROVIDER=off, OPERATOR_BOOTSTRAP_TOKEN=qa-token.
- 9.1: held = round(goods×1.05)+cap, 검사 +5%(105kg/100kg)에서 공장 몫 깎이지 않음, 0.1+0.2kg 등록 후 0.285kg 검사가 5% 안, 0.5원 사사오입, 100억 초과 판매 400, 22억 원 주문 성공(500 아님), regrade 단가 인상 400, treat 칸(factory_charge_krw·recycler_fee_krw), return 후 마대 재등급·재판매 가능.
- 9.2: release 뒤 다른 기사 수락 후 이전 기사의 pickup·arrive·release 409, 재등급으로 통과증 없어진 마대로 판매 409.
- 9.4: 남의 agent-run 404, sold 판매 상세는 제3자 404, /health에 model 없음, 일반 회사 /harness에 cards 없음.
- 9.3은 LLM이 꺼져 있으면 요약이 템플릿이므로: 등급 없는 마대 요약에 등급 글자 없음, 사용자 문자열(회사 이름·메모·이상한 재질명)이 public_claims 문장에 그대로 안 나옴을 확인.
- 동시성 테스트는 엔진이 sqlite면 pytest.skip.
마지막에 테스트 이름 목록과 v02 파일과 달라진 점 목록을 짧게 출력.
