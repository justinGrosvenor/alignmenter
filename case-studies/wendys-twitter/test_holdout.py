#!/usr/bin/env python3
"""Test holdout data with calibrated persona."""
import json
import sys
import yaml
from pathlib import Path
from sklearn.metrics import roc_auc_score, accuracy_score, precision_score, recall_score, f1_score

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "alignmenter" / "src"))

from alignmenter.scorers.authenticity import AuthenticityScorer
from alignmenter.providers.embeddings import load_embedding_provider

def evaluate_holdout(holdout_path: str, persona_path: str = "wendys_twitter.yaml"):
    """Evaluate holdout data and return metrics."""
    # Load holdout data
    with open(holdout_path) as f:
        data = [json.loads(line) for line in f if line.strip()]

    # Filter for assistant turns with labels
    labeled_turns = [t for t in data if t.get("role") == "assistant" and "label" in t]

    if not labeled_turns:
        return {"error": "No labeled assistant turns found"}

    # Create scorer
    scorer = AuthenticityScorer(
        persona_path=Path(persona_path),
        embedding="sentence-transformer:all-MiniLM-L6-v2"
    )

    # Score all turns - need to call score() on full sessions
    # For evaluation, create mini-sessions with each turn
    y_true = []
    y_scores = []

    for i, turn in enumerate(labeled_turns):
        # Create a mini-session for this turn with proper format
        # scorer expects sessions with "turns" key
        mini_session = [{"turns": [turn]}]
        result = scorer.score(mini_session)

        # Get the score from the result
        # The result has 'mean' score which is the average authenticity
        score = result.get('mean', 0.0)

        # Debug: print first few scores
        if i < 5:
            print(f"  Turn {i}: label={turn['label']}, score={score:.4f}, text='{turn['text'][:50]}...'")

        y_true.append(turn["label"])
        y_scores.append(score)

    # Compute metrics
    y_pred = [1 if s >= 0.5 else 0 for s in y_scores]

    metrics = {
        "n_samples": len(labeled_turns),
        "n_positive": sum(y_true),
        "n_negative": len(y_true) - sum(y_true),
        "roc_auc": roc_auc_score(y_true, y_scores),
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
    }

    return metrics

if __name__ == "__main__":
    holdout_files = [
        "demo/wendys_holdout_trend_expanded.jsonl",
        "demo/wendys_holdout_crisis_expanded.jsonl",
        "demo/wendys_holdout_mixed.jsonl",
        "demo/wendys_holdout_edgecases.jsonl",
    ]

    print("=" * 80)
    print("HOLDOUT EVALUATION RESULTS")
    print("=" * 80)

    all_results = {}
    for holdout_file in holdout_files:
        print(f"\n{holdout_file}")
        print("-" * 80)
        metrics = evaluate_holdout(holdout_file)
        all_results[holdout_file] = metrics

        for key, value in metrics.items():
            if isinstance(value, float):
                print(f"  {key:15s}: {value:.4f}")
            else:
                print(f"  {key:15s}: {value}")

    # Overall metrics
    print("\n" + "=" * 80)
    print("OVERALL (COMBINED HOLDOUT)")
    print("=" * 80)

    all_metrics = []
    for file in holdout_files:
        m = all_results[file]
        if "error" not in m:
            all_metrics.append(m)

    if all_metrics:
        total_samples = sum(m["n_samples"] for m in all_metrics)
        total_positive = sum(m["n_positive"] for m in all_metrics)
        total_negative = sum(m["n_negative"] for m in all_metrics)

        # Weighted average by sample count
        weighted_roc_auc = sum(m["roc_auc"] * m["n_samples"] for m in all_metrics) / total_samples
        weighted_accuracy = sum(m["accuracy"] * m["n_samples"] for m in all_metrics) / total_samples
        weighted_f1 = sum(m["f1"] * m["n_samples"] for m in all_metrics) / total_samples

        print(f"  n_samples      : {total_samples}")
        print(f"  n_positive     : {total_positive}")
        print(f"  n_negative     : {total_negative}")
        print(f"  roc_auc        : {weighted_roc_auc:.4f}")
        print(f"  accuracy       : {weighted_accuracy:.4f}")
        print(f"  f1             : {weighted_f1:.4f}")

    # Save results
    with open("holdout_evaluation_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print("\n✓ Results saved to holdout_evaluation_results.json")
