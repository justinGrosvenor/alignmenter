"""Base provider protocols."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class ChatProvider(Protocol):
    """Minimal provider protocol extracted from requirements."""

    name: str

    def chat(self, messages: list[dict], **kwargs) -> ChatResponse:
        ...

    def tokenizer(self) -> Any | None:
        ...


@dataclass
class ChatResponse:
    """Standardized provider response."""

    text: str
    usage: dict[str, Any] | None = None
    #: Structured context behind the reply — retrieved documents, latency, tool calls.
    #: Carried onto the turn as ``metadata["context"]`` so scorers can inspect what the
    #: model was actually given. Retrieval-augmented systems cannot be scored without it.
    context: dict[str, Any] | None = None


def parse_provider_model(identifier: str) -> tuple[str, str]:
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
