"""Diagnose calibration errors using LLM judge analysis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


from alignmenter.scorers.authenticity import AuthenticityScorer
from alignmenter.providers.judges import load_judge_provider
from alignmenter.judges.authenticity_judge import AuthenticityJudge


def diagnose_calibration_errors(
    labeled_path: Path,
    persona_path: Path,
    output_path: Path,
    *,
    embedding_provider: Optional[str] = None,
    judge_provider: str,
    judge_budget: Optional[int] = None,
) -> dict:
    """
    Diagnose calibration errors by analyzing false positives and false negatives.

    Args:
        labeled_path: Path to labeled JSONL data
        persona_path: Path to persona YAML (with .traits.json calibration)
        output_path: Path to output error analysis JSON
        embedding_provider: Embedding provider (default: sentence-transformer)
        judge_provider: LLM judge provider (required)
        judge_budget: Maximum number of judge API calls

    Returns:
        Error analysis report with judge reasoning
    """
    # Load labeled data
    labeled_data = []
    with open(labeled_path, "r") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                if item.get("label") is not None:
                    labeled_data.append(item)

    if len(labeled_data) < 5:
        raise ValueError(f"Need at least 5 labeled examples, got {len(labeled_data)}")

    print(f"Loaded {len(labeled_data)} labeled examples")

    # Initialize scorer
    scorer = AuthenticityScorer(persona_path, embedding=embedding_provider)

    # Score all examples
    print("Scoring examples...")
    scores = []
    for example in labeled_data:
        session = [{
            "session_id": "temp",
            "turns": [
                {"role": "user", "text": "validation"},
                {"role": "assistant", "text": example["text"]},
            ],
        }]
        result = scorer.score(session)
        scores.append(result.get("mean", 0.5))

    # Identify errors
    false_positives = []
    false_negatives = []
    for i, (score, example) in enumerate(zip(scores, labeled_data)):
        label = example["label"]
        prediction = 1 if score >= 0.5 else 0

        if prediction == 1 and label == 0:
            false_positives.append({
                "index": i,
                "text": example["text"],
                "calibrated_score": score,
                "true_label": label,
            })
        elif prediction == 0 and label == 1:
            false_negatives.append({
                "index": i,
                "text": example["text"],
                "calibrated_score": score,
                "true_label": label,
            })

    print(
        f"Found {len(false_positives)} false positives, "
        f"{len(false_negatives)} false negatives"
    )

    if len(false_positives) + len(false_negatives) == 0:
        print("✓ No errors found - calibration is perfect!")
        report = {
            "false_positives": [],
            "false_negatives": [],
            "total_errors": 0,
            "message": "Perfect calibration - no errors to analyze",
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        return report

    # Load judge
    judge = load_judge_provider(judge_provider)
    if not judge:
        raise ValueError(f"Could not load judge provider: {judge_provider}")

    auth_judge = AuthenticityJudge(
        persona_path=persona_path,
        judge_provider=judge,
        cost_per_call=0.003,
    )

    # Analyze errors with judge
    errors_to_analyze = false_positives + false_negatives
    if judge_budget and len(errors_to_analyze) > judge_budget:
        errors_to_analyze = errors_to_analyze[:judge_budget]

    print(f"Analyzing {len(errors_to_analyze)} errors with LLM judge...")

    analyzed_fps = []
    analyzed_fns = []

    for error in errors_to_analyze:
        try:
            analysis = auth_judge.evaluate_session(
                session_id=f"error_{error['index']}",
                turns=[
                    {"role": "user", "text": "validation"},
                    {"role": "assistant", "text": error["text"]},
                ],
                calibrated_score=error["calibrated_score"],
            )

            error_with_analysis = {
                "text": error["text"][:200],  # Truncate for report
                "calibrated_score": round(error["calibrated_score"], 3),
                "true_label": error["true_label"],
                "judge_score": round(analysis.score, 1),
                "judge_reasoning": analysis.reasoning,
                "judge_weaknesses": analysis.weaknesses,
                "judge_suggestion": analysis.suggestion,
            }

            if error["true_label"] == 0:
                analyzed_fps.append(error_with_analysis)
            else:
                analyzed_fns.append(error_with_analysis)

        except Exception as e:
            print(f"  Warning: Judge failed for error {error['index']}: {e}")
            continue

    # Get cost summary
    cost_summary = auth_judge.get_cost_summary()

    # Build report
    report = {
        "false_positives": analyzed_fps,
        "false_negatives": analyzed_fns,
        "total_errors": len(false_positives) + len(false_negatives),
        "errors_analyzed": len(analyzed_fps) + len(analyzed_fns),
        "judge_cost": {
            "total_cost": round(cost_summary.total_cost, 4),
            "calls_made": cost_summary.calls_made,
        },
    }

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print("✓ Analysis complete")
    print(f"  Total cost: ${cost_summary.total_cost:.3f}")

    return report
