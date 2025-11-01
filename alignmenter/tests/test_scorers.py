"""Tests for baseline scorers."""

from __future__ import annotations

from pathlib import Path

from alignmenter.scorers.authenticity import AuthenticityScorer
from alignmenter.scorers.safety import SafetyScorer
from alignmenter.scorers.stability import StabilityScorer


def _sample_sessions():
    return [
        {
            "session_id": "s1",
            "turns": [
                {"role": "user", "text": "hi"},
                {"role": "assistant", "text": "This is a signal response with precision."},
                {"role": "assistant", "text": "Another precise answer to test consistency."},
            ],
        },
        {
            "session_id": "s2",
            "turns": [
                {"role": "user", "text": "hello"},
                {"role": "assistant", "text": "We should avoid talking about an attack."},
                {"role": "assistant", "text": "Continuing the conversation cautiously."},
            ],
        },
    ]


def _fixture_root() -> Path:
    return Path(__file__).resolve().parents[2] / "alignmenter"


def test_authenticity_scorer(tmp_path: Path) -> None:
    persona_path = _fixture_root() / "configs" / "persona" / "default.yaml"
    scorer = AuthenticityScorer(persona_path=persona_path)
    result = scorer.score(_sample_sessions())
    assert 0.0 <= result["mean"] <= 1.0
    assert 0.0 <= result["style_sim"] <= 1.0
    assert 0.0 <= result["traits"] <= 1.0
    assert 0.0 <= result["lexicon"] <= 1.0
    assert result["turns"] == 4
    assert result["tokens"] > 0


def test_safety_scorer(tmp_path: Path) -> None:
    keywords_path = _fixture_root() / "configs" / "safety_keywords.yaml"
    scorer = SafetyScorer(keyword_path=keywords_path)
    result = scorer.score(_sample_sessions())
    assert result["violations"] >= 1
    assert "violence" in result["categories"]
    assert result["judge_calls"] == 0
    assert result["judge_budget"] is None


def test_stability_scorer() -> None:
    scorer = StabilityScorer()
    result = scorer.score(_sample_sessions())
    assert 0.0 <= result["stability"] <= 1.0
    assert result["sessions"] == 2
    assert "session_variance" in result


def test_safety_scorer_respects_judge_budget(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2] / "alignmenter"
    keywords_path = root / "configs" / "safety_keywords.yaml"

    judge_calls = {"count": 0}

    def judge(prompt: str) -> dict:  # pragma: no cover - trivial closure
        judge_calls["count"] += 1
        return {"score": 0.4, "notes": prompt}

    scorer = SafetyScorer(keyword_path=keywords_path, judge=judge, judge_budget=1)
    result = scorer.score(_sample_sessions())

    assert result["judge_calls"] == 1
    assert judge_calls["count"] == 1
    assert result["judge_budget"] == 1
