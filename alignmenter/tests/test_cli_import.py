"""Tests for the GPT importer command."""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

import alignmenter.cli as cli


def test_import_gpt(monkeypatch, tmp_path: Path) -> None:
    instructions = tmp_path / "instructions.txt"
    instructions.write_text(
        "Be concise and evidence-driven. Avoid hype and speculation."
        "Prefer words like 'alignment' and 'baseline'."
        "Never use emojis."
        "Disallow: hate speech; illegal advice; self-harm instructions.",
        encoding="utf-8",
    )

    out_path = tmp_path / "persona.yaml"

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "import",
            "gpt",
            "--name",
            "AlignmenterGPT",
            "--instructions",
            str(instructions),
            "--out",
            str(out_path),
        ],
    )

    assert result.exit_code == 0, result.stdout
    persona_doc = yaml.safe_load(out_path.read_text())
    assert persona_doc["display_name"] == "AlignmenterGPT"
    assert persona_doc["lexicon"]["preferred"]
    assert persona_doc["safety_rules"]["disallowed_topics"]


def test_import_gpt_short_text_still_creates_exemplars(tmp_path: Path) -> None:
    instructions = tmp_path / "short.txt"
    instructions.write_text("Warm, friendly, encouraging.", encoding="utf-8")

    out_path = tmp_path / "persona_short.yaml"

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "import",
            "gpt",
            "--name",
            "FriendlyGPT",
            "--instructions",
            str(instructions),
            "--out",
            str(out_path),
        ],
    )

    assert result.exit_code == 0, result.stdout
    persona_doc = yaml.safe_load(out_path.read_text())
    assert persona_doc["exemplars"], "Expected exemplar fallback for short instructions"
    assert persona_doc["lexicon"]["avoid"] == []


def test_import_gpt_detects_emoji_allowance(tmp_path: Path) -> None:
    instructions = tmp_path / "emoji.txt"
    instructions.write_text(
        (
            "Encourage concise answers. Prefer words like trusted, thoughtful, careful. "
            "Emojis are ok to use sparingly when highlighting a success."
        ),
        encoding="utf-8",
    )

    out_path = tmp_path / "persona_emoji.yaml"

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "import",
            "gpt",
            "--name",
            "EmojiGPT",
            "--instructions",
            str(instructions),
            "--out",
            str(out_path),
        ],
    )

    assert result.exit_code == 0, result.stdout
    persona_doc = yaml.safe_load(out_path.read_text())
    style = persona_doc["style_rules"]
    assert style["emojis"]["allowed"] is True
    # No explicit "avoid" language, importer should leave the list empty
    assert persona_doc["lexicon"]["avoid"] == []
