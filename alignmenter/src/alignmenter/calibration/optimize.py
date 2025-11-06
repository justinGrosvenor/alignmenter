"""Optimize component weights for authenticity scoring."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.metrics import roc_auc_score, f1_score, confusion_matrix

from alignmenter.providers.embeddings import load_embedding_provider
from alignmenter.utils import load_yaml


def optimize_weights(
    labeled_path: Path,
    persona_path: Path,
    output_path: Path,
    *,
    bounds_path: Optional[Path] = None,
    embedding_provider: Optional[str] = None,
    grid_step: float = 0.1,
) -> dict:
    """
    Optimize component weights using grid search.

    Evaluates all weight combinations (style, traits, lexicon) that sum to 1.0
    and selects the combination that maximizes ROC-AUC on labeled data.

    Args:
        labeled_path: Path to labeled JSONL data
        persona_path: Path to persona YAML
        output_path: Path to output weights report JSON
        bounds_path: Optional path to bounds report (for normalization)
        embedding_provider: Embedding provider (default: sentence-transformer)
        grid_step: Grid search step size (default: 0.1)

    Returns:
        Weights report with best weights and metrics
    """
    # Load labeled data
    labeled_data = []
    with open(labeled_path, "r") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                if item.get("label") is not None:  # Only include labeled
                    labeled_data.append(item)

    if len(labeled_data) < 10:
        raise ValueError(
            f"Need at least 10 labeled examples for optimization, got {len(labeled_data)}"
        )

    labels = [item["label"] for item in labeled_data]
    if len(set(labels)) < 2:
        raise ValueError("Need both on-brand (1) and off-brand (0) examples")

    # Load persona and embedder
    persona = load_yaml(persona_path) or {}
    embedder = load_embedding_provider(embedding_provider)

    # Load bounds if available
    bounds = None
    if bounds_path and bounds_path.exists():
        with open(bounds_path, "r") as f:
            bounds = json.load(f)

    # Pre-compute scores for all examples
    print(f"Computing component scores for {len(labeled_data)} examples...")
    examples_with_scores = []

    for i, example in enumerate(labeled_data):
        if (i + 1) % 10 == 0:
            print(f"  Progress: {i + 1}/{len(labeled_data)}")

        scores = _compute_component_scores(
            example["text"],
            persona,
            embedder,
            bounds=bounds,
        )
        examples_with_scores.append({
            "label": example["label"],
            "style": scores["style"],
            "traits": scores["traits"],
            "lexicon": scores["lexicon"],
        })

    # Grid search over weight combinations
    print(f"\nRunning grid search (step={grid_step})...")
    best_weights = None
    best_auc = 0.0
    best_metrics = None
    search_results = []

    # Generate all weight combinations that sum to 1.0
    weight_values = np.arange(0.0, 1.0 + grid_step, grid_step)
    count = 0

    for style_w in weight_values:
        for traits_w in weight_values:
            lexicon_w = 1.0 - style_w - traits_w

            # Check if lexicon_w is valid (within bounds and positive)
            if lexicon_w < -0.001 or lexicon_w > 1.001:
                continue

            # Clamp to [0, 1] to handle float precision
            lexicon_w = max(0.0, min(1.0, lexicon_w))

            count += 1
            if count % 50 == 0:
                print(f"  Evaluated {count} combinations...")

            # Compute combined scores with these weights
            combined_scores = [
                style_w * ex["style"] + traits_w * ex["traits"] + lexicon_w * ex["lexicon"]
                for ex in examples_with_scores
            ]

            # Compute metrics
            auc = roc_auc_score(labels, combined_scores)

            # Compute F1 at threshold 0.5
            predictions = [1 if score >= 0.5 else 0 for score in combined_scores]
            f1 = f1_score(labels, predictions)

            # Compute correlation
            correlation = np.corrcoef(labels, combined_scores)[0, 1]

            metrics = {
                "roc_auc": float(auc),
                "f1": float(f1),
                "correlation": float(correlation),
            }

            search_results.append({
                "weights": {
                    "style": round(float(style_w), 2),
                    "traits": round(float(traits_w), 2),
                    "lexicon": round(float(lexicon_w), 2),
                },
                "metrics": metrics,
            })

            # Track best
            if auc > best_auc:
                best_auc = auc
                best_weights = {
                    "style": float(style_w),
                    "traits": float(traits_w),
                    "lexicon": float(lexicon_w),
                }
                best_metrics = metrics

    print(f"  Evaluated {count} total combinations")

    # Compute confusion matrix for best weights
    best_combined_scores = [
        best_weights["style"] * ex["style"] +
        best_weights["traits"] * ex["traits"] +
        best_weights["lexicon"] * ex["lexicon"]
        for ex in examples_with_scores
    ]
    best_predictions = [1 if score >= 0.5 else 0 for score in best_combined_scores]
    cm = confusion_matrix(labels, best_predictions)

    # Build report
    report = {
        "best_weights": {
            "style": round(best_weights["style"], 3),
            "traits": round(best_weights["traits"], 3),
            "lexicon": round(best_weights["lexicon"], 3),
        },
        "metrics": {
            "roc_auc": round(best_metrics["roc_auc"], 3),
            "f1": round(best_metrics["f1"], 3),
            "correlation": round(best_metrics["correlation"], 3),
        },
        "confusion_matrix": {
            "true_negative": int(cm[0, 0]),
            "false_positive": int(cm[0, 1]),
            "false_negative": int(cm[1, 0]),
            "true_positive": int(cm[1, 1]),
        },
        "num_examples": len(labeled_data),
        "grid_step": grid_step,
        "combinations_evaluated": count,
    }

    # Add top 5 results for reference
    search_results.sort(key=lambda x: x["metrics"]["roc_auc"], reverse=True)
    report["top_5_alternatives"] = search_results[:5]

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n✓ Weight optimization complete")
    print(f"  Best weights: style={best_weights['style']:.2f}, "
          f"traits={best_weights['traits']:.2f}, lexicon={best_weights['lexicon']:.2f}")
    print(f"  ROC-AUC: {best_metrics['roc_auc']:.3f}")
    print(f"  F1: {best_metrics['f1']:.3f}")
    print(f"  Output: {output_path}")

    return report


def _compute_component_scores(
    text: str,
    persona: dict,
    embedder,
    bounds: Optional[dict] = None,
) -> dict:
    """
    Compute style, traits, and lexicon scores for a single text.

    This replicates the scoring logic from authenticity.py.
    """
    # Tokenize
    import re
    TOKEN_PATTERN = re.compile(r"[\w']+")
    tokens = [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]

    # Style similarity
    exemplar_texts = persona.get("exemplars", [])
    if exemplar_texts:
        text_embedding = _normalize_vector(embedder.embed([text])[0])
        exemplar_embeddings = [
            _normalize_vector(emb) for emb in embedder.embed(exemplar_texts)
        ]
        similarities = [
            _cosine_similarity(text_embedding, ex)
            for ex in exemplar_embeddings
        ]
        raw_style = max(similarities) if similarities else 0.0

        # Apply normalization bounds if available
        if bounds:
            style_min = bounds.get("style_sim_min", 0.05)
            style_max = bounds.get("style_sim_max", 0.25)
            normalized = (raw_style - style_min) / max(0.0001, style_max - style_min)
            normalized = max(0.0, min(1.0, normalized))
            style_score = 0.3 + (normalized * 0.6)  # Rescale to [0.3, 0.9]
        else:
            style_score = raw_style
    else:
        style_score = 0.5

    # Traits (simplified - just use heuristic)
    # In real scoring, this would use trained trait model
    lexicon = persona.get("lexicon", {})
    preferred = set(w.lower() for w in lexicon.get("preferred", []))
    avoided = set(w.lower() for w in lexicon.get("avoid", []))

    token_set = set(tokens)
    pref_count = sum(1 for t in token_set if t in preferred)
    avoid_count = sum(1 for t in token_set if t in avoided)

    # Simple heuristic: sigmoid of (preferred - avoided)
    logit = pref_count - avoid_count
    traits_score = 1.0 / (1.0 + math.exp(-logit))

    # Lexicon score (matches authenticity.py logic)
    if not tokens:
        lexicon_score = 0.5
    else:
        preferred_hits = sum(1 for t in tokens if t in preferred)
        avoided_hits = sum(1 for t in tokens if t in avoided)

        lexicon_density = (preferred_hits + avoided_hits) / max(1, len(tokens))

        if preferred_hits + avoided_hits == 0:
            balance = 0.0
        else:
            balance = (preferred_hits - avoided_hits) / (preferred_hits + avoided_hits)

        normalized_balance = 0.5 + balance / 2
        lexicon_score = normalized_balance * min(1.0, lexicon_density * 10)
        lexicon_score = max(0.0, min(1.0, lexicon_score))

    return {
        "style": style_score,
        "traits": traits_score,
        "lexicon": lexicon_score,
    }


def _normalize_vector(vector: list[float]) -> list[float]:
    """Normalize vector to unit length."""
    norm = math.sqrt(sum(v * v for v in vector))
    if not norm:
        return [0.0] * len(vector)
    return [v / norm for v in vector]


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    length = min(len(vec_a), len(vec_b))
    if not length:
        return 0.0
    dot = sum(vec_a[i] * vec_b[i] for i in range(length))
    return max(-1.0, min(1.0, dot))


def main():
    """CLI entry point for optimize_weights."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Optimize component weights using grid search"
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
        help="Path to persona YAML",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to output weights report JSON",
    )
    parser.add_argument(
        "--bounds",
        type=Path,
        help="Path to bounds report JSON (optional)",
    )
    parser.add_argument(
        "--embedding",
        type=str,
        help="Embedding provider (default: sentence-transformer)",
    )
    parser.add_argument(
        "--grid-step",
        type=float,
        default=0.1,
        help="Grid search step size (default: 0.1)",
    )

    args = parser.parse_args()

    optimize_weights(
        labeled_path=args.labeled,
        persona_path=args.persona,
        output_path=args.output,
        bounds_path=args.bounds,
        embedding_provider=args.embedding,
        grid_step=args.grid_step,
    )


if __name__ == "__main__":
    main()
