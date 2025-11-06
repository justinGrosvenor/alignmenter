"""Validate calibration quality and generate diagnostics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.metrics import roc_auc_score, f1_score, precision_recall_curve, roc_curve

from alignmenter.scorers.authenticity import AuthenticityScorer


def validate_calibration(
    labeled_path: Path,
    persona_path: Path,
    output_path: Path,
    *,
    embedding_provider: Optional[str] = None,
    train_split: float = 0.8,
    seed: int = 42,
) -> dict:
    """
    Validate calibration using train/validation split.

    Args:
        labeled_path: Path to labeled JSONL data
        persona_path: Path to persona YAML (should have .traits.json calibration)
        output_path: Path to output diagnostics report JSON
        embedding_provider: Embedding provider (default: sentence-transformer)
        train_split: Fraction of data for training (default: 0.8)
        seed: Random seed for splitting

    Returns:
        Diagnostics report with metrics and analysis
    """
    np.random.seed(seed)

    # Load labeled data
    labeled_data = []
    with open(labeled_path, "r") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                if item.get("label") is not None:
                    labeled_data.append(item)

    if len(labeled_data) < 10:
        raise ValueError(
            f"Need at least 10 labeled examples for validation, got {len(labeled_data)}"
        )

    # Split into train/validation
    indices = np.random.permutation(len(labeled_data))
    train_size = int(len(labeled_data) * train_split)
    train_indices = set(indices[:train_size])
    val_indices = set(indices[train_size:])

    train_data = [labeled_data[i] for i in train_indices]
    val_data = [labeled_data[i] for i in val_indices]

    print(f"Train set: {len(train_data)} examples")
    print(f"Validation set: {len(val_data)} examples")

    # Initialize scorer with calibration
    scorer = AuthenticityScorer(persona_path, embedding=embedding_provider)

    # Score validation set
    print(f"\nScoring validation set...")
    val_sessions = _convert_to_sessions(val_data)
    val_scores_raw = scorer.score(val_sessions)

    # Extract per-turn scores
    val_scores = []
    val_labels = []
    for example in val_data:
        # Score individual turn
        session = _convert_to_sessions([example])
        result = scorer.score(session)
        val_scores.append(result.get("mean", 0.5))
        val_labels.append(example["label"])

    # Compute metrics
    val_auc = roc_auc_score(val_labels, val_scores)
    val_predictions = [1 if s >= 0.5 else 0 for s in val_scores]
    val_f1 = f1_score(val_labels, val_predictions)
    val_correlation = float(np.corrcoef(val_labels, val_scores)[0, 1])

    # Compute precision-recall curve
    precision, recall, pr_thresholds = precision_recall_curve(val_labels, val_scores)

    # Compute ROC curve
    fpr, tpr, roc_thresholds = roc_curve(val_labels, val_scores)

    # Find optimal threshold (maximize F1)
    f1_scores = []
    thresholds_to_try = np.linspace(0.0, 1.0, 101)
    for threshold in thresholds_to_try:
        preds = [1 if s >= threshold else 0 for s in val_scores]
        if len(set(preds)) == 1:  # All same prediction
            f1_scores.append(0.0)
        else:
            f1_scores.append(f1_score(val_labels, preds))

    optimal_threshold_idx = np.argmax(f1_scores)
    optimal_threshold = float(thresholds_to_try[optimal_threshold_idx])
    optimal_f1 = float(f1_scores[optimal_threshold_idx])

    # Analyze score distributions
    on_brand_scores = [s for s, l in zip(val_scores, val_labels) if l == 1]
    off_brand_scores = [s for s, l in zip(val_scores, val_labels) if l == 0]

    # Identify errors
    false_positives = []
    false_negatives = []
    for i, (score, label, example) in enumerate(zip(val_scores, val_labels, val_data)):
        prediction = 1 if score >= 0.5 else 0
        if prediction == 1 and label == 0:
            false_positives.append({
                "text": example["text"][:100],
                "score": round(score, 3),
            })
        elif prediction == 0 and label == 1:
            false_negatives.append({
                "text": example["text"][:100],
                "score": round(score, 3),
            })

    # Build report
    report = {
        "validation_metrics": {
            "roc_auc": round(val_auc, 3),
            "f1": round(val_f1, 3),
            "correlation": round(val_correlation, 3),
            "optimal_threshold": round(optimal_threshold, 3),
            "optimal_f1": round(optimal_f1, 3),
        },
        "score_distributions": {
            "on_brand": {
                "mean": round(float(np.mean(on_brand_scores)), 3) if on_brand_scores else None,
                "std": round(float(np.std(on_brand_scores)), 3) if on_brand_scores else None,
                "median": round(float(np.median(on_brand_scores)), 3) if on_brand_scores else None,
                "count": len(on_brand_scores),
            },
            "off_brand": {
                "mean": round(float(np.mean(off_brand_scores)), 3) if off_brand_scores else None,
                "std": round(float(np.std(off_brand_scores)), 3) if off_brand_scores else None,
                "median": round(float(np.median(off_brand_scores)), 3) if off_brand_scores else None,
                "count": len(off_brand_scores),
            },
        },
        "error_analysis": {
            "false_positives": false_positives[:5],  # Top 5
            "false_negatives": false_negatives[:5],  # Top 5
            "num_false_positives": len(false_positives),
            "num_false_negatives": len(false_negatives),
        },
        "data_split": {
            "train_size": len(train_data),
            "validation_size": len(val_data),
            "train_split": train_split,
        },
    }

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n✓ Validation complete")
    print(f"  ROC-AUC: {val_auc:.3f}")
    print(f"  F1 Score: {val_f1:.3f}")
    print(f"  Optimal Threshold: {optimal_threshold:.3f} (F1={optimal_f1:.3f})")
    print(f"  Score separation:")
    if on_brand_scores:
        print(f"    On-brand mean: {np.mean(on_brand_scores):.3f}")
    if off_brand_scores:
        print(f"    Off-brand mean: {np.mean(off_brand_scores):.3f}")
    print(f"  Output: {output_path}")

    return report


def _convert_to_sessions(examples: list[dict]) -> list[dict]:
    """Convert list of examples to session format for scoring."""
    sessions = []
    for i, example in enumerate(examples):
        sessions.append({
            "session_id": f"val_{i}",
            "turns": [
                {
                    "role": "user",
                    "text": "validation prompt",
                },
                {
                    "role": "assistant",
                    "text": example["text"],
                },
            ],
        })
    return sessions


def main():
    """CLI entry point for validate_calibration."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate calibration and generate diagnostics"
    )
    parser.add_argument(
        "--labeled",
        type=Path,
        required=True,
        help="Path to labeled JSONL data",
    )
    parser.add_argument(
        "--persona",
        type=Path,
        required=True,
        help="Path to persona YAML (with .traits.json calibration)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to output diagnostics report JSON",
    )
    parser.add_argument(
        "--embedding",
        type=str,
        help="Embedding provider (default: sentence-transformer)",
    )
    parser.add_argument(
        "--train-split",
        type=float,
        default=0.8,
        help="Fraction of data for training (default: 0.8)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for splitting (default: 42)",
    )

    args = parser.parse_args()

    validate_calibration(
        labeled_path=args.labeled,
        persona_path=args.persona,
        output_path=args.output,
        embedding_provider=args.embedding,
        train_split=args.train_split,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
