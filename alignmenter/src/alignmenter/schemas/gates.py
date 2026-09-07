"""Versioned release policies with explicit populations and metric names."""

from typing import Literal

from pydantic import Field, model_validator

from alignmenter.schemas.execution import VersionedRecord
from alignmenter.schemas.metrics import FiniteNumber, Name


class MetricGate(VersionedRecord):
    id: Name
    metric: Name
    operator: Literal["at_least", "at_most"]
    threshold: FiniteNumber
    criterion: Name | None = None
    tag: Name | None = None
    min_denominator: int = Field(default=1, strict=True, ge=1)


class RegressionGate(VersionedRecord):
    id: Name
    metric: Name = "evaluation.met_rate"
    max_regression: FiniteNumber = Field(default=0, ge=0)


class GatePolicy(VersionedRecord):
    id: Name = "complete-reviewed-evaluation"
    revision: Name = "v1"
    gates: tuple[MetricGate, ...] = ()
    regressions: tuple[RegressionGate, ...] = ()

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [g.id for g in (*self.gates, *self.regressions)]
        if len(ids) != len(set(ids)):
            raise ValueError("Gate IDs must be unique")
        return self
