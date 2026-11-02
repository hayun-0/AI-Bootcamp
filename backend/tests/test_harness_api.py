from app.db.models import AgentRun
from app.db.session import get_session
from app.harness.runner import run_flow
from app.harness.trace import save_run
from app.main import app
from tests.conftest import H, mk_company


def test_agent_run_lookup_and_harness(client):
    cid = mk_company(client, "테스트공장", "factory")
    op = mk_company(client, "운영자", "operator")
    r = run_flow("deal_check", {"listing": {"waste_code": "51-03-01"}, "recycler": {"permit_codes": []}}, llm=None)
    save_run(None, r)       # DB 세션 없이도 예외 없음(메모리 보관)
    assert client.get(f"/v1/agent-runs/{r.run_id}").status_code == 401        # 헤더 없음
    assert client.get(f"/v1/agent-runs/{r.run_id}", headers=H(cid)).status_code == 404   # 메모리 대체 조회는 운영자만
    got = client.get(f"/v1/agent-runs/{r.run_id}", headers=H(op))
    assert got.status_code == 200 and got.json()["run_id"] == r.run_id
    assert client.get("/v1/agent-runs/none", headers=H(op)).status_code == 404


def test_harness_cards_operator_only(client):
    cid = mk_company(client, "테스트공장", "factory")
    op = mk_company(client, "운영자", "operator")
    for headers in ({}, H(cid), H(999)):
        h = client.get("/v1/harness", headers=headers).json()
        assert set(h) == {"teams", "agents", "flows"} and "grade_bag" in h["flows"]
        assert "0.95" not in str(h)
    h = client.get("/v1/harness", headers=H(op)).json()
    assert set(h) == {"teams", "agents", "flows", "cards"} and "## 역할" in h["cards"]["grading"]


def test_saved_run_visible_only_to_company_ids_and_operator(client):
    a, b = mk_company(client, "공장A", "factory"), mk_company(client, "공장B", "factory")
    op = mk_company(client, "운영자", "operator")
    r = run_flow("deal_check", {"listing": {"waste_code": "51-03-01"}, "recycler": {"permit_codes": []}}, llm=None)
    gen = app.dependency_overrides[get_session]()
    session = next(gen)
    row = AgentRun(run_id=r.run_id, flow=r.flow, result=r.model_dump(mode="json"))
    if hasattr(AgentRun, "company_ids"):
        row.company_ids = [a]
    session.add(row)
    session.commit()
    expect_a = 200 if hasattr(AgentRun, "company_ids") else 404       # 칸이 없으면 운영자만
    assert client.get(f"/v1/agent-runs/{r.run_id}", headers=H(a)).status_code == expect_a
    assert client.get(f"/v1/agent-runs/{r.run_id}", headers=H(b)).status_code == 404
    assert client.get(f"/v1/agent-runs/{r.run_id}", headers=H(op)).status_code == 200
    gen.close()
