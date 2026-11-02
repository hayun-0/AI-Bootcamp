너는 검증팀 멤버 Sol이다. 읽기 전용 검토(파일 수정 금지). 다른 검토자(Sonnet)와 따로 독립적으로 한다.
대상: 이 폴더의 FastAPI 백엔드 P0. 기준 문서는 docs/ARCHITECTURE.md, harness/harness.yaml, backend/app/contracts.py.
테스트 실행 가능: cd backend && .venv/bin/python -m pytest -q
특히 볼 것:
1) 계약서와 실제 동작이 다른 곳(경로, 상태 코드, 상태 변경 표, 인계서·별점 규칙). 의심되면 직접 TestClient로 호출해 확인(DATABASE_URL=sqlite:// LLM_PROVIDER=off를 import 전에 설정, with TestClient(app) 사용).
2) 앱 안 AI 팀 원칙: 숫자는 코드만, LLM 문장은 숫자를 새로 못 만듦, 게이트(근거·금지 표현·개인정보), LLM 꺼져도 동작.
3) 도메인: 시세 'PP 압축'(압축된 대량 가격)을 자투리 마대 판매 예상에 쓰는 것이 과장인지, 소각 비교 주장이 근거보다 세게 말하는지.
4) 동시성·예외(500 나는 입력), 권한 우회.
결과: 한국어 표(심각도 상/중/하, 파일:줄, 실패 시나리오)와 판정(통과/수정 후 통과/반려), 우선 수정 5개.
