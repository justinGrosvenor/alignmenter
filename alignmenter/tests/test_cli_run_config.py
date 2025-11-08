"""Tests CLI integration with environment config defaults."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from alignmenter import app

DATA_DIR = Path(__file__).resolve().parent / "data"
MINI_DATASET = DATA_DIR / "mini_cli_dataset.jsonl"

runner = CliRunner()


def test_cli_run_uses_run_config_file(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2] / "alignmenter"
    persona = root / "configs" / "persona" / "default.yaml"
    keywords = root / "configs" / "safety_keywords.yaml"

    config_path = tmp_path / "mini_config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "run_id: cli-mini",
                f"model: openai:gpt-4o-mini",
                f"dataset: {MINI_DATASET}",
                f"persona: {persona}",
                f"keywords: {keywords}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "run",
            "--config", str(config_path),
            "--out", str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
