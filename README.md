# AI-Bootcamp

산업 부산물판 배달의민족(마대 장터) — AI Bootcamp Innovation Challenger 2026, Microsoft '산업자원 순환 AI Agent'


공장이 마대를 올리면 AI가 등급(마대 통과증)을 매기고, 허가 재활용업체가 주문하고, 허가 운반업체가 콜을 받아 나르는 앱의 서버.
설계 계약: `docs/ARCHITECTURE.md` · 앱 안 오케스트라 선언: `harness/harness.yaml`

```bash
cd backend
.venv/bin/python -m pytest -q                         # 테스트
.venv/bin/python -m seed.gumi_demo                    # 구미 가상 시나리오 데이터
LLM_PROVIDER=ollama .venv/bin/uvicorn app.main:app    # 서버 (LLM_PROVIDER=off|mock|ollama|claude)
```

## 폴더
- `docs/ARCHITECTURE.md` 설계 계약서 (v0.3: 9절 > 8절 > 앞 절)
- `harness/` 앱 안 AI 팀 선언(harness.yaml), 에이전트 카드, 금지 표현·근거 규칙
- `backend/` FastAPI 서버, 테스트(`tests/`, 인수 테스트 `tests/acceptance/`)
- `data/` 법 조문·시세·폐기물 코드 등 공개 데이터 사본
- `docs/qa/` 사용자 입장 QA와 재검사, `docs/orchestra/` 검토·판정 기록

## 테스트
```bash
cd backend
uv venv .venv && uv pip install --python .venv/bin/python -r pyproject.toml pytest   # 처음 한 번
.venv/bin/python -m pytest -q                                      # SQLite
DATABASE_URL="postgresql+psycopg://…" .venv/bin/python -m pytest -q  # PostgreSQL(동시성 테스트 포함)
```
