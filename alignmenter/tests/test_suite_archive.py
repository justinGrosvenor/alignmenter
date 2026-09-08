"""Noninteractive suite execution, frozen budgets, and portable inspection snapshots."""

import json
import zipfile
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from alignmenter.cli import app
from alignmenter.examples import resource_task
from alignmenter.execution.archive import export_archive, import_archive
from alignmenter.execution.evaluation import evaluate_saved, evaluation_summary
from alignmenter.execution.suite import run_suite
from alignmenter.providers.base import ChatResponse
from alignmenter.providers.callable import CallableProvider, CaptureTarget
from alignmenter.schemas.execution import RecoveryContract, content_digest
from alignmenter.storage.evaluations import EvaluationStore
from alignmenter.storage.runs import RunStore

from .test_release_workflow import evaluated, plugin, task_spec


def suite_file(path, **updates):
    path.mkdir()
    records, suite = resource_task.example_files()
    suite.update(updates)
    (path / "dataset.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    config = path / "suite.yaml"
    config.write_text(yaml.safe_dump(suite))
    return config


def test_installed_offline_example_and_saved_ci_artifacts(tmp_path):
    cli = CliRunner()
    example = tmp_path / "example"
    result = cli.invoke(app, ["init-suite", "--out", str(example)])
    assert result.exit_code == 0, result.output
    result = cli.invoke(app, ["run-suite", str(example / "suite.yaml"), "--out", str(tmp_path / "reports")])
    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    run = summary["run_dir"]
    report = evaluation_summary(run, details=True)
    assert report["budget"]["target"]["reserved_calls"] == 2 and report["budget"]["reserved_calls"] == 0
    assert report["decision"] == "pass" and RunStore(run).manifest().suite
    before = RunStore(run).path.read_bytes()
    result = cli.invoke(app, ["run-suite", str(example / "suite.yaml"), "--resume", run])
    assert result.exit_code == 0, result.output
    assert RunStore(run).path.read_bytes() == before


def test_target_budget_is_reserved_before_dispatch_and_survives_resume(tmp_path):
    config = suite_file(tmp_path / "example", max_target_calls=1)
    result = run_suite(config, out_dir=tmp_path / "reports")
    run = result["run_dir"]
    assert result["decision"] == "inconclusive" and result["capture_error"] == "TargetBudgetBlocked"
    store = RunStore(run)
    assert len(store.attempts()) == len(store.observations()) == 1
    assert evaluation_summary(run)["counts"] == {"met": 1, "missing_capture": 1}
    before = store.path.read_bytes()
    with pytest.raises(ValueError, match="budget exhausted"):
        run_suite(config, resume=run)
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("minimum,threshold,expected", [(3, 1, 3), (2, 2, 2)])
def test_saved_check_preserves_the_suite_gate_policy(tmp_path, minimum, threshold, expected):
    config = suite_file(tmp_path / "example", policy={"id": "strict-release", "revision": "v2", "gates": [
        {"id": "required_success", "metric": "resource_task.success", "operator": "at_least",
         "threshold": threshold, "min_denominator": minimum}]})
    result = run_suite(config, out_dir=tmp_path / "runs")
    assert evaluation_summary(result["run_dir"])["decision"] == "pass"
    output = tmp_path / "saved-check"
    checked = CliRunner().invoke(app, ["check", result["run_dir"], "--out", str(output)])
    assert checked.exit_code == expected, checked.output
    report = json.loads((output / "evaluation.json").read_text())
    assert report["gate_report"]["decision"] == result["decision"]
    assert report["gate_report"]["policy"]["id"] == "strict-release"


def test_invalid_gate_rejected_before_target_factory_or_dispatch(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(resource_task, "make_target", lambda: calls.append("unexpected"))
    config = suite_file(tmp_path / "example", policy={"gates": [{"id": "typo", "metric": "resource_task.sucess", "operator": "at_least", "threshold": 1}]})
    with pytest.raises(ValueError, match="Unknown gate"):
        run_suite(config, out_dir=tmp_path / "reports")
    assert calls == [] and not (tmp_path / "reports").exists()


def test_target_failure_exports_partial_work_then_resume_reuses_answers(tmp_path, monkeypatch):
    calls = []

    def target(messages, *, request_id):
        calls.append(request_id)
        if len(calls) == 2:
            raise TimeoutError("sensitive transport message")
        available = json.loads(messages[-1]["content"])["available"]
        return ChatResponse(text=json.dumps({"action": "prepare", "needed": available[:1]}))

    contract = RecoveryContract(configuration_digest=content_digest({"target": "fixture"}), session_state="stateless", interrupted_request="idempotent")
    monkeypatch.setattr(resource_task, "make_target", lambda: CaptureTarget("fixture:target", CallableProvider(target, contract)))
    config = suite_file(tmp_path / "example", max_target_calls=3)
    first = run_suite(config, out_dir=tmp_path / "reports")
    run = first["run_dir"]
    assert first["decision"] == "inconclusive" and first["capture_error"] == "TimeoutError"
    old = RunStore(run).observations()[0]
    second = run_suite(config, resume=run)
    assert second["decision"] == "pass" and len(calls) == 3
    assert calls[1] == calls[2] and calls[0] != calls[1]
    assert RunStore(run).observations()[0] == old
    assert len(EvaluationStore(run).manifests()) == 2
    assert "sensitive transport message" not in json.dumps(evaluation_summary(run, details=True))


def test_suite_resume_rejects_configuration_drift_before_new_work(tmp_path):
    config = suite_file(tmp_path / "example")
    first = run_suite(config, out_dir=tmp_path / "reports")
    value = yaml.safe_load(config.read_text())
    value["max_target_calls"] = 100
    config.write_text(yaml.safe_dump(value))
    before = RunStore(first["run_dir"]).path.read_bytes()
    with pytest.raises(ValueError, match="Suite configuration differs"):
        run_suite(config, resume=first["run_dir"])
    assert RunStore(first["run_dir"]).path.read_bytes() == before


def test_suite_baseline_comparison_detects_a_resource_regression(tmp_path, monkeypatch):
    config = suite_file(tmp_path / "example")
    first = run_suite(config, out_dir=tmp_path / "reports")
    value = yaml.safe_load(config.read_text())
    value["baseline"] = first["run_dir"]
    value["baseline_evaluation_id"] = first["evaluation_id"]
    value["policy"]["regressions"] = [{"id": "no_regression", "metric": "resource_task.success", "max_regression": 0}]
    config.write_text(yaml.safe_dump(value))
    monkeypatch.setenv("ALIGNMENTER_DEMO_VARIANT", "bad")
    second = run_suite(config, out_dir=tmp_path / "reports")
    report = json.loads((Path(second["artifacts"]) / "evaluation.json").read_text())
    assert second["decision"] == "fail" and report["comparison"]["regressions"] == 2


def test_portable_archive_verifies_and_cannot_fork_a_live_budget(tmp_path):
    run = evaluated(tmp_path / "run")
    before = RunStore(run).path.read_bytes()
    report = evaluation_summary(run, details=True)
    path = tmp_path / "run.zip"
    export_archive(run, path)
    imported = tmp_path / "imported"
    manifest = import_archive(path, imported)
    assert manifest.id == RunStore(run).manifest().id
    assert evaluation_summary(imported, details=True) == report
    assert RunStore(run).path.read_bytes() == before
    with pytest.raises(ValueError, match="read-only"):
        evaluate_saved(imported, task_spec(), evaluators=(plugin(),), new_evaluation=True)
    with pytest.raises(ValueError, match="already exist"):
        import_archive(path, imported)


@pytest.mark.parametrize("attack", ["path", "checksum", "duplicate", "schema", "identity"])
def test_archive_rejects_invalid_entries_without_exposing_destination(tmp_path, attack):
    run = evaluated(tmp_path / "run")
    original = tmp_path / "original.zip"
    export_archive(run, original)
    with zipfile.ZipFile(original) as archive:
        metadata, database = json.loads(archive.read("archive.json")), archive.read("run.sqlite3")
    if attack == "checksum":
        database += b"changed"
    if attack == "schema":
        metadata["schema_version"] = True
    if attack == "identity":
        metadata["run_id"] = "incorrect"
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr("archive.json", json.dumps(metadata))
        archive.writestr("../escape.sqlite3" if attack == "path" else "run.sqlite3", database)
        if attack == "duplicate":
            with pytest.warns(UserWarning, match="Duplicate name"):
                archive.writestr("run.sqlite3", database)
    with pytest.raises(ValueError):
        import_archive(bad, tmp_path / "imported")
    assert not (tmp_path / "imported").exists() and not (tmp_path / "escape.sqlite3").exists()
