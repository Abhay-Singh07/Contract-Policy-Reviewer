"""
Wraps Cohere's embed endpoint. Same real/mock pattern as core/llm_client.py:
set COHERE_API_KEY in .env to use the real thing, otherwise a deterministic
mock kicks in so the rest of the pipeline can still be built/tested.
"""
from __future__ import annotations

import hashlib
from typing import Protocol

from app.config import settings

EMBED_DIM = 1024  # matches Cohere embed-english-v3.0


class EmbeddingClient(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class CohereEmbeddingClient:
    def __init__(self, model: str | None = None):
        import cohere  # imported lazily, only required when actually used
        self.model = model or settings.COHERE_EMBED_MODEL
        self._client = cohere.Client(settings.COHERE_API_KEY)

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embed(texts=texts, model=self.model, input_type="search_document")
        return resp.embeddings


class MockEmbeddingClient:
    """Deterministic fake embeddings — same text always maps to the same vector,
    so similarity search is testable without hitting Cohere."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._fake_vector(t) for t in texts]

    @staticmethod
    def _fake_vector(text: str) -> list[float]:
        seed = hashlib.sha256(text.encode()).digest()
        # repeat the 32-byte hash to fill EMBED_DIM floats in [0, 1)
        return [(seed[i % len(seed)] / 255.0) for i in range(EMBED_DIM)]


def get_embedding_client() -> EmbeddingClient:
    if settings.COHERE_API_KEY:
        return CohereEmbeddingClient()
    return MockEmbeddingClient()