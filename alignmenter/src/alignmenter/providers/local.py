"""Local OpenAI-compatible provider implementation."""

from __future__ import annotations

import os
from typing import Any, Optional, Tuple

import requests

from alignmenter.providers.base import ChatResponse, parse_provider_model


class LocalProvider:
    """Adapter targeting self-hosted OpenAI-compatible endpoints."""

    name = "local"

    def __init__(
        self,
        endpoint: str,
        *,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        if not endpoint:
            raise ValueError("endpoint is required for LocalProvider")
        self.endpoint = endpoint
        self.default_model = model
        self.timeout = timeout
        self.api_key = api_key or os.getenv("ALIGNMENTER_LOCAL_API_KEY") or os.getenv("OPENAI_API_KEY")

    @classmethod
    def from_identifier(cls, identifier: str) -> "LocalProvider":
        provider, remainder = parse_provider_model(identifier)
        if provider != cls.name:
            raise ValueError(f"Expected provider 'local', got '{provider}'.")

        endpoint, model = _split_endpoint_model(remainder)
        return cls(endpoint=endpoint, model=model)

    def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> ChatResponse:
        model_name = kwargs.pop("model", None) or self.default_model
        if not model_name:
            raise ValueError(
                "Local provider requires a model name. Include it as 'local:<endpoint>|<model>' or pass via kwargs."
            )

        payload = {"model": model_name, "messages": messages}
        payload.update(kwargs)

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = requests.post(self.endpoint, json=payload, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        text = _extract_content(data)
        usage = _extract_usage(data)
        return ChatResponse(text=text, usage=usage)

    def tokenizer(self) -> None:
        return None


def _split_endpoint_model(value: str) -> Tuple[str, Optional[str]]:
    endpoint, sep, model = value.partition("|")
    endpoint = endpoint.strip()
    model = model.strip() if sep else None
    if not endpoint:
        raise ValueError("Local provider identifier must include an endpoint URL after 'local:'.")
    return endpoint, model or None


def _extract_content(payload: Any) -> str:
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, list):
                return "".join(part.get("text", "") for part in content if isinstance(part, dict))
            if content is not None:
                return str(content)
    return payload.get("text", "") if isinstance(payload, dict) else ""


def _extract_usage(payload: Any) -> Optional[dict[str, Any]]:
    if not isinstance(payload, dict):
        return None

    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None

    return {
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }
