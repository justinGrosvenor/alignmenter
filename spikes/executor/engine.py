"""Shared target guards plus two scheduling options for the same acceptance tests."""

from __future__ import annotations

import fcntl
import json
import os
import sqlite3
from contextlib import ExitStack, contextmanager
from pathlib import Path

from .store import Store, canonical, digest


def barrier(name: str) -> None:
    if os.environ.get("SPIKE_BARRIER") == name:
        print("SPIKE_BARRIER", flush=True)
        os.read(0, 1)


class FixtureTarget:
    """Independent durable target acceptance log; never uses the coordinator DB."""

    def __init__(self, root: Path):
        self.path = root / "target.sqlite"
        with sqlite3.connect(self.path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, kind TEXT, payload TEXT)"
            )

    def event(self, kind: str, payload: dict) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO events VALUES (NULL, ?, ?)", (kind, canonical(payload)))

    def reconcile(self) -> None:
        # This local fixture acknowledges reset/quiescence synchronously. A physical
        # adapter must actually verify cancellation and idle state before takeover.
        self.event("reconcile", {})

    def reset(self, session: str) -> None:
        self.event("reset", {"session": session})

    def ask(self, case: dict, turn: int, session: str, request: str, history: list) -> dict:
        self.event(
            "accepted",
            {
                "sample": case["id"],
                "turn": turn,
                "session": session,
                "request": request,
                "question": case["turns"][turn],
                "history": history,
            },
        )
        barrier(f"accepted:{case['id']}:{turn}")
        if case.get("timeout_turn") == turn:
            raise TimeoutError("classified local fixture timeout")
        response = {"request": request, "answer": f"answer:{case['id']}:{turn}", "usage": None}
        if case.get("wrong_request"):
            response["request"] = "stale-request-from-an-earlier-identical-question"
        if "evidence" in case:
            response["evidence"] = case["evidence"]
        return response


@contextmanager
def resource_lease(root: Path, resource: str):
    # Sibling run directories share the fixture's device namespace. Production needs
    # a configured host-wide resource directory and an actual adapter reconciliation.
    with ExitStack() as stack:
        for path in [root / "coordinator.lock", root.parent / f"device-{digest(resource)}.lock"]:
            lock = stack.enter_context(path.open("a"))
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError("Device resource already owned") from exc
        yield


def execute_sample(store: Store, sample_id: str) -> None:
    case = json.loads(store.sample(sample_id)["case_json"])
    target = FixtureTarget(store.root)
    attempt, session = store.start(sample_id)
    target.reset(session)
    history: list[dict] = []
    for turn, question in enumerate(case["turns"]):
        request = store.reserve("target", f"{attempt}:{turn}")
        if request is None:
            store.finish(attempt, "skipped_budget")
            return
        try:
            response = target.ask(case, turn, session, request, history)
        except TimeoutError:
            store.finish(attempt, "failed")
            return
        if response["request"] != request:
            store.finish(attempt, "failed")
            return
        if not store.record(attempt, turn, response, final=turn == len(case["turns"]) - 1):
            return
        store.settle(request, response)
        history.extend(
            [{"role": "user", "text": question}, {"role": "assistant", "text": response["answer"]}]
        )
        barrier(f"committed:{sample_id}:{turn}")


def run(root: Path, backend: str) -> None:
    store = Store(root)
    with resource_lease(root, store.config().get("resource", "fixture-device")):
        target = FixtureTarget(root)
        target.reconcile()
        store.recover()
        barrier("before_dispatch")
        pending = [s for s in store.samples() if s["status"] == "pending"]
        if backend == "native":
            for sample in pending:
                execute_sample(store, sample["id"])
        elif pending:
            from inspect_ai import eval

            from .inspect_tasks import guarded_probe

            # Inspect schedules work; it cannot silently retry this external target.
            eval(
                guarded_probe(str(root)),
                model="mockllm/model",
                display="none",
                log_dir=str(root / "inspect-logs"),
                max_samples=1,
                log_buffer=1,
                log_realtime=False,
                score=False,
                retry_on_error=0,
                ctl_server=False,
                acp_server=False,
            )


def judge(
    store: Store, sample_id: str, observation: dict, raw_verdict: dict, repeat: str | None = None
) -> dict:
    """Small strict support fixture; not a qualified semantic evaluator."""
    observed = digest(observation)
    status, verdict = "scored", None
    evidence = observation.get("evidence")
    if evidence is None or evidence.get("capture") != "complete":
        status = "missing_evidence"
    elif not evidence["excerpts"]:
        status = "not_applicable"
    else:
        cache_key = digest(
            {"observation": observation, "evaluator": "fixture-v1", "repeat": repeat}
        )
        result = store.cached(cache_key) if repeat is None else None
        if result is None:
            call = store.reserve("judge", cache_key)
            if call is None:
                status = "skipped_budget"
            else:
                FixtureTarget(store.root).event("judge_accepted", {"request": call})
                barrier("judge_accepted")
                result = raw_verdict
                # Invalid results are charged but not put into the successful cache.
                if set(result) == {"supported"} and type(result["supported"]) is bool:
                    store.settle(call, result)
                else:
                    store.reject_verdict(call, result)
                    status = "invalid_result"
        if result is not None and status == "scored":
            verdict = "met" if result["supported"] else "violated"
    result_id = store.evaluation(sample_id, observed, status, verdict)
    return {"id": result_id, "status": status, "verdict": verdict}


def report(store: Store, sample_ids: list[str] | None = None) -> dict:
    """Pure saved-result projection. Real HTML/CI renderers are outside the spike."""
    samples = [s for s in store.samples() if sample_ids is None or s["id"] in sample_ids]
    results = store.rows("evaluations")
    observations = store.rows("observations")
    selected = {}
    for sample in samples:
        current = {o["digest"] for o in observations if o["attempt"] == sample["selected"]}
        selected[sample["id"]] = next(
            (
                r
                for r in reversed(results)
                if r["sample"] == sample["id"] and r["observation_digest"] in current
            ),
            None,
        )
    scored = [r for r in selected.values() if r and r["status"] == "scored"]
    failures = sum(r["verdict"] == "violated" for r in scored)
    complete = sum(s["status"] == "succeeded" for s in samples)
    decision = (
        "fail"
        if failures
        else "pass"
        if samples and complete == len(samples) == len(scored)
        else "inconclusive"
    )
    return {
        "planned": len(samples),
        "completed": complete,
        "scored": len(scored),
        "violations": failures,
        "decision": decision,
        "results": selected,
    }


def compare(left: dict, right: dict) -> dict:
    pairs = [(key, value, right["results"].get(key)) for key, value in left["results"].items()]
    comparable = [
        (key, a, b) for key, a, b in pairs if a and b and a["status"] == b["status"] == "scored"
    ]
    return {
        "pairs": len(comparable),
        "missing": len(pairs) - len(comparable),
        "changed": [key for key, a, b in comparable if a["verdict"] != b["verdict"]],
    }
