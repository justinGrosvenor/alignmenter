"""Judge adapters with a single accounted dispatch per invocation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version
from typing import Protocol

from alignmenter.schemas.evaluation import JudgeContract, JudgeReply, JudgeRequest
from alignmenter.schemas.execution import content_digest


class DurableJudge(Protocol):
    contract: JudgeContract

    def evaluate(self, request: JudgeRequest) -> JudgeReply: ...


@dataclass(frozen=True)
class CallableJudge:
    """The callable must perform at most one external dispatch, including SDK retries."""

    function: Callable[[JudgeRequest], JudgeReply]
    contract: JudgeContract

    def evaluate(self, request: JudgeRequest) -> JudgeReply:
        return self.function(request)


class ChatCompletionJudge:
    """OpenAI-compatible text judge, including locally hosted Atlas evaluation models.

    Uses an explicitly configured client, a finite timeout, and no retry/fallback.
    No implicit model or price lookup. Monetary bounds/actual pricing need a custom
    adapter; this adapter supports the durable call-count budget only.
    """

    def __init__(self, *, client, model: str, revision: str, max_completion_tokens: int = 2048,
                 timeout: float = 60.0, json_mode: bool = True) -> None:
        if type(max_completion_tokens) is not int or max_completion_tokens < 1:
            raise ValueError("max_completion_tokens must be a positive integer")
        import math

        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Judge timeout must be positive and finite")
        if not revision.strip():
            raise ValueError("Judge deployment revision is required")
        self._client = client.with_options(max_retries=0, timeout=timeout)
        self._model, self._tokens, self._json_mode = model, max_completion_tokens, json_mode
        self.contract = JudgeContract(model=model, configuration_digest=content_digest({
            "adapter": "chat-completion-v1", "model": model, "deployment_revision": revision,
            "sdk_version": version("openai"),
            "organization": getattr(self._client, "organization", None),
            "project": getattr(self._client, "project", None),
            # Persist only the digest; endpoint URLs may contain private routing details.
            "endpoint": str(self._client.base_url), "max_completion_tokens": max_completion_tokens,
            "timeout": timeout, "json_mode": json_mode, "max_retries": 0,
        }))

    def evaluate(self, request: JudgeRequest) -> JudgeReply:
        options = {"response_format": {"type": "json_object"}} if self._json_mode else {}
        response = self._client.chat.completions.create(
            model=self._model, extra_body={"max_completion_tokens": self._tokens},
            messages=[{"role": "system", "content": request.system},
                      {"role": "user", "content": request.prompt}], **options,
        )
        choice = response.choices[0]
        reason = "refusal" if getattr(choice.message, "refusal", None) else choice.finish_reason
        usage = response.usage.model_dump(mode="json") if response.usage is not None else None
        return JudgeReply(text=choice.message.content or "",
                          finish_reason=reason if reason in {"stop", "length", "refusal"} else "other",
                          usage=usage)
