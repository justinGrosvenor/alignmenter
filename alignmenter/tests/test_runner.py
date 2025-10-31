"""Runner pipeline tests."""

from __future__ import annotations

import json
from pathlib import Path

from alignmenter.runner import RunConfig, Runner


class StubScorer:
    id = "stub"

    def score(self, sessions):
        return {"mean": 0.5, "count": len(sessions)}


def test_runner_execute_creates_reports(tmp_path: Path) -> None:
    config = RunConfig(
        model="openai:gpt-4o-mini",
        dataset_path=Path("alignmenter/datasets/demo_conversations.jsonl"),
        persona_path=Path("alignmenter/configs/persona/default.yaml"),
        run_id="test",
        report_out_dir=tmp_path,
    )

    runner = Runner(config=config, scorers=[StubScorer()])
    run_dir = runner.execute()

    assert run_dir.exists()
    report_json = run_dir / "report.json"
    html = run_dir / "index.html"
    run_meta = run_dir / "run.json"

    assert report_json.exists()
    assert html.exists()
    assert run_meta.exists()

    payload = json.loads(report_json.read_text())
    assert payload["scores"]["stub"]["mean"] == 0.5
