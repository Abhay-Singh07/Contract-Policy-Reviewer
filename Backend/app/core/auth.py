"""
Simple API-key gate for the backend. Not OAuth, not JWT, not user accounts —
just a shared secret in a header, which is enough for a single-tenant tool
like this one before it's exposed beyond localhost.

Dev-mode behavior: if API_KEY is unset in .env, auth is disabled entirely so
local development and the test suite don't need a key configured. This is
the same real/mock fallback pattern used everywhere else in this project
(GroqLLMClient/MockLLMClient, CohereEmbeddingClient/MockEmbeddingClient) —
but unlike those, this one is a genuine security control. API_KEY MUST be
set before this backend is deployed anywhere reachable outside localhost.
"""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.config import settings


def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if not settings.API_KEY:
        return  # dev mode: no key configured, don't block requests
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")