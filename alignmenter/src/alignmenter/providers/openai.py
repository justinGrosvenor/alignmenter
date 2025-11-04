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


class OpenAICustomGPTProvider:
    """Adapter for OpenAI Custom GPTs via the Responses API."""

    name = "openai-gpt"

    def __init__(self, gpt_id: str, client: Optional["_OpenAI"] = None) -> None:
        if OpenAI is None:
            raise RuntimeError(
                "The 'openai' package is required for Custom GPT support. Install with 'pip install openai'."
            )
        self.model = gpt_id
        if client is not None:
            self._client = client
        else:
            settings = get_settings()
            self._client = OpenAI(api_key=settings.openai_api_key)

    @classmethod
    def from_model_identifier(cls, identifier: str, client: Optional["_OpenAI"] = None) -> "OpenAICustomGPTProvider":
        provider, model = parse_provider_model(identifier)
        if provider != cls.name:
            raise ValueError(f"Expected provider 'openai-gpt', got '{provider}'.")
        return cls(gpt_id=model, client=client)

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> ChatResponse:
        inputs: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role") or "user"
            content = message.get("content") or message.get("text") or ""
            if isinstance(content, list):
                content = "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
            inputs.append({"role": role, "content": content})

        response = self._client.responses.create(
            model=self.model,
            input=inputs,
            **kwargs,
        )

        text = getattr(response, "output_text", None)
        if not text:
            text = _extract_responses_text(getattr(response, "output", None))

        usage = _extract_usage(response)
        return ChatResponse(text=text or "", usage=usage)

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
    if isinstance(usage, dict):
        getter = usage.get
    else:

        def getter(key: str, default: int | None = None) -> int | None:
            return getattr(usage, key, default)
    return {
        "prompt_tokens": getter("prompt_tokens"),
        "completion_tokens": getter("completion_tokens"),
        "total_tokens": getter("total_tokens"),
    }


def _extract_responses_text(output: Any) -> str:
    if not output:
        return ""
    pieces: list[str] = []
    if isinstance(output, list):
        for segment in output:
            if not isinstance(segment, dict):
                continue
            content = segment.get("content")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        pieces.append(str(item.get("text", "")))
            elif content is not None:
                pieces.append(str(content))
    return "".join(pieces)
