"""Tests CLI integration with environment config defaults."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from alignmenter import app

runner = CliRunner()


def test_cli_run_uses_run_config_file(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2] / "alignmenter"
    config_path = root / "configs" / "demo_config.yaml"

    result = runner.invoke(
        app,
        [
            "run",
            "--config", str(config_path),
            "--out", str(tmp_path),
            "--no-generate",
        ],
    )

    assert result.exit_code == 0, result.output
