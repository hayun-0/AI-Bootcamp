"""테스트용 LLM. 기본 동작: user 글의 '- ' 줄(주장)을 그대로 이어 붙여 돌려준다(새 숫자 없음)."""
from __future__ import annotations

from typing import Callable

from app.llm.base import LLMReply


class MockProvider:
    name = "mock"
    model = "mock-1"

    def __init__(self, reply_fn: Callable[[str, str, dict | None], str | dict] | None = None, fail: bool = False):
        self.reply_fn = reply_fn
        self.fail = fail
        self.calls: list[tuple[str, str, dict | None]] = []

    def chat(self, system: str, user: str, schema: dict | None = None) -> LLMReply:
        self.calls.append((system, user, schema))
        if self.fail:
            raise RuntimeError("mock LLM 실패")
        if self.reply_fn:
            out = self.reply_fn(system, user, schema)
        elif schema:
            out = {k: ([] if v.get("type") == "array" else "") for k, v in schema.get("properties", {}).items()}
        else:
            out = " ".join(ln[2:].split("] ", 1)[-1] if ln.startswith("- [") else ln[2:]
                           for ln in user.splitlines() if ln.startswith("- "))
        if isinstance(out, dict):
            return LLMReply(text=str(out), data=out, model=self.model, ms=1)
        return LLMReply(text=out, data={"summary": out} if schema else None, model=self.model, ms=1)
