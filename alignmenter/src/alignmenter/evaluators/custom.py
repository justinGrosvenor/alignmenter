"""Explicit, deterministic application evaluators; saved reports need no plugin imports."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib import import_module

from alignmenter.schemas.execution import JsonObject, VersionedRecord
from alignmenter.schemas.metrics import EvaluatorDescriptor, validate_samples
from alignmenter.schemas.scoring import CustomAssessment

BUILTINS = {"rubric", "grounding", "faithfulness"}


class EvaluatorContext(VersionedRecord):
    answer: str
    conversation: list[JsonObject]
    context: JsonObject | None
    config: JsonObject
    sources: dict[str, str]


@dataclass(frozen=True)
class DeterministicEvaluator:
    """The function must make no remote calls; use the shared rubric judge for inference."""

    descriptor: EvaluatorDescriptor
    function: Callable[[EvaluatorContext], CustomAssessment]

    def evaluate(self, payload):
        context = EvaluatorContext.model_validate(payload).model_copy(deep=True)
        raw = self.function(context)
        value = CustomAssessment.model_validate(raw.model_dump() if isinstance(raw, CustomAssessment) else raw)
        validate_samples(value.metrics, self.descriptor.metrics)
        for quote in value.evidence:
            if quote.source_id not in context.sources or quote.quote not in context.sources[quote.source_id]:
                raise ValueError("Custom evaluator cited evidence outside saved sources")
        return value


def evaluator_registry(evaluators: Iterable[DeterministicEvaluator], criteria):
    registry, metrics = {}, {}
    for evaluator in evaluators:
        if not isinstance(evaluator, DeterministicEvaluator):
            raise ValueError("Evaluator factories must return a DeterministicEvaluator")
        descriptor = evaluator.descriptor
        if descriptor.id in BUILTINS or descriptor.id in registry:
            raise ValueError("Evaluator IDs cannot override built-ins or another evaluator")
        for metric in descriptor.metrics:
            if metric.id.startswith(("grounding.", "faithfulness.", "evaluation.")) or metric.id in metrics:
                raise ValueError("Custom metric IDs must be unique and cannot use built-in namespaces")
            metrics[metric.id] = metric
        registry[descriptor.id] = evaluator
    unknown = {c.evaluator for c in criteria} - BUILTINS - set(registry)
    if unknown:
        raise ValueError("Unregistered evaluators: " + ", ".join(sorted(unknown)))
    return registry


def load_evaluators(factories):
    evaluators = []
    for factory in factories:
        module, separator, name = factory.partition(":")
        if not separator or not module or not name.isidentifier():
            raise ValueError("Evaluator factory must be module.path:function_name")
        evaluators.append(getattr(import_module(module), name)())
    return evaluators
