"""Durable capture through the production runner, including abrupt process death."""

from __future__ import annotations

import json
import os
import selectors
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from alignmenter.cli import app
from alignmenter.providers.base import ChatResponse
from alignmenter.runner import RunConfig, Runner, prepare_run_directory
from alignmenter.schemas.execution import (
    Attempt,
    ExecutionStatus,
    Observation,
    RunManifest,
    RunPhase,
    content_digest,
)
from alignmenter.storage.runs import DATABASE_NAME, RunStore
from alignmenter.utils.io import read_jsonl


class Provider:
    name = "fixture"

    def __init__(self, responses=None):
        self.responses = list(responses or [ChatResponse(text="new-A"), ChatResponse(text="new-B")])
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        result = self.responses.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


class Scorer:
    id = "fixture"

    def score(self, sessions):
        return {"mean": 0.5}


def make_runner(tmp_path, provider=None, *, records=None, scorers=None, **kwargs):
    records = records or [
        {"session_id": name, "turn_index": i, "role": role, "text": text}
        for name in ("A", "B")
        for i, role, text in [(1, "user", f"question-{name}"), (2, "assistant", f"old-{name}")]
    ]
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("".join(json.dumps(r) + "\n" for r in records))
    persona = tmp_path / "persona.yaml"
    persona.write_text("id: example\n")
    config = RunConfig(
        model="fixture:local",
        dataset_path=dataset,
        persona_path=persona,
        report_out_dir=tmp_path / "reports",
    )
    return Runner(config, [Scorer()] if scorers is None else scorers, provider=provider, **kwargs)


def test_timeout_preserves_first_answer_and_frozen_source(tmp_path):
    provider = Provider(
        [ChatResponse(text="new-A", context={"excerpts": []}), TimeoutError("opaque")]
    )
    runner = make_runner(tmp_path, provider)
    original_dataset = read_jsonl(runner.config.dataset_path)
    original_persona = runner.config.persona_path.read_bytes()
    with pytest.raises(TimeoutError, match="opaque"):
        runner.execute()
    store = RunStore(runner.run_dir)
    summary = store.summary()
    assert summary.run.status == ExecutionStatus.FAILED
    assert summary.run.phase == RunPhase.CAPTURE
    assert summary.planned_records == 4 and summary.committed_records == 3
    assert summary.planned_generations == 2 and summary.observations == 1
    assert [a.status for a in store.attempts()] == [
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.UNKNOWN_OUTCOME,
    ]
    assert store.attempts()[1].failure.kind == "timeout"
    assert store.observations()[0].text == "new-A"
    assert [r["text"] for r in store.transcripts()] == ["question-A", "new-A", "question-B"]
    assert read_jsonl(next((runner.run_dir / "transcripts").glob("*.jsonl"))) == store.transcripts()
    assert not (runner.run_dir / "results.json").exists()
    runner.config.dataset_path.unlink()
    runner.config.persona_path.unlink()
    manifest = store.manifest()
    assert json.loads(store.source_artifact(manifest.dataset_digest)) == original_dataset
    assert store.source_artifact(manifest.persona_digest) == original_persona


@pytest.mark.parametrize("context", [None, {}])
def test_new_generation_clears_old_evidence_and_preserves_empty_context(tmp_path, context):
    records = [
        {"session_id": "A", "role": "user", "text": "q"},
        {
            "session_id": "A",
            "role": "assistant",
            "text": "old",
            "metadata": {
                "context": {"excerpts": ["old source"]},
                "usage": {"total_tokens": 999},
                "generated_by": "old-model",
                "baseline_text": "older",
                "case_note": "preserve",
            },
        },
    ]
    runner = make_runner(
        tmp_path, Provider([ChatResponse(text="  new\n", context=context)]), records=records
    )
    store = RunStore(runner.execute())
    observation = store.observations()[0]
    assert observation.text == "  new\n" and observation.usage is None
    assert observation.context == context
    assert observation.context_status == ("missing" if context is None else "provided")
    assert observation.evidence_completeness == "unknown"
    record = store.transcripts()[1]
    assert record["text"] == "new"
    metadata = record["metadata"]
    assert "usage" not in metadata
    assert ("context" in metadata) == (context is not None)
    assert metadata["baseline_text"] == "old" and metadata["case_note"] == "preserve"
    assert metadata["attempt_id"] == str(observation.attempt_id)
    assert metadata["observation_id"] == str(observation.id)


@pytest.mark.parametrize("failure_stage", ["scoring", "reporting", "progress"])
def test_later_failure_preserves_successful_attempts(tmp_path, failure_stage):
    class BrokenScorer(Scorer):
        def score(self, sessions):
            raise RuntimeError("scoring failure")

    class BrokenReporter:
        def write(self, *args, **kwargs):
            raise RuntimeError("reporting failure")

    def broken_progress(count):
        raise RuntimeError("progress failure")

    options = {}
    if failure_stage == "scoring":
        options["scorers"] = [BrokenScorer()]
    elif failure_stage == "reporting":
        options["reporters"] = [BrokenReporter()]
    else:
        options["progress_callback"] = broken_progress
    runner = make_runner(tmp_path, Provider(), **options)
    with pytest.raises(RuntimeError, match=failure_stage):
        runner.execute()
    store = RunStore(runner.run_dir)
    assert all(a.status == ExecutionStatus.SUCCEEDED for a in store.attempts())
    assert len(store.observations()) == (1 if failure_stage == "progress" else 2)
    assert store.summary().run.status == ExecutionStatus.FAILED
    assert runner.latest_results is None


def test_interrupt_records_unknown_outcome_without_retries(tmp_path):
    provider = Provider([KeyboardInterrupt()])
    runner = make_runner(tmp_path, provider)
    with pytest.raises(KeyboardInterrupt):
        runner.execute()
    store = RunStore(runner.run_dir)
    assert store.summary().run.status == ExecutionStatus.INTERRUPTED
    assert store.attempts()[0].status == ExecutionStatus.UNKNOWN_OUTCOME
    assert store.attempts()[0].failure.kind == "interrupted"
    assert len(provider.calls) == 1 and store.observations() == []


@pytest.mark.parametrize(
    "response", [ChatResponse(text=None), ChatResponse(text="x", usage={"tokens": float("nan")})]
)
def test_invalid_response_cannot_become_a_successful_observation(tmp_path, response):
    runner = make_runner(tmp_path, Provider([response]))
    with pytest.raises(ValueError):
        runner.execute()
    store = RunStore(runner.run_dir)
    assert store.observations() == []
    attempt = store.attempts()[0]
    assert attempt.status == ExecutionStatus.FAILED and attempt.failure.kind == "invalid_response"


def test_recorded_mode_has_observations_without_fake_dispatches(tmp_path):
    provider = Provider()
    runner = make_runner(tmp_path, provider, generate_transcripts=False)
    store = RunStore(runner.execute())
    assert provider.calls == [] and store.attempts() == []
    assert {o.origin for o in store.observations()} == {"recorded"}
    assert all(o.attempt_id is None for o in store.observations())
    assert store.transcripts() == read_jsonl(runner.config.dataset_path)
    assert store.summary().planned_generations == 0


def test_same_model_comparison_has_separate_saved_streams(tmp_path):
    runner = make_runner(
        tmp_path,
        Provider(),
        compare_scorers=[Scorer()],
        compare_provider=Provider([ChatResponse(text="compare-A"), ChatResponse(text="compare-B")]),
    )
    runner.config.compare_model = runner.config.model
    store = RunStore(runner.execute())
    meta = json.loads((runner.run_dir / "run.json").read_text())
    primary, compared = [meta["transcripts"][stream]["path"] for stream in ("primary", "compare")]
    assert primary != compared
    assert read_jsonl(runner.run_dir / primary)[1]["text"] == "new-A"
    assert read_jsonl(runner.run_dir / compared)[1]["text"] == "compare-A"
    assert len(store.attempts()) == len(store.observations()) == 4
    assert len({a.request_id for a in store.attempts()}) == 4


def test_provider_sees_frozen_inputs_and_persisted_attempt(tmp_path):
    runner = None

    class InspectingProvider(Provider):
        def chat(self, messages):
            store = RunStore(runner.run_dir)
            current = store.attempts()[-1]
            assert current.status == ExecutionStatus.RUNNING
            assert current.messages == messages and current.input_digest == content_digest(messages)
            runner.config.dataset_path.write_text("not the original dataset")
            return super().chat(messages)

    provider = InspectingProvider()
    runner = make_runner(tmp_path, provider)
    runner.execute()
    assert provider.calls[-1] == [{"role": "user", "content": "question-B"}]


def test_duplicate_source_turns_reject_before_provider_calls(tmp_path):
    provider = Provider()
    records = [
        {"session_id": "A", "turn_index": 1, "role": role, "text": "x"}
        for role in ("user", "assistant")
    ]
    runner = make_runner(tmp_path, provider, records=records)
    with pytest.raises(ValueError, match="Duplicate"):
        runner.execute()
    assert provider.calls == [] and runner.run_dir is None


def test_run_directories_never_reuse_existing_content(tmp_path):
    first = prepare_run_directory(tmp_path, "2026-09-06T00:00:00Z", "same")
    (first / "sentinel").write_text("keep")
    second = prepare_run_directory(tmp_path, "2026-09-06T00:00:00Z", "same")
    assert first != second and (first / "sentinel").read_text() == "keep"
    escaped = prepare_run_directory(tmp_path, "2026-09-06T00:00:00Z", "../../elsewhere")
    assert escaped.parent == tmp_path


def test_versioned_records_roundtrip_and_reject_unknown_formats(tmp_path):
    store = RunStore(make_runner(tmp_path, Provider()).execute())
    for record, model in [
        (store.manifest(), RunManifest),
        (store.attempts()[0], Attempt),
        (store.observations()[0], Observation),
    ]:
        assert model.model_validate_json(record.model_dump_json()) == record
        for bad_version in (2, True, "1"):
            with pytest.raises(ValidationError):
                model.model_validate({**record.model_dump(), "schema_version": bad_version})
        with pytest.raises(ValidationError):
            model.model_validate({**record.model_dump(), "unknown_field": "unrecognized"})
    with pytest.raises(ValidationError, match="digest"):
        Attempt.model_validate({**store.attempts()[0].model_dump(), "input_digest": "0" * 64})
    with pytest.raises(ValidationError, match="Context"):
        Observation.model_validate(
            {**store.observations()[0].model_dump(), "context_status": "provided"}
        )


def test_store_refuses_changed_sources_or_an_existing_database(tmp_path):
    store = RunStore(make_runner(tmp_path, Provider()).execute())
    manifest, plan = store.manifest(), store.plan()
    dataset = json.loads(store.source_artifact(manifest.dataset_digest))
    persona = store.source_artifact(manifest.persona_digest)
    original = store.path.read_bytes()
    with pytest.raises(FileExistsError):
        RunStore.create(store.run_dir, manifest, plan, dataset=dataset, persona=persona)
    assert store.path.read_bytes() == original
    with pytest.raises(ValueError, match="Dataset snapshot"):
        RunStore.create(tmp_path / "other", manifest, plan, dataset=[], persona=persona)
    with pytest.raises(ValueError, match="Persona snapshot"):
        RunStore.create(tmp_path / "other", manifest, plan, dataset=dataset, persona=b"changed")
    with pytest.raises(ValueError, match="Duplicate"):
        RunStore.create(
            tmp_path / "other", manifest, plan + [plan[0]], dataset=dataset, persona=persona
        )
    assert not (tmp_path / "other").exists()


def test_failed_commit_cannot_leave_an_attempt_successful(tmp_path):
    runner = None

    class FailingStorageProvider(Provider):
        def chat(self, messages):
            # A real SQLite write failure at the end of the capture transaction.
            with sqlite3.connect(RunStore(runner.run_dir).path) as db:
                db.execute(
                    "CREATE TRIGGER fail_record BEFORE INSERT ON records WHEN NEW.ordinal=1 "
                    "BEGIN SELECT RAISE(ABORT, 'injected storage failure'); END"
                )
            return ChatResponse(text="answer")

    runner = make_runner(tmp_path, FailingStorageProvider())
    with pytest.raises(sqlite3.IntegrityError, match="injected storage failure"):
        runner.execute()
    store = RunStore(runner.run_dir)
    assert store.observations() == []
    assert store.summary().committed_records == 1
    assert store.attempts()[0].status == ExecutionStatus.UNKNOWN_OUTCOME
    assert store.summary().run.status == ExecutionStatus.FAILED


def test_mismatched_observation_does_not_complete_another_attempt(tmp_path):
    original = RunStore(make_runner(tmp_path, Provider()).execute())
    manifest = original.manifest()
    store = RunStore.create(
        tmp_path / "new",
        manifest,
        original.plan(),
        dataset=json.loads(original.source_artifact(manifest.dataset_digest)),
        persona=original.source_artifact(manifest.persona_digest),
    )
    first, second = [t for t in store.plan() if t.generate]
    attempt = store.start_attempt(first, [{"role": "user", "content": "q"}])
    observed = Observation(
        stream=second.stream,
        ordinal=second.ordinal,
        attempt_id=attempt.id,
        origin="generated",
        text="new",
        context_status="missing",
    )
    with pytest.raises(ValueError, match="matching attempt"):
        store.commit_record(second, {**second.record, "text": "new"}, observed)
    assert store.observations() == []
    assert store.attempts()[0].status == ExecutionStatus.RUNNING
    with pytest.raises(ValueError, match="Incomplete"):
        store.set_run_state(status=ExecutionStatus.SUCCEEDED)


def test_readers_do_not_create_or_mutate_unknown_databases(tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        RunStore(missing).summary()
    assert not missing.exists()
    store = RunStore(make_runner(tmp_path, Provider()).execute())
    with sqlite3.connect(store.path) as db:
        db.execute("PRAGMA user_version=999")
    original = store.path.read_bytes()
    with pytest.raises(ValueError, match="migration"):
        RunStore(store.run_dir).summary()
    assert store.path.read_bytes() == original


def test_cli_exports_preserve_existing_files_and_database(tmp_path):
    store = RunStore(make_runner(tmp_path, Provider()).execute())
    cli = CliRunner()
    out = tmp_path / "existing.jsonl"
    out.write_text("keep this")
    result = cli.invoke(app, ["export-transcripts", str(store.run_dir), "--out", str(out)])
    assert result.exit_code != 0 and out.read_text() == "keep this"
    result = cli.invoke(
        app, ["export-transcripts", str(store.run_dir), "--out", str(out), "--force"]
    )
    assert result.exit_code == 0 and read_jsonl(out) == store.transcripts()
    database = store.path.read_bytes()
    result = cli.invoke(
        app, ["export-transcripts", str(store.run_dir), "--out", str(store.path), "--force"]
    )
    assert result.exit_code != 0 and store.path.read_bytes() == database
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / DATABASE_NAME).write_text("not a database")
    result = cli.invoke(app, ["status", str(broken), "--json"])
    assert result.exit_code != 0 and "database" in result.output


@pytest.mark.parametrize(
    "pause,committed,attempts",
    [("before_first", 1, 1), ("after_commit", 2, 1), ("second_provider", 3, 2)],
)
def test_sigkill_preserves_exact_commit_boundary(tmp_path, pause, committed, attempts):
    script = Path(__file__).parent / "data" / "durable_run_worker.py"
    with (tmp_path / "worker.stderr").open("w") as err:
        process = subprocess.Popen(
            [sys.executable, str(script), str(tmp_path), pause],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=err,
        )
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        received = b""
        deadline = time.monotonic() + 20
        try:
            while b"READY:" not in received or not received.endswith(b"\n"):
                assert selector.select(max(0, deadline - time.monotonic())), (
                    "Worker barrier timeout"
                )
                part = os.read(process.stdout.fileno(), 65536)
                assert part, (tmp_path / "worker.stderr").read_text()
                received += part
            run_dir = Path(received.decode().split("READY:", 1)[1].strip())
            # A fresh reader sees committed records while the writer process still exists.
            assert RunStore(run_dir).summary().committed_records == committed
            process.kill()
            assert process.wait(timeout=10) != 0
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            selector.close()
            process.stdin.close()
            process.stdout.close()
    store = RunStore(run_dir)
    summary = store.summary()
    assert summary.committed_records == committed and len(store.attempts()) == attempts
    assert summary.run.status == ExecutionStatus.RUNNING and summary.liveness == "not_checked"
    if committed > 1:
        assert store.observations()[0].text == "answer-1"
        assert store.attempts()[0].status == ExecutionStatus.SUCCEEDED
    status = CliRunner().invoke(app, ["status", str(run_dir), "--json"])
    assert status.exit_code == 0, status.output
    assert json.loads(status.output)["committed_records"] == committed
    out = tmp_path / "recovered.jsonl"
    result = CliRunner().invoke(app, ["export-transcripts", str(run_dir), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert read_jsonl(out) == store.transcripts()
