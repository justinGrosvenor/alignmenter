"""Embedding providers."""

from __future__ import annotations

import os
from typing import Iterable, Optional

try:  # pragma: no cover
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover
    SentenceTransformer = None  # type: ignore

try:  # pragma: no cover
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore


from .base import EmbeddingProvider, parse_provider_model


class SentenceTransformerProvider(EmbeddingProvider):
    """Local embedding provider via sentence-transformers."""

    name = "sentence-transformer"

    def __init__(self, model: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        if SentenceTransformer is None:
            raise RuntimeError(
                "sentence-transformers is required. Install with 'pip install sentence-transformers'."
            )
        self.model_name = model
        self._model = SentenceTransformer(model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, convert_to_numpy=False)
        return [list(map(float, vector)) for vector in vectors]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embedding provider using OpenAI embeddings API."""

    name = "openai"

    def __init__(self, model: str, client: Optional[OpenAI] = None) -> None:
        if OpenAI is None:
            raise RuntimeError("The 'openai' package is required for OpenAI embeddings.")
        self.model_name = model
        api_key = os.getenv("OPENAI_API_KEY")
        self._client = client or OpenAI(api_key=api_key)

    @classmethod
    def from_identifier(cls, identifier: str, client: Optional[OpenAI] = None) -> "OpenAIEmbeddingProvider":
        provider, model = parse_provider_model(identifier)
        if provider != cls.name:
            raise ValueError(f"Expected provider 'openai', got '{provider}'.")
        return cls(model=model, client=client)

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self.model_name, input=texts)
        return [row.embedding for row in response.data]


class PassthroughEmbeddingProvider(EmbeddingProvider):
    """Fallback provider returning hashed vectors."""

    name = "hashed"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [hashed_vector(text) for text in texts]


def hashed_vector(text: str, buckets: int = 512) -> list[float]:
    from alignmenter.utils import stable_hash

    vector = [0.0] * buckets
    for token in text.split():
        bucket = stable_hash(token, buckets)
        vector[bucket] += 1.0
    norm = sum(value * value for value in vector) ** 0.5
    if norm:
        vector = [value / norm for value in vector]
    return vector


def load_embedding_provider(identifier: Optional[str]) -> EmbeddingProvider:
    if identifier in (None, "", "hashed"):
        return PassthroughEmbeddingProvider()
    provider, model = parse_provider_model(identifier)
    if provider == "openai":
        return OpenAIEmbeddingProvider(model=model)
    if provider == "sentence-transformer":
        name = model or "sentence-transformers/all-MiniLM-L6-v2"
        return SentenceTransformerProvider(model=name)
    raise ValueError(f"Unsupported embedding provider: {identifier}")
