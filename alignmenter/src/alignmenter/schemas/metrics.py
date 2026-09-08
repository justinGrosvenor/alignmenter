"""Portable metric definitions and sufficient statistics for pure aggregation."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, model_validator

from alignmenter.schemas.execution import VersionedRecord

Name = Annotated[str, Field(strict=True, min_length=1, pattern=r"\S")]
FiniteNumber = Annotated[float, Field(strict=True, allow_inf_nan=False)]


class MetricDescriptor(VersionedRecord):
    id: Name
    revision: Name
    unit: Name
    direction: Literal["higher", "lower", "neutral"]
    aggregation: Literal["ratio", "mean", "count"]
    description: Name


class MetricSample(VersionedRecord):
    numerator: FiniteNumber
    denominator: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def empty_population(self):
        if self.denominator == 0 and self.numerator != 0:
            raise ValueError("An empty population cannot have a nonzero numerator")
        return self


class EvaluatorDescriptor(VersionedRecord):
    id: Name
    revision: Name
    configuration_digest: str = Field(pattern=r"^[a-f0-9]{64}$", strict=True)
    metrics: tuple[MetricDescriptor, ...] = ()

    @model_validator(mode="after")
    def unique_metrics(self):
        if len({m.id for m in self.metrics}) != len(self.metrics):
            raise ValueError("Evaluator metric IDs must be unique")
        return self


def validate_samples(samples: dict[str, MetricSample], descriptors: tuple[MetricDescriptor, ...]):
    definitions = {d.id: d for d in descriptors}
    if set(samples) != set(definitions):
        raise ValueError("An assessment must provide every registered metric, and no unknown metrics")
    for name, sample in samples.items():
        aggregation = definitions[name].aggregation
        if aggregation == "ratio" and not 0 <= sample.numerator <= sample.denominator:
            raise ValueError("Ratio numerators must be within their population")
        if aggregation == "count" and (sample.numerator < 0 or not sample.numerator.is_integer()):
            raise ValueError("Count numerators must be nonnegative integers")


def aggregate_samples(descriptor, samples):
    numerator = sum(s.numerator for s in samples)
    denominator = sum(s.denominator for s in samples)
    value = (numerator if descriptor.aggregation == "count" else numerator / denominator) if denominator else None
    return {"value": value, "numerator": numerator, "denominator": denominator,
            **descriptor.model_dump(mode="json")}
