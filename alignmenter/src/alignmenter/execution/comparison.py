"""Matched comparisons of immutable evaluations; no target, judge, or plugin execution."""

from __future__ import annotations

import random
from collections import Counter, defaultdict

from alignmenter.execution.evaluation import evaluation_summary
from alignmenter.schemas.evaluation import EvaluationManifest
from alignmenter.schemas.metrics import MetricDescriptor


def _compatible(baseline, candidate):
    left, right = (EvaluationManifest.model_validate(r["manifest"]) for r in (baseline, candidate))
    if len(left.spec.streams) != 1 or len(right.spec.streams) != 1:
        raise ValueError("Saved comparisons require evaluations selecting one stream each")
    for field in ("judge", "engine_revision", "evaluators", "package_version"):
        if getattr(left, field) != getattr(right, field):
            raise ValueError(f"Incompatible evaluation {field}; rescore both captures with a common configuration")
    if left.spec.model_dump(exclude={"streams"}) != right.spec.model_dump(exclude={"streams"}):
        raise ValueError("Incompatible evaluation specs; rescore both captures with a common spec")


def _index(report):
    results = {r["input_key"]: r for r in report["results"]}
    index = {}
    for item in report["inputs"]:
        if item["case_id"] is None or item["case_revision"] is None or item["split_group"] is None:
            raise ValueError("This evaluation predates stable case identities; rescore with the current engine")
        key = (item["case_id"], item["criterion_id"])
        if key in index:
            raise ValueError("Duplicate case and criterion identity in comparison")
        index[key] = (item, results.get(item["key"]))
    return index


def _sample(result, metric):
    if result is None or result["status"] not in {"met", "violated"}:
        return None
    if metric == "evaluation.met_rate":
        return (int(result["status"] == "met"), 1)
    value = result["metrics"].get(metric)
    return (value["numerator"], value["denominator"]) if value is not None and value["denominator"] else None


def _aggregate(samples, aggregation):
    numerator, denominator = sum(s[0] for s in samples), sum(s[1] for s in samples)
    return numerator if aggregation == "count" else numerator / denominator


def _interval(values, aggregation, *, seed, resamples):
    groups = defaultdict(list)
    for group, baseline, candidate in values:
        groups[group].append((baseline, candidate))
    if len(groups) < 5 or aggregation == "count":
        return None
    rng = random.Random(seed)
    groups = list(groups.values())
    deltas = []
    for _ in range(resamples):
        sample = [pair for _ in groups for pair in rng.choice(groups)]
        deltas.append(_aggregate([p[1] for p in sample], aggregation) - _aggregate([p[0] for p in sample], aggregation))
    deltas.sort()
    return {"low": deltas[int(0.025 * (len(deltas) - 1))], "high": deltas[int(0.975 * (len(deltas) - 1))],
            "confidence": 0.95, "method": "paired_cluster_percentile_bootstrap",
            "clusters": len(groups), "resamples": resamples, "seed": seed,
            "assumption": "Split groups are independent; within-group cases are resampled together."}


def _metrics(pairs, descriptors, owners, *, seed, resamples):
    result = {}
    for descriptor in descriptors:
        values, unavailable, not_applicable = [], 0, 0
        for pair in pairs:
            if descriptor.id != "evaluation.met_rate" and pair["criterion_id"] not in owners[descriptor.id]:
                continue
            left, right = pair["baseline_result"], pair["candidate_result"]
            if left is not None and right is not None and left["status"] == right["status"] == "not_applicable":
                not_applicable += 1
                continue
            a, b = _sample(left, descriptor.id), _sample(right, descriptor.id)
            if a is None or b is None:
                unavailable += 1
            else:
                values.append((pair["split_group"], a, b))
        a = _aggregate([p[1] for p in values], descriptor.aggregation) if values else None
        b = _aggregate([p[2] for p in values], descriptor.aggregation) if values else None
        delta = b - a if values else None
        regression = -delta if delta is not None and descriptor.direction == "higher" else delta if descriptor.direction == "lower" else None
        result[descriptor.id] = {"descriptor": descriptor.model_dump(mode="json"), "baseline": a,
                                 "candidate": b, "delta": delta, "regression": regression,
                                 "paired": len(values), "unavailable": unavailable, "not_applicable": not_applicable,
                                 "interval": _interval(values, descriptor.aggregation, seed=seed, resamples=resamples) if values else None}
    return result


def compare_saved(baseline_dir, candidate_dir, *, baseline_id=None, candidate_id=None, seed=0, resamples=1000):
    if type(seed) is not int or type(resamples) is not int or not 100 <= resamples <= 10000:
        raise ValueError("Bootstrap seed must be an integer and resamples between 100 and 10000")
    baseline = evaluation_summary(baseline_dir, baseline_id, details=True)
    candidate = evaluation_summary(candidate_dir, candidate_id, details=True)
    _compatible(baseline, candidate)
    left, right = _index(baseline), _index(candidate)
    pairs, mismatched = [], []
    for key in sorted(set(left) & set(right)):
        a, ar = left[key]
        b, br = right[key]
        if (a["case_revision"], a["split_group"]) != (b["case_revision"], b["split_group"]):
            mismatched.append({"case_id": key[0], "criterion_id": key[1], "baseline_revision": a["case_revision"], "candidate_revision": b["case_revision"]})
            continue
        pairs.append({"case_id": key[0], "criterion_id": key[1], "case_revision": a["case_revision"],
                      "split_group": a["split_group"], "tags": sorted(set(a["tags"]) | set(b["tags"])),
                      "baseline_input": a, "candidate_input": b, "baseline_result": ar, "candidate_result": br})
    descriptors = [MetricDescriptor(id="evaluation.met_rate", revision="v1", unit="fraction", direction="higher", aggregation="ratio", description="Met / judged applicable criteria")]
    manifest = EvaluationManifest.model_validate(candidate["manifest"])
    descriptors += [m for e in manifest.evaluators for m in e.metrics]
    owners = {m.id: {c.id for c in manifest.spec.criteria if c.evaluator == e.id}
              for e in manifest.evaluators for m in e.metrics}

    def summarize(selected):
        outcomes = Counter((p["baseline_result"]["status"] if p["baseline_result"] else "pending",
                            p["candidate_result"]["status"] if p["candidate_result"] else "pending") for p in selected)
        return {"pairs": len(selected), "transitions": [{"baseline": a, "candidate": b, "count": n} for (a, b), n in sorted(outcomes.items())],
                "metrics": _metrics(selected, descriptors, owners, seed=seed, resamples=resamples)}

    summary = summarize(pairs)
    additions, removals = sorted(set(right) - set(left)), sorted(set(left) - set(right))
    regressions = sum(p["baseline_result"] is not None and p["candidate_result"] is not None
                      and p["baseline_result"]["status"] == "met" and p["candidate_result"]["status"] == "violated" for p in pairs)
    quality = summary["metrics"]["evaluation.met_rate"]
    incomplete = bool(additions or removals or mismatched or not quality["paired"] or quality["unavailable"]
                      or candidate["decision"] == "inconclusive" or baseline["decision"] == "inconclusive")
    decision = "fail" if candidate["decision"] == "fail" or regressions else "inconclusive" if incomplete else "pass"
    return {"schema_version": 1, "kind": "comparison", "decision": decision,
            "baseline_evaluation": baseline["evaluation_id"], "candidate_evaluation": candidate["evaluation_id"],
            "added": [{"case_id": k[0], "criterion_id": k[1]} for k in additions],
            "removed": [{"case_id": k[0], "criterion_id": k[1]} for k in removals], "mismatched": mismatched,
            "regressions": regressions, **summary, "details": pairs,
            "criteria": {c.id: summarize([p for p in pairs if p["criterion_id"] == c.id]) for c in manifest.spec.criteria},
            "tags": {t: summarize([p for p in pairs if t in p["tags"]]) for t in sorted({t for p in pairs for t in p["tags"]})}}
