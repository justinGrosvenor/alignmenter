"""Anthropic provider implementation."""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

try:  # pragma: no cover - import guard
    from anthropic import Anthropic  # type: ignore
except ImportError:  # pragma: no cover - handled at runtime
    Anthropic = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    from anthropic import Anthropic as _Anthropic

from alignmenter.config import get_settings

from .base import ChatResponse, parse_provider_model


class AnthropicProvider:
    """Adapter for Anthropic Messages API."""

    name = "anthropic"

    def __init__(self, model: str, client: Optional["_Anthropic"] = None) -> None:
        self.model = model
        if client is not None:
            self._client = client
        else:
            if Anthropic is None:
                raise RuntimeError(
                    "The 'anthropic' package is required for AnthropicProvider. Install with 'pip install anthropic'."
                )
            settings = get_settings()
            self._client = Anthropic(api_key=settings.anthropic_api_key)

    @classmethod
    def from_model_identifier(cls, identifier: str, client: Optional["_Anthropic"] = None) -> "AnthropicProvider":
        provider, model = parse_provider_model(identifier)
        if provider != cls.name:
            raise ValueError(f"Expected provider 'anthropic', got '{provider}'.")
        return cls(model=model, client=client)

    def chat(self, messages: list[dict[str, Any]], **kwargs) -> ChatResponse:
        # Extract system message if present (Anthropic requires separate system param)
        system = None
        filtered_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system = msg.get("content", "")
            else:
                filtered_messages.append(msg)

        # Build API call params
        params = {"model": self.model, "messages": filtered_messages, "max_tokens": 4096, **kwargs}
        if system:
            params["system"] = system

        response = self._client.messages.create(**params)

        content = _extract_content(response)
        usage = _extract_usage(response)

        return ChatResponse(text=content, usage=usage)

    def tokenizer(self) -> None:
        return None


def _extract_content(response: Any) -> str:
    if response is None:
        return ""
    content = getattr(response, "content", [])
    if isinstance(content, list):
        return "".join(block.text for block in content if hasattr(block, "text"))
    return str(content)


def _extract_usage(response: Any) -> Optional[dict[str, Any]]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return {
        "prompt_tokens": getattr(usage, "input_tokens", None),
        "completion_tokens": getattr(usage, "output_tokens", None),
        "total_tokens": getattr(usage, "input_tokens", 0) + getattr(usage, "output_tokens", 0),
    }
