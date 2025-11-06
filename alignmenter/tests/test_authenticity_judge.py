"""Tests for authenticity judge."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alignmenter.judges.authenticity_judge import AuthenticityJudge, JudgeAnalysis
from alignmenter.judges.prompts import format_authenticity_prompt


class MockJudgeProvider:
    """Mock judge provider for testing."""

    name = "mock"

    def __init__(self, mock_response: dict | None = None, model: str | None = None):
        self.model = model  # For pricing calculations
        self.mock_response = mock_response or {
            "score": 0.8,
            "notes": json.dumps({
                "score": 8,
                "reasoning": "Good brand voice alignment with preferred vocabulary.",
                "strengths": ["Uses preferred terminology", "Appropriate tone"],
                "weaknesses": [],
                "suggestion": None,
                "context_appropriate": True,
            }),
            "usage": {
                "prompt_tokens": 500,
                "completion_tokens": 100,
                "total_tokens": 600,
            },
        }
        self.calls = []

    def evaluate(self, prompt: str) -> dict:
        self.calls.append(prompt)
        return self.mock_response


def _fixture_root() -> Path:
    return Path(__file__).resolve().parents[2] / "alignmenter"


def _sample_session_turns() -> list[dict]:
    return [
        {"role": "user", "text": "What's your refund policy?"},
        {"role": "assistant", "text": "Our baseline policy allows refunds within 30 days with signal documentation."},
        {"role": "user", "text": "How do I request one?"},
        {"role": "assistant", "text": "Submit a ticket through our alignment portal with your order details."},
    ]


def test_authenticity_judge_initialization():
    """Test judge initialization with persona."""
    persona_path = _fixture_root() / "configs" / "persona" / "default.yaml"
    mock_provider = MockJudgeProvider()
    judge = AuthenticityJudge(
        persona_path=persona_path,
        judge_provider=mock_provider,
        cost_per_call=0.003,
    )

    assert judge.persona_id == "default_v1"
    assert "absolutely" in judge.preferred_words or "configure" in judge.preferred_words
    assert "lol" in judge.avoided_words
    assert len(judge.exemplars) > 0
    assert judge.total_cost == 0.0
    assert judge.calls_made == 0


def test_authenticity_judge_evaluate_session():
    """Test evaluating a session."""
    persona_path = _fixture_root() / "configs" / "persona" / "default.yaml"
    mock_provider = MockJudgeProvider()
    judge = AuthenticityJudge(
        persona_path=persona_path,
        judge_provider=mock_provider,
        cost_per_call=0.003,
    )

    turns = _sample_session_turns()
    analysis = judge.evaluate_session(
        session_id="test-001",
        turns=turns,
        scenario_tag="customer_service",
        calibrated_score=0.75,
    )

    assert isinstance(analysis, JudgeAnalysis)
    assert analysis.session_id == "test-001"
    assert 0 <= analysis.score <= 10
    assert analysis.score == 8.0
    assert analysis.reasoning != ""
    assert analysis.calibrated_score == 0.75
    assert analysis.cost == 0.003
    assert judge.calls_made == 1
    assert judge.total_cost == 0.003


def test_authenticity_judge_parse_json_response():
    """Test parsing valid JSON response."""
    persona_path = _fixture_root() / "configs" / "persona" / "default.yaml"
    mock_provider = MockJudgeProvider()
    judge = AuthenticityJudge(
        persona_path=persona_path,
        judge_provider=mock_provider,
    )

    turns = _sample_session_turns()
    analysis = judge.evaluate_session(
        session_id="test-002",
        turns=turns,
    )

    assert analysis.session_id == "test-002"
    assert analysis.score == 8.0
    assert "Good brand voice" in analysis.reasoning
    assert len(analysis.strengths) == 2
    assert len(analysis.weaknesses) == 0
    assert analysis.suggestion is None
    assert analysis.context_appropriate is True


def test_authenticity_judge_parse_markdown_json():
    """Test parsing JSON wrapped in markdown code blocks."""
    persona_path = _fixture_root() / "configs" / "persona" / "default.yaml"
    mock_response = {
        "score": 0.6,
        "notes": """Here's my analysis:

```json
{
  "score": 6,
  "reasoning": "Decent but could be better.",
  "strengths": ["Clear communication"],
  "weaknesses": ["Missing brand keywords"],
  "suggestion": "Add more signal and baseline terminology",
  "context_appropriate": true
}
```

Hope this helps!""",
        "usage": {"prompt_tokens": 400, "completion_tokens": 80},
    }
    mock_provider = MockJudgeProvider(mock_response)
    judge = AuthenticityJudge(
        persona_path=persona_path,
        judge_provider=mock_provider,
    )

    turns = _sample_session_turns()
    analysis = judge.evaluate_session(session_id="test-003", turns=turns)

    assert analysis.score == 6.0
    assert "could be better" in analysis.reasoning
    assert analysis.suggestion == "Add more signal and baseline terminology"


def test_authenticity_judge_invalid_json_fallback():
    """Test fallback when JSON parsing fails."""
    persona_path = _fixture_root() / "configs" / "persona" / "default.yaml"
    mock_response = {
        "score": 0.5,
        "notes": "This is not valid JSON at all, just plain text response.",
        "usage": None,
    }
    mock_provider = MockJudgeProvider(mock_response)
    judge = AuthenticityJudge(
        persona_path=persona_path,
        judge_provider=mock_provider,
    )

    turns = _sample_session_turns()
    analysis = judge.evaluate_session(session_id="test-004", turns=turns)

    assert analysis.score == 5.0  # Neutral fallback
    assert "Failed to parse" in analysis.reasoning
    assert len(analysis.strengths) == 0
    assert len(analysis.weaknesses) == 0


def test_authenticity_judge_cost_tracking():
    """Test cost tracking across multiple calls."""
    persona_path = _fixture_root() / "configs" / "persona" / "default.yaml"
    mock_provider = MockJudgeProvider()
    judge = AuthenticityJudge(
        persona_path=persona_path,
        judge_provider=mock_provider,
        cost_per_call=0.005,
    )

    turns = _sample_session_turns()

    # Make 3 calls
    for i in range(3):
        judge.evaluate_session(session_id=f"test-{i}", turns=turns)

    assert judge.calls_made == 3
    assert judge.total_cost == pytest.approx(0.015, rel=1e-6)

    summary = judge.get_cost_summary()
    assert summary.calls_made == 3
    assert summary.total_cost == pytest.approx(0.015, rel=1e-6)
    assert summary.cost_per_call == 0.005
    assert summary.average_cost == pytest.approx(0.005, rel=1e-6)


def test_authenticity_judge_exception_handling():
    """Test graceful handling when judge provider fails."""
    persona_path = _fixture_root() / "configs" / "persona" / "default.yaml"

    class FailingProvider:
        name = "failing"

        def evaluate(self, prompt: str) -> dict:
            raise RuntimeError("Provider connection failed")

    judge = AuthenticityJudge(
        persona_path=persona_path,
        judge_provider=FailingProvider(),
    )

    turns = _sample_session_turns()
    analysis = judge.evaluate_session(session_id="test-error", turns=turns)

    assert analysis.session_id == "test-error"
    assert analysis.score == 5.0  # Neutral fallback
    assert "Judge evaluation failed" in analysis.reasoning
    assert analysis.cost == 0.0


def test_format_authenticity_prompt():
    """Test prompt formatting."""
    prompt = format_authenticity_prompt(
        persona_id="test-bot",
        persona_description="A helpful AI assistant",
        persona_tone=["professional", "friendly"],
        persona_formality="business_casual",
        preferred_words=["efficient", "reliable"],
        avoided_words=["lol", "bro"],
        exemplars=["We prioritize efficiency.", "Our reliable service is key."],
        scenario_tag="customer_support",
        session_id="test-session",
        conversation_turns=[
            {"role": "user", "text": "Hello"},
            {"role": "assistant", "text": "Hi there!"},
        ],
    )

    assert "test-bot" in prompt
    assert "A helpful AI assistant" in prompt
    assert "professional, friendly" in prompt
    assert "business_casual" in prompt
    assert "efficient" in prompt
    assert "lol" in prompt
    assert "customer_support" in prompt
    assert "test-session" in prompt
    assert "Hello" in prompt
    assert "Hi there!" in prompt


def test_judge_analysis_dataclass():
    """Test JudgeAnalysis dataclass."""
    analysis = JudgeAnalysis(
        session_id="test",
        score=7.5,
        reasoning="Good work",
        strengths=["Clear", "Concise"],
        weaknesses=["Missing keywords"],
        suggestion="Add more brand terms",
        context_appropriate=True,
        calibrated_score=0.72,
        cost=0.004,
    )

    assert analysis.session_id == "test"
    assert analysis.score == 7.5
    assert analysis.reasoning == "Good work"
    assert len(analysis.strengths) == 2
    assert len(analysis.weaknesses) == 1
    assert analysis.suggestion == "Add more brand terms"
    assert analysis.context_appropriate is True
    assert analysis.calibrated_score == 0.72
    assert analysis.cost == 0.004


def test_persona_tone_string_normalization(tmp_path):
    """Test that persona tone is normalized to list when provided as string."""
    # Create a test persona with tone as a string (not a list)
    persona_content = """
id: test_string_tone
description: Test persona with string tone
voice:
  tone: formal
  formality: business
lexicon:
  preferred: [signal, baseline]
  avoid: [lol, bro]
exemplars:
  - "Our baseline approach prioritizes signal clarity."
"""
    persona_path = tmp_path / "test_persona.yaml"
    persona_path.write_text(persona_content)

    mock_provider = MockJudgeProvider()
    judge = AuthenticityJudge(
        persona_path=persona_path,
        judge_provider=mock_provider,
    )

    # Should normalize string to list
    assert isinstance(judge.persona_tone, list)
    assert judge.persona_tone == ["formal"]

    # Verify it works in prompt formatting
    turns = _sample_session_turns()
    analysis = judge.evaluate_session(session_id="test-tone", turns=turns)
    assert analysis.score == 8.0


def test_parse_prose_wrapped_json():
    """Test parsing JSON wrapped in explanatory prose."""
    persona_path = _fixture_root() / "configs" / "persona" / "default.yaml"
    mock_response = {
        "score": 0.7,
        "notes": """I've analyzed this conversation and here are my findings:

{
  "score": 7,
  "reasoning": "Mostly on-brand with some areas for improvement.",
  "strengths": ["Uses preferred vocabulary", "Professional tone"],
  "weaknesses": ["Could be more concise"],
  "suggestion": "Tighten up the language",
  "context_appropriate": true
}

This assessment reflects the overall brand alignment.""",
        "usage": {"prompt_tokens": 450, "completion_tokens": 90},
    }
    mock_provider = MockJudgeProvider(mock_response)
    judge = AuthenticityJudge(
        persona_path=persona_path,
        judge_provider=mock_provider,
    )

    turns = _sample_session_turns()
    analysis = judge.evaluate_session(session_id="test-prose", turns=turns)

    # Should successfully extract JSON despite surrounding prose
    assert analysis.score == 7.0
    assert "Mostly on-brand" in analysis.reasoning
    assert len(analysis.strengths) == 2
    assert len(analysis.weaknesses) == 1
    assert analysis.suggestion == "Tighten up the language"


def test_real_cost_calculation_with_usage():
    """Test that real costs are calculated from token usage when available."""
    persona_path = _fixture_root() / "configs" / "persona" / "default.yaml"

    # Mock response with realistic token counts for gpt-4o-mini
    mock_response = {
        "score": 0.8,
        "notes": json.dumps({
            "score": 8,
            "reasoning": "Good alignment.",
            "strengths": ["Clear"],
            "weaknesses": [],
            "suggestion": None,
            "context_appropriate": True,
        }),
        "usage": {
            "prompt_tokens": 1000,
            "completion_tokens": 200,
            "total_tokens": 1200,
        },
    }

    # Test with gpt-4o-mini pricing: $0.15 per 1M input, $0.60 per 1M output
    mock_provider = MockJudgeProvider(mock_response, model="gpt-4o-mini")
    judge = AuthenticityJudge(
        persona_path=persona_path,
        judge_provider=mock_provider,
        cost_per_call=0.005,  # This should be overridden by real calculation
    )

    turns = _sample_session_turns()
    analysis = judge.evaluate_session(session_id="test-cost", turns=turns)

    # Expected cost: (1000 / 1M * $0.15) + (200 / 1M * $0.60)
    # = $0.00015 + $0.00012 = $0.00027
    expected_cost = (1000 / 1_000_000) * 0.15 + (200 / 1_000_000) * 0.60
    assert analysis.cost == pytest.approx(expected_cost, rel=1e-6)
    assert judge.total_cost == pytest.approx(expected_cost, rel=1e-6)

    # Test with model not in pricing table - should fall back to estimate
    mock_provider_unknown = MockJudgeProvider(mock_response, model="unknown-model")
    judge_unknown = AuthenticityJudge(
        persona_path=persona_path,
        judge_provider=mock_provider_unknown,
        cost_per_call=0.005,
    )

    analysis_unknown = judge_unknown.evaluate_session(
        session_id="test-unknown", turns=turns
    )

    # Should fall back to flat estimate
    assert analysis_unknown.cost == 0.005
