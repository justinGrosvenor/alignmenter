"""Provider adapter scaffolds."""

from __future__ import annotations

from typing import Optional

from .anthropic import AnthropicProvider
from .base import ChatProvider, parse_provider_model
from .classifiers import load_safety_classifier
from .local import LocalProvider
from .openai import OpenAIProvider, OpenAICustomGPTProvider

__all__ = [
    "OpenAIProvider",
    "OpenAICustomGPTProvider",
    "AnthropicProvider",
    "LocalProvider",
    "load_safety_classifier",
    "load_chat_provider",
]


def load_chat_provider(identifier: Optional[str]) -> Optional[ChatProvider]:
    """Instantiate a chat provider for the given identifier.

    Returns ``None`` when *identifier* is falsy or explicitly disabled.
    """

    if not identifier:
        return None

    identifier = identifier.strip()
    if identifier.lower() in {"none", "offline"}:
        return None

    provider_name, _ = parse_provider_model(identifier)

    if provider_name == OpenAIProvider.name:
        return OpenAIProvider.from_model_identifier(identifier)
    if provider_name == OpenAICustomGPTProvider.name:
        return OpenAICustomGPTProvider.from_model_identifier(identifier)
    if provider_name == AnthropicProvider.name:
        return AnthropicProvider.from_model_identifier(identifier)
    if provider_name == LocalProvider.name:
        return LocalProvider.from_identifier(identifier)

    raise ValueError(f"Unsupported chat provider prefix: '{provider_name}'.")
