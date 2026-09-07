"""Recovery contract acceptance through the production SDK and CLI."""

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
from typer.testing import CliRunner

from alignmenter.cli import app
from alignmenter.execution.leases import RunBusyError, coordinator_lease
from alignmenter.execution.recovery import ResumeError, resume_capture
from alignmenter.providers.base import ChatResponse
from alignmenter.providers.callable import CallableProvider, CaptureTarget
from alignmenter.schemas.execution import (
    ExecutionStatus,
    Observation,
    RecoveryContract,
    RunPhase,
    content_digest,
)
from alignmenter.storage.runs import RunStore
from alignmenter.utils.io import read_jsonl

from .test_durable_execution import Provider, Scorer, make_runner


def adapter(function, *, revision="fixture-v1", recovery="idempotent", state="stateless", limit=3):
    return CallableProvider(function, RecoveryContract(
        configuration_digest=content_digest({"revision": revision}),
        session_state=state, interrupted_request=recovery, max_attempts=limit,
    ))


def target(provider, model="fixture:local"):
    return {"primary": CaptureTarget(model, provider)}


class Backend:
    """Target-side durable response semantics (disk-backed in subprocess tests)."""

    def __init__(self):
        self.accepted = {}
        self.dispatches = []
        self.fail = True

    def __call__(self, messages, *, request_id):
        self.dispatches.append((messages, request_id))
        if request_id not in self.accepted:
            self.accepted[request_id] = ChatResponse(text="answer:" + messages[-1]["content"])
        if self.fail and messages[-1]["content"] == "question-B":
            self.fail = False
            raise TimeoutError("reply was lost after acceptance")
        return self.accepted[request_id]


def test_resume_reuses_answers_and_recovers_original_request_without_new_effect(tmp_path):
    backend = Backend()
    provider = adapter(backend)
    runner = make_runner(tmp_path, provider)
    with pytest.raises(TimeoutError):
        runner.capture()
    store = RunStore(runner.run_dir)
    original_observation = store.observations()[0]
    original_request = store.attempts()[-1].request_id
    runner.config.dataset_path.unlink()
    runner.config.persona_path.unlink()
    summary = resume_capture(store.run_dir, targets=target(adapter(backend)))
    assert summary.run.status == ExecutionStatus.CAPTURED and summary.run.phase == RunPhase.CAPTURE
    assert summary.committed_records == 4 and summary.observations == 2
    assert len(backend.dispatches) == 3 and len(backend.accepted) == 2
    assert store.observations()[0] == original_observation
    assert [a.status for a in store.attempts()] == [
        ExecutionStatus.SUCCEEDED, ExecutionStatus.UNKNOWN_OUTCOME, ExecutionStatus.SUCCEEDED,
    ]
    assert store.attempts()[-1].request_id == original_request
    assert len({a.id for a in store.attempts()}) == 3
    assert not (store.run_dir / "results.json").exists()
    assert read_jsonl(store.run_dir / "transcripts" / "fixture_local.jsonl") == store.transcripts()
    saved = store.path.read_bytes()
    assert resume_capture(store.run_dir) == summary
    assert store.path.read_bytes() == saved and len(backend.dispatches) == 3


def test_resume_reconstructs_full_conversation_without_retry_capability(tmp_path):
    calls = []

    def chat(messages, *, request_id):
        calls.append(messages)
        return ChatResponse(text=f"new-{len(calls)}")

    def stop(_count):
        raise RuntimeError("stop after commit")

    records = [
        {"session_id": "A", "turn_index": i, "role": role, "text": text}
        for i, (role, text) in enumerate([
            ("system", "rules"), ("user", "one"), ("assistant", "old-one"),
            ("user", "two"), ("assistant", "old-two"),
        ])
    ]
    provider = adapter(chat, recovery="refuse")
    runner = make_runner(tmp_path, provider, records=records, progress_callback=stop)
    with pytest.raises(RuntimeError, match="stop"):
        runner.capture()
    resume_capture(runner.run_dir, targets=target(provider))
    assert calls == [
        [{"role": "system", "content": "rules"}, {"role": "user", "content": "one"}],
        [{"role": "system", "content": "rules"}, {"role": "user", "content": "one"},
         {"role": "assistant", "content": "new-1"}, {"role": "user", "content": "two"}],
    ]


@pytest.mark.parametrize("change", ["config", "model", "dataset", "persona", "capability", "package"])
def test_incompatible_resume_is_rejected_before_any_writes_or_calls(tmp_path, change):
    backend, options = Backend(), {}
    provider = adapter(backend)
    runner = make_runner(tmp_path, provider)
    with pytest.raises(TimeoutError):
        runner.capture()
    if change == "config":
        provider = adapter(backend, revision="v2")
    elif change == "model":
        options["targets"] = target(provider, "fixture:other")
    elif change == "capability":
        provider = adapter(backend, recovery="refuse")
    elif change == "dataset":
        runner.config.dataset_path.write_text(json.dumps({"session_id": "changed"}) + "\n")
        options["dataset_path"] = runner.config.dataset_path
    elif change == "persona":
        runner.config.persona_path.write_text("id: changed")
        options["persona_path"] = runner.config.persona_path
    else:
        with sqlite3.connect(RunStore(runner.run_dir).path) as db:
            manifest = json.loads(db.execute("SELECT payload FROM manifest").fetchone()[0])
            manifest["package_version"] = "other-version"
            db.execute("UPDATE manifest SET payload=?", (json.dumps(manifest),))
    options.setdefault("targets", target(provider))
    store = RunStore(runner.run_dir)
    saved = store.path.read_bytes()
    with pytest.raises(ResumeError, match="differs"):
        resume_capture(runner.run_dir, **options)
    assert len(backend.dispatches) == 2 and store.path.read_bytes() == saved


@pytest.mark.parametrize("kind", ["legacy", "opaque", "refuse"])
def test_unsupported_recovery_never_repeats_an_unfinished_request(tmp_path, kind):
    backend = Backend()
    provider = (
        Provider([ChatResponse(text="saved"), TimeoutError()]) if kind == "legacy"
        else adapter(backend, state="opaque" if kind == "opaque" else "stateless", recovery="refuse")
    )
    runner = make_runner(tmp_path, provider)
    with pytest.raises(TimeoutError):
        runner.capture()
    store = RunStore(runner.run_dir)
    original = store.path.read_bytes()
    with pytest.raises(ResumeError, match="contract|idempotent"):
        resume_capture(runner.run_dir, targets=target(provider))
    assert store.path.read_bytes() == original and len(store.attempts()) == 2


def test_attempt_limit_survives_repeated_resumes(tmp_path):
    calls = []

    def chat(messages, *, request_id):
        calls.append(request_id)
        raise TimeoutError()

    provider = adapter(chat)
    runner = make_runner(tmp_path, provider)
    with pytest.raises(TimeoutError):
        runner.capture()
    for _ in range(2):
        with pytest.raises(TimeoutError):
            resume_capture(runner.run_dir, targets=target(provider))
    with pytest.raises(ResumeError, match="limit exhausted"):
        resume_capture(runner.run_dir, targets=target(provider))
    assert len(calls) == 3 and len(set(calls)) == 1
    assert len(RunStore(runner.run_dir).attempts()) == 3


def test_complete_capture_never_restarts_failed_scoring(tmp_path):
    calls = []

    class BrokenScorer(Scorer):
        def score(self, sessions):
            calls.append("score")
            raise RuntimeError("judge failed")

    runner = make_runner(tmp_path, Provider(), scorers=[BrokenScorer()])
    with pytest.raises(RuntimeError, match="judge"):
        runner.execute()
    store = RunStore(runner.run_dir)
    before = store.path.read_bytes()
    summary = resume_capture(store.run_dir)
    assert summary.run.status == ExecutionStatus.FAILED and summary.run.phase == RunPhase.SCORING
    assert calls == ["score"] and store.path.read_bytes() == before


def test_check_and_busy_coordinator_do_not_mutate_or_dispatch(tmp_path):
    backend = Backend()
    provider = adapter(backend)
    runner = make_runner(tmp_path, provider)
    with pytest.raises(TimeoutError):
        runner.capture()
    store = RunStore(runner.run_dir)
    before = store.path.read_bytes()
    result = resume_capture(store.run_dir, targets=target(provider), check_only=True)
    assert result.committed_records == 3 and store.path.read_bytes() == before
    with coordinator_lease(store.run_dir), pytest.raises(RunBusyError):
        resume_capture(store.run_dir, targets=target(provider))
    assert len(backend.dispatches) == 2 and store.path.read_bytes() == before


def test_comparison_target_preflight_precedes_primary_dispatch(tmp_path):
    backend = Backend()
    provider = adapter(backend)
    runner = make_runner(tmp_path, provider, compare_provider=provider, compare_scorers=[Scorer()])
    runner.config.compare_model = "fixture:compare"
    with pytest.raises(TimeoutError):
        runner.capture()
    targets = {**target(provider), "compare": CaptureTarget("wrong:model", provider)}
    with pytest.raises(ResumeError, match="compare"):
        resume_capture(runner.run_dir, targets=targets)
    assert len(backend.dispatches) == 2
    targets["compare"] = CaptureTarget("fixture:compare", provider)
    summary = resume_capture(runner.run_dir, targets=targets)
    assert summary.observations == 4 and summary.committed_records == 8
    assert len(backend.dispatches) == 5 and len(backend.accepted) == 4


def test_cli_import_and_resume_recorded_work_without_loading_targets(tmp_path):
    dataset = tmp_path / "records.jsonl"
    records = [{"session_id": "A", "role": "assistant", "text": "saved"}]
    dataset.write_text(json.dumps(records[0]) + "\n")
    cli = CliRunner()
    result = cli.invoke(app, ["capture", "--dataset", str(dataset), "--out", str(tmp_path / "runs")])
    assert result.exit_code == 0, result.output
    run_dir = next((tmp_path / "runs").iterdir())
    store = RunStore(run_dir)
    assert store.transcripts() == records and store.attempts() == []
    for args in (["--check"], []):
        result = cli.invoke(app, ["resume", str(run_dir), *args])
        assert result.exit_code == 0, result.output
    assert store.summary().run.status == ExecutionStatus.CAPTURED


def test_partial_recorded_capture_continues_from_saved_inputs(tmp_path):
    runner = make_runner(tmp_path, scorers=[])
    dataset = read_jsonl(runner.config.dataset_path)
    manifest, plan, persona = runner._plan_run(dataset)
    store = RunStore.create(tmp_path / "partial", manifest, plan, dataset=dataset, persona=persona)
    store.commit_record(plan[0], plan[0].record)
    runner.config.dataset_path.unlink()
    result = CliRunner().invoke(app, ["resume", str(store.run_dir)])
    assert result.exit_code == 0, result.output
    assert store.transcripts() == dataset and store.attempts() == []
    assert store.summary().run.status == ExecutionStatus.CAPTURED


def test_old_attempt_cannot_commit_during_its_replacement(tmp_path):
    backend = Backend()
    runner = make_runner(tmp_path, adapter(backend))
    with pytest.raises(TimeoutError):
        runner.capture()
    store = RunStore(runner.run_dir)
    stale = store.attempts()[-1]
    turn = store.plan()[-1]

    def chat(messages, *, request_id):
        observation = Observation(stream=turn.stream, ordinal=turn.ordinal,
                                  attempt_id=stale.id, origin="generated", text="stale",
                                  context_status="missing")
        with pytest.raises(ValueError, match="active matching attempt"):
            store.commit_record(turn, {**turn.record, "text": "stale"}, observation)
        return backend(messages, request_id=request_id)

    resume_capture(store.run_dir, targets=target(adapter(chat)))
    assert store.transcripts()[-1]["text"] == "answer:question-B"
    assert len(store.observations()) == 2


@pytest.mark.parametrize("corruption", ["plan", "observation", "request"])
def test_corrupt_saved_evidence_or_request_is_rejected_before_dispatch(tmp_path, corruption):
    backend = Backend()
    runner = make_runner(tmp_path, adapter(backend))
    with pytest.raises(TimeoutError):
        runner.capture()
    store = RunStore(runner.run_dir)
    with sqlite3.connect(store.path) as db:
        if corruption == "plan":
            turn = json.loads(db.execute("SELECT payload FROM inputs WHERE ordinal=0").fetchone()[0])
            turn["record"]["text"] = "changed"
            db.execute("UPDATE inputs SET payload=? WHERE ordinal=0", (json.dumps(turn),))
        elif corruption == "observation":
            db.execute("UPDATE observations SET digest=?", ("0" * 64,))
        else:
            attempt = store.attempts()[-1].model_dump(mode="json")
            attempt["messages"] = [{"role": "user", "content": "changed"}]
            attempt["input_digest"] = content_digest(attempt["messages"])
            db.execute("UPDATE attempts SET payload=? WHERE id=?", (json.dumps(attempt), attempt["id"]))
    before = store.path.read_bytes()
    with pytest.raises(ValueError, match="digest|messages"):
        resume_capture(store.run_dir, targets=target(adapter(backend)))
    assert store.path.read_bytes() == before and len(backend.dispatches) == 2


def test_v1_database_remains_readable_but_cannot_be_reopened(tmp_path):
    runner = make_runner(tmp_path, Provider([TimeoutError()]))
    with pytest.raises(TimeoutError):
        runner.capture()
    store = RunStore(runner.run_dir)
    with sqlite3.connect(store.path) as db:
        db.execute("PRAGMA user_version=1")
    assert store.summary().committed_records == 1
    original = store.path.read_bytes()
    with pytest.raises(ValueError, match="read-only"):
        store.reopen_capture()
    assert store.path.read_bytes() == original


@pytest.mark.parametrize("pause", ["before_accept", "after_accept", "after_commit"])
def test_killed_process_resumes_via_cli_without_duplicate_target_effects(tmp_path, pause):
    data = Path(__file__).parent / "data"
    env = {**os.environ, "ALIGNMENTER_TEST_TARGET_ROOT": str(tmp_path),
           "ALIGNMENTER_TEST_PAUSE": pause,
           "PYTHONPATH": str(data) + os.pathsep + os.environ.get("PYTHONPATH", "")}
    with (tmp_path / "stderr").open("w") as err:
        process = subprocess.Popen([sys.executable, str(data / "durable_recovery_worker.py")],
                                   env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        received, deadline = b"", time.monotonic() + 20
        try:
            while not received.endswith(b"\n"):
                assert selector.select(max(0, deadline - time.monotonic())), "Worker barrier timeout"
                part = os.read(process.stdout.fileno(), 65536)
                assert part, (tmp_path / "stderr").read_text()
                received += part
            run_dir = Path(received.decode().split("READY:", 1)[1].strip())
            store = RunStore(run_dir)
            saved_answer = store.observations()[0]
            cli = [sys.executable, "-c", "from alignmenter.cli import app; app()", "resume",
                   str(run_dir), "--target", "durable_recovery_target:make_target"]
            busy = subprocess.run(cli, env=env, capture_output=True, text=True, timeout=20)
            assert busy.returncode != 0 and "active coordinator" in busy.stderr
            process.kill()
            assert process.wait(timeout=10) != 0
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            selector.close()
            process.stdin.close()
            process.stdout.close()
    env.pop("ALIGNMENTER_TEST_PAUSE")
    # The new process has neither the original target instance nor source files.
    (tmp_path / "dataset.jsonl").unlink()
    checked = subprocess.run([*cli, "--check"], env=env, capture_output=True, text=True, timeout=20)
    assert checked.returncode == 0, checked.stderr
    completed = subprocess.run(cli, env=env, capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stderr
    assert "4/4" in completed.stdout and "no scoring" in completed.stdout
    assert store.summary().run.status == ExecutionStatus.CAPTURED
    assert store.observations()[0] == saved_answer
    assert len(store.attempts()) == (2 if pause == "after_commit" else 3)
    if pause != "after_commit":
        assert store.attempts()[1].status == ExecutionStatus.UNKNOWN_OUTCOME
        assert store.attempts()[1].failure.exception_type == "AbandonedCoordinator"
    with sqlite3.connect(tmp_path / "target.sqlite3") as db:
        assert db.execute("SELECT count(*) FROM accepted").fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM transports").fetchone()[0] == len(store.attempts())
