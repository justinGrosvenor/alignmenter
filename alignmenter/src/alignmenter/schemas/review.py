"""Append-only reference labels, separate from immutable machine assessments."""

from typing import Literal
from uuid import UUID, uuid4

from pydantic import AwareDatetime, Field

from alignmenter.schemas.evaluation import Criterion, EvaluationInput, EvaluationResult, Outcome
from alignmenter.schemas.execution import Digest, VersionedRecord, utc_now
from alignmenter.schemas.metrics import Name


class ReviewDraft(VersionedRecord):
    id: UUID = Field(default_factory=uuid4)
    reviewer: Name | None = None
    outcome: Outcome | None = None
    rationale: Name | None = None
    role: Literal["opinion", "adjudication"] = "opinion"
    provenance: Literal["human", "model", "synthetic"] | None = None
    supersedes: UUID | None = None


class ReviewTask(VersionedRecord):
    review_key: Digest
    evaluation_id: UUID
    input_digest: Digest
    input: EvaluationInput
    criterion: Criterion
    machine_result: EvaluationResult | None
    annotation: ReviewDraft = Field(default_factory=ReviewDraft)


class Annotation(VersionedRecord):
    id: UUID
    review_key: Digest
    evaluation_id: UUID
    input_key: Digest
    input_digest: Digest
    case_id: Name
    criterion_id: Name
    reviewer: Name
    outcome: Outcome
    rationale: Name
    role: Literal["opinion", "adjudication"]
    provenance: Literal["human", "model", "synthetic"]
    supersedes: UUID | None
    recorded_at: AwareDatetime = Field(default_factory=utc_now)
