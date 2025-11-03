"""Tests for syncing custom GPT personas."""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

import alignmenter.cli as cli


def test_persona_sync_gpt(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "configs" / "persona" / "_gpt").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    cli.get_settings.cache_clear()

    def fake_metadata(gpt_id: str, api_key: str | None):
        return (
            {
                "id": gpt_id,
                "name": "Brand Voice",
                "instructions": "Keep responses warm and concise.",
                "conversation_starters": ["Tell me about the brand tone."],
            },
            None,
        )

    monkeypatch.setattr(cli, "_fetch_custom_gpt_metadata", fake_metadata)

    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "persona",
            "sync-gpt",
            "gpt://brand/voice",
            "--out",
            "configs/persona/_gpt/brand-voice.yaml",
            "--force",
        ],
    )

    assert result.exit_code == 0, result.stdout
    persona_doc = yaml.safe_load((tmp_path / "configs" / "persona" / "_gpt" / "brand-voice.yaml").read_text())
    assert persona_doc["display_name"] == "Brand Voice"
    assert persona_doc["source"]["id"] == "gpt://brand/voice"
    assert "Keep responses warm" in persona_doc["brand_notes"]
    assert persona_doc["exemplars"]
