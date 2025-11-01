"""Tests for run configuration loader."""

from __future__ import annotations

from pathlib import Path

from alignmenter.run_config import load_run_options


def test_load_run_options_resolves_paths(tmp_path: Path) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir(parents=True)

    dataset_path = tmp_path / "data" / "dataset.jsonl"
    persona_path = config_dir / "persona.yaml"
    keywords_path = config_dir / "keywords.yaml"
    dataset_path.parent.mkdir()
    dataset_path.write_text("{}\n")
    persona_path.write_text("persona")
    keywords_path.write_text("keywords")

    config_path = config_dir / "run.yaml"
    config_path.write_text(
        """
run_id: sample
model: openai:gpt-4o-mini
dataset: ../data/dataset.jsonl
persona: persona.yaml
embedding: hashed
scorers:
  safety:
    keyword_lists: keywords.yaml
    judge:
      provider: none
      budget: 3
report:
  out_dir: ../reports
  include_raw: false
"""
    )

    options = load_run_options(config_path)
    assert options["run_id"] == "sample"
    assert options["model"] == "openai:gpt-4o-mini"
    assert options["dataset"] == dataset_path.resolve()
    assert options["persona"] == persona_path.resolve()
    assert options["keywords"] == keywords_path.resolve()
    assert options["embedding"] == "hashed"
    assert options["judge_provider"] == "none"
    assert options["judge_budget"] == 3
    assert options["report_out_dir"] == (tmp_path / "reports").resolve()
    assert options["include_raw"] is False
