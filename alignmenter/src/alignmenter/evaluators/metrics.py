"""Pure metric aggregation over persisted assessments, including explicit denominators."""

from alignmenter.schemas.execution import content_digest
from alignmenter.schemas.metrics import (
    EvaluatorDescriptor,
    MetricDescriptor,
    MetricSample,
    aggregate_samples,
)

BUILTIN_METRICS = {
    "grounding.quantity_traceability": ("ratio", "fraction", "higher", "Matched quantities / recognized quantities"),
    "grounding.question_quantities": ("count", "quantities", "neutral", "Quantities traceable to the user question"),
    "grounding.ambiguous_quantities": ("count", "quantities", "lower", "Recognized quantities needing interpretation"),
    "grounding.citation_resolution": ("ratio", "fraction", "higher", "Resolved / numbered citations"),
    "faithfulness.claim_support": ("ratio", "fraction", "higher", "Supported / extracted claims"),
    "faithfulness.correctness": ("mean", "score_0_10", "higher", "Practical correctness over applicable answers"),
    "faithfulness.answers_question": ("ratio", "fraction", "higher", "Answers addressing the question / applicable answers"),
    "faithfulness.dangerous_answers": ("count", "answers", "lower", "Dangerous answers among valid assessments"),
    "faithfulness.appropriate_abstentions": ("ratio", "fraction", "higher", "Appropriate abstentions / abstentions"),
}


def builtin_descriptor(evaluator):
    metrics = tuple(MetricDescriptor(id=name, revision="v1", aggregation=values[0], unit=values[1],
                                      direction=values[2], description=values[3])
                    for name, values in BUILTIN_METRICS.items() if name.startswith(evaluator + "."))
    return EvaluatorDescriptor(id=evaluator, revision="v1", metrics=metrics,
                               configuration_digest=content_digest({"evaluator": evaluator, "revision": "v1",
                                                                   "metrics": [m.model_dump(mode="json") for m in metrics]}))


def result_metrics(item, result):
    if result.assessment is not None and result.assessment.kind == "custom":
        return result.assessment.metrics
    return {name: MetricSample(numerator=m["numerator"], denominator=m["denominator"])
            for name, m in saved_metrics([item], {item.key: result}).items()}


def registered_metrics(inputs, results, descriptors):
    selected = {i.evaluator for i in inputs}
    return {metric.id: aggregate_samples(metric, [results[i.key].metrics[metric.id]
                                                  for i in inputs if i.key in results and metric.id in results[i.key].metrics])
            for evaluator in descriptors if evaluator.id in selected for metric in evaluator.metrics}


def _metric(numerator, denominator, *, aggregation="ratio", unit="fraction", direction="higher"):
    return {"value": (numerator / denominator if aggregation != "count" else numerator) if denominator else None,
            "numerator": numerator, "denominator": denominator, "aggregation": aggregation,
            "unit": unit, "direction": direction}


def saved_metrics(inputs, results):
    assessments = [results[i.key].assessment for i in inputs
                   if i.key in results and results[i.key].assessment is not None]
    metrics = {}
    if any(i.evaluator == "grounding" for i in inputs):
        grounding = [a for a in assessments if a.kind == "grounding"]
        quantities = [q for a in grounding for q in a.quantities]
        citations = [c for a in grounding for c in a.citations]
        metrics["grounding.quantity_traceability"] = _metric(sum(q.status in {"source", "question"} for q in quantities), len(quantities))
        metrics["grounding.question_quantities"] = _metric(sum(q.status == "question" for q in quantities), len(grounding), aggregation="count", unit="quantities", direction="neutral")
        metrics["grounding.ambiguous_quantities"] = _metric(sum(q.status == "ambiguous" for q in quantities), len(grounding), aggregation="count", unit="quantities", direction="lower")
        metrics["grounding.citation_resolution"] = _metric(sum(c.source_id is not None for c in citations), len(citations))
    if any(i.evaluator == "faithfulness" for i in inputs):
        faithfulness = [a for a in assessments if a.kind == "faithfulness"]
        verdicts = [a.verdict for a in faithfulness]
        claims = [c for v in verdicts for c in v.claims]
        applicable = [a.verdict for a in faithfulness if a.outcome != "not_applicable"]
        abstentions = [v for v in verdicts if v.abstained]
        metrics["faithfulness.claim_support"] = _metric(sum(c.status == "supported" for c in claims), len(claims))
        metrics["faithfulness.correctness"] = _metric(sum(v.correctness for v in applicable), len(applicable), aggregation="mean", unit="score_0_10")
        metrics["faithfulness.answers_question"] = _metric(sum(v.answers_question for v in applicable), len(applicable))
        metrics["faithfulness.dangerous_answers"] = _metric(sum(v.dangerous for v in verdicts), len(verdicts), aggregation="count", unit="answers", direction="lower")
        metrics["faithfulness.appropriate_abstentions"] = _metric(sum(v.abstention_appropriate for v in abstentions), len(abstentions))
    return metrics
