"""Tests for CLI helper commands."""

from __future__ import annotations

from pathlib import Path
import json

from typer.testing import CliRunner

from alignmenter import app


DATA_DIR = Path(__file__).resolve().parent / "data"
MINI_DATASET = DATA_DIR / "mini_cli_dataset.jsonl"

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


def test_dataset_sanitize_command(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(
        json.dumps({
            "session_id": "s1",
            "turn_index": 1,
            "role": "assistant",
            "text": "Contact me at test@example.com",
            "tags": [],
            "persona_id": "demo_v1",
        })
        + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "dataset",
            "sanitize",
            str(dataset),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Total PII instances" in result.output
    assert "[DRY RUN]" in result.output


def test_bootstrap_dataset_command(tmp_path: Path) -> None:
    out_path = tmp_path / "generated.jsonl"
    result = runner.invoke(
        app,
        [
            "bootstrap-dataset",
            "--out",
            str(out_path),
            "--sessions",
            "2",
            "--turns-per-session",
            "2",
            "--safety-trap-ratio",
            "0.5",
            "--brand-trap-ratio",
            "0.0",
            "--persona-id",
            "demo_v1",
            "--seed",
            "7",
        ],
    )

    assert result.exit_code == 0, result.output
    assert out_path.exists()
    lines = out_path.read_text().strip().splitlines()
    assert len(lines) == 4  # 2 sessions × 2 turns


def test_calibrate_persona_command(tmp_path: Path) -> None:
    persona_path = tmp_path / "persona.yaml"
    persona_path.write_text("id: sample_persona\n", encoding="utf-8")

    dataset_path = tmp_path / "annotations.jsonl"
    dataset_path.write_text(
        json.dumps({"text": "On brand reply", "label": 1, "persona_id": "sample_persona"})
        + "\n"
        + json.dumps({"text": "off brand hype", "label": 0, "persona_id": "sample_persona"})
        + "\n",
        encoding="utf-8",
    )

    out_path = tmp_path / "persona.traits.json"
    result = runner.invoke(
        app,
        [
            "calibrate-persona",
            "--persona-path",
            str(persona_path),
            "--dataset",
            str(dataset_path),
            "--out",
            str(out_path),
            "--min-samples",
            "2",
            "--epochs",
            "10",
        ],
    )

    assert result.exit_code == 0, result.output
    assert out_path.exists()
    payload = json.loads(out_path.read_text())
    assert "trait_model" in payload


def test_run_command(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2] / "alignmenter"
    dataset = MINI_DATASET
    persona = root / "configs" / "persona" / "default.yaml"
    keywords = root / "configs" / "safety_keywords.yaml"

    result = runner.invoke(
        app,
        [
            "run",
            "--model",
            "openai:gpt-4o-mini",
            "--dataset",
            str(dataset),
            "--persona",
            str(persona),
            "--keywords",
            str(keywords),
            "--out",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    contents = list(tmp_path.glob("*"))
    assert contents, "Expected artifacts in output directory"
    results_path = contents[0] / "results.json"
    assert results_path.exists()
    payload = json.loads(results_path.read_text())
    assert payload.get("scorecards")
    assert "Open in browser:" in result.output


def test_run_command_with_compare(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2] / "alignmenter"
    dataset = MINI_DATASET
    persona = root / "configs" / "persona" / "default.yaml"
    keywords = root / "configs" / "safety_keywords.yaml"

    result = runner.invoke(
        app,
        [
            "run",
            "--model",
            "openai:gpt-4o-mini",
            "--compare",
            "openai:gpt-4o-mini",
            "--dataset",
            str(dataset),
            "--persona",
            str(persona),
            "--keywords",
            str(keywords),
            "--out",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Loading dataset:" in result.output
    assert "Brand voice score" in result.output
    assert "Report written to:" in result.output
    assert "Open in browser:" in result.output


def test_run_command_threshold_failure(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2] / "alignmenter"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "run_id: threshold",
                "model: openai:gpt-4o-mini",
                f"dataset: {MINI_DATASET}",
                f"persona: {root / 'configs' / 'persona' / 'default.yaml'}",
                f"keywords: {root / 'configs' / 'safety_keywords.yaml'}",
                "scorers:",
                "  authenticity:",
                "    threshold_fail: 0.99",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run",
            "--config",
            str(config_path),
        ],
    )

    assert result.exit_code == 2
    assert "✗" in result.output


def test_run_command_invalid_model() -> None:
    root = Path(__file__).resolve().parents[2] / "alignmenter"
    dataset = root / "datasets" / "demo_conversations.jsonl"
    persona = root / "configs" / "persona" / "default.yaml"

    result = runner.invoke(
        app,
        [
            "run",
            "--model",
            "gpt-4o-mini",
            "--dataset",
            str(dataset),
            "--persona",
            str(persona),
        ],
    )

    assert result.exit_code != 0
    assert "Path not found" not in result.output
