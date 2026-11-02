"""Ollama: httpx로 /api/chat 호출(stream 끔, temperature 0, schema는 format으로)."""
from __future__ import annotations

import json
import time

import httpx

from app.llm.base import DEADLINE_S, LLMReply, call_with_deadline


class OllamaProvider:
    name = "ollama"

    def __init__(self, url: str, model: str, timeout_s: float = 120, deadline_s: float = DEADLINE_S):
        self.url = url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s
        self.deadline_s = deadline_s

    def chat(self, system: str, user: str, schema: dict | None = None) -> LLMReply:
        return call_with_deadline(lambda: self._chat(system, user, schema), self.deadline_s)

    def _chat(self, system: str, user: str, schema: dict | None = None) -> LLMReply:
        body = {
            "model": self.model,
            "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": 0},
        }
        if schema:
            body["format"] = schema
        t0 = time.monotonic()
        r = httpx.post(f"{self.url}/api/chat", json=body, timeout=httpx.Timeout(self.timeout_s, connect=min(3, self.timeout_s)))
        r.raise_for_status()
        text = r.json()["message"]["content"]
        data = None
        if schema:
            data = json.loads(text)
        return LLMReply(text=text, data=data, model=self.model, ms=int((time.monotonic() - t0) * 1000))

    def reachable(self) -> bool:
        try:
            return httpx.get(f"{self.url}/api/tags", timeout=3).status_code == 200
        except httpx.HTTPError:
            return False
