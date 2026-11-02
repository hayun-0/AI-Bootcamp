"""GET /v1/agent-runs/{run_id}, GET /v1/harness. DB(A의 AgentRun 표)가 있으면 거기서, 없으면 메모리 보관분에서 읽는다."""
from __future__ import annotations

import copy

from fastapi import APIRouter, Depends, Header, HTTPException

from app.harness.registry import harness_view
from app.harness.trace import recent_run

try:
    from app.db.session import get_session as _get_session
except Exception:        # A의 세션 모듈이 아직 없을 때
    _get_session = None


def _no_session():
    return None


try:
    from app.api.deps import current_company as _auth
except Exception:        # A의 인증 의존성을 못 불러오면 헤더 유무만 확인
    def _auth(x_company_id: str | None = Header(default=None)):
        if not x_company_id:
            raise HTTPException(status_code=401, detail="X-Company-Id 헤더가 필요함")


def _hide_blocked(data: dict) -> dict:
    """막힌 주장 본문은 조회 응답에서 가린다(개인정보 모양 등이 있을 수 있음)."""
    for res in data.get("results") or []:
        for c in res.get("claims") or []:
            if c.get("blocked"):
                c["text"] = "[차단됨]"
    return data


router = APIRouter()


def _is_operator(company) -> bool:
    return getattr(company, "role", None) == "operator"


def _may_read(company, row) -> bool:
    """저장된 실행은 company_ids(요청 회사 + 거래 당사자)에 든 회사와 운영자만. 칸이 없거나 비면 운영자만."""
    if _is_operator(company):
        return True
    ids = getattr(row, "company_ids", None) or []
    cid = getattr(company, "id", None)
    return cid is not None and cid in ids


@router.get("/v1/agent-runs/{run_id}")
def get_agent_run(run_id: str, company=Depends(_auth), session=Depends(_get_session or _no_session)):
    if session is not None:
        try:
            from sqlalchemy import select
            from app.db.models import AgentRun
            row = session.execute(select(AgentRun).where(AgentRun.run_id == run_id)).scalar_one_or_none()
        except Exception:
            row = None
        if row is not None:
            if not _may_read(company, row):
                raise HTTPException(status_code=404, detail="agent run not found")
            return _hide_blocked(copy.deepcopy(row.result))
    data = recent_run(run_id) if _is_operator(company) else None      # 메모리 대체 조회는 운영자만
    if data is None:
        raise HTTPException(status_code=404, detail="agent run not found")
    return _hide_blocked(copy.deepcopy(data))


@router.get("/v1/harness")
def get_harness(x_company_id: str | None = Header(default=None), session=Depends(_get_session or _no_session)):
    """운영자가 아니면 팀·에이전트 이름·흐름만, 운영자는 카드 본문도."""
    view = harness_view()
    operator = False
    if session is not None and x_company_id:
        try:
            from app.db.models import Company
            operator = _is_operator(session.get(Company, int(x_company_id)))
        except Exception:
            operator = False
    if not operator:
        view.pop("cards", None)
        view["agents"] = [{k: v for k, v in a.items() if k != "card"} for a in view.get("agents", [])]
    return view
