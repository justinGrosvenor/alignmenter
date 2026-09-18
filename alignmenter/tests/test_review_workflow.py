"""Reviewers can annotate and adjudicate without rewriting machine evidence."""

import json
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from alignmenter.cli import app
from alignmenter.execution.evaluation import evaluate_saved, evaluation_summary
from alignmenter.execution.review import (
    export_review,
    import_review,
    promote_regression,
    qualification_report,
)
from alignmenter.schemas.evaluation import Criterion, EvaluationSpec, JudgeBudget
from alignmenter.storage.evaluations import EvaluationStore
from alignmenter.storage.reviews import ReviewStore

from .test_durable_evaluations import Judge, captured, spec
from .test_release_workflow import evaluated, plugin


def annotated_file(run, path, *, outcome="met", role="adjudication", provenance="human", reviewer="Fixture reviewer"):
    export_review(run, path)
    values = [json.loads(line) for line in path.read_text().splitlines()]
    for row in values:
        row["annotation"].update(outcome=outcome, reviewer=reviewer, role=role,
                                  rationale="Unit test reference; not an actual product qualification.", provenance=provenance)
    path.write_text("".join(json.dumps(row) + "\n" for row in values))
    return values


def test_review_is_append_only_and_machine_failures_remain_failures(tmp_path):
    run = evaluated(tmp_path / "run", ("bad",))
    before = evaluation_summary(run, details=True)
    rows = annotated_file(run, tmp_path / "review.jsonl", outcome="met")
    assert import_review(run, tmp_path / "review.jsonl") == 1
    assert evaluation_summary(run, details=True) == before
    report = qualification_report(run)
    assert report["false_failures"] == 1 and report["decision"] == "fail"
    assert report["reference_coverage"] == 1
    saved = ReviewStore(run).path.read_bytes()
    import_review(run, tmp_path / "review.jsonl")
    assert ReviewStore(run).path.read_bytes() == saved
    rows[0]["annotation"]["outcome"] = "violated"
    (tmp_path / "review.jsonl").write_text(json.dumps(rows[0]) + "\n")
    with pytest.raises(ValueError, match="overwrite"):
        import_review(run, tmp_path / "review.jsonl")
    assert ReviewStore(run).path.read_bytes() == saved


def test_correction_requires_a_new_annotation_with_explicit_lineage(tmp_path):
    run = evaluated(tmp_path / "run", ("good",))
    rows = annotated_file(run, tmp_path / "review.jsonl", outcome="violated")
    import_review(run, tmp_path / "review.jsonl")
    assert qualification_report(run)["false_passes"] == 1
    previous = rows[0]["annotation"]["id"]
    rows[0]["annotation"].update(id=str(uuid4()), outcome="met")
    path = tmp_path / "correction.jsonl"
    path.write_text(json.dumps(rows[0]) + "\n")
    with pytest.raises(ValueError, match="supersedes"):
        import_review(run, path)
    rows[0]["annotation"]["supersedes"] = previous
    path.write_text(json.dumps(rows[0]) + "\n")
    import_review(run, path)
    assert len(ReviewStore(run).annotations()) == 2 and qualification_report(run)["decision"] == "pass"


def test_import_batch_rolls_back_when_evidence_was_edited(tmp_path):
    run = evaluated(tmp_path / "run")
    rows = annotated_file(run, tmp_path / "review.jsonl")
    rows[1]["input"]["sources"]["answer"] = "fabricated evidence"
    (tmp_path / "review.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    before = ReviewStore(run).path.read_bytes()
    with pytest.raises(ValueError, match="snapshot"):
        import_review(run, tmp_path / "review.jsonl")
    assert ReviewStore(run).path.read_bytes() == before and ReviewStore(run).annotations() == []


@pytest.mark.parametrize("role,provenance", [("opinion", "human"), ("adjudication", "model"), ("adjudication", "synthetic")])
def test_opinions_and_machine_labels_do_not_become_qualified_references(tmp_path, role, provenance):
    run = evaluated(tmp_path / "run", ("good",))
    annotated_file(run, tmp_path / "review.jsonl", role=role, provenance=provenance)
    import_review(run, tmp_path / "review.jsonl")
    report = qualification_report(run)
    assert report["references"] == 0 and report["agreement"] is None and report["decision"] == "inconclusive"
    with pytest.raises(ValueError, match="human adjudication"):
        promote_regression(run, ReviewStore(run).annotations()[0].id, tmp_path / "promoted")


def test_conflicting_opinions_and_unreviewed_cases_remain_visible(tmp_path):
    run = evaluated(tmp_path / "run")
    annotated_file(run, tmp_path / "one.jsonl", reviewer="First", role="opinion", outcome="met")
    annotated_file(run, tmp_path / "two.jsonl", reviewer="Second", role="opinion", outcome="violated")
    import_review(run, tmp_path / "one.jsonl")
    import_review(run, tmp_path / "two.jsonl")
    assert qualification_report(run)["review_states"] == {"conflicting_opinions": 2}
    rows = annotated_file(run, tmp_path / "final.jsonl")
    rows[1]["annotation"]["outcome"] = None
    (tmp_path / "final.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    import_review(run, tmp_path / "final.jsonl")
    report = qualification_report(run)
    assert report["references"] == 1 and report["decision"] == "inconclusive"


def test_rubric_change_marks_old_reference_stale(tmp_path):
    run = evaluated(tmp_path / "run", ("good",))
    annotated_file(run, tmp_path / "review.jsonl")
    import_review(run, tmp_path / "review.jsonl")
    new_spec = EvaluationSpec(id="task", revision="v2", qualification="reviewed",
                              criteria=(Criterion(id="task", revision="v2", evaluator="fixture"),))
    evaluate_saved(run, new_spec, evaluators=(plugin(),), new_evaluation=True)
    report = qualification_report(run)
    assert report["references"] == 0 and report["stale_references"] == 1 and report["decision"] == "inconclusive"


def test_repeated_judgments_reuse_references_without_pooling_evaluator_results(tmp_path):
    run = captured(tmp_path)
    judge = Judge()
    evaluate_saved(run, spec(), judge, budget=JudgeBudget(max_calls=4))
    annotated_file(run, tmp_path / "review.jsonl")
    import_review(run, tmp_path / "review.jsonl")
    evaluate_saved(run, spec(sample=1), judge, new_evaluation=True)
    report = qualification_report(run)
    assert report["references"] == 2 and report["decision"] == "pass" and len(judge.calls) == 4


def test_cli_review_promote_and_recorded_rerun_preserve_lineage(tmp_path):
    run = evaluated(tmp_path / "run", ("bad",))
    path = tmp_path / "review.jsonl"
    cli = CliRunner()
    assert cli.invoke(app, ["review-export", str(run), "--out", str(path)]).exit_code == 0
    row = json.loads(path.read_text())
    row["annotation"].update(reviewer="Fixture owner", outcome="violated", role="adjudication", provenance="human",
                              rationale="Simulated human input for this software regression test.")
    path.write_text(json.dumps(row) + "\n")
    assert cli.invoke(app, ["review-import", str(run), "--annotations", str(path)]).exit_code == 0
    result = cli.invoke(app, ["qualify", str(run)])
    assert result.exit_code == 0, result.output
    promoted = tmp_path / "promoted"
    result = cli.invoke(app, ["promote", str(run), "--annotation-id", row["annotation"]["id"], "--out", str(promoted)])
    assert result.exit_code == 0, result.output
    expectation = json.loads((promoted / "expectations.jsonl").read_text())
    dataset = [json.loads(line) for line in (promoted / "dataset.jsonl").read_text().splitlines()]
    assert expectation["expected_outcome"] == "violated" and expectation["split_group"] == "case-0"
    assert all("expected_outcome" not in r and "annotation" not in r for r in dataset)
    result = cli.invoke(app, ["capture", "--dataset", str(promoted / "dataset.jsonl"), "--out", str(tmp_path / "rerun")])
    assert result.exit_code == 0, result.output
    runs = list((tmp_path / "rerun").iterdir())
    assert len(runs) == 1 and len(EvaluationStore(runs[0]).observations()) == 1


# --- Opt-in per-run human-sign-off enforcement (GatePolicy.require_human_review) ---

def _gate(run, out, *, require_human_review):
    from alignmenter.reporting.durable import export_evaluation
    from alignmenter.schemas.gates import GatePolicy
    report = export_evaluation(run, out, policy=GatePolicy(require_human_review=require_human_review), force=True)
    return report["gate_report"]


def _human_review_check(gate_report):
    return next((c for c in gate_report["checks"] if c["id"] == "human-review"), None)


def test_require_human_review_without_adjudications_is_inconclusive(tmp_path):
    run = evaluated(tmp_path / "run", ("good", "good"))  # clean machine pass, no sign-off
    gated = _gate(run, tmp_path / "a", require_human_review=True)
    assert gated["decision"] == "inconclusive"
    check = _human_review_check(gated)
    assert check is not None and check["decision"] == "inconclusive" and check["references"] == 0
    # The flag is opt-in: without it, the trusted-evaluator reviewed pass is unchanged.
    assert _gate(run, tmp_path / "b", require_human_review=False)["decision"] == "pass"
    assert _human_review_check(_gate(run, tmp_path / "c", require_human_review=False)) is None


def test_require_human_review_with_full_signoff_passes(tmp_path):
    run = evaluated(tmp_path / "run", ("good", "good"))
    annotated_file(run, tmp_path / "adj.jsonl", outcome="met")  # human adjudicates every case, agrees
    import_review(run, tmp_path / "adj.jsonl")
    gated = _gate(run, tmp_path / "out", require_human_review=True)
    assert gated["decision"] == "pass"
    assert _human_review_check(gated)["decision"] == "pass"


def test_require_human_review_partial_signoff_is_inconclusive(tmp_path):
    run = evaluated(tmp_path / "run", ("good", "good"))
    export_review(run, tmp_path / "adj.jsonl")
    rows = [json.loads(line) for line in (tmp_path / "adj.jsonl").read_text().splitlines()]
    rows[0]["annotation"].update(outcome="met", reviewer="R", role="adjudication",
                                 rationale="Unit test reference.", provenance="human")  # only 1 of 2 cases
    (tmp_path / "adj.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    import_review(run, tmp_path / "adj.jsonl")
    assert _gate(run, tmp_path / "out", require_human_review=True)["decision"] == "inconclusive"


def test_require_human_review_disagreement_fails(tmp_path):
    run = evaluated(tmp_path / "run", ("good", "good"))  # machine: both met
    annotated_file(run, tmp_path / "adj.jsonl", outcome="violated")  # human disagrees
    import_review(run, tmp_path / "adj.jsonl")
    assert _gate(run, tmp_path / "out", require_human_review=True)["decision"] == "fail"
