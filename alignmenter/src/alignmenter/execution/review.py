"""Human review exchange, qualification, and regression lineage over frozen evidence."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from alignmenter.execution.leases import coordinator_lease
from alignmenter.schemas.execution import content_digest
from alignmenter.schemas.review import Annotation, ReviewTask
from alignmenter.storage.reviews import ReviewStore, active_annotations


def review_tasks(run_dir, evaluation_id=None):
    store = ReviewStore(run_dir)
    manifest, inputs, results, _, _ = store.snapshot(evaluation_id)
    results = {r.input_key: r for r in results}
    criteria = {c.id: c for c in manifest.spec.criteria}
    return [ReviewTask(review_key=content_digest({"run_id": str(manifest.run_id), "stream": item.stream,
                                                  "ordinal": item.ordinal, "observation": item.observation_digest,
                                                  "sources": item.sources, "data": item.data.model_dump(mode="json") if item.data else None,
                                                  "payload": item.payload, "criterion": criteria[item.criterion_id].model_dump(mode="json")}),
                       evaluation_id=manifest.id, input=item, input_digest=content_digest(item.model_dump(mode="json")),
                       criterion=criteria[item.criterion_id], machine_result=results.get(item.key)) for item in inputs]


def export_review(run_dir, path, *, evaluation_id=None, force=False):
    path = Path(path)
    tasks = review_tasks(run_dir, evaluation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w" if force else "x", encoding="utf-8") as handle:
        for task in tasks:
            handle.write(task.model_dump_json() + "\n")
    return len(tasks)


def import_review(run_dir, path):
    tasks = [ReviewTask.model_validate_json(line) for line in Path(path).read_text().splitlines() if line.strip()]
    store = ReviewStore(run_dir)
    annotations = []
    with coordinator_lease(store.run_dir):
        snapshots = {}
        for task in tasks:
            if task.annotation.outcome is None:
                continue
            if task.evaluation_id not in snapshots:
                snapshots[task.evaluation_id] = {t.review_key: t for t in review_tasks(run_dir, task.evaluation_id)}
            expected = snapshots[task.evaluation_id].get(task.review_key)
            if expected is None or expected.model_dump(exclude={"annotation"}) != task.model_dump(exclude={"annotation"}):
                raise ValueError("Review evidence or evaluator snapshot differs from the saved task")
            if task.input.observation_id is None:
                raise ValueError("A missing captured answer cannot receive an answer-quality label")
            if task.annotation.outcome == "not_applicable" and not task.criterion.allow_not_applicable:
                raise ValueError("The reviewed criterion does not permit not_applicable")
            annotations.append(Annotation(**task.annotation.model_dump(exclude={"schema_version"}),
                                           review_key=task.review_key, evaluation_id=task.evaluation_id,
                                           input_key=task.input.key, input_digest=task.input_digest,
                                           case_id=task.input.case_id or task.input.session_id, criterion_id=task.criterion.id))
        if annotations:
            store.append_annotations(annotations)
    return len(annotations)


def qualification_report(run_dir, evaluation_id=None):
    tasks = review_tasks(run_dir, evaluation_id)
    annotations = active_annotations(ReviewStore(run_dir).annotations())
    references = {a.review_key: a for a in annotations if a.role == "adjudication" and a.provenance == "human"}
    opinions = [a for a in annotations if a.role == "opinion"]
    rows = []
    current_keys = {t.review_key for t in tasks}
    identities = {(t.input.case_id or t.input.session_id, t.criterion.id) for t in tasks}
    stale = [a for a in references.values() if a.review_key not in current_keys and (a.case_id, a.criterion_id) in identities]
    for task in tasks:
        label = references.get(task.review_key)
        votes = {a.outcome for a in opinions if a.review_key == task.review_key}
        if label is None:
            state = "conflicting_opinions" if len(votes) > 1 else "awaiting_adjudication" if votes else "unreviewed"
        else:
            state = "adjudicated"
        predicted = task.machine_result.status if task.machine_result is not None else "pending"
        rows.append({"review_key": task.review_key, "input_key": task.input.key, "case_id": task.input.case_id,
                     "criterion_id": task.criterion.id, "tags": list(task.input.tags), "review_state": state,
                     "reference": label.outcome if label else None, "predicted": predicted,
                     "annotation_id": str(label.id) if label else None})

    def summarize(selected):
        labeled = [r for r in selected if r["reference"] is not None]
        measured = [r for r in labeled if r["predicted"] in {"met", "violated", "not_applicable"}]
        agreement = sum(r["predicted"] == r["reference"] for r in measured)
        false_passes = sum(r["predicted"] == "met" and r["reference"] == "violated" for r in measured)
        false_failures = sum(r["predicted"] == "violated" and r["reference"] == "met" for r in measured)
        disagreement = len(measured) - agreement
        decision = "fail" if disagreement else "pass" if labeled and len(measured) == len(labeled) == len(selected) else "inconclusive"
        return {"planned": len(selected), "references": len(labeled), "evaluated_references": len(measured),
                "reference_coverage": len(labeled) / len(selected) if selected else None,
                "evaluation_coverage": len(measured) / len(labeled) if labeled else None,
                "agreement": agreement / len(measured) if measured else None, "agreements": agreement,
                "false_passes": false_passes, "false_failures": false_failures,
                "disagreements": disagreement, "decision": decision,
                "review_states": dict(Counter(r["review_state"] for r in selected))}

    return {"schema_version": 1, "kind": "qualification", **summarize(rows), "selection": "review_queue",
            "interpretation": "Agreement on supplied human adjudications; not a population quality estimate or independent verification of reviewer provenance.",
            "stale_references": len(stale), "details": rows,
            "criteria": {c: summarize([r for r in rows if r["criterion_id"] == c]) for c in sorted({r["criterion_id"] for r in rows})},
            "tags": {t: summarize([r for r in rows if t in r["tags"]]) for t in sorted({t for r in rows for t in r["tags"]})}}


def promote_regression(run_dir, annotation_id, out_dir):
    from alignmenter.reporting.durable import write_artifacts

    store = ReviewStore(run_dir)
    annotation = next((a for a in active_annotations(store.annotations()) if a.id == annotation_id), None)
    if annotation is None or annotation.role != "adjudication" or annotation.provenance != "human":
        raise ValueError("Promotion requires an active human adjudication")
    task = next((t for t in review_tasks(run_dir, annotation.evaluation_id) if t.review_key == annotation.review_key), None)
    if task is None or content_digest(task.input.model_dump(mode="json")) != annotation.input_digest:
        raise ValueError("Annotation evidence is stale or unavailable")
    records = store.committed_records(task.input.stream)
    dataset = []
    for turn in store.plan(task.input.stream):
        if turn.session_id == task.input.session_id and turn.ordinal <= task.input.ordinal:
            if turn.ordinal not in records:
                raise ValueError("Cannot promote an incomplete captured conversation")
            record = dict(records[turn.ordinal])
            record["metadata"] = {**record.get("metadata", {}), "split_group": task.input.split_group}
            if turn.ordinal == task.input.ordinal:
                record["case_id"] = task.input.case_id
            dataset.append(record)
    expectation = {"schema_version": 1, "case_id": task.input.case_id, "case_revision": task.input.case_revision,
                   "split_group": task.input.split_group, "expected_outcome": annotation.outcome,
                   "criterion": task.criterion.model_dump(mode="json"), "annotation": annotation.model_dump(mode="json"),
                   "source_run": str(store.manifest().id), "source_evaluation": str(task.evaluation_id),
                   "source_input_key": task.input.key, "dataset_digest": content_digest(dataset)}
    write_artifacts(out_dir, {"dataset.jsonl": "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in dataset),
                              "expectations.jsonl": json.dumps(expectation, ensure_ascii=False) + "\n",
                              "README.md": "# Promoted regression\n\nThe captured answer is preserved for recorded replay. Generate a new answer to evaluate a candidate. Human expectations are in a separate sidecar and are never target messages. Keep this case and its source/variants in the same split group.\n"})
    return expectation
