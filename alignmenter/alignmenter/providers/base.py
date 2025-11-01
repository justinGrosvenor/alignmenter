"""Base provider protocols."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol, Tuple


class ChatProvider(Protocol):
    """Minimal provider protocol extracted from requirements."""

    name: str

    def chat(self, messages: list[dict], **kwargs) -> dict:
        ...

    def tokenizer(self) -> Optional[Any]:
        ...


@dataclass
class ChatResponse:
    """Standardized provider response placeholder."""

    text: str
    usage: Optional[dict[str, Any]] = None


def parse_provider_model(identifier: str) -> Tuple[str, str]:
    """Split a provider specifier like ``openai:gpt-4o`` into parts."""

    if ":" not in identifier:
        raise ValueError("Model identifier must include provider prefix, e.g. 'openai:gpt-4o'.")
    provider, model = identifier.split(":", 1)
    provider = provider.strip()
    model = model.strip()
    if not provider or not model:
        raise ValueError("Provider and model name must be non-empty.")
    return provider, model


class EmbeddingProvider(Protocol):
    """Protocol for embedding generators."""

    name: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class JudgeProvider(Protocol):
    """Protocol for safety judge models."""

    name: str

    def evaluate(self, prompt: str) -> dict:
        ...
