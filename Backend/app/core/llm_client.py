"""
Thin wrapper around Groq's chat completions, always run in JSON mode
(agents ask for structured findings back, not prose).

Set GROQ_API_KEY in backend/.env to hit the real API.
If it's missing, LLMClient falls back to a MockLLMClient so the rest
of the pipeline (agents, qa, judge) can still be built and tested.
"""
from __future__ import annotations

import json
from typing import Protocol

from app.config import settings


class LLMClient(Protocol):
    def generate_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> dict:
        ...


class GroqLLMClient:
    def __init__(self, model: str | None = None):
        from groq import Groq  # imported lazily so the package is only required when actually used
        self.model = model or settings.GROQ_MODEL
        self._client = Groq(api_key=settings.GROQ_API_KEY)

    def generate_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> dict:
        resp = self._client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return json.loads(resp.choices[0].message.content)


class MockLLMClient:
    """Returns canned responses so agent wiring can be tested with zero network calls."""

    def __init__(self, canned: dict | None = None):
        self.canned = canned or {"findings": []}

    def generate_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> dict:
        return self.canned


def get_llm_client(model: str | None = None) -> LLMClient:
    if settings.GROQ_API_KEY:
        return GroqLLMClient(model=model)
    return MockLLMClient()