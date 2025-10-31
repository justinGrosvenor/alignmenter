"""Local OpenAI-compatible provider scaffold."""

from __future__ import annotations


class LocalProvider:
    """Adapter targeting self-hosted OpenAI-compatible endpoints."""

    name = "local"

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def chat(self, messages: list[dict], **kwargs) -> dict:
        raise NotImplementedError("Local provider not implemented.")

    def tokenizer(self) -> None:
        return None
