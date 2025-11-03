"""Tests for configuration defaults."""

from alignmenter.config import Settings


def test_settings_defaults():
    settings = Settings(_env_file=None)
    assert settings.default_model == "openai:gpt-4o-mini"
    assert settings.default_dataset.endswith("datasets/demo_conversations.jsonl")
    assert settings.default_persona.endswith("configs/persona/default.yaml")
    assert settings.default_keywords.endswith("configs/safety_keywords.yaml")
    assert settings.embedding_provider in (None, "hashed")
    assert settings.judge_provider is None
