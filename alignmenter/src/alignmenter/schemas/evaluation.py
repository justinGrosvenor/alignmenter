"""Versioned rubric, judge accounting, and saved verdict contracts."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field, field_validator, model_validator

from alignmenter.schemas.execution import (
    Digest,
    JsonObject,
    NonNegativeInt,
    Stream,
    VersionedRecord,
    content_digest,
    utc_now,
)
from alignmenter.schemas.metrics import EvaluatorDescriptor, MetricSample
from alignmenter.schemas.scoring import Assessment, EvidenceBundle

NonBlank = Annotated[str, Field(min_length=1, strict=True, pattern=r"\S")]
Outcome = Literal["met", "violated", "not_applicable"]
ResultStatus = Literal[
    "met", "violated", "not_applicable", "missing_capture", "missing_evidence",
    "invalid", "budget_blocked", "unknown_outcome", "needs_review",
]


class Criterion(VersionedRecord):
    id: NonBlank
    revision: NonBlank
    rubric: NonBlank | None = None
    evaluator: NonBlank = "rubric"
    config: JsonObject = Field(default_factory=dict)
    evidence_requirement: Literal["conversation", "context", "complete_context"] = "conversation"
    allow_not_applicable: bool = Field(default=False, strict=True)
    min_correctness: int | None = Field(default=None, strict=True, ge=0, le=10)

    @model_validator(mode="before")
    @classmethod
    def builtin_defaults(cls, value):
        if isinstance(value, dict) and value.get("evaluator") in {"grounding", "faithfulness"}:
            value = dict(value)
            value.setdefault("evidence_requirement", "context")
            value.setdefault("allow_not_applicable", True)
            if value.get("evaluator") == "faithfulness":
                value.setdefault("min_correctness", 7)
        return value

    @model_validator(mode="after")
    def evaluator_configuration(self):
        if self.evaluator == "rubric" and self.rubric is None:
            raise ValueError("Rubric evaluators require rubric text")
        if self.evaluator not in {"rubric", "faithfulness"} and self.rubric is not None:
            raise ValueError("Deterministic evaluators do not accept judge instructions")
        if self.evaluator in {"grounding", "faithfulness"} and (self.evidence_requirement == "conversation" or not self.allow_not_applicable):
            raise ValueError("Built-in evidence evaluators require context and explicit not_applicable support")
        if (self.evaluator == "faithfulness") != (self.min_correctness is not None):
            raise ValueError("Only faithfulness accepts a required min_correctness threshold")
        if self.evaluator in {"rubric", "grounding", "faithfulness"} and self.config:
            raise ValueError("Built-in evaluators do not accept custom config")
        content_digest(self.config)
        return self


class EvaluationSpec(VersionedRecord):
    id: NonBlank
    revision: NonBlank
    criteria: tuple[Criterion, ...] = Field(min_length=1)
    qualification: Literal["draft", "reviewed"] = "draft"
    scope: Literal["turn"] = "turn"
    streams: tuple[Stream, ...] = ("primary",)
    # Intentional repeat judgments have different request/cache identities.
    sample: NonNegativeInt = 0

    @model_validator(mode="after")
    def unique_criteria(self):
        if len({c.id for c in self.criteria}) != len(self.criteria):
            raise ValueError("Criterion IDs must be unique")
        if not self.streams or len(set(self.streams)) != len(self.streams):
            raise ValueError("Evaluation streams must be nonempty and unique")
        return self


class JudgeContract(VersionedRecord):
    model: NonBlank
    configuration_digest: Digest
    # Includes transport/SDK settings: no hidden retries, fallbacks, or repair calls.
    max_dispatches_per_request: Literal[1] = 1
    max_cost_micros_per_call: NonNegativeInt | None = None

    @field_validator("max_dispatches_per_request", mode="before")
    @classmethod
    def single_dispatch(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("Exactly one dispatch per judge request must be declared")
        return value


class JudgeBudget(VersionedRecord):
    max_calls: NonNegativeInt
    max_cost_micros: NonNegativeInt | None = None


class JudgeRequest(VersionedRecord):
    system: NonBlank
    prompt: NonBlank


class JudgeReply(VersionedRecord):
    text: str = Field(strict=True)
    finish_reason: Literal["stop", "length", "refusal", "other"]
    usage: JsonObject | None = None
    actual_cost_micros: NonNegativeInt | None = None

    @model_validator(mode="after")
    def finite_payload(self):
        content_digest(self.model_dump(mode="json"))
        return self


class EvidenceCitation(VersionedRecord):
    source_id: NonBlank
    quote: NonBlank


class RubricVerdict(VersionedRecord):
    outcome: Outcome
    rationale: NonBlank
    evidence: list[EvidenceCitation]


class EvaluationInput(VersionedRecord):
    key: Digest
    stream: Stream
    ordinal: NonNegativeInt
    session_id: NonBlank
    criterion_id: NonBlank
    observation_id: UUID | None
    observation_digest: Digest | None
    request: JudgeRequest | None
    sources: dict[str, str]
    unavailable: Literal["missing_capture", "missing_evidence"] | None = None
    tags: tuple[str, ...] = ()
    persona_ids: tuple[str, ...] = ()
    evaluator: NonBlank = "rubric"
    data: EvidenceBundle | None = None
    payload: JsonObject | None = None
    case_id: NonBlank | None = None
    case_revision: Digest | None = None
    split_group: NonBlank | None = None

    @model_validator(mode="after")
    def availability(self):
        if self.unavailable is not None:
            if self.request is not None or self.data is not None or self.payload is not None:
                raise ValueError("Unavailable inputs cannot contain executable requests or data")
        elif self.evaluator == "grounding":
            if self.request is not None or self.data is None:
                raise ValueError("Grounding requires evidence data and no judge request")
        elif self.evaluator not in {"rubric", "faithfulness"}:
            if self.request is not None or self.payload is None:
                raise ValueError("Custom deterministic inputs require payload and no judge request")
        elif self.request is None or (self.evaluator == "faithfulness" and self.data is None):
            raise ValueError("Available judged inputs require a request and built-in evidence data")
        return self


class EvaluationManifest(VersionedRecord):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    identity: Digest
    spec: EvaluationSpec
    judge: JudgeContract | None
    inputs_digest: Digest
    engine_revision: Literal["rubric-v1", "evaluators-v1", "evaluators-v2"] = "rubric-v1"
    evaluators: tuple[EvaluatorDescriptor, ...] = ()
    package_version: str
    created_at: AwareDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def judge_matches_evaluators(self):
        if any(c.evaluator in {"rubric", "faithfulness"} for c in self.spec.criteria) != (self.judge is not None):
            raise ValueError("Judged evaluations require a contract; deterministic evaluations omit it")
        if len({e.id for e in self.evaluators}) != len(self.evaluators):
            raise ValueError("Evaluator descriptor IDs must be unique")
        if self.engine_revision == "evaluators-v2" and {e.id for e in self.evaluators} != {c.evaluator for c in self.spec.criteria}:
            raise ValueError("Every evaluator must have a frozen descriptor")
        return self


class JudgeCall(VersionedRecord):
    id: UUID = Field(default_factory=uuid4)
    cache_key: Digest
    judge: JudgeContract
    request: JudgeRequest
    status: Literal["running", "response_saved", "unknown_outcome", "invalid_response", "cost_bound_exceeded"] = "running"
    reserved_cost_micros: NonNegativeInt | None
    reply: JudgeReply | None = None
    exception_type: str | None = None
    started_at: AwareDatetime = Field(default_factory=utc_now)
    finished_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def committed_boundary(self):
        if self.cache_key != content_digest({"request": self.request.model_dump(mode="json"),
                                             "judge": self.judge.model_dump(mode="json")}):
            raise ValueError("Judge call cache identity mismatch")
        if (self.status == "running") != (self.finished_at is None):
            raise ValueError("Only running judge calls have no finish time")
        if (self.reply is not None) != (self.status in {"response_saved", "cost_bound_exceeded"}):
            raise ValueError("Saved response state must match reply presence")
        return self


class EvaluationResult(VersionedRecord):
    id: UUID = Field(default_factory=uuid4)
    evaluation_id: UUID
    input_key: Digest
    status: ResultStatus
    call_id: UUID | None = None
    verdict: RubricVerdict | None = None
    assessment: Assessment | None = None
    metrics: dict[str, MetricSample] = Field(default_factory=dict)
    reason: NonBlank | None = None
    recorded_at: AwareDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def verdict_matches(self):
        valid = self.status in {"met", "violated", "not_applicable", "needs_review"}
        values = [v for v in (self.verdict, self.assessment) if v is not None]
        if len(values) != int(valid):
            raise ValueError("Evaluated results require exactly one verdict or assessment")
        if values and values[0].outcome != self.status:
            raise ValueError("Result and verdict outcomes disagree")
        if self.assessment is not None and self.assessment.kind == "custom" and self.metrics != self.assessment.metrics:
            raise ValueError("Saved metrics must match the custom assessment")
        return self
