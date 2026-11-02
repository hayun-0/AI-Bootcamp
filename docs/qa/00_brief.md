# QA 공통 브리프 (2026-11-02)

대상: 마대 장터 백엔드 P0 (FastAPI). 루트 `/mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market`
- 계약서: docs/ARCHITECTURE.md (v0.1.2) · AI 팀 선언: harness/harness.yaml · 노션 사용자 설명은 계약서와 같음
- 코드는 읽어도 되지만 **고치지 말 것**(이번은 QA만). 결과는 자기 파일 하나(docs/qa/<번호>_<이름>.md)에만 쓴다.

## 서버 띄우기 (각자 자기 포트·자기 DB)
```bash
cd "/mnt/c/Users/User/Desktop/대학교/3학년/AI Innovation 공모전/masdae-market/backend"
export DATABASE_URL="postgresql+psycopg://postgres:@/<자기DB>?host=/run/user/1000/python_PostgresServer/2bc6e585c8"
export LLM_PROVIDER=<off|ollama>      # ollama면 OLLAMA_URL 기본값 http://172.20.32.1:11434 (Windows의 실제 Ollama)
nohup .venv/bin/uvicorn app.main:app --port <자기포트> > /tmp/claude-1000/-mnt-c-Users-User-Desktop-----3---AI-Innovation----/263a1eec-1862-4544-90ff-4b16d6eea42e/scratchpad/qa_<번호>.log 2>&1 &
echo $! > /tmp/claude-1000/-mnt-c-Users-User-Desktop-----3---AI-Innovation----/263a1eec-1862-4544-90ff-4b16d6eea42e/scratchpad/qa_<번호>.pid
```
- 끝나면 반드시 `kill $(cat …/qa_<번호>.pid)` 로 자기 서버만 끈다. `pkill -f` 금지.
- 요청은 curl 또는 httpx로 **실제 HTTP**. 인증은 헤더 `X-Company-Id`.
- 회사 이름은 가상 이름만(실제 회사명 금지). 개인정보 넣지 말 것(전화번호는 가짜 형식 테스트만).
- PostgreSQL은 공용 서버(DB만 따로). 다른 DB는 건드리지 말 것.

## 보고 형식 (자기 파일 + 최종 답변)
| # | 심각도(상/중/하) | 사용자가 겪는 일 | 재현(HTTP 순서) | 기대 | 실제 | 원인 추정(파일:줄) |
- 심각도: 상 = 돈·안전·법·데이터가 틀어지거나 서비스가 멈춤 / 중 = 사용자가 막히거나 오해함 / 하 = 불편·문구
- "계약서대로인데 사용자에게는 이상한 것"도 적되 `[계약 문제]`로 표시.
- 재현한 것만 "확인", 코드만 보고 짐작한 것은 "추정"으로 표시.
- 마지막에 좋았던 점 3개와 가장 먼저 고칠 것 3개.
