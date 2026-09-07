"""An executable resource-constraint fixture, not an AI quality benchmark."""

import json
import os

from alignmenter.evaluators.custom import DeterministicEvaluator
from alignmenter.providers.base import ChatResponse
from alignmenter.providers.callable import CallableProvider, CaptureTarget
from alignmenter.schemas.execution import RecoveryContract, content_digest
from alignmenter.schemas.metrics import EvaluatorDescriptor, MetricDescriptor, MetricSample
from alignmenter.schemas.scoring import CustomAssessment, SourceQuote


def make_target():
    variant = os.environ.get("ALIGNMENTER_DEMO_VARIANT", "good")
    if variant not in {"good", "bad"}:
        raise ValueError("Demo variant must be good or bad")

    def target(messages, *, request_id):
        question = json.loads(next(m["content"] for m in reversed(messages) if m["role"] == "user"))
        needed = question["available"][:1] if variant == "good" else ["unavailable-equipment"]
        return ChatResponse(text=json.dumps({"action": "prepare", "needed": needed}), context={"available": question["available"]})

    return CaptureTarget("example:resource-task", CallableProvider(target, RecoveryContract(
        configuration_digest=content_digest({"example": "resource-task-v1", "variant": variant}),
        session_state="stateless", interrupted_request="idempotent", max_attempts=2)))


def make_evaluator():
    def assess(context):
        question = json.loads(next(m["content"] for m in reversed(context.conversation) if m["role"] == "user"))
        answer = json.loads(context.answer)
        if not isinstance(answer, dict) or set(answer) != {"action", "needed"} or not isinstance(answer["needed"], list) or not all(isinstance(v, str) for v in answer["needed"]):
            raise ValueError("Expected action and a list of needed resources")
        met = answer["action"] == "prepare" and bool(answer["needed"]) and set(answer["needed"]) <= set(question["available"])
        return CustomAssessment(outcome="met" if met else "violated", rationale="The action must prepare using available resources.",
                                evidence=[SourceQuote(source_id="answer", quote=context.answer)],
                                metrics={"resource_task.success": MetricSample(numerator=int(met), denominator=1)})

    return DeterministicEvaluator(EvaluatorDescriptor(id="resource_task", revision="v1",
        configuration_digest=content_digest({"example": "resource-task-evaluator-v1"}),
        metrics=(MetricDescriptor(id="resource_task.success", revision="v1", unit="fraction", direction="higher",
                                  aggregation="ratio", description="Preparation actions using only available resources"),)), assess)


def example_files():
    records = [r for name, available in (("water", ["water", "pot"]), ("shelter", ["tarp", "rope"])) for r in (
        {"session_id": name, "role": "user", "text": json.dumps({"available": available, "task": "prepare"})},
        {"session_id": name, "case_id": name, "role": "assistant", "text": json.dumps({"action": "prepare", "needed": available[:1]}), "tags": ["resource-constraints"]},
    )]
    suite = {"id": "resource-task", "revision": "v1", "dataset": "dataset.jsonl",
             "target_factory": "alignmenter.examples.resource_task:make_target", "max_target_calls": 2,
             "evaluator_factories": ["alignmenter.examples.resource_task:make_evaluator"],
             "evaluation": {"id": "resource-constraints", "revision": "v1", "qualification": "reviewed",
                            "criteria": [{"id": "uses_available_resources", "revision": "v1", "evaluator": "resource_task"}]},
             "policy": {"id": "resource-release", "revision": "v1", "gates": [
                 {"id": "resource_success", "metric": "resource_task.success", "operator": "at_least", "threshold": 1}]}}
    return records, suite
