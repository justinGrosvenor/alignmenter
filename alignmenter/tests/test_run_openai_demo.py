"""Tests for the OpenAI demo script."""

from __future__ import annotations

from pathlib import Path
import yaml

from alignmenter.scripts.run_openai_demo import _write_config


def test_write_config_generates_relative_paths(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path
    (project / "datasets").mkdir()
    (project / "configs" / "persona").mkdir(parents=True)
    (project / "configs").mkdir(exist_ok=True)
    (project / "configs" / "safety_keywords.yaml").write_text("keywords: {}", encoding="utf-8")
    (project / "datasets" / "demo_conversations.jsonl").write_text("{}\n", encoding="utf-8")
    (project / "configs" / "persona" / "default.yaml").write_text("id: demo\n", encoding="utf-8")

    config_path = project / "configs" / "openai_demo.yaml"
    monkeypatch.setenv("ALIGNMENTER_JUDGE_BUDGET", "5")
    monkeypatch.setenv("ALIGNMENTER_JUDGE_BUDGET_USD", "0.5")

    _write_config(config_path, project)

    payload = yaml.safe_load(config_path.read_text())
    assert payload["dataset"] == "datasets/demo_conversations.jsonl"
    assert payload["persona"] == "configs/persona/default.yaml"
    assert payload["keywords"] == "configs/safety_keywords.yaml"
    assert payload["report"]["out_dir"] == "reports"
