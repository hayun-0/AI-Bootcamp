"""실행 기록: 이벤트 만들기, DB 저장(A의 AgentRun 표, 없으면 건너뜀), 메모리 보관."""
from __future__ import annotations

from collections import OrderedDict

from app.contracts import RunEvent, RunResult

_RECENT: "OrderedDict[str, dict]" = OrderedDict()   # DB가 없을 때 쓰는 최근 실행 보관
_MAX_RECENT = 200


class EventLog:
    def __init__(self) -> None:
        self.events: list[RunEvent] = []

    def add(self, type_: str, **payload) -> None:
        self.events.append(RunEvent(seq=len(self.events) + 1, type=type_, payload=payload))


def remember(result: RunResult) -> None:
    _RECENT[result.run_id] = result.model_dump(mode="json")
    while len(_RECENT) > _MAX_RECENT:
        _RECENT.popitem(last=False)


def recent_run(run_id: str) -> dict | None:
    return _RECENT.get(run_id)


def save_run(session, result: RunResult) -> None:
    """A의 AgentRun(run_id, flow, result JSON)을 세션에 넣는다. 모델이 없으면 아무것도 안 한다.
    commit은 호출자(A) 몫."""
    remember(result)
    if session is None:
        return
    try:
        from app.db.models import AgentRun
        session.add(AgentRun(run_id=result.run_id, flow=result.flow, result=result.model_dump(mode="json")))
    except Exception:
        return
