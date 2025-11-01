"""Tests CLI integration with environment config defaults."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from alignmenter import app

runner = CliRunner()


def test_cli_run_uses_settings_defaults(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2] / "alignmenter"

    result = runner.invoke(
        app,
        [
            "run",
            "--model", "openai:gpt-4o-mini",
            "--dataset", str(root / "datasets" / "demo_conversations.jsonl"),
            "--persona", str(root / "configs" / "persona" / "default.yaml"),
            "--keywords", str(root / "configs" / "safety_keywords.yaml"),
            "--out", str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
