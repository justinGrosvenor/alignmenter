"""CLI error handling tests."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from alignmenter import app

runner = CliRunner()


def test_cli_run_missing_dataset(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "run",
            "--model",
            "openai:gpt-4o-mini",
            "--dataset",
            str(tmp_path / "missing.jsonl"),
            "--persona",
            str(tmp_path / "persona.yaml"),
            "--keywords",
            str(tmp_path / "keywords.yaml"),
            "--out",
            str(tmp_path),
        ],
    )

    assert result.exit_code != 0
    assert "Path not found" in result.output
