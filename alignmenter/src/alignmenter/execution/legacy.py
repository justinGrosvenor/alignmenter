"""Capture legacy provider output without inferring unexposed adapter capabilities."""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable

from alignmenter.providers.base import ChatProvider
from alignmenter.providers.callable import recovery_contract
from alignmenter.schemas.execution import (
    Attempt,
    ExecutionStatus,
    FailureInfo,
    Observation,
    PlannedTurn,
    Stream,
)
from alignmenter.storage.runs import RunStore

logger = logging.getLogger(__name__)


def failure_info(exc: BaseException, *, invalid_response: bool = False) -> FailureInfo:
    kind = "invalid_response" if invalid_response else "provider_error"
    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
        kind = "interrupted"
    elif isinstance(exc, TimeoutError):
        kind = "timeout"
    return FailureInfo(kind=kind, exception_type=type(exc).__name__)


def _record_failure(
    store: RunStore, attempt: Attempt, exc: BaseException, *, invalid: bool = False
) -> None:
    try:
        store.fail_attempt(
            attempt,
            failure_info(exc, invalid_response=invalid),
            ExecutionStatus.FAILED if invalid else ExecutionStatus.UNKNOWN_OUTCOME,
        )
    except Exception:
        # A storage failure must not obscure the original provider exception/interrupt.
        logger.error("Could not finalize the active attempt; inspect its last committed state")


def _generate(
    store: RunStore,
    turn: PlannedTurn,
    provider: ChatProvider,
    model_identifier: str,
    conversation: list[dict[str, str]],
) -> dict:
    contract = recovery_contract(provider)
    target = next(t for t in store.manifest().targets if t.stream == turn.stream)
    if contract != target.recovery:
        raise ValueError("Provider recovery contract changed after the plan was frozen")
    attempt = store.start_attempt(turn, conversation)
    try:
        kwargs = {"request_id": str(attempt.request_id)} if contract is not None else {}
        response = provider.chat(copy.deepcopy(conversation), **kwargs)
    except BaseException as exc:
        _record_failure(store, attempt, exc)
        raise
    try:
        context = getattr(response, "context", None)
        observation = Observation(
            stream=turn.stream,
            ordinal=turn.ordinal,
            attempt_id=attempt.id,
            origin="generated",
            text=response.text,
            context=context,
            usage=getattr(response, "usage", None),
            context_status="missing" if context is None else "provided",
        )
        record = copy.deepcopy(turn.record)
        metadata = record.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        # These fields describe the replaced answer, not the new observation.
        for key in (
            "context",
            "usage",
            "generated_by",
            "baseline_text",
            "attempt_id",
            "observation_id",
        ):
            metadata.pop(key, None)
        if record.get("text"):
            metadata["baseline_text"] = record["text"]
        metadata.update(
            generated_by=model_identifier,
            attempt_id=str(attempt.id),
            observation_id=str(observation.id),
        )
        if observation.context is not None:
            metadata["context"] = observation.context
        if observation.usage is not None:
            metadata["usage"] = observation.usage
        record["metadata"] = metadata
        record["text"] = observation.text.strip()
    except Exception as exc:
        _record_failure(store, attempt, exc, invalid=True)
        raise
    # The record, raw observation, and successful attempt share one transaction.
    store.commit_record(turn, record, observation)
    return record


def capture_transcripts(
    store: RunStore,
    stream: Stream,
    provider: ChatProvider | None,
    model_identifier: str,
    progress: Callable[[int], None] | None = None,
) -> list[dict]:
    conversation: list[dict[str, str]] = []
    session_id: str | None = None
    committed = store.committed_records(stream)
    for turn in store.plan(stream):
        if session_id != turn.session_id:
            session_id, conversation = turn.session_id, []
        if turn.ordinal in committed:
            record = committed[turn.ordinal]
        elif turn.generate:
            if provider is None:
                raise ValueError("Frozen plan requires a provider for generation")
            record = _generate(store, turn, provider, model_identifier, conversation)
            if progress is not None:
                progress(1)  # Durable acknowledgment precedes progress reporting.
        else:
            record = copy.deepcopy(turn.record)
            observed = None
            if turn.role == "assistant":
                metadata = record.get("metadata") or {}
                if not isinstance(metadata, dict):
                    metadata = {}
                context = metadata.get("context")
                observed = Observation(
                    stream=stream,
                    ordinal=turn.ordinal,
                    origin="recorded",
                    text=record.get("text", ""),
                    context=context,
                    usage=metadata.get("usage"),
                    context_status="missing" if context is None else "provided",
                )
            store.commit_record(turn, record, observed)
        conversation.append({"role": turn.role, "content": record.get("text", "")})
    return store.transcripts(stream)
