너는 분석팀 멤버 Sol이다. 블라인드 인수 테스트를 쓴다.
읽을 수 있는 것: docs/ARCHITECTURE.md, backend/app/contracts.py, harness/harness.yaml, data/ 폴더. backend/app/ 아래 다른 구현 파일은 열지 말 것(다른 팀원이 지금 만들고 있고, 너는 계약서만 보고 독립적으로 테스트를 써야 함).
할 일: backend/tests/acceptance/test_contract_scenario.py 파일 하나만 작성한다. 다른 파일은 만들거나 고치지 말 것. 테스트는 실행하지 말 것(구현이 아직 없음).
- pytest + fastapi.testclient.TestClient(app.main.app). 환경변수 DATABASE_URL="sqlite://"(메모리)와 LLM_PROVIDER="off"를 app import 전에 설정.
- 계약서 7절 완료 기준 2번 시나리오를 HTTP로 끝까지: 회사 가입(공장 3, 재활용 1, 운반 2, 운영자 1) → 운영자 허가 확인 → 마대 4개 등록(PP 순도 0.97, 0.92, 0.85, 그리고 oil 섞인 것) → 각각 grade → 등급 A, B, C, None 확인 → A 마대로 판매(now) → 재활용업체 주문(status payment_held, goods_krw 계산 확인) → 운반업체 두 곳이 콜 목록 확인 → 첫 수락 200, 두 번째 409 → 수거(마대별 무게) → 도착 → 검사 합격 → status settled, platform_krw 0 → 인계서: 남의 칸 403, 3칸 각자 채움, 번호 입력 → 별점(공장↔재활용) → 주문 status rated.
- 부정 케이스도 별도 테스트로: 허가 확인 안 된 재활용업체 주문 403, 허가 코드 다른 운반업체 수락 403, 결제 보류 상태에서 pickup 409, 인계서 3칸 안 채우고 번호 409, 인계서 번호 없이 별점 409, 헤더 없이 요청 401.
- 계약서에 정확히 적힌 경로·필드·상태 코드만 사용. 계약서가 애매한 곳은 테스트 파일 맨 위 주석에 "계약서 애매: ..."로 적고 가장 자연스러운 해석으로 쓴다.
마지막에 작성한 테스트 이름 목록과 애매했던 점을 짧게 출력.
