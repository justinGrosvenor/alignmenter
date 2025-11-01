"""OpenAI provider implementation."""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

try:  # pragma: no cover - import guard
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover - handled at runtime
    OpenAI = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    from openai import OpenAI as _OpenAI

from alignmenter.config import get_settings

from .base import ChatResponse, parse_provider_model


class OpenAIProvider:
    """Adapter for OpenAI Chat Completions API."""

    name = "openai"

    def __init__(self, model: str, client: Optional["_OpenAI"] = None) -> None:
        self.model = model
        if client is not None:
            self._client = client
        else:
            if OpenAI is None:
                raise RuntimeError(
                    "The 'openai' package is required for OpenAIProvider. Install with 'pip install openai'."
                )
            settings = get_settings()
            self._client = OpenAI(api_key=settings.openai_api_key)

    @classmethod
    def from_model_identifier(cls, identifier: str, client: Optional["_OpenAI"] = None) -> "OpenAIProvider":
        provider, model = parse_provider_model(identifier)
        if provider != cls.name:
            raise ValueError(f"Expected provider 'openai', got '{provider}'.")
        return cls(model=model, client=client)

    def chat(self, messages: list[dict[str, Any]], **kwargs) -> ChatResponse:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )

        choice = response.choices[0]
        content = _extract_content(choice.message)
        usage = _extract_usage(response)

        return ChatResponse(text=content, usage=usage)

    def tokenizer(self) -> None:
        return None


def _extract_content(message: Any) -> str:
    if message is None:
        return ""
    content = getattr(message, "content", "")
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return str(content)


def _extract_usage(response: Any) -> Optional[dict[str, Any]]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }
