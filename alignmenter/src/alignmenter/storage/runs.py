"""Transactional execution records with immutable observations and source snapshots."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

from alignmenter.schemas.execution import (
    Attempt,
    ExecutionStatus,
    ExecutionSummary,
    FailureInfo,
    JsonObject,
    Observation,
    PlannedTurn,
    RunManifest,
    RunPhase,
    RunRecord,
    Stream,
    canonical_json_bytes,
    content_digest,
    utc_now,
)

DATABASE_NAME = "run.sqlite3"
DATABASE_VERSION = 2


class TargetBudgetBlocked(ValueError):
    """No new target attempt fits the immutable run call limit."""


class RunStore:
    """One database per run. Readers never create or silently migrate a database."""

    def __init__(self, run_dir: Path):
        self.run_dir = Path(run_dir)
        self.path = self.run_dir / DATABASE_NAME

    @classmethod
    def create(
        cls,
        run_dir: Path,
        manifest: RunManifest,
        plan: list[PlannedTurn],
        *,
        dataset: list[JsonObject],
        persona: bytes | None = None,
    ) -> RunStore:
        keys = [(turn.stream, turn.ordinal) for turn in plan]
        if len(set(keys)) != len(keys):
            raise ValueError("Duplicate planned turn identity")
        streams = [target.stream for target in manifest.targets]
        if len(streams) != len(set(streams)) or not set(t.stream for t in plan) <= set(streams):
            raise ValueError("Plan and target streams disagree")
        if content_digest(dataset) != manifest.dataset_digest:
            raise ValueError("Dataset snapshot digest does not match manifest")
        if manifest.plan_digest is not None and content_digest([
            t.model_dump(mode="json") for t in sorted(plan, key=lambda t: (t.stream, t.ordinal))
        ]) != manifest.plan_digest:
            raise ValueError("Frozen plan digest does not match manifest")
        expected_records = Counter(content_digest(record) for record in dataset)
        for target in manifest.targets:
            turns = sorted((t for t in plan if t.stream == target.stream), key=lambda t: t.ordinal)
            if [t.ordinal for t in turns] != list(range(len(dataset))):
                raise ValueError("Planned ordinals must cover every source record")
            if Counter(content_digest(t.record) for t in turns) != expected_records:
                raise ValueError("Frozen plan differs from the source dataset")
            if any(
                t.generate != (target.mode == "generate" and t.role == "assistant") for t in turns
            ):
                raise ValueError("Planned generation disagrees with target mode")
        if (
            hashlib.sha256(persona).hexdigest() if persona is not None else None
        ) != manifest.persona_digest:
            raise ValueError("Persona snapshot digest does not match manifest")
        # Serialize all user/provider-independent inputs before creating durable state.
        manifest_json = manifest.model_dump_json()
        plan_json = [(t.stream, t.ordinal, t.model_dump_json()) for t in plan]
        content_digest(manifest.model_dump(mode="json"))
        for turn in plan:
            content_digest(turn.model_dump(mode="json"))
        store = cls(run_dir)
        store.run_dir.mkdir(parents=True, exist_ok=True)
        fd = os.open(store.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
        try:
            with store._connection(write=True, check_version=False) as db:
                for sql in (
                    "CREATE TABLE manifest (singleton INTEGER PRIMARY KEY CHECK(singleton=1), payload TEXT NOT NULL)",
                    "CREATE TABLE run_state (singleton INTEGER PRIMARY KEY CHECK(singleton=1), payload TEXT NOT NULL)",
                    "CREATE TABLE inputs (stream TEXT NOT NULL, ordinal INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(stream,ordinal))",
                    "CREATE TABLE attempts (id TEXT PRIMARY KEY, stream TEXT NOT NULL, ordinal INTEGER NOT NULL, payload TEXT NOT NULL, FOREIGN KEY(stream,ordinal) REFERENCES inputs(stream,ordinal))",
                    "CREATE INDEX attempts_turn ON attempts(stream,ordinal)",
                    "CREATE TABLE observations (id TEXT PRIMARY KEY, stream TEXT NOT NULL, ordinal INTEGER NOT NULL, attempt_id TEXT REFERENCES attempts(id), payload TEXT NOT NULL, digest TEXT NOT NULL, UNIQUE(stream,ordinal), FOREIGN KEY(stream,ordinal) REFERENCES inputs(stream,ordinal))",
                    "CREATE TABLE records (stream TEXT NOT NULL, ordinal INTEGER NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(stream,ordinal), FOREIGN KEY(stream,ordinal) REFERENCES inputs(stream,ordinal))",
                    "CREATE TABLE source_artifacts (digest TEXT PRIMARY KEY, content BLOB NOT NULL)",
                    "CREATE TABLE events (sequence INTEGER PRIMARY KEY, kind TEXT NOT NULL, recorded_at TEXT NOT NULL, reference TEXT)",
                ):
                    db.execute(sql)
                db.execute(f"PRAGMA user_version={DATABASE_VERSION}")
                db.execute("INSERT INTO manifest VALUES (1, ?)", (manifest_json,))
                db.execute(
                    "INSERT INTO run_state VALUES (1, ?)",
                    (RunRecord(id=manifest.id).model_dump_json(),),
                )
                db.executemany("INSERT INTO inputs VALUES (?, ?, ?)", plan_json)
                db.execute(
                    "INSERT INTO source_artifacts VALUES (?, ?)",
                    (manifest.dataset_digest, canonical_json_bytes(dataset)),
                )
                if persona is not None:
                    db.execute(
                        "INSERT OR IGNORE INTO source_artifacts VALUES (?, ?)",
                        (manifest.persona_digest, persona),
                    )
                store._event(db, "run_created", str(manifest.id))
        except BaseException:
            # No provider work can have started, and this is the exclusively created file.
            store.path.unlink(missing_ok=True)
            raise
        return store

    @contextmanager
    def _connection(
        self, *, write: bool = False, check_version: bool = True
    ) -> Iterator[sqlite3.Connection]:
        if not self.path.is_file():
            raise FileNotFoundError(f"No durable run database at {self.path}")
        uri = self.path.resolve().as_uri() + ("?mode=rw" if write else "?mode=ro")
        db = sqlite3.connect(uri, uri=True, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            if check_version:
                database_version = db.execute("PRAGMA user_version").fetchone()[0]
                if database_version not in {1, DATABASE_VERSION}:
                    raise ValueError("Unsupported run database version; explicit migration is required")
                if write and database_version != DATABASE_VERSION:
                    raise ValueError("Version 1 runs are read-only; export transcripts to start a new run")
                if write and db.execute("SELECT 1 FROM sqlite_master WHERE name='imported_archive'").fetchone():
                    raise ValueError("Imported archives are read-only; return annotations to the owner or capture a new run")
            if write:
                db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _event(db: sqlite3.Connection, kind: str, reference: str | None = None) -> None:
        db.execute(
            "INSERT INTO events VALUES (NULL, ?, ?, ?)", (kind, utc_now().isoformat(), reference)
        )

    def manifest(self) -> RunManifest:
        with self._connection() as db:
            return RunManifest.model_validate_json(
                db.execute("SELECT payload FROM manifest").fetchone()[0]
            )

    def plan(self, stream: Stream | None = None) -> list[PlannedTurn]:
        with self._connection() as db:
            rows = db.execute(
                "SELECT payload FROM inputs WHERE (? IS NULL OR stream=?) ORDER BY stream,ordinal",
                (stream, stream),
            )
            return [PlannedTurn.model_validate_json(r[0]) for r in rows]

    def set_run_state(
        self,
        *,
        status: ExecutionStatus = ExecutionStatus.RUNNING,
        phase: RunPhase | None = None,
        failure: FailureInfo | None = None,
    ) -> None:
        with self._connection(write=True) as db:
            previous = RunRecord.model_validate_json(
                db.execute("SELECT payload FROM run_state").fetchone()[0]
            )
            if previous.status != ExecutionStatus.RUNNING:
                raise ValueError("A finalized run cannot change state")
            if status in {ExecutionStatus.PENDING, ExecutionStatus.UNKNOWN_OUTCOME}:
                raise ValueError("Invalid run-level transition")
            phases = list(RunPhase)
            if phase is not None and phases.index(phase) < phases.index(previous.phase):
                raise ValueError("Run phases cannot move backwards")
            if status in {
                ExecutionStatus.FAILED,
                ExecutionStatus.INTERRUPTED,
                ExecutionStatus.CANCELLED,
            }:
                if failure is None:
                    raise ValueError("Finalizing failed work requires a failure classification")
                for row in db.execute("SELECT payload FROM attempts").fetchall():
                    attempt = Attempt.model_validate_json(row[0])
                    if attempt.status == ExecutionStatus.RUNNING:
                        ended = Attempt.model_validate(
                            {
                                **attempt.model_dump(),
                                "status": ExecutionStatus.UNKNOWN_OUTCOME,
                                "finished_at": utc_now(),
                                "failure": failure,
                            }
                        )
                        db.execute(
                            "UPDATE attempts SET payload=? WHERE id=?",
                            (ended.model_dump_json(), str(attempt.id)),
                        )
                        self._event(db, "attempt_failed", str(attempt.id))
            if status in {ExecutionStatus.SUCCEEDED, ExecutionStatus.CAPTURED}:
                planned = db.execute("SELECT count(*) FROM inputs").fetchone()[0]
                captured = db.execute("SELECT count(*) FROM records").fetchone()[0]
                if planned != captured:
                    raise ValueError("Incomplete capture cannot finalize as successful")
                if status == ExecutionStatus.CAPTURED and (phase or previous.phase) != RunPhase.CAPTURE:
                    raise ValueError("Captured status is only valid in the capture phase")
            updated = RunRecord(
                id=previous.id, status=status, phase=phase or previous.phase, failure=failure
            )
            db.execute("UPDATE run_state SET payload=?", (updated.model_dump_json(),))
            self._event(db, "run_state_changed", status.value)

    def reopen_capture(self) -> None:
        """Reconcile abandoned dispatches while the caller holds the coordinator lease."""
        with self._connection(write=True) as db:
            previous = RunRecord.model_validate_json(
                db.execute("SELECT payload FROM run_state").fetchone()[0]
            )
            if previous.phase != RunPhase.CAPTURE or previous.status in {
                ExecutionStatus.SUCCEEDED, ExecutionStatus.CAPTURED,
            }:
                raise ValueError("Only unfinished capture can be reopened")
            failure = FailureInfo(kind="interrupted", exception_type="AbandonedCoordinator")
            for row in db.execute("SELECT payload FROM attempts").fetchall():
                attempt = Attempt.model_validate_json(row[0])
                if attempt.status == ExecutionStatus.RUNNING:
                    ended = Attempt.model_validate({
                        **attempt.model_dump(), "status": ExecutionStatus.UNKNOWN_OUTCOME,
                        "finished_at": utc_now(), "failure": failure,
                    })
                    db.execute("UPDATE attempts SET payload=? WHERE id=?",
                               (ended.model_dump_json(), str(attempt.id)))
                    self._event(db, "attempt_abandoned", str(attempt.id))
            self._event(db, "capture_resumed", previous.model_dump_json())
            db.execute("UPDATE run_state SET payload=?", (RunRecord(id=previous.id).model_dump_json(),))

    def start_attempt(self, turn: PlannedTurn, messages: list[JsonObject]) -> Attempt:
        with self._connection(write=True) as db:
            expected = self._planned(db, turn.stream, turn.ordinal)
            if expected != turn or not expected.generate:
                raise ValueError("Attempt does not match a generated turn in the frozen plan")
            state = RunRecord.model_validate_json(
                db.execute("SELECT payload FROM run_state").fetchone()[0]
            )
            if state.status != ExecutionStatus.RUNNING or state.phase != RunPhase.CAPTURE:
                raise ValueError("Run is not accepting generation attempts")
            if db.execute("SELECT 1 FROM records WHERE stream=? AND ordinal=?",
                          (turn.stream, turn.ordinal)).fetchone():
                raise ValueError("Committed turns cannot be dispatched again")
            previous = [Attempt.model_validate_json(row[0]) for row in db.execute(
                "SELECT payload FROM attempts WHERE stream=? AND ordinal=? ORDER BY rowid",
                (turn.stream, turn.ordinal),
            )]
            request = {}
            manifest = RunManifest.model_validate_json(db.execute("SELECT payload FROM manifest").fetchone()[0])
            if manifest.max_target_calls is not None and db.execute("SELECT count(*) FROM attempts").fetchone()[0] >= manifest.max_target_calls:
                raise TargetBudgetBlocked("Run target call budget exhausted")
            if previous:
                contract = next(t.recovery for t in manifest.targets if t.stream == turn.stream)
                if (
                    contract is None or contract.session_state != "stateless"
                    or contract.interrupted_request != "idempotent"
                    or any(a.status not in {ExecutionStatus.FAILED, ExecutionStatus.UNKNOWN_OUTCOME}
                           for a in previous)
                ):
                    raise ValueError("Turn has no safe retry under its frozen recovery contract")
                if len(previous) >= contract.max_attempts:
                    raise ValueError("Turn has exhausted its frozen attempt limit")
                if any(a.input_digest != content_digest(messages) for a in previous):
                    raise ValueError("Retry messages differ from the original request")
                request["request_id"] = previous[0].request_id
            attempt = Attempt(stream=turn.stream, ordinal=turn.ordinal, messages=messages,
                              input_digest=content_digest(messages), **request)
            db.execute(
                "INSERT INTO attempts VALUES (?, ?, ?, ?)",
                (str(attempt.id), turn.stream, turn.ordinal, attempt.model_dump_json()),
            )
            self._event(db, "attempt_started", str(attempt.id))
        return attempt

    @staticmethod
    def _planned(db: sqlite3.Connection, stream: Stream, ordinal: int) -> PlannedTurn:
        row = db.execute(
            "SELECT payload FROM inputs WHERE stream=? AND ordinal=?", (stream, ordinal)
        ).fetchone()
        if row is None:
            raise ValueError("Turn is not in the frozen plan")
        return PlannedTurn.model_validate_json(row[0])

    def fail_attempt(
        self,
        attempt: Attempt,
        failure: FailureInfo,
        status: ExecutionStatus = ExecutionStatus.UNKNOWN_OUTCOME,
    ) -> None:
        if status not in {ExecutionStatus.UNKNOWN_OUTCOME, ExecutionStatus.FAILED}:
            raise ValueError("Invalid failed attempt status")
        with self._connection(write=True) as db:
            current = self._attempt(db, attempt.id)
            if current.status != ExecutionStatus.RUNNING:
                raise ValueError("A terminal attempt cannot change state")
            updated = Attempt.model_validate(
                {
                    **current.model_dump(),
                    "status": status,
                    "finished_at": utc_now(),
                    "failure": failure,
                }
            )
            db.execute(
                "UPDATE attempts SET payload=? WHERE id=?",
                (updated.model_dump_json(), str(attempt.id)),
            )
            self._event(db, "attempt_failed", str(attempt.id))

    @staticmethod
    def _attempt(db: sqlite3.Connection, attempt_id: UUID) -> Attempt:
        row = db.execute("SELECT payload FROM attempts WHERE id=?", (str(attempt_id),)).fetchone()
        if row is None:
            raise ValueError("Unknown attempt")
        return Attempt.model_validate_json(row[0])

    def commit_record(
        self, turn: PlannedTurn, record: JsonObject, observation: Observation | None = None
    ) -> None:
        payload = json.dumps(record, ensure_ascii=False, allow_nan=False)
        observed_json = observation.model_dump_json() if observation is not None else None
        with self._connection(write=True) as db:
            state = RunRecord.model_validate_json(
                db.execute("SELECT payload FROM run_state").fetchone()[0]
            )
            if state.status != ExecutionStatus.RUNNING or state.phase != RunPhase.CAPTURE:
                raise ValueError("Run is not accepting captured records")
            if self._planned(db, turn.stream, turn.ordinal) != turn:
                raise ValueError("Record does not match the frozen plan")
            if (turn.role == "assistant") != (observation is not None):
                raise ValueError("Assistant records require exactly one observation")
            if not turn.generate and record != turn.record:
                raise ValueError("Recorded input must be preserved unchanged")
            if record.get("session_id") != turn.session_id:
                raise ValueError("Captured record belongs to a different session")
            if observation is not None:
                if (observation.stream, observation.ordinal) != (turn.stream, turn.ordinal):
                    raise ValueError("Observation belongs to a different turn")
                if (observation.origin == "generated") != turn.generate:
                    raise ValueError("Observation origin disagrees with the frozen plan")
                expected_text = observation.text.strip() if turn.generate else observation.text
                if record.get("text", "") != expected_text:
                    raise ValueError("Transcript text disagrees with its observation")
                metadata = record.get("metadata") or {}
                metadata = metadata if isinstance(metadata, dict) else {}
                if (
                    metadata.get("context") != observation.context
                    or metadata.get("usage") != observation.usage
                ):
                    raise ValueError("Transcript evidence disagrees with its observation")
                if observation.attempt_id is not None:
                    attempt = self._attempt(db, observation.attempt_id)
                    if (attempt.stream, attempt.ordinal) != (
                        turn.stream,
                        turn.ordinal,
                    ) or attempt.status != ExecutionStatus.RUNNING:
                        raise ValueError("Observation has no active matching attempt")
                    finished = Attempt.model_validate(
                        {
                            **attempt.model_dump(),
                            "status": ExecutionStatus.SUCCEEDED,
                            "finished_at": utc_now(),
                        }
                    )
                    db.execute(
                        "UPDATE attempts SET payload=? WHERE id=?",
                        (finished.model_dump_json(), str(attempt.id)),
                    )
                db.execute(
                    "INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        str(observation.id),
                        turn.stream,
                        turn.ordinal,
                        str(observation.attempt_id) if observation.attempt_id else None,
                        observed_json,
                        content_digest(observation.model_dump(mode="json")),
                    ),
                )
                self._event(db, "observation_committed", str(observation.id))
            db.execute("INSERT INTO records VALUES (?, ?, ?)", (turn.stream, turn.ordinal, payload))

    def transcripts(self, stream: Stream = "primary") -> list[JsonObject]:
        return list(self.committed_records(stream).values())

    def committed_records(self, stream: Stream = "primary") -> dict[int, JsonObject]:
        with self._connection() as db:
            return {
                r[0]: json.loads(r[1])
                for r in db.execute(
                    "SELECT ordinal,payload FROM records WHERE stream=? ORDER BY ordinal", (stream,)
                )
            }

    def observations(self) -> list[Observation]:
        with self._connection() as db:
            result = []
            for row in db.execute(
                "SELECT payload,digest FROM observations ORDER BY stream,ordinal"
            ):
                observation = Observation.model_validate_json(row[0])
                if content_digest(observation.model_dump(mode="json")) != row[1]:
                    raise ValueError("Observation content digest mismatch")
                result.append(observation)
            return result

    def attempts(self) -> list[Attempt]:
        with self._connection() as db:
            return [
                Attempt.model_validate_json(r[0])
                for r in db.execute("SELECT payload FROM attempts ORDER BY stream,ordinal,rowid")
            ]

    def source_artifact(self, digest: str) -> bytes:
        with self._connection() as db:
            row = db.execute(
                "SELECT content FROM source_artifacts WHERE digest=?", (digest,)
            ).fetchone()
            if row is None:
                raise ValueError("Source artifact is not available")
            content = bytes(row[0])
            if hashlib.sha256(content).hexdigest() != digest:
                raise ValueError("Source artifact digest mismatch")
            return content

    def summary(self) -> ExecutionSummary:
        with self._connection() as db:
            run = RunRecord.model_validate_json(
                db.execute("SELECT payload FROM run_state").fetchone()[0]
            )
            plan = [
                PlannedTurn.model_validate_json(r[0])
                for r in db.execute("SELECT payload FROM inputs")
            ]
            counts = {status: 0 for status in ExecutionStatus}
            for row in db.execute("SELECT payload FROM attempts"):
                counts[Attempt.model_validate_json(row[0]).status] += 1
            return ExecutionSummary(
                run=run,
                planned_records=len(plan),
                planned_generations=sum(turn.generate for turn in plan),
                committed_records=db.execute("SELECT count(*) FROM records").fetchone()[0],
                observations=db.execute("SELECT count(*) FROM observations").fetchone()[0],
                attempts=counts,
            )
