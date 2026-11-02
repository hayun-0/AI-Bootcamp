"""LLM 공급자 공통 타입."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

DEADLINE_S = 15.0       # LLM 호출 1번의 전체 시간 상한(초). 응답이 조금씩 계속 와도 여기서 끊음


@dataclass
class LLMReply:
    text: str = ""
    data: dict[str, Any] | None = None   # schema를 줬을 때 파싱된 JSON
    model: str = ""
    ms: int = 0


class LLMProvider(Protocol):
    name: str
    model: str

    def chat(self, system: str, user: str, schema: dict | None = None) -> LLMReply: ...


def call_with_deadline(fn: Callable[[], Any], deadline_s: float) -> Any:
    """fn을 작업 스레드에서 돌리고 deadline_s(벽시계)까지만 기다린다. 넘으면 TimeoutError(작업은 버림)."""
    box: dict[str, Any] = {}

    def work() -> None:
        try:
            box["value"] = fn()
        except BaseException as e:      # 호출자 스레드로 그대로 전달
            box["error"] = e

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(deadline_s)
    if t.is_alive():
        raise TimeoutError(f"LLM 호출이 {deadline_s:g}초를 넘겨 끊음")
    if "error" in box:
        raise box["error"]
    return box["value"]
