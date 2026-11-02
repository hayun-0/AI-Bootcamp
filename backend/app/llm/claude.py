"""Claude: 공식 anthropic SDK. 샘플링 파라미터(temperature 등)는 보내지 않는다.
구조화 출력은 output_config.format, 키는 환경변수 ANTHROPIC_API_KEY."""
from __future__ import annotations

import json
import time

import anthropic

from app.llm.base import DEADLINE_S, LLMReply, call_with_deadline


class ClaudeProvider:
    name = "claude"

    def __init__(self, model: str, max_tokens: int = 2000, deadline_s: float = DEADLINE_S):
        self.model = model
        self.max_tokens = max_tokens
        self.deadline_s = deadline_s
        self._client: anthropic.Anthropic | None = None

    def chat(self, system: str, user: str, schema: dict | None = None) -> LLMReply:
        return call_with_deadline(lambda: self._chat(system, user, schema), self.deadline_s)

    def _chat(self, system: str, user: str, schema: dict | None = None) -> LLMReply:
        if self._client is None:
            self._client = anthropic.Anthropic()   # ANTHROPIC_API_KEY 없으면 여기서 예외 → 호출자가 처리
        kwargs: dict = {}
        if schema:
            kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
        t0 = time.monotonic()
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            **kwargs,
        )
        text = next((b.text for b in resp.content if b.type == "text"), "")
        data = json.loads(text) if schema else None
        return LLMReply(text=text, data=data, model=self.model, ms=int((time.monotonic() - t0) * 1000))
