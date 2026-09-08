"""Public Inspect extension points used by the spike; no private imports."""

from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import ModelOutput
from inspect_ai.solver import Generate, TaskState, solver


@solver
def raw_target(root: str):
    """An external target boundary, intentionally without Alignmenter's guards."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        with sqlite3.connect(Path(root) / "target.sqlite") as db:
            db.execute("CREATE TABLE IF NOT EXISTS calls (sample TEXT, request TEXT)")
            db.execute("INSERT INTO calls VALUES (?, ?)", (str(state.sample_id), uuid.uuid4().hex))
        from .engine import barrier

        barrier(f"accepted:{state.sample_id}:0")
        state.output = ModelOutput.from_content("external-fixture", f"answer:{state.sample_id}")
        state.metadata["capture"] = "complete"
        state.metadata["excerpts"] = []
        return state

    return solve


@task
def raw_probe(root: str):
    return Task(
        dataset=[Sample(id=name, input="same question") for name in ("A", "B", "C")],
        solver=raw_target(root),
    )


@solver
def guarded_target(root: str):
    from .engine import execute_sample
    from .store import Store

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        store = Store(Path(root))
        execute_sample(store, str(state.sample_id))
        sample = store.sample(str(state.sample_id))
        state.metadata["alignmenter_status"] = sample["status"]
        state.metadata["alignmenter_attempt"] = sample["selected"]
        state.output = ModelOutput.from_content("external-fixture", sample["status"])
        return state

    return solve


@task
def guarded_probe(root: str):
    from .store import Store

    store = Store(Path(root))
    # The ledger is authoritative; Inspect logs are diagnostic derivative artifacts.
    samples = [
        Sample(id=s["id"], input=json.loads(s["case_json"])["turns"][0])
        for s in store.samples()
        if s["status"] == "pending"
    ]
    return Task(dataset=samples, solver=guarded_target(root))
