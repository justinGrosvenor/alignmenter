"""Characterize default Inspect retry separately from guarded acceptance results."""

from __future__ import annotations

import json
import sqlite3
import subprocess

from .test_acceptance import REPO, command, kill_at


def test_default_inspect_retry_reuses_A_but_repeats_accepted_B(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()
    kill_at("raw-inspect", root, "accepted:B:0")
    old_log = next((root / "inspect-logs").glob("*.eval"))
    old_bytes = old_log.read_bytes()
    with sqlite3.connect(root / "target.sqlite") as db:
        before = dict(db.execute("SELECT sample,count(*) FROM calls GROUP BY sample"))
    assert before == {"A": 1, "B": 1}
    result = subprocess.run(
        command("raw-inspect", root) + ["--retry", str(old_log)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=40,
    )
    (root / "retry.stdout").write_text(result.stdout)
    (root / "retry.stderr").write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(root / "target.sqlite") as db:
        after = dict(db.execute("SELECT sample,count(*) FROM calls GROUP BY sample"))
    assert after == {"A": 1, "B": 2, "C": 1}
    assert old_log.read_bytes() == old_bytes
    (root / "probe-result.json").write_text(
        json.dumps(
            {
                "before_retry": before,
                "after_retry": after,
                "interpretation": "Completed A reused; default external-target retry needs an unknown-outcome guard.",
            },
            indent=2,
        )
        + "\n"
    )
