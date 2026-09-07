"""One saved-result gate decision for the CLI and every report format."""

from alignmenter.schemas.gates import GatePolicy

SYSTEM_METRICS = {"evaluation.coverage", "evaluation.met_rate"}


def validate_policy(policy, spec, descriptors):
    known = SYSTEM_METRICS | {m.id for e in descriptors for m in e.metrics}
    criteria = {c.id for c in spec.criteria}
    directions = {m.id: m.direction for e in descriptors for m in e.metrics}
    for gate in (*policy.gates, *policy.regressions):
        if gate.metric not in known:
            raise ValueError(f"Unknown gate metric: {gate.metric}")
        if getattr(gate, "criterion", None) is not None and gate.criterion not in criteria:
            raise ValueError(f"Unknown gate criterion: {gate.criterion}")
        if getattr(gate, "criterion", None) is not None and getattr(gate, "tag", None) is not None:
            raise ValueError("A metric gate selects a criterion or a tag, not both")
    for gate in policy.regressions:
        if gate.metric == "evaluation.coverage" or directions.get(gate.metric) == "neutral":
            raise ValueError("Regression gates require a directional quality metric")


def _value(report, metric):
    if metric == "evaluation.coverage":
        return {"value": report["coverage"], "denominator": report["applicable"]}
    if metric == "evaluation.met_rate":
        return {"value": report["met_rate"], "denominator": report["judged"]}
    return report["metrics"].get(metric, {"value": None, "denominator": 0})


def gate_report(report, policy: GatePolicy | None = None, *, comparison=None):
    from alignmenter.schemas.evaluation import EvaluationManifest

    policy = policy or GatePolicy()
    manifest = EvaluationManifest.model_validate(report["manifest"])
    validate_policy(policy, manifest.spec, manifest.evaluators)
    checks = [{"id": "evaluation", "decision": report["decision"],
               "reason": "All required outcomes and coverage, including the spec's qualification."}]
    for gate in policy.gates:
        selected = report
        if gate.criterion is not None:
            selected = report["criteria"][gate.criterion]
        if gate.tag is not None:
            if gate.criterion is not None:
                raise ValueError("Combined criterion/tag gates are not supported; define a criterion or tag gate")
            if gate.tag not in report["tags"]:
                raise ValueError(f"Unknown gate tag: {gate.tag}")
            selected = report["tags"][gate.tag]
        metric = _value(selected, gate.metric)
        value = metric["value"]
        decision = "inconclusive"
        if value is not None and metric["denominator"] >= gate.min_denominator:
            met = value >= gate.threshold if gate.operator == "at_least" else value <= gate.threshold
            decision = "pass" if met else "fail"
        checks.append({**gate.model_dump(mode="json"), **metric, "decision": decision})
    if policy.regressions and comparison is None:
        raise ValueError("Regression gates require a saved baseline comparison")
    if comparison is not None:
        checks.append({"id": "comparison", "decision": comparison["decision"],
                       "reason": "Matched cases, common evaluator configuration, and paired coverage."})
    for gate in policy.regressions:
        metric = comparison["metrics"].get(gate.metric)
        if metric is None:
            raise ValueError(f"Metric is unavailable in the comparison: {gate.metric}")
        regression = metric["regression"]
        decision = "inconclusive" if regression is None or metric["unavailable"] else "pass" if regression <= gate.max_regression else "fail"
        checks.append({**gate.model_dump(mode="json"), "value": regression, "decision": decision})
    decisions = {c["decision"] for c in checks}
    decision = "fail" if "fail" in decisions else "inconclusive" if "inconclusive" in decisions else "pass"
    return {"schema_version": 1, "policy": policy.model_dump(mode="json"), "decision": decision, "checks": checks}
