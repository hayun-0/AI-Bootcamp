import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")  # app import 전에: 테스트가 파일 DB를 건드리지 않게

from app.contracts import AgentResult, Claim, Evidence, RunResult
from app.core.config import harness_config
from app.db.models import Base
from app.db.session import get_session
from app.main import app
from app.services import flows

CODE = "51-03-01"


def fake_run_flow(flow: str, ctx: dict) -> RunResult:
    """하네스 대역: 계약 규칙대로 등급 계산."""
    results = []
    if flow == "grade_bag":
        bag, cfg = ctx["bag"], harness_config()["assumptions"]
        target = bag["target_material"].lower()
        total = sum(i["kg"] for i in bag["items"])
        purity = sum(i["kg"] for i in bag["items"] if i["material"].lower() == target) / total
        hazard = any(i["material"].lower() in cfg["hazard_materials"] for i in bag["items"])
        grade = None
        if not hazard:
            grade = next((g for g in "ABC" if purity >= cfg["grade_thresholds"][g]), None)
        results.append(AgentResult(agent_id="grading", data={"grade": {
            "target_material": target, "purity": purity, "grade": grade, "hazard": hazard, "reasons": []}}))
    claim = Claim(agent_id="x", text="가상 주장", level="assumption", evidence=[Evidence(kind="assumption", ref="t")])
    return RunResult(run_id=uuid.uuid4().hex, flow=flow, plan=[r.agent_id for r in results], results=results,
                     public_claims=[claim], blocked_count=0, summary="가상 요약", summary_source="template",
                     llm={"provider": "off", "model": "", "available": False}, events=[])


OP_TOKEN = "test-operator-token"
PG_URL = os.environ.get("DATABASE_URL", "")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OPERATOR_BOOTSTRAP_TOKEN", OP_TOKEN)
    if PG_URL.startswith("postgresql"):   # 동시 요청 테스트는 PostgreSQL에서 의미가 있다
        engine = create_engine(PG_URL)
        Base.metadata.drop_all(engine)
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        with Session() as s:
            yield s

    app.dependency_overrides[get_session] = override
    monkeypatch.setattr(flows, "load_run_flow", lambda: fake_run_flow)
    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()


def H(cid: int) -> dict:
    return {"X-Company-Id": str(cid)}


def mk_company(client, name, role, **kw) -> int:
    body = {"name": name, "role": role, "biz_no": "000-00-00000", "lat": 36.1, "lon": 128.4, **kw}
    headers = {"X-Operator-Token": OP_TOKEN} if role == "operator" else {}   # 운영자는 부트스트랩 토큰으로만
    r = client.post("/v1/companies", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]
