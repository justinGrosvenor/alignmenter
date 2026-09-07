"""Evaluation extension in the run's authoritative SQLite database."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from alignmenter.schemas.evaluation import (
    EvaluationInput,
    EvaluationManifest,
    EvaluationResult,
    JudgeBudget,
    JudgeCall,
    JudgeContract,
    JudgeReply,
    JudgeRequest,
)
from alignmenter.schemas.execution import RunManifest, content_digest, utc_now
from alignmenter.schemas.metrics import validate_samples
from alignmenter.storage.runs import RunStore

EVALUATION_DATABASE_VERSION = 1


class BudgetBlocked(ValueError):
    """A new judge dispatch cannot be reserved within the frozen budget."""


def _encode(record):
    value = record.model_dump(mode="json")
    return record.model_dump_json(), content_digest(value)


def _decode(model, row):
    payload = json.loads(row[0])
    if content_digest(payload) != row[1]:
        raise ValueError("Saved evaluation content digest mismatch")
    return model.model_validate(payload)


class EvaluationStore(RunStore):
    """Owns evaluation tables only; capture records and state remain unchanged.

    Initialization explicitly adds a versioned extension to v2 run databases.
    All mutations are coordinated with the same run lease as capture/resume.
    Budget reservation is also atomic for callers sharing this store directly.
    """

    @contextmanager
    def transaction(self, *, write=False) -> Iterator[sqlite3.Connection]:
        with self._connection(write=write) as db:
            self._check_schema(db)
            yield db

    @staticmethod
    def _check_schema(db):
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='evaluation_schema'").fetchone():
            raise ValueError("Run has no saved rubric evaluations")
        if db.execute("SELECT version FROM evaluation_schema").fetchone()[0] != EVALUATION_DATABASE_VERSION:
            raise ValueError("Unsupported evaluation database version")

    def initialize(
        self, manifest: EvaluationManifest, inputs: list[EvaluationInput],
        budget: JudgeBudget | None, *, new_evaluation: bool = False,
    ) -> EvaluationManifest:
        if content_digest([i.model_dump(mode="json") for i in inputs]) != manifest.inputs_digest:
            raise ValueError("Evaluation input digest differs from manifest")
        if len({i.key for i in inputs}) != len(inputs):
            raise ValueError("Duplicate evaluation input key")
        if manifest.run_id != self.manifest().id:
            raise ValueError("Evaluation belongs to a different capture run")
        with self._connection(write=True) as db:
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='evaluation_schema'").fetchone()
            if not exists:
                if budget is None and manifest.judge is not None:
                    raise ValueError("The first evaluation requires an explicit judge call budget")
                for sql in (
                    "CREATE TABLE evaluation_schema (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL)",
                    "CREATE TABLE judge_budget (singleton INTEGER PRIMARY KEY CHECK(singleton=1), payload TEXT NOT NULL, digest TEXT NOT NULL)",
                    "CREATE TABLE evaluation_manifests (id TEXT PRIMARY KEY, identity TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, digest TEXT NOT NULL)",
                    "CREATE TABLE evaluation_inputs (evaluation_id TEXT REFERENCES evaluation_manifests(id), key TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL, PRIMARY KEY(evaluation_id,key))",
                    "CREATE TABLE judge_calls (id TEXT PRIMARY KEY, cache_key TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, digest TEXT NOT NULL)",
                    "CREATE TABLE evaluation_results (evaluation_id TEXT NOT NULL, input_key TEXT NOT NULL, call_id TEXT REFERENCES judge_calls(id), payload TEXT NOT NULL, digest TEXT NOT NULL, PRIMARY KEY(evaluation_id,input_key), FOREIGN KEY(evaluation_id,input_key) REFERENCES evaluation_inputs(evaluation_id,key))",
                ):
                    db.execute(sql)
                db.execute("INSERT INTO evaluation_schema VALUES (1, ?)", (EVALUATION_DATABASE_VERSION,))
            self._check_schema(db)
            frozen = self._budget(db)
            if frozen is None and budget is not None:
                db.execute("INSERT INTO judge_budget VALUES (1, ?, ?)", _encode(budget))
                frozen = budget
            if frozen is None and manifest.judge is not None:
                raise ValueError("The first judged evaluation requires an explicit judge call budget")
            if budget is not None and budget != frozen:
                raise ValueError("Judge budget differs from the frozen run budget")
            if (manifest.judge is not None and frozen.max_cost_micros is not None
                    and manifest.judge.max_cost_micros_per_call is None):
                raise ValueError("Monetary budgets require an adapter-declared per-call cost upper bound")
            row = db.execute("SELECT payload,digest FROM evaluation_manifests WHERE identity=?",
                             (manifest.identity,)).fetchone()
            if row:
                existing = _decode(EvaluationManifest, row)
                if (existing.spec, existing.judge, existing.inputs_digest, existing.package_version, existing.evaluators) != (
                    manifest.spec, manifest.judge, manifest.inputs_digest, manifest.package_version, manifest.evaluators,
                ):
                    raise ValueError("Saved evaluation identity disagrees with its manifest")
                return existing
            if not new_evaluation and db.execute("SELECT 1 FROM evaluation_manifests LIMIT 1").fetchone():
                raise ValueError("Evaluation inputs, rubric, or judge changed; use new_evaluation explicitly")
            db.execute("INSERT INTO evaluation_manifests VALUES (?, ?, ?, ?)",
                       (str(manifest.id), manifest.identity, *_encode(manifest)))
            db.executemany("INSERT INTO evaluation_inputs VALUES (?, ?, ?, ?)",
                           [(str(manifest.id), i.key, *_encode(i)) for i in inputs])
            self._event(db, "evaluation_created", str(manifest.id))
        return manifest

    def manifests(self) -> list[EvaluationManifest]:
        with self.transaction() as db:
            return [_decode(EvaluationManifest, row) for row in db.execute(
                "SELECT payload,digest FROM evaluation_manifests ORDER BY rowid")]

    def evaluation_inputs(self, evaluation_id: UUID) -> list[EvaluationInput]:
        with self.transaction() as db:
            return [_decode(EvaluationInput, row) for row in db.execute(
                "SELECT payload,digest FROM evaluation_inputs WHERE evaluation_id=? ORDER BY rowid",
                (str(evaluation_id),))]

    def results(self, evaluation_id: UUID) -> list[EvaluationResult]:
        with self.transaction() as db:
            return [_decode(EvaluationResult, row) for row in db.execute(
                "SELECT payload,digest FROM evaluation_results WHERE evaluation_id=? ORDER BY rowid",
                (str(evaluation_id),))]

    def calls(self) -> list[JudgeCall]:
        with self.transaction() as db:
            return self._calls(db)

    @staticmethod
    def _calls(db):
        return [_decode(JudgeCall, row) for row in db.execute(
            "SELECT payload,digest FROM judge_calls ORDER BY rowid")]

    def budget_summary(self) -> dict:
        with self.transaction() as db:
            return self._budget_summary(db)

    def _budget_summary(self, db) -> dict:
        budget = self._budget(db)
        calls = self._calls(db)
        actual = [c.reply.actual_cost_micros if c.reply is not None else None for c in calls]
        charged = [self._charge(c) for c in calls]
        capture = RunManifest.model_validate_json(db.execute("SELECT payload FROM manifest").fetchone()[0])
        return {
            "scope": "durable_evaluations",
            "limits": budget.model_dump(mode="json") if budget is not None else None,
            "reserved_calls": len(calls),
            "known_actual_cost_micros": sum(n for n in actual if n is not None),
            "calls_with_unknown_actual_cost": sum(n is None for n in actual),
            "accounted_cost_micros": sum(charged) if all(n is not None for n in charged) else None,
            "cost_bound_violations": sum(c.status == "cost_bound_exceeded" for c in calls),
            "target": {"scope": "capture_run", "max_calls": capture.max_target_calls,
                       "reserved_calls": db.execute("SELECT count(*) FROM attempts").fetchone()[0],
                       "actual_cost_micros": None},
        }

    @staticmethod
    def _budget(db):
        row = db.execute("SELECT payload,digest FROM judge_budget").fetchone()
        if row is None and db.execute("SELECT 1 FROM judge_calls LIMIT 1").fetchone():
            raise ValueError("Saved judge calls have no frozen budget")
        return _decode(JudgeBudget, row) if row is not None else None

    def snapshot(self, evaluation_id: UUID | None = None):
        """Read one consistent snapshot even while another process records results."""
        with self.transaction() as db:
            row = db.execute(
                "SELECT payload,digest FROM evaluation_manifests WHERE (? IS NULL OR id=?) ORDER BY rowid DESC LIMIT 1",
                (str(evaluation_id) if evaluation_id else None, str(evaluation_id)),
            ).fetchone()
            if row is None:
                raise ValueError("Unknown evaluation ID")
            manifest = _decode(EvaluationManifest, row)
            input_rows = db.execute(
                "SELECT payload,digest FROM evaluation_inputs WHERE evaluation_id=? ORDER BY rowid",
                (str(manifest.id),)).fetchall()
            # Hash the actual saved wire representation, before adding schema defaults.
            if content_digest([json.loads(row[0]) for row in input_rows]) != manifest.inputs_digest:
                raise ValueError("Saved evaluation input digest mismatch")
            inputs = [_decode(EvaluationInput, row) for row in input_rows]
            results = [_decode(EvaluationResult, row) for row in db.execute(
                "SELECT payload,digest FROM evaluation_results WHERE evaluation_id=? ORDER BY rowid",
                (str(manifest.id),))]
            return manifest, inputs, results, self._budget_summary(db), self._calls(db)

    @staticmethod
    def _charge(call):
        if call.reply is not None and call.reply.actual_cost_micros is not None:
            return call.reply.actual_cost_micros
        return call.reserved_cost_micros

    def reserve(self, request: JudgeRequest, judge: JudgeContract) -> tuple[JudgeCall, bool]:
        """Return an existing call, or atomically charge and create one new dispatch."""
        key = content_digest({"request": request.model_dump(mode="json"),
                              "judge": judge.model_dump(mode="json")})
        with self.transaction(write=True) as db:
            row = db.execute("SELECT payload,digest FROM judge_calls WHERE cache_key=?", (key,)).fetchone()
            if row:
                return _decode(JudgeCall, row), False
            budget = self._budget(db)
            if budget is None:
                raise BudgetBlocked("Judge budget is not configured")
            calls = self._calls(db)
            if len(calls) >= budget.max_calls:
                raise BudgetBlocked("Run judge call budget exhausted")
            if any(c.status == "cost_bound_exceeded" for c in calls):
                raise BudgetBlocked("Judge exceeded a declared cost bound; further dispatch is blocked")
            upper = judge.max_cost_micros_per_call
            if budget.max_cost_micros is not None:
                charges = [self._charge(c) for c in calls]
                if upper is None or any(c is None for c in charges):
                    raise BudgetBlocked("Cannot reserve a judge call with an unknown cost upper bound")
                if sum(charges) + upper > budget.max_cost_micros:
                    raise BudgetBlocked("Run judge cost budget exhausted")
            call = JudgeCall(cache_key=key, judge=judge, request=request, reserved_cost_micros=upper)
            db.execute("INSERT INTO judge_calls VALUES (?, ?, ?, ?)",
                       (str(call.id), key, *_encode(call)))
            self._event(db, "judge_call_reserved", str(call.id))
            return call, True

    def finish_call(self, call_id: UUID, *, reply: JudgeReply | None = None,
                    exception_type: str | None = None, invalid: bool = False) -> JudgeCall:
        with self.transaction(write=True) as db:
            row = db.execute("SELECT payload,digest FROM judge_calls WHERE id=?", (str(call_id),)).fetchone()
            if row is None:
                raise ValueError("Unknown judge call")
            previous = _decode(JudgeCall, row)
            if previous.status != "running":
                raise ValueError("A terminal judge call cannot be changed")
            status = "response_saved" if reply is not None else "invalid_response" if invalid else "unknown_outcome"
            if (reply is not None and reply.actual_cost_micros is not None
                    and previous.reserved_cost_micros is not None
                    and reply.actual_cost_micros > previous.reserved_cost_micros):
                status = "cost_bound_exceeded"
            ended = JudgeCall.model_validate({**previous.model_dump(), "status": status,
                                             "reply": reply, "exception_type": exception_type,
                                             "finished_at": utc_now()})
            db.execute("UPDATE judge_calls SET payload=?,digest=? WHERE id=?", (*_encode(ended), str(call_id)))
            self._event(db, "judge_call_finished", str(call_id))
            return ended

    def abandon_calls(self) -> None:
        """Caller holds the run lease; never redispatch an abandoned reservation."""
        with self.transaction(write=True) as db:
            for call in self._calls(db):
                if call.status == "running":
                    ended = JudgeCall.model_validate({**call.model_dump(), "status": "unknown_outcome",
                                                     "exception_type": "AbandonedCoordinator",
                                                     "finished_at": utc_now()})
                    db.execute("UPDATE judge_calls SET payload=?,digest=? WHERE id=?",
                               (*_encode(ended), str(call.id)))
                    self._event(db, "judge_call_abandoned", str(call.id))

    def save_result(self, result: EvaluationResult) -> None:
        with self.transaction(write=True) as db:
            row = db.execute("SELECT payload,digest FROM evaluation_inputs WHERE evaluation_id=? AND key=?",
                             (str(result.evaluation_id), result.input_key)).fetchone()
            if row is None:
                raise ValueError("Evaluation result has no frozen input")
            item = _decode(EvaluationInput, row)
            evaluation = _decode(EvaluationManifest, db.execute(
                "SELECT payload,digest FROM evaluation_manifests WHERE id=?", (str(result.evaluation_id),)).fetchone())
            descriptor = next((d for d in evaluation.evaluators if d.id == item.evaluator), None)
            if descriptor is not None and result.assessment is not None:
                validate_samples(result.metrics, descriptor.metrics)
            elif result.metrics:
                raise ValueError("Only an assessment with registered metrics can save metric samples")
            if item.unavailable is not None and result.status != item.unavailable:
                raise ValueError("Unavailable result disagrees with its frozen input")
            if result.status in {"missing_capture", "missing_evidence"}:
                if item.unavailable != result.status or result.call_id is not None:
                    raise ValueError("Unavailable result disagrees with its frozen input")
            elif item.evaluator not in {"rubric", "faithfulness"}:
                expected = "grounding" if item.evaluator == "grounding" else "custom"
                if (result.call_id is not None or result.status == "budget_blocked"
                        or result.status != "invalid" and (result.assessment is None or result.assessment.kind != expected)):
                    raise ValueError("Grounding requires a deterministic assessment without a judge call")
            elif result.status != "budget_blocked":
                call_row = db.execute("SELECT payload,digest FROM judge_calls WHERE id=?",
                                      (str(result.call_id),)).fetchone()
                if call_row is None:
                    raise ValueError("Evaluated result requires a saved judge call")
                call = _decode(JudgeCall, call_row)
                manifest = _decode(EvaluationManifest, db.execute(
                    "SELECT payload,digest FROM evaluation_manifests WHERE id=?",
                    (str(result.evaluation_id),)).fetchone())
                if call.request != item.request or call.judge != manifest.judge or call.status == "running":
                    raise ValueError("Result has no matching terminal judge request")
                if (result.verdict is not None or result.assessment is not None) and call.status != "response_saved":
                    raise ValueError("Valid verdict requires a saved judge response")
                if result.assessment is not None and result.assessment.kind != item.evaluator:
                    raise ValueError("Assessment type differs from its frozen evaluator")
                if result.verdict is not None and item.evaluator != "rubric":
                    raise ValueError("Built-in evaluators cannot save generic rubric verdicts")
            elif result.call_id is not None:
                raise ValueError("Budget-blocked results cannot reference a dispatched call")
            db.execute("INSERT INTO evaluation_results VALUES (?, ?, ?, ?, ?)",
                       (str(result.evaluation_id), result.input_key,
                        str(result.call_id) if result.call_id is not None else None, *_encode(result)))
            self._event(db, "evaluation_result_saved", str(result.id))
