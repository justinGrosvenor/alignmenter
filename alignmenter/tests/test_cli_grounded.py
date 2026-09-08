"""End-to-end: `alignmenter run --grounding` on recorded grounded transcripts."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from alignmenter.cli import app

ROOT = Path(__file__).resolve().parents[1]


def test_run_grounding_on_recorded_transcripts(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--model",
            "openai:gpt-4o-mini",
            "--dataset",
            str(ROOT / "datasets" / "grounded_demo.jsonl"),
            "--persona",
            str(ROOT / "configs" / "persona" / "default.yaml"),
            "--keywords",
            str(ROOT / "configs" / "safety_keywords.yaml"),
            "--out",
            str(tmp_path),
            "--grounding",
        ],
    )
    assert result.exit_code == 0, result.output

    run_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert len(run_dirs) == 1
    results = json.loads((run_dirs[0] / "results.json").read_text())
    grounding = results["scores"]["primary"]["grounding"]

    # g01 fully grounded (1 min, 2000 m, 3 min); g02 contradicts (8 drops, 16 drops vs 2 drops)
    # and supports 30 min; g03 supports 30 min. 7 checked, 5 supported.
    assert grounding["quantities_checked"] == 7
    assert grounding["quantities_supported"] == 5
    assert grounding["contradicted"] == 2
    assert grounding["invented"] == 0
    assert grounding["citation_validity"] == 1.0
    assert grounding["violations"][0]["question"].startswith("How much bleach")

    html = (run_dirs[0] / "index.html").read_text()
    assert "Answers with figures the passages never gave" in html
    assert "contradicted: 8 drop, 16 drop" in html
    assert any(card["id"] == "grounding" for card in results["scorecards"])


def test_custom_scorer_option_loads_product_scorer(tmp_path: Path) -> None:
    module = tmp_path / "product_scorers.py"
    module.write_text(
        "class Latency:\n"
        "    id = 'latency'\n"
        "    def score(self, sessions):\n"
        "        return {'score': 0.42, 'sessions': len(list(sessions))}\n"
    )
    import sys

    sys.path.insert(0, str(tmp_path))
    try:
        result = CliRunner().invoke(
            app,
            [
                "run",
                "--model",
                "openai:gpt-4o-mini",
                "--dataset",
                str(ROOT / "datasets" / "grounded_demo.jsonl"),
                "--persona",
                str(ROOT / "configs" / "persona" / "default.yaml"),
                "--keywords",
                str(ROOT / "configs" / "safety_keywords.yaml"),
                "--out",
                str(tmp_path / "out"),
                "--custom-scorer",
                "product_scorers:Latency",
            ],
        )
    finally:
        sys.path.remove(str(tmp_path))
    assert result.exit_code == 0, result.output
    run_dir = next(p for p in (tmp_path / "out").iterdir() if p.is_dir())
    results = json.loads((run_dir / "results.json").read_text())
    assert results["scores"]["primary"]["latency"] == {"score": 0.42, "sessions": 3}
