"""Verified portable snapshots. Imported copies cannot fork a live call budget."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from alignmenter.execution.recovery import _check_inputs, _check_saved_capture
from alignmenter.storage.evaluations import EvaluationStore
from alignmenter.storage.reviews import ReviewStore
from alignmenter.storage.runs import DATABASE_NAME, RunStore

MAX_DATABASE_BYTES = 512 * 1024 * 1024


def verify_run(run_dir):
    store = RunStore(run_dir)
    with store._connection() as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Run database integrity or reference check failed")
        if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('view','trigger')").fetchone():
            raise ValueError("Run archives cannot contain views or triggers")
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for digest, data in db.execute("SELECT digest,content FROM source_artifacts"):
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError("Source artifact checksum mismatch")
    manifest = store.manifest()
    _check_inputs(store, None, None)
    _check_saved_capture(store)
    summary = store.summary()
    if summary.run.id != manifest.id:
        raise ValueError("Capture state belongs to a different run")
    if manifest.max_target_calls is not None and sum(summary.attempts.values()) > manifest.max_target_calls:
        raise ValueError("Saved target calls exceed the frozen limit")
    if "evaluation_schema" in tables:
        evaluations = EvaluationStore(run_dir)
        for evaluation in evaluations.manifests():
            if evaluation.run_id != manifest.id:
                raise ValueError("Evaluation belongs to a different capture")
            evaluations.snapshot(evaluation.id)
        ReviewStore(run_dir).annotations()
    return manifest


def export_archive(run_dir, path, *, force=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        raise ValueError("Archive already exists; use force to replace it")
    with tempfile.TemporaryDirectory(prefix="alignmenter-export-") as temporary:
        temporary = Path(temporary)
        copy = temporary / DATABASE_NAME
        source = RunStore(run_dir)
        with source._connection() as db, sqlite3.connect(copy) as destination:
            db.backup(destination)
        manifest = verify_run(temporary)
        payload = copy.read_bytes()
        if len(payload) > MAX_DATABASE_BYTES:
            raise ValueError("Run exceeds the supported 512 MiB archive size")
        index = {"schema_version": 1, "run_id": str(manifest.id), "database": DATABASE_NAME,
                 "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload), "import_mode": "read_only"}
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            pending = Path(handle.name)
        try:
            with zipfile.ZipFile(pending, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("archive.json", json.dumps(index))
                archive.writestr(DATABASE_NAME, payload)
            if force:
                os.replace(pending, path)
            else:
                os.link(pending, path)
        finally:
            pending.unlink(missing_ok=True)
    return index


def import_archive(path, out_dir):
    path, out_dir = Path(path), Path(out_dir)
    if out_dir.exists():
        raise ValueError("Archive destination must not already exist")
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != 2 or set(names) != {"archive.json", DATABASE_NAME}:
            raise ValueError("Archive entries must be exactly archive.json and run.sqlite3")
        if archive.getinfo("archive.json").file_size > 16384 or archive.getinfo(DATABASE_NAME).file_size > MAX_DATABASE_BYTES:
            raise ValueError("Archive exceeds supported size limits")
        index = json.loads(archive.read("archive.json"))
        if (type(index.get("schema_version")) is not int or index["schema_version"] != 1
                or index.get("database") != DATABASE_NAME or index.get("import_mode") != "read_only"):
            raise ValueError("Unsupported archive format")
        payload = archive.read(DATABASE_NAME)
        if len(payload) != index.get("size") or hashlib.sha256(payload).hexdigest() != index.get("sha256"):
            raise ValueError("Archive database checksum or size mismatch")
    with tempfile.TemporaryDirectory(prefix=".alignmenter-import-", dir=out_dir.parent) as temporary:
        temporary = Path(temporary)
        (temporary / DATABASE_NAME).write_bytes(payload)
        manifest = verify_run(temporary)
        if str(manifest.id) != index.get("run_id"):
            raise ValueError("Archive run identity mismatch")
        with sqlite3.connect(temporary / DATABASE_NAME) as db:
            db.execute("CREATE TABLE IF NOT EXISTS imported_archive (singleton INTEGER PRIMARY KEY CHECK(singleton=1), payload TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO imported_archive VALUES (1,?)", (json.dumps(index),))
        # Atomic directory handoff; no unverified database is exposed as the destination.
        os.rename(temporary, out_dir)
    return manifest
