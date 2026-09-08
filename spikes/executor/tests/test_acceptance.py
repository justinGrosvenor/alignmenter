"""The same E01–E14 assertions for both scheduling choices, with real child death."""

from __future__ import annotations

import json
import os
import selectors
import shutil
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Barrier

import pytest

from spikes.executor.engine import compare, judge, report
from spikes.executor.store import Store, canonical

REPO = Path(__file__).resolve().parents[3]
EVIDENCE = {"capture": "complete", "excerpts": [{"id": "s1", "text": "Synthetic fixture."}]}


@pytest.fixture(params=["native", "inspect"])
def backend(request):
    return request.param


def make_store(root: Path, cases=None, **options) -> Store:
    cases = cases or [
        {"id": name, "turns": ["same question"], "safe_restart": True, "evidence": EVIDENCE}
        for name in ("A", "B", "C")
    ]
    store = Store(root)
    store.create({"cases": cases, "judge_budget": 20, "target_version": "fixture-v1", **options})
    return store


def command(backend, root):
    return [sys.executable, "-m", "spikes.executor.worker", backend, str(root)]


def invoke(backend, root):
    result = subprocess.run(
        command(backend, root), cwd=REPO, capture_output=True, text=True, timeout=40
    )
    (root / "last-worker.stdout").write_text(result.stdout)
    (root / "last-worker.stderr").write_text(result.stderr)
    assert result.returncode == 0, result.stderr


@contextmanager
def paused(backend, root, barrier, extra_args=()):
    env = {**os.environ, "SPIKE_BARRIER": barrier}
    with (root / "paused-worker.stderr").open("w") as err:
        process = subprocess.Popen(
            command(backend, root) + list(extra_args),
            cwd=REPO,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=err,
        )
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        received = b""
        deadline = time.monotonic() + 40
        try:
            while b"SPIKE_BARRIER" not in received:
                assert selector.select(max(0, deadline - time.monotonic())), "Barrier timeout"
                part = os.read(process.stdout.fileno(), 65536)
                assert part, (root / "paused-worker.stderr").read_text()
                received += part
            yield process
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            (root / "paused-worker.stdout").write_bytes(received)
            selector.close()
            process.stdin.close()
            process.stdout.close()


def kill_at(backend, root, barrier):
    with paused(backend, root, barrier) as process:
        process.kill()
        process.wait(timeout=10)
        assert process.returncode == -9


def target_events(root: Path, kind="accepted"):
    if not (root / "target.sqlite").exists():
        return []
    with sqlite3.connect(root / "target.sqlite") as db:
        return [
            json.loads(row[0])
            for row in db.execute("SELECT payload FROM events WHERE kind=? ORDER BY seq", (kind,))
        ]


def observation(store: Store, sample_id: str):
    attempt = store.sample(sample_id)["selected"]
    return json.loads(
        next(r for r in store.rows("observations") if r["attempt"] == attempt)["payload"]
    )


def test_E01_before_dispatch(tmp_path, backend):
    store = make_store(tmp_path / "run")
    kill_at(backend, store.root, "before_dispatch")
    assert len(store.samples()) == 3
    assert {s["status"] for s in store.samples()} == {"pending"}
    assert store.config()["target_version"] == "fixture-v1"
    assert not target_events(store.root)


def test_E02_committed_answer_survives_sigkill(tmp_path, backend):
    store = make_store(tmp_path / "run")
    kill_at(backend, store.root, "accepted:B:0")
    original = store.rows("observations")[0]
    invoke(backend, store.root)
    assert store.rows("observations")[0] == original
    calls = target_events(store.root)
    assert [c["sample"] for c in calls] == ["A", "B", "B", "C"]
    assert {s["status"] for s in store.samples()} == {"succeeded"}
    assert len([a for a in store.rows("attempts") if a["status"] == "unknown_outcome"]) == 1


def test_E03_unknown_action_is_not_replayed(tmp_path, backend):
    store = make_store(
        tmp_path / "run",
        cases=[
            {"id": name, "turns": ["same question"], "safe_restart": name != "B"}
            for name in ("A", "B", "C")
        ],
    )
    kill_at(backend, store.root, "accepted:B:0")
    invoke(backend, store.root)
    assert store.sample("B")["status"] == "unknown_outcome"
    assert [c["sample"] for c in target_events(store.root)] == ["A", "B", "C"]
    assert report(store)["decision"] == "inconclusive"


def test_committed_final_answer_does_not_dispatch_again(tmp_path, backend):
    store = make_store(tmp_path / "run")
    kill_at(backend, store.root, "committed:A:0")
    original = store.rows("observations")[0]
    invoke(backend, store.root)
    assert [c["sample"] for c in target_events(store.root)] == ["A", "B", "C"]
    assert store.rows("observations")[0] == original
    assert store.sample("A")["selected"] == original["attempt"]


def test_E04_late_response_does_not_replace_retry(tmp_path, backend):
    store = make_store(tmp_path / "run")
    kill_at(backend, store.root, "accepted:B:0")
    old = store.sample("B")["selected"]
    with paused(backend, store.root, "accepted:B:0") as process:
        new = store.sample("B")["selected"]
        assert new != old
        assert not store.record(old, 0, {"answer": "late old answer"})
        process.stdin.write(b"x")
        process.stdin.flush()
        assert process.wait(timeout=40) == 0
    assert observation(store, "B")["answer"] == "answer:B:0"
    assert any(e["kind"] == "late_response" for e in store.rows("events"))


def test_E05_device_owned_across_two_runs_and_reconciled(tmp_path, backend):
    first = make_store(tmp_path / "first")
    second = make_store(tmp_path / "second")
    with paused(backend, first.root, "accepted:A:0"):
        result = subprocess.run(
            command(backend, second.root), cwd=REPO, capture_output=True, text=True, timeout=40
        )
        assert result.returncode != 0
        assert "Device resource already owned" in result.stderr
        assert not target_events(second.root)
    invoke(backend, second.root)
    with sqlite3.connect(second.root / "target.sqlite") as db:
        kinds = [row[0] for row in db.execute("SELECT kind FROM events ORDER BY seq")]
    assert kinds[0] == "reconcile"
    assert kinds.index("reconcile") < kinds.index("accepted")


def test_E06_identical_questions_and_stale_request_echo(tmp_path, backend):
    store = make_store(
        tmp_path / "run",
        cases=[
            {"id": name, "turns": ["same question"], "wrong_request": name == "C"}
            for name in ("A", "B", "C")
        ],
    )
    invoke(backend, store.root)
    calls = target_events(store.root)
    assert len({c["request"] for c in calls}) == 3
    assert len({c["session"] for c in calls}) == 3
    assert observation(store, "A")["request"] != observation(store, "B")["request"]
    assert store.sample("C")["status"] == "failed"
    assert len(store.rows("observations")) == 2


def test_E07_restart_session_at_safe_boundary(tmp_path, backend):
    store = make_store(
        tmp_path / "run",
        cases=[
            {
                "id": "A",
                "turns": ["No rope available.", "Simplify the plan."],
                "safe_restart": True,
            },
        ],
    )
    kill_at(backend, store.root, "accepted:A:1")
    invoke(backend, store.root)
    calls = target_events(store.root)
    assert [c["turn"] for c in calls] == [0, 1, 0, 1]
    assert calls[0]["session"] == calls[1]["session"]
    assert calls[2]["session"] == calls[3]["session"] != calls[0]["session"]
    assert calls[2]["history"] == []
    assert calls[3]["history"] == [
        {"role": "user", "text": "No rope available."},
        {"role": "assistant", "text": "answer:A:0"},
    ]
    assert len(store.rows("calls")) == 4
    assert len(store.rows("observations")) == 3


def test_E08_racing_judges_share_durable_cap(tmp_path, backend):
    store = make_store(tmp_path / "run", judge_budget=1)
    invoke(backend, store.root)
    start = Barrier(2)

    def evaluate(sample_id):
        start.wait(timeout=10)
        return judge(
            Store(store.root), sample_id, observation(store, sample_id), {"supported": True}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(evaluate, ["A", "B"]))
    assert sorted(r["status"] for r in results) == ["scored", "skipped_budget"]
    assert len(target_events(store.root, "judge_accepted")) == 1
    invoke(backend, store.root)
    result = judge(Store(store.root), "C", observation(store, "C"), {"supported": True})
    assert result["status"] == "skipped_budget"
    assert len(target_events(store.root, "judge_accepted")) == 1
    assert report(store)["decision"] == "inconclusive"


def test_E09_cache_and_intentional_repetition(tmp_path, backend):
    store = make_store(tmp_path / "run")
    invoke(backend, store.root)
    obs = observation(store, "A")
    first = judge(store, "A", obs, {"supported": True})
    cached = judge(Store(store.root), "A", obs, {"supported": False})
    assert first["verdict"] == cached["verdict"] == "met"
    assert len(target_events(store.root, "judge_accepted")) == 1
    repeated = judge(store, "A", obs, {"supported": False}, repeat="repeat-2")
    assert repeated["verdict"] == "violated"
    assert len(target_events(store.root, "judge_accepted")) == 2
    assert len(store.rows("evaluations")) == 3


def test_E10_unavailable_evidence_invalid_verdict_and_timeout(tmp_path, backend):
    store = make_store(
        tmp_path / "run",
        cases=[
            {"id": "missing", "turns": ["q"]},
            {"id": "empty", "turns": ["q"], "evidence": {"capture": "complete", "excerpts": []}},
            {"id": "invalid", "turns": ["q"], "evidence": EVIDENCE},
            {"id": "timeout", "turns": ["q"], "timeout_turn": 0},
        ],
    )
    invoke(backend, store.root)
    results = [
        judge(store, name, observation(store, name), {}) for name in ("missing", "empty", "invalid")
    ]
    assert [r["status"] for r in results] == [
        "missing_evidence",
        "not_applicable",
        "invalid_result",
    ]
    assert all(r["verdict"] is None for r in results)
    assert store.sample("timeout")["status"] == "failed"
    assert report(store)["scored"] == 0
    assert report(store)["decision"] == "inconclusive"


def test_E11_saved_reporting_comparison_and_exports_are_pure(tmp_path, backend, monkeypatch):
    store = make_store(tmp_path / "run")
    invoke(backend, store.root)
    for name in ("A", "B"):
        judge(store, name, observation(store, name), {"supported": name == "A"})
    calls_before = target_events(store.root, "judge_accepted")
    report_before = report(store)

    def unexpected_dispatch(*args, **kwargs):
        raise AssertionError("Reporting attempted a fresh dispatch")

    monkeypatch.setattr(Store, "reserve", unexpected_dispatch)
    for index in range(2):
        assert report(Store(store.root)) == report_before
        assert report(store, ["A"])["decision"] == "pass"
        assert report(store, ["C"])["decision"] == "inconclusive"
        assert compare(report_before, report(store)) == {"pairs": 2, "missing": 1, "changed": []}
        destination = tmp_path / f"export-{index}"
        store.export(destination)
        Store.verify_export(destination)
        assert report(Store(destination)) == report_before
    assert target_events(store.root, "judge_accepted") == calls_before
    assert report_before["decision"] == "fail"


def test_E12_portable_partial_run_without_original_logs_or_buffers(tmp_path, backend):
    store = make_store(tmp_path / "run")
    kill_at(backend, store.root, "accepted:B:0")
    first = store.rows("observations")[0]
    destination = tmp_path / "export"
    store.export(destination)
    Store.verify_export(destination)
    shutil.rmtree(store.root)  # This test's own isolated temporary run only.
    invoke(backend, destination)
    imported = Store(destination)
    assert imported.rows("observations")[0] == first
    assert [c["sample"] for c in target_events(destination)] == ["B", "C"]
    assert {s["status"] for s in imported.samples()} == {"succeeded"}
    assert any(a["status"] == "unknown_outcome" for a in imported.rows("attempts"))


def test_E13_configuration_change_cannot_resume(tmp_path, backend):
    store = make_store(tmp_path / "run")
    kill_at(backend, store.root, "accepted:B:0")
    before = target_events(store.root)
    with pytest.raises(ValueError, match="Incompatible run configuration"):
        Store(store.root).create({**store.config(), "target_version": "fixture-v2"})
    assert target_events(store.root) == before


def test_E14_retry_does_not_inherit_old_context_or_usage(tmp_path, backend):
    store = make_store(tmp_path / "run", cases=[{"id": "A", "turns": ["q"]}])
    old, _ = store.start("A")
    store.record(old, 0, {"answer": "old", "evidence": EVIDENCE, "usage": {"tokens": 999}})
    judge(store, "A", json.loads(store.rows("observations")[0]["payload"]), {"supported": True})
    store.finish(old, "failed")
    store.retry("A")
    invoke(backend, store.root)
    new = observation(store, "A")
    assert "evidence" not in new and new["usage"] is None
    assert len(store.rows("observations")) == 2
    assert report(store)["scored"] == 0  # The old judgment is not selected for the new output.
    assert report(store)["decision"] == "inconclusive"


def test_unknown_cost_and_reserved_dispatch_remain_unknown(tmp_path, backend):
    store = make_store(tmp_path / "run", judge_budget=1)
    invoke(backend, store.root)
    # Kill after the independent judge boundary accepts the request, before settlement.
    with paused(backend, store.root, "judge_accepted", extra_args=["--judge", "A"]):
        assert len(target_events(store.root, "judge_accepted")) == 1
    reloaded = Store(store.root)
    result = subprocess.run(
        command(backend, store.root) + ["--judge", "B"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=40,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "skipped_budget"
    assert len(target_events(store.root, "judge_accepted")) == 1
    row = next(r for r in reloaded.rows("calls") if r["kind"] == "judge")
    assert row["status"] == "reserved" and row["actual_cost_micros"] is None


def test_cost_reservations_use_bounds_and_record_actuals(tmp_path, backend):
    store = make_store(tmp_path / "run", judge_cost_limit_micros=60)
    invoke(backend, store.root)
    # Synthetic tariff: input tokens cost 2 units; output tokens cost 3 units.
    # Five input tokens, maximum ten output tokens -> upper bound of 40 units.
    bound = 5 * 2 + 10 * 3
    first = store.reserve("judge", "first", upper_cost_micros=bound)
    assert first is not None
    assert Store(store.root).reserve("judge", "parallel", upper_cost_micros=bound) is None
    store.settle(first, {"supported": True}, actual_cost_micros=5 * 2 + 2 * 3)
    second = store.reserve("judge", "second", upper_cost_micros=bound)
    assert second is not None  # 16 actual + 40 reserved fits in 60.
    assert store.reserve("judge", "unpriced") is None
    assert store.reserve("judge", "third", upper_cost_micros=5) is None
    assert Store(store.root).reserve("judge", "after-restart", upper_cost_micros=5) is None
    # A violated provider bound must be reported honestly, even after overspend.
    store.settle(second, {"supported": True}, actual_cost_micros=50)
    row = next(r for r in store.rows("calls") if r["id"] == second)
    assert row["status"] == "cost_bound_exceeded" and row["actual_cost_micros"] == 50
    assert store.reserve("judge", "overspent", upper_cost_micros=0) is None


def test_strict_boolean_and_export_integrity(tmp_path, backend):
    store = make_store(tmp_path / "run")
    invoke(backend, store.root)
    invalid = judge(store, "A", observation(store, "A"), {"supported": "false"})
    assert invalid["status"] == "invalid_result" and invalid["verdict"] is None
    raw = next(r for r in store.rows("calls") if r["kind"] == "judge")
    assert raw["status"] == "invalid_result"
    assert json.loads(raw["result"]) == {"supported": "false"}
    destination = tmp_path / "export"
    store.export(destination)
    manifest = json.loads((destination / "manifest.json").read_text())
    manifest["sha256"] = "0" * 64
    (destination / "manifest.json").write_text(canonical(manifest))
    with pytest.raises(ValueError, match="digest"):
        Store.verify_export(destination)
