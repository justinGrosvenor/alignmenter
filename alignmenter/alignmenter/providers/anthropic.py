"""Anthropic provider scaffold."""

from __future__ import annotations


class AnthropicProvider:
    """Placeholder implementation for Anthropic chat provider."""

    name = "anthropic"

    def chat(self, messages: list[dict], **kwargs) -> dict:
        raise NotImplementedError("Anthropic provider not implemented.")

    def tokenizer(self) -> None:
        return None
