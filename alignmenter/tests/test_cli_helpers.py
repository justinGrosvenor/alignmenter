"""Tests for CLI helper commands."""

from __future__ import annotations

from pathlib import Path
import json

from typer.testing import CliRunner

from alignmenter import app


runner = CliRunner()


def test_persona_scaffold(tmp_path: Path) -> None:
    target = tmp_path / "custom_persona.yaml"
    result = runner.invoke(
        app,
        ["persona", "scaffold", "--name", "Custom Persona", "--out", str(target)],
    )

    assert result.exit_code == 0, result.output
    assert target.exists()
    content = target.read_text()
    assert "display_name: Custom Persona" in content


def _write_sample_dataset(path: Path) -> None:
    path.write_text(
        '{"session_id": "sess-1", "turn_index": 1, "role": "user", "text": "Hi", "tags": ["scenario:greeting"], "persona_id": "demo_v1"}\n'
        '{"session_id": "sess-1", "turn_index": 2, "role": "assistant", "text": "Hello there.", "tags": ["scenario:greeting"], "persona_id": "demo_v1"}\n'
    )


def test_persona_export(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.jsonl"
    _write_sample_dataset(dataset)

    output_csv = tmp_path / "export.csv"
    result = runner.invoke(
        app,
        [
            "persona",
            "export",
            "--dataset",
            str(dataset),
            "--out",
            str(output_csv),
            "--persona-id",
            "demo_v1",
        ],
    )

    assert result.exit_code == 0, result.output
    content = output_csv.read_text().splitlines()
    assert len(content) == 2  # header + one assistant turn
    assert "demo_v1" in content[1]


def test_persona_export_labelstudio(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.jsonl"
    _write_sample_dataset(dataset)

    output_json = tmp_path / "export.json"
    result = runner.invoke(
        app,
        [
            "persona",
            "export",
            "--dataset",
            str(dataset),
            "--out",
            str(output_json),
            "--format",
            "labelstudio",
        ],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(output_json.read_text())
    assert isinstance(data, list) and data
    assert "data" in data[0]
    assert data[0]["data"]["text"]


def test_dataset_lint(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.jsonl"
    _write_sample_dataset(dataset)

    persona_dir = tmp_path / "persona"
    persona_dir.mkdir()
    (persona_dir / "demo.yaml").write_text("id: demo_v1\n")

    result = runner.invoke(
        app,
        ["dataset", "lint", str(dataset), "--persona-dir", str(persona_dir)],
    )

    assert result.exit_code == 0, result.output
    assert "Dataset lint passed" in result.output


def test_dataset_lint_strict(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.jsonl"
    _write_sample_dataset(dataset)

    persona_dir = tmp_path / "persona"
    persona_dir.mkdir()
    (persona_dir / "demo.yaml").write_text("id: demo_v1\n")

    result = runner.invoke(
        app,
        ["dataset", "lint", str(dataset), "--persona-dir", str(persona_dir), "--strict"],
    )

    assert result.exit_code == 0, result.output
    assert "Dataset lint passed" in result.output


def test_run_command(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "run",
            "--model",
            "openai:gpt-4o-mini",
            "--dataset",
            "alignmenter/datasets/demo_conversations.jsonl",
            "--persona",
            "alignmenter/configs/persona/default.yaml",
            "--keywords",
            "alignmenter/configs/safety_keywords.yaml",
            "--out",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    contents = list(tmp_path.glob("*"))
    assert contents, "Expected artifacts in output directory"


def test_run_command_invalid_model() -> None:
    result = runner.invoke(
        app,
        [
            "run",
            "--model",
            "gpt-4o-mini",
            "--dataset",
            "alignmenter/datasets/demo_conversations.jsonl",
            "--persona",
            "alignmenter/configs/persona/default.yaml",
        ],
    )

    assert result.exit_code != 0
    assert "Path not found" not in result.output
