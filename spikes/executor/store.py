"""Minimal shared durability/accounting experiment, not a production storage API."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Store:
    def __init__(self, root: Path):
        self.root = root
        self.path = root / "run.sqlite"

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def create(self, config: dict) -> None:
        ids = [case["id"] for case in config["cases"]]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("Plan needs unique nonempty sample IDs")
        self.root.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            if self.config() != config:
                raise ValueError("Incompatible run configuration")
            return
        with self.transaction() as db:
            # SQLite keeps the small fixture payloads inline, including evidence.
            for sql in (
                "CREATE TABLE run (config TEXT NOT NULL)",
                "CREATE TABLE samples (id TEXT PRIMARY KEY, case_json TEXT NOT NULL, status TEXT NOT NULL, selected TEXT)",
                "CREATE TABLE attempts (id TEXT PRIMARY KEY, sample TEXT REFERENCES samples(id), session TEXT, status TEXT)",
                "CREATE TABLE events (seq INTEGER PRIMARY KEY, attempt TEXT, kind TEXT, payload TEXT)",
                "CREATE TABLE observations (attempt TEXT REFERENCES attempts(id), turn INTEGER, payload TEXT, digest TEXT, PRIMARY KEY(attempt,turn))",
                "CREATE TABLE calls (id TEXT PRIMARY KEY, kind TEXT, cache_key TEXT, status TEXT, result TEXT, actual_cost_micros INTEGER, reserved_cost_micros INTEGER)",
                "CREATE TABLE evaluations (id TEXT PRIMARY KEY, sample TEXT REFERENCES samples(id), observation_digest TEXT, status TEXT, verdict TEXT)",
            ):
                db.execute(sql)
            db.execute("INSERT INTO run VALUES (?)", (canonical(config),))
            db.executemany(
                "INSERT INTO samples VALUES (?, ?, 'pending', NULL)",
                [(case["id"], canonical(case)) for case in config["cases"]],
            )

    def config(self) -> dict:
        return json.loads(self.rows("run")[0]["config"])

    def rows(self, table: str) -> list[dict]:
        allowed = {"run", "samples", "attempts", "events", "observations", "calls", "evaluations"}
        if table not in allowed:
            raise ValueError(table)
        with self.transaction() as db:
            return [dict(r) for r in db.execute(f"SELECT * FROM {table} ORDER BY rowid")]

    def samples(self) -> list[dict]:
        return self.rows("samples")

    def sample(self, sample_id: str) -> dict:
        return next(s for s in self.samples() if s["id"] == sample_id)

    @staticmethod
    def event(db, attempt: str, kind: str, payload=None) -> None:
        db.execute("INSERT INTO events VALUES (NULL, ?, ?, ?)", (attempt, kind, canonical(payload)))

    def recover(self) -> None:
        """Called only while holding the exclusive resource/coordinator lease."""
        with self.transaction() as db:
            for row in db.execute("SELECT * FROM samples WHERE status='running'").fetchall():
                case = json.loads(row["case_json"])
                db.execute(
                    "UPDATE attempts SET status='unknown_outcome' WHERE id=?", (row["selected"],)
                )
                self.event(db, row["selected"], "unknown_outcome")
                status = "pending" if case.get("safe_restart", False) else "unknown_outcome"
                db.execute("UPDATE samples SET status=? WHERE id=?", (status, row["id"]))

    def start(self, sample_id: str) -> tuple[str, str]:
        attempt, session = uuid.uuid4().hex, uuid.uuid4().hex
        with self.transaction() as db:
            row = db.execute("SELECT status FROM samples WHERE id=?", (sample_id,)).fetchone()
            if row is None or row["status"] != "pending":
                raise ValueError("Sample is not pending")
            db.execute(
                "INSERT INTO attempts VALUES (?, ?, ?, 'running')", (attempt, sample_id, session)
            )
            db.execute(
                "UPDATE samples SET status='running', selected=? WHERE id=?", (attempt, sample_id)
            )
            self.event(db, attempt, "started", {"session": session})
        return attempt, session

    def record(self, attempt: str, turn: int, observation: dict, *, final: bool = False) -> bool:
        with self.transaction() as db:
            active = db.execute(
                "SELECT samples.id FROM samples JOIN attempts ON samples.selected=attempts.id "
                "WHERE attempts.id=? AND attempts.status='running' AND samples.status='running'",
                (attempt,),
            ).fetchone()
            if active is None:
                self.event(db, attempt, "late_response", observation)
                return False
            db.execute(
                "INSERT INTO observations VALUES (?, ?, ?, ?)",
                (attempt, turn, canonical(observation), digest(observation)),
            )
            self.event(db, attempt, "observation_committed", {"turn": turn})
            if final:
                # Last answer and sample completion have one acknowledgment boundary.
                db.execute("UPDATE attempts SET status='succeeded' WHERE id=?", (attempt,))
                db.execute("UPDATE samples SET status='succeeded' WHERE selected=?", (attempt,))
                self.event(db, attempt, "succeeded")
        return True

    def finish(self, attempt: str, status: str) -> None:
        with self.transaction() as db:
            db.execute(
                "UPDATE attempts SET status=? WHERE id=? AND status='running'", (status, attempt)
            )
            db.execute(
                "UPDATE samples SET status=? WHERE selected=? AND status='running'",
                (status, attempt),
            )
            self.event(db, attempt, status)

    def retry(self, sample_id: str) -> None:
        with self.transaction() as db:
            updated = db.execute(
                "UPDATE samples SET status='pending' WHERE id=? AND status='failed'", (sample_id,)
            ).rowcount
            if updated != 1:
                raise ValueError("Only classified fixture failures may be retried")

    def reserve(
        self, kind: str, cache_key: str, upper_cost_micros: int | None = None
    ) -> str | None:
        """Run-wide call-count limit; every reservation remains charged after a crash."""
        if upper_cost_micros is not None and (
            type(upper_cost_micros) is not int or upper_cost_micros < 0
        ):
            raise ValueError("Cost bound must be nonnegative integer micro-units")
        call_id = uuid.uuid4().hex
        with self.transaction() as db:
            config = json.loads(db.execute("SELECT config FROM run").fetchone()[0])
            limit = config.get(f"{kind}_budget")
            count = db.execute("SELECT count(*) FROM calls WHERE kind=?", (kind,)).fetchone()[0]
            if limit is not None and count >= limit:
                return None
            cost_limit = config.get(f"{kind}_cost_limit_micros")
            if cost_limit is not None:
                costs = [
                    r[0]
                    for r in db.execute(
                        "SELECT coalesce(actual_cost_micros,reserved_cost_micros) FROM calls WHERE kind=?",
                        (kind,),
                    )
                ]
                if upper_cost_micros is None or any(c is None for c in costs):
                    return None
                if sum(costs) + upper_cost_micros > cost_limit:
                    return None
            db.execute(
                "INSERT INTO calls VALUES (?, ?, ?, 'reserved', NULL, NULL, ?)",
                (call_id, kind, cache_key, upper_cost_micros),
            )
        return call_id

    def settle(self, call_id: str, result: dict, actual_cost_micros: int | None = None) -> None:
        if actual_cost_micros is not None and (
            type(actual_cost_micros) is not int or actual_cost_micros < 0
        ):
            raise ValueError("Actual cost must be nonnegative integer micro-units")
        with self.transaction() as db:
            row = db.execute("SELECT * FROM calls WHERE id=?", (call_id,)).fetchone()
            if row is None or row["status"] != "reserved":
                raise ValueError("Call is not awaiting settlement")
            status = "succeeded"
            bound = row["reserved_cost_micros"]
            if actual_cost_micros is not None and bound is not None and actual_cost_micros > bound:
                status = (
                    "cost_bound_exceeded"  # Preserve actual spend, never clamp it to the estimate.
                )
            db.execute(
                "UPDATE calls SET status=?, result=?, actual_cost_micros=? WHERE id=?",
                (status, canonical(result), actual_cost_micros, call_id),
            )

    def cached(self, cache_key: str) -> dict | None:
        with self.transaction() as db:
            row = db.execute(
                "SELECT result FROM calls WHERE kind='judge' AND cache_key=? AND status='succeeded' ORDER BY rowid LIMIT 1",
                (cache_key,),
            ).fetchone()
            return json.loads(row[0]) if row else None

    def reject_verdict(self, call_id: str, result: dict) -> None:
        with self.transaction() as db:
            updated = db.execute(
                "UPDATE calls SET status='invalid_result', result=? WHERE id=? AND status='reserved'",
                (canonical(result), call_id),
            ).rowcount
            if updated != 1:
                raise ValueError("Call is not awaiting settlement")

    def evaluation(
        self, sample_id: str, observation_digest: str, status: str, verdict: str | None
    ) -> str:
        result_id = uuid.uuid4().hex
        with self.transaction() as db:
            db.execute(
                "INSERT INTO evaluations VALUES (?, ?, ?, ?, ?)",
                (result_id, sample_id, observation_digest, status, verdict),
            )
        return result_id

    def export(self, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=False)
        with (
            sqlite3.connect(self.path) as source,
            sqlite3.connect(destination / "run.sqlite") as target,
        ):
            source.backup(target)
        payload = (destination / "run.sqlite").read_bytes()
        (destination / "manifest.json").write_text(
            canonical(
                {
                    "schema_version": 1,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "payloads": "inline SQLite; Inspect logs are optional diagnostics",
                }
            )
        )

    @staticmethod
    def verify_export(root: Path) -> None:
        manifest = json.loads((root / "manifest.json").read_text())
        actual = hashlib.sha256((root / "run.sqlite").read_bytes()).hexdigest()
        if manifest.get("schema_version") != 1 or actual != manifest["sha256"]:
            raise ValueError("Invalid export manifest or digest")
        for row in Store(root).rows("observations"):
            if digest(json.loads(row["payload"])) != row["digest"]:
                raise ValueError("Invalid observation digest")
