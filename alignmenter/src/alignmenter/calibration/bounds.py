"""Estimate normalization bounds from labeled calibration data."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

import numpy as np

from alignmenter.providers.embeddings import load_embedding_provider
from alignmenter.utils import load_yaml


def estimate_bounds(
    labeled_path: Path,
    persona_path: Path,
    output_path: Path,
    *,
    embedding_provider: Optional[str] = None,
    percentile_low: float = 5.0,
    percentile_high: float = 95.0,
) -> dict:
    """
    Estimate normalization bounds from labeled calibration data.

    Uses empirical percentiles for robustness to outliers.

    Args:
        labeled_path: Path to labeled JSONL data
        persona_path: Path to persona YAML
        output_path: Path to output bounds report JSON
        embedding_provider: Embedding provider (default: sentence-transformer)
        percentile_low: Lower percentile for min bound (default: 5)
        percentile_high: Upper percentile for max bound (default: 95)

    Returns:
        Bounds report with statistics
    """
    # Load labeled data
    labeled_data = []
    with open(labeled_path, "r") as f:
        for line in f:
            if line.strip():
                labeled_data.append(json.loads(line))

    if not labeled_data:
        raise ValueError(f"No labeled data found in {labeled_path}")

    # Load persona and embedder
    persona = load_yaml(persona_path) or {}
    embedder = load_embedding_provider(embedding_provider)

    # Embed exemplars
    exemplar_texts = persona.get("exemplars", [])
    if not exemplar_texts:
        raise ValueError(f"No exemplars found in {persona_path}")

    exemplar_embeddings = [
        _normalize_vector(emb) for emb in embedder.embed(exemplar_texts)
    ]

    # Compute raw style similarity for all labeled examples
    print(f"Computing style similarity for {len(labeled_data)} examples...")
    raw_style_scores = []
    on_brand_scores = []
    off_brand_scores = []

    for i, example in enumerate(labeled_data):
        if (i + 1) % 10 == 0:
            print(f"  Progress: {i + 1}/{len(labeled_data)}")

        text = example.get("text", "")
        if not text:
            continue

        # Embed and compute max similarity to exemplars
        embedding = _normalize_vector(embedder.embed([text])[0])
        similarities = [
            _cosine_similarity(embedding, exemplar)
            for exemplar in exemplar_embeddings
        ]
        max_sim = max(similarities) if similarities else 0.0

        raw_style_scores.append(max_sim)

        # Track by label
        label = example.get("label")
        if label == 1:
            on_brand_scores.append(max_sim)
        elif label == 0:
            off_brand_scores.append(max_sim)

    if not raw_style_scores:
        raise ValueError("No valid examples to compute bounds from")

    # Compute bounds using percentiles
    style_sim_min = float(np.percentile(raw_style_scores, percentile_low))
    style_sim_max = float(np.percentile(raw_style_scores, percentile_high))

    # Compute statistics
    report = {
        "style_sim_min": round(style_sim_min, 4),
        "style_sim_max": round(style_sim_max, 4),
        "style_sim_mean": round(float(np.mean(raw_style_scores)), 4),
        "style_sim_std": round(float(np.std(raw_style_scores)), 4),
        "style_sim_median": round(float(np.median(raw_style_scores)), 4),
        "percentile_low": percentile_low,
        "percentile_high": percentile_high,
        "num_examples": len(raw_style_scores),
    }

    # Separate statistics by label
    if on_brand_scores:
        report["on_brand_style"] = {
            "mean": round(float(np.mean(on_brand_scores)), 4),
            "std": round(float(np.std(on_brand_scores)), 4),
            "median": round(float(np.median(on_brand_scores)), 4),
            "count": len(on_brand_scores),
        }

    if off_brand_scores:
        report["off_brand_style"] = {
            "mean": round(float(np.mean(off_brand_scores)), 4),
            "std": round(float(np.std(off_brand_scores)), 4),
            "median": round(float(np.median(off_brand_scores)), 4),
            "count": len(off_brand_scores),
        }

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n✓ Bounds estimation complete")
    print(f"  Style similarity min: {style_sim_min:.4f}")
    print(f"  Style similarity max: {style_sim_max:.4f}")
    print(f"  Mean: {report['style_sim_mean']:.4f}")
    print(f"  Output: {output_path}")

    return report


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
    """CLI entry point for estimate_bounds."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Estimate normalization bounds from labeled data"
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
        help="Path to output bounds report JSON",
    )
    parser.add_argument(
        "--embedding",
        type=str,
        help="Embedding provider (default: sentence-transformer)",
    )
    parser.add_argument(
        "--percentile-low",
        type=float,
        default=5.0,
        help="Lower percentile for min bound (default: 5)",
    )
    parser.add_argument(
        "--percentile-high",
        type=float,
        default=95.0,
        help="Upper percentile for max bound (default: 95)",
    )

    args = parser.parse_args()

    estimate_bounds(
        labeled_path=args.labeled,
        persona_path=args.persona,
        output_path=args.output,
        embedding_provider=args.embedding,
        percentile_low=args.percentile_low,
        percentile_high=args.percentile_high,
    )


if __name__ == "__main__":
    main()
