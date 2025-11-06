"""Tests for judge provider compatibility with both safety and authenticity scorers."""

from __future__ import annotations

import json
import pytest

from alignmenter.providers.judges import OpenAIJudge, AnthropicJudge


class MockOpenAIClient:
    """Mock OpenAI client for testing."""

    def __init__(self, response_content: str):
        self.response_content = response_content

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        """Return mock response."""

        class MockUsage:
            prompt_tokens = 100
            completion_tokens = 50
            total_tokens = 150

        class MockMessage:
            def __init__(self, content):
                self.content = content

        class MockChoice:
            def __init__(self, content):
                self.message = MockMessage(content)

        class MockResponse:
            def __init__(self, content):
                self.choices = [MockChoice(content)]
                self.usage = MockUsage()

        return MockResponse(self.response_content)


class MockAnthropicClient:
    """Mock Anthropic client for testing."""

    def __init__(self, response_content: str):
        self.response_content = response_content

    @property
    def messages(self):
        return self

    def create(self, **kwargs):
        """Return mock response."""

        class MockTextBlock:
            def __init__(self, text):
                self.text = text

        class MockUsage:
            input_tokens = 100
            output_tokens = 50

        class MockResponse:
            def __init__(self, content):
                self.content = [MockTextBlock(content)]
                self.usage = MockUsage()

        return MockResponse(self.response_content)


def test_openai_judge_returns_raw_json():
    """Test that OpenAI judge returns raw JSON in notes field."""
    # Mock response with full authenticity judge format
    full_json = json.dumps({
        "score": 8,
        "reasoning": "Good brand voice alignment",
        "strengths": ["Uses preferred vocabulary", "Appropriate tone"],
        "weaknesses": ["Missing some brand keywords"],
        "suggestion": "Add more signal and baseline terminology",
        "context_appropriate": True,
    })

    mock_client = MockOpenAIClient(full_json)
    judge = OpenAIJudge(model="gpt-4o", client=mock_client)

    result = judge.evaluate("Test prompt")

    # Should return raw JSON in notes
    assert result["notes"] == full_json

    # Should parse score for backward compatibility with SafetyScorer
    # Note: score is clamped to 0.0-1.0 range for safety scorer
    assert result["score"] == 1.0  # 8.0 clamped to max 1.0

    # AuthenticityJudge should be able to parse the full JSON
    parsed = json.loads(result["notes"])
    assert parsed["reasoning"] == "Good brand voice alignment"
    assert len(parsed["strengths"]) == 2
    assert parsed["suggestion"] == "Add more signal and baseline terminology"


def test_anthropic_judge_returns_raw_json():
    """Test that Anthropic judge returns raw JSON in notes field."""
    # Mock response with full authenticity judge format
    full_json = json.dumps({
        "score": 0.7,
        "reasoning": "Decent alignment but could improve",
        "strengths": ["Clear communication"],
        "weaknesses": ["Too formal for brand"],
        "suggestion": "Use more casual language",
        "context_appropriate": True,
    })

    mock_client = MockAnthropicClient(full_json)
    judge = AnthropicJudge(model="claude-3-5-sonnet-20241022", client=mock_client)

    result = judge.evaluate("Test prompt")

    # Should return raw JSON in notes
    assert result["notes"] == full_json

    # Should parse score for backward compatibility with SafetyScorer
    assert result["score"] == 0.7

    # AuthenticityJudge should be able to parse the full JSON
    parsed = json.loads(result["notes"])
    assert parsed["reasoning"] == "Decent alignment but could improve"
    assert len(parsed["weaknesses"]) == 1
    assert parsed["suggestion"] == "Use more casual language"


def test_safety_scorer_format_compatibility():
    """Test that safety scorer format still works (backward compatibility)."""
    # Mock response with safety judge format (simpler)
    safety_json = json.dumps({
        "score": 0.9,
        "notes": "Minor safety issues detected in language",
    })

    mock_client = MockOpenAIClient(safety_json)
    judge = OpenAIJudge(model="gpt-4o", client=mock_client)

    result = judge.evaluate("Test prompt")

    # Should return raw JSON in notes
    assert result["notes"] == safety_json

    # Should parse score for SafetyScorer
    assert result["score"] == 0.9

    # SafetyScorer can also parse the notes if needed
    parsed = json.loads(result["notes"])
    assert parsed["notes"] == "Minor safety issues detected in language"


def test_malformed_json_fallback():
    """Test graceful handling of non-JSON responses."""
    malformed_content = "This is not valid JSON, just plain text"

    mock_client = MockOpenAIClient(malformed_content)
    judge = OpenAIJudge(model="gpt-4o", client=mock_client)

    result = judge.evaluate("Test prompt")

    # Should return raw content in notes
    assert result["notes"] == malformed_content

    # Score should fallback to 0.0
    assert result["score"] == 0.0

    # AuthenticityJudge will handle this and return neutral 5.0 score
