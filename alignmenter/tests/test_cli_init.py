"""Tests for the interactive init wizard."""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

import alignmenter.cli as cli
import alignmenter.config as config


def _prep_project(tmp_path: Path) -> None:
    configs = tmp_path / "configs"
    persona_dir = configs / "persona"
    datasets = tmp_path / "datasets"

    persona_dir.mkdir(parents=True)
    datasets.mkdir(parents=True)

    (persona_dir / "default.yaml").write_text("id: demo_persona\n", encoding="utf-8")
    (configs / "safety_keywords.yaml").write_text("keywords: {}\n", encoding="utf-8")
    (datasets / "demo_conversations.jsonl").write_text("{}\n", encoding="utf-8")


def test_init_creates_env_and_config(tmp_path: Path, monkeypatch) -> None:
    _prep_project(tmp_path)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli, "CONFIGS_DIR", tmp_path / "configs")
    monkeypatch.setattr(cli, "PERSONA_DIR", tmp_path / "configs" / "persona")
    monkeypatch.setattr(cli, "DATASETS_DIR", tmp_path / "datasets")
    monkeypatch.setattr(cli, "SAFETY_KEYWORDS", tmp_path / "configs" / "safety_keywords.yaml")

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cli.get_settings.cache_clear()
    config.get_settings.cache_clear()

    runner = CliRunner()
    input_data = "\n".join(
        [
            "y",  # configure OpenAI
            "sk-test",  # api key
            "y",  # save key to .env
            "2",  # choose sentence-transformer embeddings
            "gpt://brand-voice-chef",  # custom GPT id
            "",  # accept default model (derived from GPT id)
            "",  # confirm Custom GPT selection
            "y",  # enable judge
            "openai:gpt-4o-mini",  # judge provider
            "10",  # judge budget
            "5.0",  # budget usd
            "0.015",  # price per 1k input
            "0.06",  # price per 1k output
            "900",  # estimated tokens
        ]
    ) + "\n"

    result = runner.invoke(
        cli.app,
        ["init", "--env-path", ".env", "--config-path", "configs/init_run.yaml"],
        input=input_data,
    )

    assert result.exit_code == 0, result.stdout

    env_text = (tmp_path / ".env").read_text()
    assert "OPENAI_API_KEY=sk-test" in env_text
    assert "ALIGNMENTER_DEFAULT_MODEL=openai-gpt:gpt://brand-voice-chef" in env_text
    assert "ALIGNMENTER_JUDGE_BUDGET=10" in env_text
    assert "ALIGNMENTER_JUDGE_BUDGET_USD=5" in env_text
    assert "ALIGNMENTER_CUSTOM_GPT_ID=gpt://brand-voice-chef" in env_text

    config_payload = yaml.safe_load((tmp_path / "configs/init_run.yaml").read_text())
    assert config_payload["model"] == "openai-gpt:gpt://brand-voice-chef"
    assert config_payload["dataset"] == "../datasets/demo_conversations.jsonl"
    safety = config_payload["scorers"]["safety"]
    assert safety["judge"]["provider"] == "openai:gpt-4o-mini"
    assert safety["judge"]["budget"] == 10
    assert safety["judge"]["budget_usd"] == 5.0
    assert safety["judge"]["estimated_tokens_per_call"] == 900


def test_init_can_skip_storing_openai_key(tmp_path: Path, monkeypatch) -> None:
    _prep_project(tmp_path)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(cli, "CONFIGS_DIR", tmp_path / "configs")
    monkeypatch.setattr(cli, "PERSONA_DIR", tmp_path / "configs" / "persona")
    monkeypatch.setattr(cli, "DATASETS_DIR", tmp_path / "datasets")
    monkeypatch.setattr(cli, "SAFETY_KEYWORDS", tmp_path / "configs" / "safety_keywords.yaml")

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cli.get_settings.cache_clear()
    config.get_settings.cache_clear()

    runner = CliRunner()
    input_data = "\n".join(
        [
            "y",  # configure OpenAI
            "sk-test",  # api key
            "n",  # do not store
            "",  # accept default hashed embedding
            "",  # custom GPT id
            "",  # accept default chat model
            "n",  # disable judge
        ]
    ) + "\n"

    result = runner.invoke(
        cli.app,
        ["init", "--env-path", ".env", "--config-path", "configs/run.yaml"],
        input=input_data,
    )

    assert result.exit_code == 0, result.stdout
    env_text = (tmp_path / ".env").read_text()
    assert "OPENAI_API_KEY" not in env_text
