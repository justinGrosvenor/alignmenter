"""A noninteractive, versioned application evaluation entry point."""

from uuid import UUID

from pydantic import model_validator

from alignmenter.schemas.evaluation import EvaluationSpec, JudgeBudget
from alignmenter.schemas.execution import NonNegativeInt, VersionedRecord
from alignmenter.schemas.gates import GatePolicy
from alignmenter.schemas.metrics import Name


class SuiteSpec(VersionedRecord):
    id: Name
    revision: Name
    dataset: Name
    persona: Name | None = None
    target_factory: Name | None = None
    max_target_calls: NonNegativeInt | None = None
    judge_factory: Name | None = None
    judge_budget: JudgeBudget | None = None
    evaluator_factories: tuple[Name, ...] = ()
    evaluation: EvaluationSpec
    policy: GatePolicy = GatePolicy()
    baseline: Name | None = None
    baseline_evaluation_id: UUID | None = None

    @model_validator(mode="after")
    def explicit_resources(self):
        if self.target_factory is not None and self.max_target_calls is None:
            raise ValueError("Generated suites require an explicit max_target_calls budget")
        if any(c.evaluator in {"rubric", "faithfulness"} for c in self.evaluation.criteria):
            if self.judge_factory is None or self.judge_budget is None:
                raise ValueError("Judged suites require a judge_factory and explicit judge_budget")
        if self.policy.regressions and self.baseline is None:
            raise ValueError("Regression policy requires a baseline")
        if self.baseline_evaluation_id is not None and self.baseline is None:
            raise ValueError("A baseline evaluation ID requires a baseline run")
        if self.evaluation.streams != ("primary",):
            raise ValueError("Suites capture one primary stream; use separate suites for target variants")
        return self
