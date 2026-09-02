"""Run-config parsing for the retrieval-grounded scorers and custom scorer specs."""

from __future__ import annotations

from pathlib import Path

from alignmenter.run_config import load_run_options


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "run.yaml"
    path.write_text(body)
    return path


def test_grounded_sections_parse(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        """
model: openai:gpt-4o-mini
scorers:
  grounding:
    enabled: true
    units_only: false
    threshold_fail: 0.8
  faithfulness:
    judge: anthropic:claude-sonnet-5
    budget: 40
    domain: an offline survival reference
    max_excerpt_chars: 900
    threshold_warn: 0.9
  custom:
    - atlas_eval.scorers:ContributionScorer
    - spec: my_product.scorers:ResolutionRate
thresholds:
  dangerous:
    fail: 0
""",
    )
    options = load_run_options(path)
    assert options["grounding"] is True
    assert options["grounding_units_only"] is False
    assert options["faithfulness"] is True
    assert options["faithfulness_judge"] == "anthropic:claude-sonnet-5"
    assert options["faithfulness_budget"] == 40
    assert options["faithfulness_domain"] == "an offline survival reference"
    assert options["faithfulness_max_excerpt_chars"] == 900
    assert options["custom_scorers"] == [
        "atlas_eval.scorers:ContributionScorer",
        "my_product.scorers:ResolutionRate",
    ]
    assert options["thresholds"]["grounding"] == {"fail": 0.8}
    assert options["thresholds"]["faithfulness"] == {"warn": 0.9}
    assert options["thresholds"]["dangerous"] == {"fail": 0.0}


def test_grounded_sections_default_off(tmp_path: Path) -> None:
    options = load_run_options(_write(tmp_path, "model: openai:gpt-4o-mini\n"))
    assert "grounding" not in options
    assert "faithfulness" not in options
    assert "custom_scorers" not in options


def test_boolean_shorthand(tmp_path: Path) -> None:
    options = load_run_options(_write(tmp_path, "scorers:\n  grounding: true\n  faithfulness: false\n"))
    assert options["grounding"] is True
    assert options["faithfulness"] is False
