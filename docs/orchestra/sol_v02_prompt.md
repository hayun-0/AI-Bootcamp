너는 분석팀 멤버 Sol이다. 계약서 v0.2용 블라인드 인수 테스트를 쓴다.
읽을 것: docs/ARCHITECTURE.md (특히 8절 v0.2 변경, 앞 절보다 우선), backend/app/contracts.py, harness/harness.yaml, data/waste_codes.json, docs/qa/10_종합.md. backend/app/ 아래 구현 파일은 열지 말 것(지금 다른 팀원이 고치는 중, 계약서만 보고 독립적으로).
할 일: backend/tests/acceptance/test_contract_v02.py 파일 하나만 새로 쓴다. 다른 파일은 만들거나 고치지 말 것. 실행하지 않아도 됨.
- pytest + fastapi.testclient.TestClient, `with TestClient(app) as client`. app import 전에 os.environ.setdefault("DATABASE_URL","sqlite://"), os.environ["LLM_PROVIDER"]="off", os.environ["OPERATOR_BOOTSTRAP_TOKEN"]="qa-token" 설정. 운영자는 헤더 X-Operator-Token: qa-token으로 가입.
- 8.1~8.8을 HTTP로 검사: 범위 밖 입력 400(운임 1e10, kg 2001, NaN 좌표, 없는 waste_code, 거대 id), operator 공개 가입 403, 운임 상한(주문 held_krw, 콜 목록 필드, 상한 초과 수락 400, 정산 refund_krw), 무게(97/100 비례 정산 사사오입, 40/100 → disputed와 dispute_reason, pickup weight_warning), 출구(cancel·release·withdraw·resolve 3종과 각 금액), 인계서 번호 후 칸 잠금 409, 판매된 마대 재등급 409, 메모 위험어 → 통과증 보류 → confirm_no_hazard로 등급, 품목 위험어는 확인해도 None, 재질 별칭(피피·폴리프로필렌) 순도, 화면용 조회(/me, /me/bags, /bags/{id}, /me/listings, /listings/{id}, /me/orders) 필드와 남의 것 403, 날짜 +00:00, /v1/harness에 LLM 주소·assumptions 없음, /v1/agent-runs 헤더 없으면 401.
- 동시성은 스레드 몇 개로 같은 마대 판매·같은 pickup을 동시에 보내 성공 1건 확인(SQLite면 통과가 약할 수 있다고 주석).
- 계약서가 애매하면 파일 맨 위에 "계약서 애매: …" 주석.
마지막에 테스트 이름 목록과 애매한 점을 짧게 출력.
