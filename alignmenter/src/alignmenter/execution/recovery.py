"""Resume only captured target work, with no implicit evaluation calls."""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from alignmenter.execution.artifacts import export_capture
from alignmenter.execution.leases import coordinator_lease
from alignmenter.execution.legacy import capture_transcripts
from alignmenter.providers.callable import CaptureTarget, recovery_contract
from alignmenter.schemas.execution import (
    ExecutionStatus,
    ExecutionSummary,
    FailureInfo,
    RunPhase,
    Stream,
    content_digest,
)
from alignmenter.storage.runs import RunStore
from alignmenter.utils.io import read_jsonl

logger = logging.getLogger(__name__)


class ResumeError(ValueError):
    """Saved work cannot safely continue with the supplied target."""


def _check_inputs(store: RunStore, dataset_path: Path | None, persona_path: Path | None) -> None:
    manifest, plan = store.manifest(), store.plan()
    dataset = json.loads(store.source_artifact(manifest.dataset_digest))
    if manifest.persona_digest is not None:
        store.source_artifact(manifest.persona_digest)
    if manifest.plan_digest is None:
        raise ResumeError("Run has no frozen plan identity; export transcripts to start a new run")
    if content_digest([t.model_dump(mode="json") for t in plan]) != manifest.plan_digest:
        raise ResumeError("Frozen plan digest mismatch")
    source_records = Counter(content_digest(record) for record in dataset)
    for target in manifest.targets:
        turns = [t for t in plan if t.stream == target.stream]
        if (
            [t.ordinal for t in turns] != list(range(len(dataset)))
            or Counter(content_digest(t.record) for t in turns) != source_records
        ):
            raise ResumeError("Frozen plan differs from source snapshot")
    if dataset_path is not None and content_digest(read_jsonl(Path(dataset_path))) != manifest.dataset_digest:
        raise ResumeError("Dataset differs from the frozen run inputs")
    if persona_path is not None and hashlib.sha256(Path(persona_path).read_bytes()).hexdigest() != manifest.persona_digest:
        raise ResumeError("Persona differs from the frozen run inputs")


def _check_saved_capture(store: RunStore) -> None:
    observations = {(o.stream, o.ordinal): o for o in store.observations()}
    attempts = {a.id: a for a in store.attempts()}
    for target in store.manifest().targets:
        records = store.committed_records(target.stream)
        if list(records) != list(range(len(records))):
            raise ResumeError("Committed records are not a conversation prefix")
        conversation, session_id, unknown_history = [], None, False
        for turn in store.plan(target.stream):
            if turn.session_id != session_id:
                conversation, session_id, unknown_history = [], turn.session_id, False
            previous = [a for a in attempts.values()
                        if (a.stream, a.ordinal) == (turn.stream, turn.ordinal)]
            if previous and (unknown_history or any(
                a.input_digest != content_digest(conversation) for a in previous
            )):
                raise ResumeError("Saved request messages differ from the committed conversation")
            if previous and len({a.request_id for a in previous}) != 1:
                raise ResumeError("Retry attempts disagree on request identity")
            record = records.get(turn.ordinal)
            observed = observations.pop((turn.stream, turn.ordinal), None)
            if record is None:
                if observed is not None:
                    raise ResumeError("Observation has no committed transcript record")
                if turn.generate:
                    unknown_history = True
                else:
                    conversation.append({"role": turn.role, "content": turn.record.get("text", "")})
                continue
            if not turn.generate and record != turn.record:
                raise ResumeError("Saved recorded input differs from its frozen source")
            if turn.role == "assistant":
                if observed is None:
                    raise ResumeError("Saved assistant record has no observation")
                text = observed.text.strip() if turn.generate else observed.text
                metadata = record.get("metadata") or {}
                metadata = metadata if isinstance(metadata, dict) else {}
                if (
                    record.get("text", "") != text
                    or metadata.get("context") != observed.context
                    or metadata.get("usage") != observed.usage
                    or (observed.origin == "generated") != turn.generate
                ):
                    raise ResumeError("Saved transcript disagrees with its observation")
                if turn.generate:
                    attempt = attempts.get(observed.attempt_id)
                    if (
                        attempt is None or attempt.status != ExecutionStatus.SUCCEEDED
                        or (attempt.stream, attempt.ordinal) != (turn.stream, turn.ordinal)
                        or record.get("session_id") != turn.session_id
                        or metadata.get("attempt_id") != str(attempt.id)
                        or metadata.get("observation_id") != str(observed.id)
                    ):
                        raise ResumeError("Saved observation has no matching successful attempt")
            elif observed is not None:
                raise ResumeError("Non-assistant record has an observation")
            conversation.append({"role": turn.role, "content": record.get("text", "")})
    if observations:
        raise ResumeError("Observation lies outside the frozen plan")


def _preflight(
    store: RunStore, targets: Mapping[Stream, CaptureTarget],
    dataset_path: Path | None, persona_path: Path | None,
) -> None:
    summary = store.summary()
    if summary.committed_records < summary.planned_records and (
        summary.run.phase != RunPhase.CAPTURE
        or summary.run.status in {ExecutionStatus.SUCCEEDED, ExecutionStatus.CAPTURED}
    ):
        raise ResumeError("Incomplete capture has an incompatible run state")
    _check_inputs(store, dataset_path, persona_path)
    _check_saved_capture(store)
    manifest, attempts = store.manifest(), store.attempts()
    if set(targets) - {t.stream for t in manifest.targets}:
        raise ResumeError("Supplied target stream is not in the frozen run")
    for frozen in manifest.targets:
        committed = store.committed_records(frozen.stream)
        pending = [t for t in store.plan(frozen.stream)
                   if t.generate and t.ordinal not in committed]
        supplied = targets.get(frozen.stream)
        if frozen.mode == "recorded":
            if supplied is not None:
                raise ResumeError("Recorded streams cannot be changed to generated streams")
            continue
        if supplied is None:
            if pending:
                raise ResumeError(f"{frozen.stream}: a compatible capture target is required")
            continue
        contract = recovery_contract(supplied.provider)
        adapter = f"{type(supplied.provider).__module__}.{type(supplied.provider).__qualname__}"
        if supplied.model != frozen.model or adapter != frozen.adapter or contract != frozen.recovery:
            raise ResumeError(f"{frozen.stream}: target configuration differs from the frozen run")
        if not pending:
            continue
        if manifest.max_target_calls is not None and len(attempts) >= manifest.max_target_calls:
            raise ResumeError("Run target call budget exhausted")
        if contract is None or contract.session_state != "stateless":
            raise ResumeError(f"{frozen.stream}: adapter has no supported stateless recovery contract")
        try:
            current_version = version("alignmenter")
        except PackageNotFoundError:
            current_version = "unknown"
        if current_version == "unknown" or current_version != manifest.package_version:
            raise ResumeError("Alignmenter package version differs or is unavailable; start a new run")
        for turn in pending:
            previous = [a for a in attempts if (a.stream, a.ordinal) == (turn.stream, turn.ordinal)]
            if previous and contract.interrupted_request != "idempotent":
                raise ResumeError(f"{turn.stream} turn {turn.ordinal}: unfinished request requires idempotent recovery")
            if len(previous) >= contract.max_attempts:
                raise ResumeError(f"{turn.stream} turn {turn.ordinal}: frozen attempt limit exhausted")
            if any(a.status not in {ExecutionStatus.RUNNING, ExecutionStatus.UNKNOWN_OUTCOME,
                                    ExecutionStatus.FAILED} for a in previous):
                raise ResumeError("Uncommitted turn has an incompatible attempt state")


def resume_capture(
    run_dir: Path,
    *,
    targets: Mapping[Stream, CaptureTarget] | None = None,
    dataset_path: Path | None = None,
    persona_path: Path | None = None,
    check_only: bool = False,
) -> ExecutionSummary:
    """Reuse committed answers and perform at most one new attempt per missing turn.

    With no source paths, use verified saved snapshots. Optional source paths assert
    compatibility; they never replace the saved plan. Preflight covers every stream
    before mutating state or dispatching. ``check_only`` performs that preflight
    under the lease, without changing the database or invoking a target.

    Completed capture is a no-op, including after a scoring/reporting failure.
    Evaluations are never restarted here. Old databases remain readable/exportable.
    """
    store, targets = RunStore(run_dir), dict(targets or {})
    with coordinator_lease(store.run_dir):
        _preflight(store, targets, dataset_path, persona_path)
        summary = store.summary()
        complete = summary.committed_records == summary.planned_records
        if check_only:
            return summary
        if complete and (summary.run.phase != RunPhase.CAPTURE or summary.run.status in {
            ExecutionStatus.SUCCEEDED, ExecutionStatus.CAPTURED,
        }):
            return summary
        store.reopen_capture()
        try:
            for target in store.manifest().targets:
                supplied = targets.get(target.stream)
                capture_transcripts(store, target.stream,
                                    supplied.provider if supplied is not None else None, target.model)
            export_capture(store)
            store.set_run_state(status=ExecutionStatus.CAPTURED)
        except BaseException as exc:
            try:
                interrupted = isinstance(exc, (KeyboardInterrupt, SystemExit))
                store.set_run_state(
                    status=ExecutionStatus.INTERRUPTED if interrupted else ExecutionStatus.FAILED,
                    failure=FailureInfo(kind="interrupted" if interrupted else "pipeline_error",
                                        exception_type=type(exc).__name__),
                )
                export_capture(store)
            except Exception:
                logger.error("Could not finalize resumed capture; inspect committed database records")
            raise
        return store.summary()
