"""harness.yaml에서 에이전트·flow를 읽고 에이전트 모듈을 찾는다."""
from __future__ import annotations

import importlib
from typing import Callable

from app.tools.data import HARNESS_DIR, load_harness

# 파일 1개 = 에이전트 1개
MODULES = {
    "profiling": "app.agents.sorting.profiling",
    "vision": "app.agents.sorting.vision",
    "grading": "app.agents.sorting.grading",
    "bundling": "app.agents.trade.bundling",
    "pricing": "app.agents.trade.pricing",
    "economics": "app.agents.review.economics",
    "regulation": "app.agents.review.regulation",
}


def flow_plan(flow: str) -> list[str] | None:
    return load_harness()["flows"].get(flow)


def get_agent(agent_id: str) -> Callable:
    return importlib.import_module(MODULES[agent_id]).run


def agent_card(agent_id: str) -> str:
    meta = next((a for a in load_harness()["agents"] if a["id"] == agent_id), None)
    if not meta:
        return ""
    path = HARNESS_DIR / meta["card"]
    return path.read_text(encoding="utf-8") if path.exists() else ""


def harness_view() -> dict:
    """GET /v1/harness: 팀·에이전트·flow·카드 본문만(LLM 주소·모델·가정값은 내보내지 않음)."""
    h = load_harness()
    return {"teams": h["teams"], "agents": h["agents"], "flows": h["flows"],
            "cards": {a["id"]: agent_card(a["id"]) for a in h["agents"]}}
