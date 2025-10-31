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
        dataset_path=Path(__file__).resolve().parents[1] / "datasets" / "demo_conversations.jsonl",
        persona_path=Path(__file__).resolve().parents[1] / "configs" / "persona" / "default.yaml",
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
    assert payload["scores"]["primary"]["stub"]["mean"] == 0.5


def test_runner_execute_with_compare(tmp_path: Path) -> None:
    config = RunConfig(
        model="openai:gpt-4o-mini",
        dataset_path=Path(__file__).resolve().parents[1] / "datasets" / "demo_conversations.jsonl",
        persona_path=Path(__file__).resolve().parents[1] / "configs" / "persona" / "default.yaml",
        compare_model="openai:gpt-4o-mini",
        run_id="test",
        report_out_dir=tmp_path,
    )

    scorer_primary = StubScorer()
    scorer_compare = StubScorer()
    runner = Runner(config=config, scorers=[scorer_primary], compare_scorers=[scorer_compare])
    run_dir = runner.execute()

    payload = json.loads((run_dir / "results.json").read_text())
    assert "primary" in payload["scores"]
    assert "compare" in payload["scores"]
    assert "diff" in payload["scores"]
    assert "scorecards" in payload
