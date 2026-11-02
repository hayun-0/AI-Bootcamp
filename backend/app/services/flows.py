"""하네스(run_flow) 호출 + agent_runs 저장. 하네스가 없거나 실패해도 거래는 계속된다."""
from sqlalchemy.orm import Session

from app.contracts import GradeResult, RunResult
from app.core.config import harness_config
from app.db.models import AgentRun


def load_run_flow():
    """B의 run_flow를 가져온다. 없으면 None (테스트는 이 함수를 monkeypatch)."""
    try:
        from app.harness.runner import run_flow
        return run_flow
    except Exception:
        return None


def _save(session: Session, result: RunResult, company_ids: list[int]) -> None:
    """실행 기록 저장. company_ids = 요청 회사 + 그 거래 당사자(조회 권한, §9.4)."""
    try:
        from app.harness.trace import save_run
        save_run(session, result)
        session.flush()
        row = session.get(AgentRun, result.run_id)
        if row is not None:
            row.company_ids = company_ids
        session.commit()
        return
    except Exception:
        session.rollback()
    if session.get(AgentRun, result.run_id) is None:
        session.add(AgentRun(run_id=result.run_id, flow=result.flow, result=result.model_dump(mode="json"),
                             company_ids=company_ids))
        session.commit()


def call_flow(session: Session, flow: str, ctx: dict, company_ids: list[int]) -> RunResult | None:
    """company_ids: 요청 회사 + 거래 당사자. 호출 전에 commit 해두므로, 저장 실패로 거래 데이터가 롤백되지 않는다."""
    session.commit()
    fn = load_run_flow()
    if fn is None:
        return None
    try:
        result = fn(flow, ctx)
        _save(session, result, sorted({c for c in company_ids if c is not None}))
        return result
    except Exception:
        session.rollback()
        return None


def dump(result: RunResult | None):
    return result.model_dump(mode="json") if result else None


def grade_from_result(result: RunResult | None) -> GradeResult | None:
    if result is None:
        return None
    for r in result.results:
        if r.agent_id == "grading" and "grade" in r.data:
            return GradeResult(**r.data["grade"])
    return None


def local_grade(bag, confirm_no_hazard: bool = False) -> GradeResult:
    """하네스 실행이 실패했을 때도 ③ grading과 같은 계산 도구를 쓴다 (기준이 두 곳에 생기지 않게)."""
    from app.tools.calc import compute_grade
    g = compute_grade(bag.target_material, bag.items, note=bag.note, confirm_no_hazard=confirm_no_hazard)
    return GradeResult(**{k: g[k] for k in ("target_material", "purity", "grade", "hazard", "reasons")})
