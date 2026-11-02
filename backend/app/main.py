"""FastAPI 앱 조립."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api import bags, companies, listings, orders, ratings
from app.core.config import llm_info
from app.db.models import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="마대 장터", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def bad_request(request: Request, exc: RequestValidationError):
    # 계약: 잘못된 입력은 422가 아니라 400
    return JSONResponse(status_code=400, content={"detail": [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]})


@app.exception_handler(IntegrityError)
async def conflict(request: Request, exc: IntegrityError):
    # UNIQUE 충돌(동시 요청 등)은 500이 아니라 409
    return JSONResponse(status_code=409, content={"detail": "이미 처리된 요청(중복)"})


for module in (companies, bags, listings, orders, ratings):
    app.include_router(module.router)

try:  # B 담당 라우트(agent-runs, harness). 아직 없으면 건너뜀
    from app.api import agents
    app.include_router(agents.router)
except ImportError:
    pass


@app.get("/v1/health")
def health():
    import app.llm as llm_mod
    fn = getattr(llm_mod, "provider_health", None)   # B가 추가하는 실제 확인 함수
    try:
        llm = fn() if fn else llm_info()
    except Exception:
        llm = llm_info()
    return {"ok": True, "db": True, "llm": {"provider": llm.get("provider"), "available": llm.get("available")}}
