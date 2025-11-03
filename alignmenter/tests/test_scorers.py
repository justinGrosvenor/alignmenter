"""Tests for baseline scorers."""

from __future__ import annotations

import json
from pathlib import Path

from alignmenter.scorers.authenticity import (
    AuthenticityScorer,
    load_persona_profile,
    score_turn,
    lexicon_score,
    traits_probability,
    bootstrap_ci,
    tokenize,
)
from alignmenter.scorers.safety import SafetyScorer
from alignmenter.scorers.stability import StabilityScorer


class MockEmbeddingProvider:
    """Mock embedding provider for deterministic testing."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return deterministic embeddings based on text hash."""
        embeddings = []
        for text in texts:
            # Simple hash-based embedding for reproducibility
            seed = sum(ord(c) for c in text)
            vector = [(seed * (i + 1)) % 100 / 100.0 for i in range(self.dimension)]
            embeddings.append(vector)
        return embeddings


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
    assert 0.0 <= result["rule_score"] <= 1.0
    assert 0.0 <= result["score"] <= 1.0
    assert result["judge_cost_spent"] == 0.0
    assert result["judge_cost_budget"] is None
    assert result["classifier_calls"] == 4


def test_stability_scorer() -> None:
    scorer = StabilityScorer()
    result = scorer.score(_sample_sessions())
    assert 0.0 <= result["stability"] <= 1.0
    assert result["sessions"] == 2
    assert "session_variance" in result
    assert "normalized_variance" in result


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
    assert result["fused_judge"] == 0.4
    assert result["judge_cost_spent"] == 0.0
    assert not result["judge_budget_threshold_hit"]


def test_safety_scorer_budget_threshold() -> None:
    root = Path(__file__).resolve().parents[2] / "alignmenter"
    keywords_path = root / "configs" / "safety_keywords.yaml"

    calls = {"count": 0}

    def judge(prompt: str) -> dict:
        calls["count"] += 1
        return {
            "score": 0.5,
            "notes": "checked",
            "usage": {"prompt_tokens": 900, "completion_tokens": 100},
        }

    cost_config = {
        "budget_usd": 0.05,
        "price_per_1k_input": 0.015,
        "price_per_1k_output": 0.06,
        "estimated_tokens_per_call": 1000,
    }

    scorer = SafetyScorer(
        keyword_path=keywords_path,
        judge=judge,
        judge_budget=None,
        cost_config=cost_config,
    )

    result = scorer.score(_sample_sessions())

    assert calls["count"] >= 1
    assert result["judge_cost_spent"] >= cost_config["budget_usd"] * 0.9
    assert result["judge_budget_threshold_hit"]
    assert result["judge_calls_skipped"] >= 0


# Edge case tests


def test_authenticity_empty_sessions() -> None:
    """Test authenticity scorer with empty sessions."""
    persona_path = _fixture_root() / "configs" / "persona" / "default.yaml"
    scorer = AuthenticityScorer(persona_path=persona_path)
    result = scorer.score([])
    assert result["mean"] == 0.0
    assert result["turns"] == 0
    assert result["tokens"] == 0
    assert result["ci95_low"] is None
    assert result["ci95_high"] is None


def test_authenticity_empty_turns() -> None:
    """Test authenticity scorer with sessions containing no assistant turns."""
    persona_path = _fixture_root() / "configs" / "persona" / "default.yaml"
    scorer = AuthenticityScorer(persona_path=persona_path)
    sessions = [{"session_id": "s1", "turns": [{"role": "user", "text": "hello"}]}]
    result = scorer.score(sessions)
    assert result["mean"] == 0.0
    assert result["turns"] == 0


def test_safety_empty_sessions() -> None:
    """Test safety scorer with empty sessions."""
    keywords_path = _fixture_root() / "configs" / "safety_keywords.yaml"
    scorer = SafetyScorer(keyword_path=keywords_path)
    result = scorer.score([])
    assert result["violations"] == 0
    assert result["turns"] == 0
    assert result["score"] == 1.0


def test_stability_empty_sessions() -> None:
    """Test stability scorer with empty sessions."""
    scorer = StabilityScorer()
    result = scorer.score([])
    assert result["sessions"] == 0
    assert result["stability"] == 1.0


def test_stability_single_session() -> None:
    """Test stability scorer with single session."""
    scorer = StabilityScorer()
    sessions = [
        {
            "session_id": "s1",
            "turns": [
                {"role": "assistant", "text": "Hello there."},
                {"role": "assistant", "text": "How can I help?"},
            ],
        }
    ]
    result = scorer.score(sessions)
    assert result["sessions"] == 1
    assert 0.0 <= result["stability"] <= 1.0


# Trait model and calibration tests


def test_authenticity_with_calibrated_weights(tmp_path: Path) -> None:
    """Test authenticity scorer with custom calibrated weights."""
    calibration_path = tmp_path / "test.traits.json"

    calibration = {
        "weights": {"style": 0.5, "traits": 0.3, "lexicon": 0.2},
        "trait_model": {
            "bias": 0.5,
            "token_weights": {"signal": 1.0, "precision": 0.8, "attack": -1.5},
            "phrase_weights": {"avoid talking": -2.0},
        },
    }
    calibration_path.write_text(json.dumps(calibration))

    # Create persona with matching stem
    test_persona_path = tmp_path / "test.yaml"
    test_persona_path.write_text(
        """
id: test
lexicon:
  preferred: [signal, precision]
  avoid: [attack]
exemplars:
  - "This is a signal response with precision."
"""
    )

    scorer = AuthenticityScorer(persona_path=test_persona_path)
    sessions = [
        {
            "session_id": "s1",
            "turns": [
                {"role": "assistant", "text": "This is a signal response with precision."}
            ],
        }
    ]
    result = scorer.score(sessions)

    assert result["turns"] == 1
    assert 0.0 <= result["mean"] <= 1.0
    assert 0.0 <= result["traits"] <= 1.0


def test_trait_model_phrase_weights() -> None:
    """Test that phrase weights are applied in trait scoring."""
    from alignmenter.scorers.authenticity import PersonaProfile, TraitModel

    trait_model = TraitModel(
        bias=0.0,
        token_weights={"signal": 1.0},
        phrase_weights={"avoid talking": -2.0, "signal response": 1.5},
    )

    profile = PersonaProfile(
        preferred={"signal"},
        avoided={"attack"},
        exemplars=[],
        trait_positive={"signal"},
        trait_negative={"attack"},
        weights={"style": 0.4, "traits": 0.4, "lexicon": 0.2},
        trait_model=trait_model,
    )

    # Text with positive phrase
    tokens1 = tokenize("This is a signal response.")
    score1 = traits_probability("This is a signal response.", tokens1, profile)

    # Text without phrase
    tokens2 = tokenize("This is signal.")
    score2 = traits_probability("This is signal.", tokens2, profile)

    # Phrase weight should boost score1
    assert score1 > score2


def test_lexicon_scoring_edge_cases() -> None:
    """Test lexicon scoring with various edge cases."""
    from alignmenter.scorers.authenticity import PersonaProfile, TraitModel

    empty_trait_model = TraitModel(bias=0.0, token_weights={}, phrase_weights={})

    # Empty tokens
    profile = PersonaProfile(
        preferred={"signal"},
        avoided={"attack"},
        exemplars=[],
        trait_positive=set(),
        trait_negative=set(),
        weights={"style": 0.6, "traits": 0.25, "lexicon": 0.15},
        trait_model=empty_trait_model,
    )
    assert lexicon_score([], profile) == 0.5

    # Only preferred
    assert lexicon_score(["signal", "precision"], profile) == 1.0

    # Only avoided
    assert lexicon_score(["attack", "weapon"], profile) == 0.0

    # Mixed
    score = lexicon_score(["signal", "attack"], profile)
    assert 0.0 < score < 1.0

    # Neutral tokens
    score = lexicon_score(["hello", "world"], profile)
    assert score == 0.5


def test_bootstrap_ci_coverage() -> None:
    """Test bootstrap confidence interval calculation."""
    import random

    rng = random.Random(42)

    # Sufficient samples
    scores = [0.7, 0.8, 0.75, 0.9, 0.65, 0.85, 0.7, 0.8]
    low, high = bootstrap_ci(rng, scores)
    assert low is not None
    assert high is not None
    assert low < high
    assert 0.0 <= low <= 1.0
    assert 0.0 <= high <= 1.0

    # Insufficient samples
    low, high = bootstrap_ci(rng, [0.5])
    assert low is None
    assert high is None


def test_tokenize_edge_cases() -> None:
    """Test tokenization edge cases."""
    assert tokenize("") == []
    assert tokenize("hello world") == ["hello", "world"]
    assert tokenize("Hello WORLD") == ["hello", "world"]
    assert tokenize("it's a test") == ["it's", "a", "test"]  # Apostrophes are kept
    assert tokenize("123 test-456") == ["123", "test", "456"]


# Safety scorer advanced tests


def test_safety_multiple_violation_categories() -> None:
    """Test safety scorer detects multiple violation categories."""
    keywords_path = _fixture_root() / "configs" / "safety_keywords.yaml"
    scorer = SafetyScorer(keyword_path=keywords_path)

    sessions = [
        {
            "session_id": "s1",
            "turns": [
                {"role": "assistant", "text": "I can help you attack someone."},
                {"role": "assistant", "text": "Here's how to harm yourself."},
                {"role": "assistant", "text": "Let's discuss weapons and violence."},
            ],
        }
    ]

    result = scorer.score(sessions)
    assert result["violations"] >= 1  # At least one violation
    assert len(result["categories"]) >= 1
    assert result["violation_rate"] > 0.0


def test_safety_no_violations() -> None:
    """Test safety scorer with clean conversations."""
    keywords_path = _fixture_root() / "configs" / "safety_keywords.yaml"
    scorer = SafetyScorer(keyword_path=keywords_path)

    sessions = [
        {
            "session_id": "s1",
            "turns": [
                {"role": "assistant", "text": "Hello! How can I help you today?"},
                {"role": "assistant", "text": "That's a great question."},
            ],
        }
    ]

    result = scorer.score(sessions)
    assert result["violations"] == 0
    assert result["violation_rate"] == 0.0
    assert result["rule_score"] == 1.0
    assert result["score"] == 1.0


def test_safety_classifier_integration(tmp_path: Path) -> None:
    """Test safety scorer with custom classifier."""
    keywords_path = _fixture_root() / "configs" / "safety_keywords.yaml"

    classifier_calls = {"count": 0}

    def mock_classifier(text: str) -> float:
        classifier_calls["count"] += 1
        if "bad" in text.lower():
            return 0.2
        return 0.9

    scorer = SafetyScorer(keyword_path=keywords_path, classifier=mock_classifier)

    sessions = [
        {
            "session_id": "s1",
            "turns": [
                {"role": "assistant", "text": "This is a good response."},
                {"role": "assistant", "text": "This is a bad response."},
            ],
        }
    ]

    result = scorer.score(sessions)
    assert result["classifier_calls"] == 2
    assert classifier_calls["count"] == 2
    assert result["fused_judge"] is not None


def test_safety_judge_with_usage_tracking() -> None:
    """Test safety scorer tracks judge usage correctly."""
    keywords_path = _fixture_root() / "configs" / "safety_keywords.yaml"

    def judge_with_usage(text: str) -> dict:
        return {
            "score": 0.8,
            "notes": "checked",
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        }

    cost_config = {
        "budget_usd": 10.0,
        "price_per_1k_input": 0.01,
        "price_per_1k_output": 0.03,
    }

    scorer = SafetyScorer(
        keyword_path=keywords_path, judge=judge_with_usage, cost_config=cost_config
    )

    sessions = [
        {
            "session_id": "s1",
            "turns": [{"role": "assistant", "text": "Test response."}],
        }
    ]

    result = scorer.score(sessions)
    assert result["judge_calls"] == 1
    assert result["judge_cost_spent"] > 0.0
    expected_cost = (100 / 1000.0) * 0.01 + (20 / 1000.0) * 0.03
    assert abs(result["judge_cost_spent"] - expected_cost) < 0.0001


# Stability scorer advanced tests


def test_stability_high_variance() -> None:
    """Test stability scorer detects high variance across sessions."""
    scorer = StabilityScorer()

    sessions = [
        {
            "session_id": "s1",
            "turns": [
                {"role": "assistant", "text": "Very professional corporate response."},
                {"role": "assistant", "text": "Delivering precise technical analysis."},
            ],
        },
        {
            "session_id": "s2",
            "turns": [
                {"role": "assistant", "text": "lol yeah bro totally!"},
                {"role": "assistant", "text": "haha that's so hype!!"},
            ],
        },
    ]

    result = scorer.score(sessions)
    assert result["sessions"] == 2
    assert 0.0 <= result["stability"] <= 1.0
    assert result["session_variance"] >= 0.0


def test_stability_low_variance() -> None:
    """Test stability scorer detects low variance (consistent style)."""
    scorer = StabilityScorer()

    sessions = [
        {
            "session_id": "s1",
            "turns": [
                {"role": "assistant", "text": "This is a consistent response."},
                {"role": "assistant", "text": "Another consistent response."},
            ],
        },
        {
            "session_id": "s2",
            "turns": [
                {"role": "assistant", "text": "A third consistent response."},
                {"role": "assistant", "text": "Yet another consistent response."},
            ],
        },
    ]

    result = scorer.score(sessions)
    assert result["sessions"] == 2
    assert result["stability"] > 0.5


def test_stability_mixed_roles() -> None:
    """Test stability scorer ignores non-assistant turns."""
    scorer = StabilityScorer()

    sessions = [
        {
            "session_id": "s1",
            "turns": [
                {"role": "user", "text": "User message should be ignored."},
                {"role": "assistant", "text": "First assistant response."},
                {"role": "system", "text": "System message should be ignored."},
                {"role": "assistant", "text": "Second assistant response."},
            ],
        }
    ]

    result = scorer.score(sessions)
    assert result["sessions"] == 1
    # Only assistant turns are counted, min_turns=2 by default


# Persona profile loading tests


def test_persona_profile_minimal(tmp_path: Path) -> None:
    """Test loading minimal persona profile."""
    persona_path = tmp_path / "minimal.yaml"
    persona_path.write_text("id: minimal\n")

    embedder = MockEmbeddingProvider()
    profile = load_persona_profile(persona_path, embedder)

    assert len(profile.preferred) == 0
    assert len(profile.avoided) == 0
    assert len(profile.exemplars) == 1  # Default fallback
    assert profile.weights["style"] == 0.6
    assert profile.weights["traits"] == 0.25
    assert profile.weights["lexicon"] == 0.15


def test_persona_profile_with_lexicon(tmp_path: Path) -> None:
    """Test loading persona with lexicon."""
    persona_path = tmp_path / "lexicon.yaml"
    persona_path.write_text(
        """
id: lexicon_test
lexicon:
  preferred: [signal, precision, clarity]
  avoid: [lol, bro, hype]
"""
    )

    embedder = MockEmbeddingProvider()
    profile = load_persona_profile(persona_path, embedder)

    assert profile.preferred == {"signal", "precision", "clarity"}
    assert profile.avoided == {"lol", "bro", "hype"}


def test_persona_profile_with_exemplars(tmp_path: Path) -> None:
    """Test loading persona with exemplars."""
    persona_path = tmp_path / "exemplars.yaml"
    persona_path.write_text(
        """
id: exemplar_test
exemplars:
  - "This is the first example response."
  - "This is the second example response."
"""
    )

    embedder = MockEmbeddingProvider()
    profile = load_persona_profile(persona_path, embedder)

    assert len(profile.exemplars) == 2


def test_score_turn_integration(tmp_path: Path) -> None:
    """Test full turn scoring with all components."""
    persona_path = tmp_path / "turn_test.yaml"
    persona_path.write_text(
        """
id: turn_test
lexicon:
  preferred: [signal, precision]
  avoid: [attack]
exemplars:
  - "A precise signal response."
"""
    )

    embedder = MockEmbeddingProvider()
    profile = load_persona_profile(persona_path, embedder)

    text = "This is a signal response with precision."
    tokens = tokenize(text)
    turn = score_turn(text, tokens, profile, embedder)

    assert 0.0 <= turn.style_sim <= 1.0
    assert 0.0 <= turn.traits <= 1.0
    assert 0.0 <= turn.lexicon <= 1.0
    assert 0.0 <= turn.score <= 1.0
