"""Sampling strategies for LLM judge evaluation."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Any


def select_scenarios_for_judge(
    sessions: list[Any],
    sample_rate: float = 0.2,
    strategy: str = "stratified",
    failure_threshold: float = 0.6,
) -> list[Any]:
    """Select representative scenarios for LLM judge analysis.

    Args:
        sessions: List of Session objects with attributes:
            - session_id: str
            - scenario_tags: set[str]
            - turns: list[dict]
            - (optional) authenticity_score: float
        sample_rate: Fraction of sessions to sample (0.0-1.0)
        strategy: Selection strategy:
            - "random": Random sample across all sessions
            - "stratified": Equal representation per scenario tag
            - "errors": Only sessions with ambiguous scores (0.4-0.6)
            - "extremes": High confidence cases to verify calibration
            - "on_failure": Only sessions below failure_threshold (most cost-effective)
        failure_threshold: Score threshold for on_failure strategy

    Returns:
        List of selected Session objects
    """
    if not sessions:
        return []

    if strategy == "random":
        k = max(1, int(len(sessions) * sample_rate))
        return random.sample(sessions, min(k, len(sessions)))

    elif strategy == "stratified":
        # Group by scenario tag
        by_scenario = defaultdict(list)
        for session in sessions:
            # Get first tag or "untagged"
            tags = getattr(session, "scenario_tags", set())
            tag = next(iter(tags)) if tags else "untagged"
            by_scenario[tag].append(session)

        # Sample equally from each scenario
        samples = []
        per_scenario = max(1, int(sample_rate * len(sessions) / len(by_scenario)))
        for scenario_sessions in by_scenario.values():
            k = min(per_scenario, len(scenario_sessions))
            samples.extend(random.sample(scenario_sessions, k))
        return samples

    elif strategy == "errors":
        # Only ambiguous scores (0.4-0.6 range)
        ambiguous = []
        for session in sessions:
            score = getattr(session, "authenticity_score", None)
            if score is not None and 0.4 <= score <= 0.6:
                ambiguous.append(session)
        # If we have too few ambiguous, fall back to random sample
        if len(ambiguous) == 0:
            k = max(1, int(len(sessions) * sample_rate))
            return random.sample(sessions, min(k, len(sessions)))
        return ambiguous

    elif strategy == "extremes":
        # High/low scores to verify calibration (< 0.3 or > 0.8)
        extremes = []
        for session in sessions:
            score = getattr(session, "authenticity_score", None)
            if score is not None and (score < 0.3 or score > 0.8):
                extremes.append(session)
        # If we have too few extremes, fall back to random sample
        if len(extremes) == 0:
            k = max(1, int(len(sessions) * sample_rate))
            return random.sample(sessions, min(k, len(sessions)))
        return extremes

    elif strategy == "on_failure":
        # Only failed scenarios (below threshold)
        failures = []
        for session in sessions:
            score = getattr(session, "authenticity_score", None)
            if score is not None and score < failure_threshold:
                failures.append(session)
        # Return all failures (no sampling)
        return failures

    else:
        raise ValueError(
            f"Unknown sampling strategy: {strategy}. "
            f"Valid options: random, stratified, errors, extremes, on_failure"
        )


def estimate_judge_cost(
    num_scenarios: int,
    sample_rate: float,
    cost_per_scenario: float = 0.003,
    strategy: str = "random",
    failure_rate: float = 0.1,
) -> dict[str, Any]:
    """Estimate cost for LLM judge evaluation.

    Args:
        num_scenarios: Total number of scenarios
        sample_rate: Fraction to sample (for random/stratified)
        cost_per_scenario: Estimated cost per judge API call (USD)
        strategy: Sampling strategy
        failure_rate: Expected failure rate (for on_failure strategy)

    Returns:
        Dict with estimated_scenarios, estimated_cost, strategy
    """
    if strategy in ("random", "stratified"):
        scenarios_judged = max(1, int(num_scenarios * sample_rate))
    elif strategy == "on_failure":
        scenarios_judged = max(1, int(num_scenarios * failure_rate))
    elif strategy in ("errors", "extremes"):
        # Assume ~10-20% of scenarios fall in these ranges
        scenarios_judged = max(1, int(num_scenarios * 0.15))
    else:
        scenarios_judged = num_scenarios

    total_cost = scenarios_judged * cost_per_scenario

    return {
        "strategy": strategy,
        "total_scenarios": num_scenarios,
        "scenarios_judged": scenarios_judged,
        "cost_per_scenario": cost_per_scenario,
        "estimated_cost": total_cost,
        "sample_rate": sample_rate if strategy in ("random", "stratified") else None,
    }
