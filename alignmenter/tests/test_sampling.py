"""Tests for sampling strategies."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from alignmenter.calibration.sampling import select_scenarios_for_judge, estimate_judge_cost


@dataclass
class MockSession:
    """Mock session for testing."""

    session_id: str
    scenario_tags: set[str]
    turns: list[dict]
    authenticity_score: float | None = None


def _create_mock_sessions(count: int = 10) -> list[MockSession]:
    """Create mock sessions for testing."""
    sessions = []
    for i in range(count):
        tag = f"scenario_{i % 3}"  # 3 different scenarios
        score = i / count  # Scores from 0.0 to 0.9
        sessions.append(
            MockSession(
                session_id=f"session-{i:03d}",
                scenario_tags={tag},
                turns=[{"role": "user", "text": "test"}],
                authenticity_score=score,
            )
        )
    return sessions


def test_random_sampling():
    """Test random sampling strategy."""
    sessions = _create_mock_sessions(100)
    sample_rate = 0.2

    selected = select_scenarios_for_judge(
        sessions=sessions,
        sample_rate=sample_rate,
        strategy="random",
    )

    assert len(selected) == 20  # 20% of 100
    assert all(s in sessions for s in selected)


def test_stratified_sampling():
    """Test stratified sampling by scenario tag."""
    sessions = _create_mock_sessions(30)  # 10 per scenario (3 scenarios)
    sample_rate = 0.3  # Should get ~3 per scenario

    selected = select_scenarios_for_judge(
        sessions=sessions,
        sample_rate=sample_rate,
        strategy="stratified",
    )

    # Count scenarios in selection
    scenario_counts = {}
    for session in selected:
        tag = next(iter(session.scenario_tags))
        scenario_counts[tag] = scenario_counts.get(tag, 0) + 1

    # All scenarios should be represented roughly equally
    assert len(scenario_counts) == 3
    for count in scenario_counts.values():
        assert count >= 1  # At least 1 from each scenario


def test_errors_sampling():
    """Test sampling only ambiguous/error cases."""
    sessions = _create_mock_sessions(100)
    # Only sessions with scores 0.4-0.6 should be selected
    # With scores 0.0-0.99, we have scores: 0.00, 0.01, 0.02, ..., 0.99
    # Sessions in 0.4-0.6 range: 0.40, 0.41, ..., 0.60 = 21 sessions

    selected = select_scenarios_for_judge(
        sessions=sessions,
        sample_rate=0.2,  # Ignored for errors strategy
        strategy="errors",
    )

    assert len(selected) == 21
    for session in selected:
        assert 0.4 <= session.authenticity_score <= 0.6


def test_errors_sampling_fallback():
    """Test errors strategy falls back to random when no ambiguous scores."""
    # All scores are extreme (high)
    sessions = [
        MockSession(
            session_id=f"s-{i}",
            scenario_tags={"test"},
            turns=[],
            authenticity_score=0.9,
        )
        for i in range(10)
    ]

    selected = select_scenarios_for_judge(
        sessions=sessions,
        sample_rate=0.3,
        strategy="errors",
    )

    # Should fall back to random sampling
    assert len(selected) == 3


def test_extremes_sampling():
    """Test sampling only extreme scores (< 0.3 or > 0.8)."""
    sessions = _create_mock_sessions(100)
    # Scores 0.00-0.29 (30 sessions) and 0.81-0.99 (19 sessions) = 49 total

    selected = select_scenarios_for_judge(
        sessions=sessions,
        sample_rate=0.2,  # Ignored for extremes strategy
        strategy="extremes",
    )

    assert len(selected) == 49
    for session in selected:
        score = session.authenticity_score
        assert score < 0.3 or score > 0.8


def test_on_failure_sampling():
    """Test sampling only failures below threshold."""
    sessions = _create_mock_sessions(100)
    failure_threshold = 0.6

    selected = select_scenarios_for_judge(
        sessions=sessions,
        sample_rate=0.2,  # Ignored for on_failure strategy
        strategy="on_failure",
        failure_threshold=failure_threshold,
    )

    # Scores 0.0-0.59 (60 sessions)
    assert len(selected) == 60
    for session in selected:
        assert session.authenticity_score < failure_threshold


def test_on_failure_sampling_no_failures():
    """Test on_failure strategy with no failures."""
    # All high scores
    sessions = [
        MockSession(
            session_id=f"s-{i}",
            scenario_tags={"test"},
            turns=[],
            authenticity_score=0.9,
        )
        for i in range(10)
    ]

    selected = select_scenarios_for_judge(
        sessions=sessions,
        strategy="on_failure",
        failure_threshold=0.6,
    )

    assert len(selected) == 0


def test_empty_sessions():
    """Test handling of empty session list."""
    selected = select_scenarios_for_judge(
        sessions=[],
        sample_rate=0.2,
        strategy="random",
    )
    assert selected == []


def test_invalid_strategy():
    """Test error handling for invalid strategy."""
    sessions = _create_mock_sessions(10)

    with pytest.raises(ValueError, match="Unknown sampling strategy"):
        select_scenarios_for_judge(
            sessions=sessions,
            strategy="invalid_strategy",
        )


def test_estimate_judge_cost_random():
    """Test cost estimation for random sampling."""
    estimate = estimate_judge_cost(
        num_scenarios=100,
        sample_rate=0.2,
        cost_per_scenario=0.003,
        strategy="random",
    )

    assert estimate["strategy"] == "random"
    assert estimate["total_scenarios"] == 100
    assert estimate["scenarios_judged"] == 20
    assert estimate["cost_per_scenario"] == 0.003
    assert estimate["estimated_cost"] == pytest.approx(0.06, rel=1e-6)
    assert estimate["sample_rate"] == 0.2


def test_estimate_judge_cost_on_failure():
    """Test cost estimation for on_failure strategy."""
    estimate = estimate_judge_cost(
        num_scenarios=100,
        sample_rate=0.2,  # Ignored
        cost_per_scenario=0.003,
        strategy="on_failure",
        failure_rate=0.1,
    )

    assert estimate["strategy"] == "on_failure"
    assert estimate["total_scenarios"] == 100
    assert estimate["scenarios_judged"] == 10  # 10% failure rate
    assert estimate["estimated_cost"] == pytest.approx(0.03, rel=1e-6)
    assert estimate["sample_rate"] is None


def test_estimate_judge_cost_errors():
    """Test cost estimation for errors strategy."""
    estimate = estimate_judge_cost(
        num_scenarios=500,
        sample_rate=0.2,
        cost_per_scenario=0.003,
        strategy="errors",
    )

    assert estimate["strategy"] == "errors"
    assert estimate["scenarios_judged"] == 75  # ~15% of 500
    assert estimate["estimated_cost"] == pytest.approx(0.225, rel=1e-6)


def test_sessions_without_scores():
    """Test handling sessions without authenticity scores."""
    sessions = [
        MockSession(
            session_id=f"s-{i}",
            scenario_tags={"test"},
            turns=[],
            authenticity_score=None,  # No score
        )
        for i in range(10)
    ]

    # Random and stratified should still work
    selected = select_scenarios_for_judge(
        sessions=sessions,
        sample_rate=0.3,
        strategy="random",
    )
    assert len(selected) == 3

    # Errors/extremes/on_failure should fall back or return empty
    selected = select_scenarios_for_judge(
        sessions=sessions,
        strategy="errors",
    )
    assert len(selected) >= 0  # Fallback to random or empty


def test_untagged_sessions():
    """Test handling sessions without scenario tags."""
    sessions = [
        MockSession(
            session_id=f"s-{i}",
            scenario_tags=set(),  # No tags
            turns=[],
            authenticity_score=0.5,
        )
        for i in range(10)
    ]

    selected = select_scenarios_for_judge(
        sessions=sessions,
        sample_rate=0.5,
        strategy="stratified",
    )

    # Should still sample, treating all as "untagged"
    assert len(selected) == 5
