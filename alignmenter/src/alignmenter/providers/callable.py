"""Explicit recovery contract for product-owned Python callables."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from alignmenter.providers.base import ChatProvider, ChatResponse
from alignmenter.schemas.execution import RecoveryContract


def recovery_contract(provider: ChatProvider | None) -> RecoveryContract | None:
    value = getattr(provider, "recovery_contract", None)
    if value is not None and not isinstance(value, RecoveryContract):
        raise ValueError("Provider recovery_contract must be a RecoveryContract")
    return value


@dataclass(frozen=True)
class CallableProvider:
    """Call ``function(messages, request_id=...)`` using a frozen declaration.

    This wrapper forwards request identity; it does not implement deduplication.
    The configuration digest must cover code, model, prompt, retrieval, tools, and
    generation settings that can change the target's behavior, excluding secrets.
    """

    function: Callable[..., ChatResponse]
    recovery_contract: RecoveryContract
    name: str = "callable"

    def chat(self, messages: list[dict], *, request_id: str) -> ChatResponse:
        return self.function(messages, request_id=request_id)

    def tokenizer(self):
        return None


@dataclass(frozen=True)
class CaptureTarget:
    """Explicit model identity and provider returned by a CLI target factory."""

    model: str
    provider: ChatProvider

    def __post_init__(self):
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("Capture target requires a nonempty model identity")
        if not callable(getattr(self.provider, "chat", None)):
            raise ValueError("Capture target requires a chat provider")
        recovery_contract(self.provider)
