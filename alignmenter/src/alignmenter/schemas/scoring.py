"""Typed evidence and assessments for the durable built-in evaluators."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from alignmenter.schemas.execution import VersionedRecord
from alignmenter.schemas.metrics import MetricSample

NonBlank = Annotated[str, Field(min_length=1, strict=True, pattern=r"\S")]


class SourceQuote(VersionedRecord):
    source_id: NonBlank
    quote: NonBlank


class Passage(VersionedRecord):
    source_id: NonBlank
    text: NonBlank
    provider_id: str | None = None


class EvidenceBundle(VersionedRecord):
    answer: str = Field(strict=True)
    question: str = Field(strict=True)
    question_source_id: NonBlank
    passages: list[Passage]


class QuantityFinding(VersionedRecord):
    quote: NonBlank
    normalized: str | None
    status: Literal["source", "question", "unmatched", "ambiguous"]
    evidence: SourceQuote | None = None

    @model_validator(mode="after")
    def match_has_evidence(self):
        if (self.status in {"source", "question"}) != (self.evidence is not None):
            raise ValueError("Matched quantities require a saved evidence quote")
        return self


class CitationFinding(VersionedRecord):
    quote: NonBlank
    index: int = Field(strict=True, ge=0)
    source_id: str | None


class GroundingAssessment(VersionedRecord):
    kind: Literal["grounding"] = "grounding"
    quantities: list[QuantityFinding]
    citations: list[CitationFinding]

    @property
    def outcome(self):
        if any(q.status == "unmatched" for q in self.quantities) or any(c.source_id is None for c in self.citations):
            return "violated"
        if any(q.status == "ambiguous" for q in self.quantities):
            return "needs_review"
        return "met" if self.quantities or self.citations else "not_applicable"


class FaithfulnessClaim(VersionedRecord):
    text: NonBlank
    status: Literal["supported", "unsupported", "contradicted"]
    evidence: list[SourceQuote]

    @model_validator(mode="after")
    def support_requires_evidence(self):
        if self.status != "unsupported" and not self.evidence:
            raise ValueError("Supported and contradicted claims require evidence")
        return self


class FaithfulnessVerdict(VersionedRecord):
    claims: list[FaithfulnessClaim]
    correctness: int = Field(strict=True, ge=0, le=10)
    answers_question: bool = Field(strict=True)
    abstained: bool = Field(strict=True)
    abstention_appropriate: bool | None = Field(strict=True)
    dangerous: bool = Field(strict=True)
    danger_reason: NonBlank | None
    reasoning: NonBlank
    no_claims_reason: Literal["appropriate_abstention", "nonfactual"] | None

    @model_validator(mode="after")
    def explicit_empty_and_safety_states(self):
        if self.abstained != (self.abstention_appropriate is not None):
            raise ValueError("Abstention appropriateness must be explicit only for abstentions")
        if self.dangerous != (self.danger_reason is not None):
            raise ValueError("Dangerous answers require a reason; other answers use null")
        if bool(self.claims) == (self.no_claims_reason is not None):
            raise ValueError("Empty claims require an explicit reason; nonempty claims use null")
        if self.no_claims_reason == "appropriate_abstention" and not (self.abstained and self.abstention_appropriate):
            raise ValueError("Empty abstention claims require an appropriate abstention")
        if self.no_claims_reason == "nonfactual" and self.abstained:
            raise ValueError("Abstentions cannot be labeled nonfactual")
        if len({c.text for c in self.claims}) != len(self.claims):
            raise ValueError("Duplicate claim quotes")
        return self


class FaithfulnessAssessment(VersionedRecord):
    kind: Literal["faithfulness"] = "faithfulness"
    verdict: FaithfulnessVerdict
    min_correctness: int = Field(strict=True, ge=0, le=10)

    @property
    def outcome(self):
        v = self.verdict
        if (v.dangerous or any(c.status != "supported" for c in v.claims)
                or v.abstained and not v.abstention_appropriate
                or not v.answers_question and not (v.abstained and v.abstention_appropriate)
                or v.correctness < self.min_correctness):
            return "violated"
        return "not_applicable" if v.no_claims_reason == "nonfactual" else "met"


class CustomAssessment(VersionedRecord):
    kind: Literal["custom"] = "custom"
    outcome: Literal["met", "violated", "not_applicable", "needs_review"]
    rationale: NonBlank
    evidence: list[SourceQuote] = Field(default_factory=list)
    metrics: dict[str, MetricSample]


Assessment = Annotated[GroundingAssessment | FaithfulnessAssessment | CustomAssessment, Field(discriminator="kind")]
