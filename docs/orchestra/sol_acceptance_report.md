`backend/tests/acceptance/test_contract_scenario.py`만 작성했습니다. 구문 검사만 통과했으며, 테스트는 실행하지 않았습니다.

테스트 이름:

- `test_contract_scenario_full_trade_to_rated`
- `test_unverified_recycler_order_is_403`
- `test_wrong_permit_hauler_accept_is_403`
- `test_payment_held_pickup_is_409`
- `test_incomplete_handover_number_is_409`
- `test_rating_without_handover_number_is_409`
- `test_missing_company_header_is_401`

애매한 점은 파일 상단에 기록했습니다: 생략된 성공 코드는 200, 통과증 없음은 생략/null 허용, 결제 보류 중 수거는 상태 충돌 409 우선, 번호 등의 형식은 가상 문자열 사용, DB 초기화 대신 테스트별 신규 회사 가입으로 해석했습니다.