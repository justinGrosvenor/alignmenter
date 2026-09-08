"""Application-owned checks, saved comparisons, and consistent offline/CI decisions."""

import json
from xml.etree import ElementTree as ET

import pytest
from typer.testing import CliRunner

from alignmenter.cli import app
from alignmenter.evaluators.custom import DeterministicEvaluator
from alignmenter.execution.comparison import compare_saved
from alignmenter.execution.evaluation import evaluate_saved, evaluation_summary
from alignmenter.execution.gates import gate_report
from alignmenter.reporting.durable import export_evaluation
from alignmenter.schemas.evaluation import (
    Criterion,
    EvaluationManifest,
    EvaluationResult,
    EvaluationSpec,
)
from alignmenter.schemas.execution import content_digest
from alignmenter.schemas.gates import GatePolicy, MetricGate, RegressionGate
from alignmenter.schemas.metrics import EvaluatorDescriptor, MetricDescriptor, MetricSample
from alignmenter.schemas.scoring import CustomAssessment, SourceQuote
from alignmenter.storage.evaluations import EvaluationStore

from .test_durable_evaluations import captured


def plugin(function=None, *, revision="v1"):
    def assess(context):
        met = "bad" not in context.answer
        return CustomAssessment(outcome="met" if met else "violated", rationale="Deterministic fixture rule.",
                                evidence=[SourceQuote(source_id="answer", quote=context.answer)],
                                metrics={"task.success": MetricSample(numerator=int(met), denominator=1)})
    return DeterministicEvaluator(EvaluatorDescriptor(
        id="fixture", revision=revision, configuration_digest=content_digest({"revision": revision}),
        metrics=(MetricDescriptor(id="task.success", revision="v1", unit="fraction", direction="higher",
                                  aggregation="ratio", description="Fixture task success"),)), function or assess)


def task_spec(*, qualification="reviewed"):
    return EvaluationSpec(id="task", revision="v1", qualification=qualification,
                          criteria=(Criterion(id="task", revision="v1", evaluator="fixture"),))


def evaluated(path, answers=("good", "good"), *, question="Question", evaluator=None, qualification="reviewed", groups=None):
    path.mkdir(parents=True)
    records = [r for i, answer in enumerate(answers) for r in (
        {"session_id": f"case-{i}", "role": "user", "text": question},
        {"session_id": f"case-{i}", "case_id": f"case-{i}", "role": "assistant", "text": answer,
         "tags": ["fixture"], "metadata": {"split_group": groups[i] if groups else f"case-{i}"}},
    )]
    run = captured(path, records=records)
    evaluate_saved(run, task_spec(qualification=qualification), evaluators=(evaluator or plugin(),))
    return run


def test_application_metric_is_saved_and_reported_without_plugin_execution(tmp_path):
    calls = []
    original = plugin()

    def assess(context):
        calls.append(context)
        return original.function(context)

    run = evaluated(tmp_path / "run", evaluator=plugin(assess))
    report = evaluation_summary(run, details=True)
    assert report["metrics"]["task.success"]["value"] == 1 and len(calls) == 2
    assert report["budget"]["reserved_calls"] == 0
    assert report["tags"]["fixture"]["metrics"]["task.success"]["denominator"] == 2
    saved = EvaluationStore(run).path.read_bytes()
    export_evaluation(run, tmp_path / "review")
    assert len(calls) == 2 and EvaluationStore(run).path.read_bytes() == saved
    assert "task.success" in (tmp_path / "review/index.html").read_text()


def test_unregistered_evaluator_rejected_before_any_saved_evaluation(tmp_path):
    run = captured(tmp_path)
    before = EvaluationStore(run).path.read_bytes()
    with pytest.raises(ValueError, match="Unregistered"):
        evaluate_saved(run, task_spec())
    assert EvaluationStore(run).path.read_bytes() == before


def test_saved_custom_contract_cannot_drop_descriptors_or_change_metric_evidence(tmp_path):
    run = evaluated(tmp_path / "run")
    report = evaluation_summary(run, details=True)
    manifest = {**report["manifest"], "evaluators": []}
    with pytest.raises(ValueError, match="frozen descriptor"):
        EvaluationManifest.model_validate(manifest)
    assessment = CustomAssessment(outcome="met", rationale="Fixture rule", evidence=[],
                                  metrics={"task.success": MetricSample(numerator=1, denominator=1)})
    with pytest.raises(ValueError, match="Saved metrics"):
        EvaluationResult(evaluation_id=report["evaluation_id"], input_key=content_digest("fixture"),
                         status="met", assessment=assessment,
                         metrics={"task.success": MetricSample(numerator=0, denominator=1)})


@pytest.mark.parametrize("failure", ["exception", "extra_metric", "missing_metric", "bad_ratio", "bad_quote"])
def test_invalid_application_check_preserves_unavailable_work(tmp_path, failure):
    def assess(context):
        if failure == "exception":
            raise RuntimeError("secret provider diagnostic must not be exported")
        value = plugin().function(context).model_dump()
        if failure == "extra_metric":
            value["metrics"]["unknown"] = {"numerator": 1, "denominator": 1}
        elif failure == "missing_metric":
            value["metrics"] = {}
        elif failure == "bad_ratio":
            value["metrics"]["task.success"]["numerator"] = 2
        else:
            value["evidence"][0]["quote"] = "not in answer"
        return value
    run = evaluated(tmp_path / "run", evaluator=plugin(assess))
    report = evaluation_summary(run, details=True)
    assert report["counts"] == {"invalid": 2} and report["metrics"]["task.success"]["value"] is None
    assert "secret provider" not in json.dumps(report) and report["decision"] == "inconclusive"


def test_plugin_revision_requires_explicit_new_evaluation(tmp_path):
    run = evaluated(tmp_path / "run")
    before = EvaluationStore(run).path.read_bytes()
    with pytest.raises(ValueError, match="new_evaluation"):
        evaluate_saved(run, task_spec(), evaluators=(plugin(revision="v2"),))
    assert EvaluationStore(run).path.read_bytes() == before


def test_saved_comparison_pairs_cases_and_cannot_hide_hard_failure(tmp_path):
    baseline = evaluated(tmp_path / "baseline")
    candidate = evaluated(tmp_path / "candidate", ("good", "bad"))
    comparison = compare_saved(baseline, candidate)
    assert comparison["pairs"] == 2 and comparison["regressions"] == 1 and comparison["decision"] == "fail"
    assert comparison["metrics"]["task.success"]["delta"] == -0.5
    assert comparison["metrics"]["task.success"]["interval"] is None
    report = evaluation_summary(candidate, details=True)
    policy = GatePolicy(gates=(MetricGate(id="lenient", metric="task.success", operator="at_least", threshold=0),),
                        regressions=(RegressionGate(id="regression", metric="task.success", max_regression=1),))
    assert gate_report(report, policy, comparison=comparison)["decision"] == "fail"


@pytest.mark.parametrize("change", ["added", "removed", "changed_question"])
def test_unmatched_cases_do_not_silently_enter_a_headline_comparison(tmp_path, change):
    baseline = evaluated(tmp_path / "baseline")
    candidate = evaluated(tmp_path / "candidate", ("good",) if change == "removed" else ("good",) * 3 if change == "added" else ("good", "good"),
                          question="Changed question" if change == "changed_question" else "Question")
    comparison = compare_saved(baseline, candidate)
    assert comparison["decision"] == "inconclusive"
    assert comparison[{"added": "added", "removed": "removed", "changed_question": "mismatched"}[change]]


def test_different_evaluator_code_cannot_be_compared_as_a_product_change(tmp_path):
    baseline = evaluated(tmp_path / "baseline")
    candidate = evaluated(tmp_path / "candidate", evaluator=plugin(revision="v2"))
    with pytest.raises(ValueError, match="Incompatible evaluation evaluators"):
        compare_saved(baseline, candidate)


def test_bootstrap_keeps_related_turns_grouped_and_is_reproducible(tmp_path):
    groups = [f"group-{i // 2}" for i in range(12)]
    baseline = evaluated(tmp_path / "baseline", ("good",) * 12, groups=groups)
    candidate = evaluated(tmp_path / "candidate", ("good", "bad") * 6, groups=groups)
    comparison = compare_saved(baseline, candidate, seed=42, resamples=200)
    interval = comparison["metrics"]["task.success"]["interval"]
    assert interval["clusters"] == 6 and interval["low"] == interval["high"] == -0.5
    assert compare_saved(baseline, candidate, seed=42, resamples=200) == comparison


@pytest.mark.parametrize("qualification,answers,decision,exit_code", [
    ("reviewed", ("good",), "pass", 0), ("reviewed", ("bad",), "fail", 2),
    ("draft", ("good",), "inconclusive", 3),
])
def test_cli_html_json_markdown_and_junit_agree(tmp_path, qualification, answers, decision, exit_code):
    run = evaluated(tmp_path / "run", answers, qualification=qualification)
    out = tmp_path / "artifacts"
    result = CliRunner().invoke(app, ["check", str(run), "--out", str(out)])
    assert result.exit_code == exit_code, result.output
    report = json.loads((out / "evaluation.json").read_text())
    assert report["gate_report"]["decision"] == decision
    assert f"evaluation: {decision}" in (out / "index.html").read_text()
    assert f"**{decision}**" in (out / "summary.md").read_text()
    junit = ET.parse(out / "junit.xml").getroot()
    failing = int(junit.attrib["failures"]) + int(junit.attrib["errors"])
    assert (failing == 0) == (decision == "pass")


def test_unknown_gate_and_unavailable_metric_cannot_pass(tmp_path):
    run = evaluated(tmp_path / "run")
    report = evaluation_summary(run, details=True)
    with pytest.raises(ValueError, match="Unknown gate metric"):
        gate_report(report, GatePolicy(gates=(MetricGate(id="typo", metric="task.sucess", operator="at_least", threshold=0.9),)))
    gates = gate_report(report, GatePolicy(gates=(MetricGate(id="sample", metric="task.success", operator="at_least", threshold=0.9, min_denominator=10),)))
    assert gates["decision"] == "inconclusive"


def test_evidence_html_is_escaped_offline_and_read_only(tmp_path):
    attack = '<script>alert("bad")</script><img src="https://example.com/pixel">'
    run = evaluated(tmp_path / "run", (attack,), question=attack)
    before = EvaluationStore(run).path.read_bytes()
    export_evaluation(run, tmp_path / "review")
    page = (tmp_path / "review/index.html").read_text()
    assert "<script>" not in page and "<img " not in page and "&lt;script&gt;" in page
    assert "Content-Security-Policy" in page and "default-src 'none'" in page
    assert EvaluationStore(run).path.read_bytes() == before
    with pytest.raises(ValueError, match="already exist"):
        export_evaluation(run, tmp_path / "review")
