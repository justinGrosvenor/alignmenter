"""An independent local target with durable request deduplication."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from alignmenter.providers.base import ChatResponse
from alignmenter.providers.callable import CallableProvider, CaptureTarget
from alignmenter.schemas.execution import RecoveryContract, content_digest


def ready(root: Path) -> None:
    run_dir = next((root / "reports").iterdir())
    print("READY:" + str(run_dir), flush=True)
    os.read(0, 1)


def make_target() -> CaptureTarget:
    root = Path(os.environ["ALIGNMENTER_TEST_TARGET_ROOT"])
    pause = os.environ.get("ALIGNMENTER_TEST_PAUSE")

    def chat(messages, *, request_id):
        is_second = messages[-1]["content"] == "question-B"
        with sqlite3.connect(root / "target.sqlite3") as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("CREATE TABLE IF NOT EXISTS transports (request TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS accepted (request TEXT PRIMARY KEY, input TEXT, response TEXT)")
            db.execute("INSERT INTO transports VALUES (?)", (request_id,))
            db.commit()
            if pause == "before_accept" and is_second:
                ready(root)
            row = db.execute("SELECT input,response FROM accepted WHERE request=?", (request_id,)).fetchone()
            if row is None:
                text = "answer:" + messages[-1]["content"]
                db.execute("INSERT INTO accepted VALUES (?, ?, ?)",
                           (request_id, content_digest(messages), json.dumps({"text": text})))
                db.commit()
            else:
                assert row[0] == content_digest(messages), "Idempotency key reused with different inputs"
                text = json.loads(row[1])["text"]
            if pause == "after_accept" and is_second:
                ready(root)
        return ChatResponse(text=text)

    return CaptureTarget("fixture:local", CallableProvider(chat, RecoveryContract(
        configuration_digest=content_digest({"code": "durable-recovery-fixture-v1"}),
        session_state="stateless", interrupted_request="idempotent",
    )))
