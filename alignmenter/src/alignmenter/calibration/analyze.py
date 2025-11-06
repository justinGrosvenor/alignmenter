"""Analyze scenario performance using LLM judge."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

from alignmenter.scorers.authenticity import AuthenticityScorer
from alignmenter.providers.judges import load_judge_provider
from alignmenter.judges.authenticity_judge import AuthenticityJudge


def analyze_scenario_performance(
    dataset_path: Path,
    persona_path: Path,
    output_path: Path,
    *,
    embedding_provider: Optional[str] = None,
    judge_provider: str,
    samples_per_scenario: int = 3,
    judge_budget: Optional[int] = None,
) -> dict:
    """
    Analyze performance across different scenario types.

    Args:
        dataset_path: Path to conversation dataset JSONL
        persona_path: Path to persona YAML
        output_path: Path to output scenario analysis JSON
        embedding_provider: Embedding provider (default: sentence-transformer)
        judge_provider: LLM judge provider (required)
        samples_per_scenario: Number of sessions to judge per scenario
        judge_budget: Maximum number of judge API calls

    Returns:
        Scenario performance analysis report
    """
    # Load dataset
    sessions = []
    with open(dataset_path, "r") as f:
        for line in f:
            if line.strip():
                session = json.loads(line)
                sessions.append(session)

    if len(sessions) < 1:
        raise ValueError("Dataset is empty")

    print(f"Loaded {len(sessions)} sessions")

    # Group by scenario tag
    by_scenario = defaultdict(list)
    for session in sessions:
        # Get scenario tags (could be in various places)
        tags = set()
        for turn in session.get("turns", []):
            if "scenario" in turn:
                tags.add(turn["scenario"])

        # If no tags, check session level
        if not tags and "tags" in session:
            tags = set(session["tags"])

        # Default to "untagged"
        if not tags:
            tags = {"untagged"}

        for tag in tags:
            by_scenario[tag].append(session)

    print(f"Found {len(by_scenario)} scenario types")

    # Initialize scorer
    scorer = AuthenticityScorer(persona_path, embedding=embedding_provider)

    # Score all sessions
    print("Scoring sessions...")
    session_scores = {}
    for session in sessions:
        result = scorer.score([session])
        session_scores[session["session_id"]] = result.get("mean", 0.5)

    # Load judge
    judge = load_judge_provider(judge_provider)
    if not judge:
        raise ValueError(f"Could not load judge provider: {judge_provider}")

    auth_judge = AuthenticityJudge(
        persona_path=persona_path,
        judge_provider=judge,
        cost_per_call=0.003,
    )

    # Analyze each scenario type
    print(f"Judging {samples_per_scenario} sessions per scenario...")
    scenario_performance = {}
    total_judged = 0

    for scenario_tag, scenario_sessions in by_scenario.items():
        # Sample sessions to judge
        samples = scenario_sessions[:samples_per_scenario]

        # Check budget
        if judge_budget and total_judged >= judge_budget:
            print(f"  Skipping {scenario_tag} - budget exhausted")
            continue

        if judge_budget and total_judged + len(samples) > judge_budget:
            samples = samples[:judge_budget - total_judged]

        # Calculate average score
        scenario_scores = [session_scores[s["session_id"]] for s in samples]
        avg_score = sum(scenario_scores) / len(scenario_scores) if scenario_scores else 0.5

        # Judge samples
        judge_results = []
        for session in samples:
            try:
                analysis = auth_judge.evaluate_session(
                    session_id=session["session_id"],
                    turns=session.get("turns", []),
                    scenario_tag=scenario_tag,
                    calibrated_score=session_scores[session["session_id"]],
                )
                judge_results.append(analysis)
                total_judged += 1
            except Exception as e:
                print(f"  Warning: Judge failed for {session['session_id']}: {e}")
                continue

        # Aggregate judge feedback
        judge_scores = [r.score for r in judge_results]
        all_strengths = []
        all_weaknesses = []
        for r in judge_results:
            all_strengths.extend(r.strengths)
            all_weaknesses.extend(r.weaknesses)

        scenario_performance[scenario_tag] = {
            "avg_score": round(avg_score, 3),
            "sessions_in_scenario": len(scenario_sessions),
            "sessions_judged": len(judge_results),
            "judge_avg_score": round(sum(judge_scores) / len(judge_scores), 1) if judge_scores else None,
            "common_strengths": _top_items(all_strengths, 3),
            "common_weaknesses": _top_items(all_weaknesses, 3),
        }

        print(f"  {scenario_tag}: {len(judge_results)} sessions judged, avg score {avg_score:.2f}")

    # Get cost summary
    cost_summary = auth_judge.get_cost_summary()

    # Build report
    report = {
        "scenario_performance": scenario_performance,
        "total_scenarios": len(by_scenario),
        "total_sessions_judged": total_judged,
        "judge_cost": {
            "total_cost": round(cost_summary["total_cost"], 4),
            "calls_made": cost_summary["calls_made"],
        },
    }

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"✓ Scenario analysis complete")
    print(f"  Total cost: ${cost_summary['total_cost']:.3f}")

    return report


def _top_items(items: list[str], n: int = 3) -> list[str]:
    """Get top N most common items from a list."""
    if not items:
        return []
    from collections import Counter
    counts = Counter(items)
    return [item for item, count in counts.most_common(n)]
