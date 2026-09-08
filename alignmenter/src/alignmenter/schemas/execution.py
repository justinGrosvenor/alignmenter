"""Version 1 execution records for the durable legacy-runner bridge."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

JsonObject = dict[str, JsonValue]
Stream = Literal["primary", "compare"]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonNegativeInt = Annotated[int, Field(ge=0, strict=True)]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def canonical_json_bytes(value: JsonValue) -> bytes:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return payload.encode("utf-8")


def content_digest(value: JsonValue) -> str:
    """SHA-256 over canonical JSON, independent of dictionary insertion order."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


class VersionedRecord(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, allow_inf_nan=False, validate_default=True
    )
    schema_version: Literal[1] = 1

    @field_validator("schema_version", mode="before")
    @classmethod
    def strict_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("Only integer schema_version 1 is supported")
        return value


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    CAPTURED = "captured"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    UNKNOWN_OUTCOME = "unknown_outcome"


class RunPhase(str, Enum):
    CAPTURE = "capture"
    SCORING = "scoring"
    REPORTING = "reporting"


class FailureInfo(VersionedRecord):
    kind: Literal["timeout", "provider_error", "invalid_response", "interrupted", "pipeline_error"]
    exception_type: str
    # Arbitrary exception messages can contain provider credentials/request headers.
    # The caller still receives the original exception; the durable record stores its type.


class RecoveryContract(VersionedRecord):
    """Adapter-owned promises, frozen before the first dispatch.

    Stateless means every request carries all conversation state. Idempotent means
    the target durably deduplicates the same request ID and returns its original
    response, including across client/process restarts. Neither is inferred.
    """

    configuration_digest: Digest
    session_state: Literal["stateless", "opaque"]
    interrupted_request: Literal["refuse", "idempotent"] = "refuse"
    max_attempts: int = Field(default=3, ge=1, strict=True)


class TargetSnapshot(VersionedRecord):
    stream: Stream
    model: str
    mode: Literal["generate", "recorded"]
    adapter: str | None = None
    recovery: RecoveryContract | None = None
    provenance: Literal["legacy_partial"] = "legacy_partial"


class PlannedTurn(VersionedRecord):
    stream: Stream
    ordinal: NonNegativeInt
    session_id: str = Field(min_length=1, strict=True)
    role: str = Field(min_length=1, strict=True)
    generate: bool = Field(strict=True)
    record: JsonObject

    @model_validator(mode="after")
    def validate_record(self) -> PlannedTurn:
        if not self.session_id.strip():
            raise ValueError("Session ID must not be blank")
        if self.generate and self.role != "assistant":
            raise ValueError("Only assistant turns may be generated")
        if self.record.get("session_id") != self.session_id:
            raise ValueError("Planned session must match the source record")
        source_role = self.record.get("role") or "user"
        if not isinstance(source_role, str) or source_role.strip().lower() != self.role:
            raise ValueError("Planned role must match the source record")
        if not isinstance(self.record.get("text", ""), str):
            raise ValueError("Turn text must be a string")
        return self


class RunManifest(VersionedRecord):
    id: UUID = Field(default_factory=uuid4)
    label: str
    created_at: AwareDatetime = Field(default_factory=utc_now)
    dataset_path: str
    dataset_digest: Digest
    plan_digest: Digest | None = None
    persona_path: str
    persona_digest: Digest | None = None
    targets: tuple[TargetSnapshot, ...]
    scorer_ids: dict[Stream, list[str]]
    thresholds: JsonObject
    include_raw: bool
    package_version: str
    max_target_calls: NonNegativeInt | None = None
    suite: JsonObject | None = None
    provenance_gaps: tuple[str, ...] = (
        "Legacy providers do not expose a complete nonsecret configuration snapshot.",
        "Legacy scorers do not expose complete configuration or evaluation identity.",
        "Legacy adapters do not declare evidence completeness or verified session state.",
    )


class RunRecord(VersionedRecord):
    id: UUID
    status: ExecutionStatus = ExecutionStatus.RUNNING
    phase: RunPhase = RunPhase.CAPTURE
    updated_at: AwareDatetime = Field(default_factory=utc_now)
    failure: FailureInfo | None = None


class Attempt(VersionedRecord):
    id: UUID = Field(default_factory=uuid4)
    request_id: UUID = Field(default_factory=uuid4)
    stream: Stream
    ordinal: NonNegativeInt
    status: ExecutionStatus = ExecutionStatus.RUNNING
    started_at: AwareDatetime = Field(default_factory=utc_now)
    finished_at: AwareDatetime | None = None
    messages: list[JsonObject]
    input_digest: Digest
    failure: FailureInfo | None = None

    @model_validator(mode="after")
    def validate_attempt(self) -> Attempt:
        if content_digest(self.messages) != self.input_digest:
            raise ValueError("Attempt input digest does not match its messages")
        if (self.status == ExecutionStatus.RUNNING) != (self.finished_at is None):
            raise ValueError("Running attempts have no finish time; terminal attempts require one")
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("Attempt cannot finish before it starts")
        return self


class Observation(VersionedRecord):
    id: UUID = Field(default_factory=uuid4)
    stream: Stream
    ordinal: NonNegativeInt
    attempt_id: UUID | None = None
    origin: Literal["generated", "recorded"]
    text: str = Field(strict=True)
    context: JsonObject | None = None
    usage: JsonObject | None = None
    context_status: Literal["missing", "provided"]
    evidence_completeness: Literal["unknown"] = "unknown"
    captured_at: AwareDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_origin(self) -> Observation:
        if (self.origin == "generated") != (self.attempt_id is not None):
            raise ValueError("Only generated observations have a dispatch attempt")
        if (self.context is None) != (self.context_status == "missing"):
            raise ValueError("Context presence and context status disagree")
        # JsonValue's recursive union can otherwise admit nonfinite values.
        content_digest(self.model_dump(mode="json"))
        return self


class ExecutionSummary(VersionedRecord):
    run: RunRecord
    planned_records: NonNegativeInt
    committed_records: NonNegativeInt
    planned_generations: NonNegativeInt
    observations: NonNegativeInt
    attempts: dict[ExecutionStatus, NonNegativeInt]
    liveness: Literal["not_checked"] = "not_checked"
