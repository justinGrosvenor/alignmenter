"""Stability metric implementation with embedding support."""

from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence

from alignmenter.providers.embeddings import load_embedding_provider

# Default global normalization bounds (empirical values for typical embeddings)
# These can be overridden via __init__ parameters or calibration data
DEFAULT_VARIANCE_MIN = 0.01  # typical minimum variance for stable sessions
DEFAULT_VARIANCE_MAX = 0.50  # typical maximum variance for unstable sessions


class StabilityScorer:
    """Measure intra-session embedding drift."""

    id = "stability"

    def __init__(
        self,
        *,
        embedding: Optional[str] = None,
        min_turns: int = 2,
        variance_min: float = DEFAULT_VARIANCE_MIN,
        variance_max: float = DEFAULT_VARIANCE_MAX,
    ) -> None:
        self.embedder = load_embedding_provider(embedding)
        self.min_turns = min_turns
        self.variance_min = variance_min
        self.variance_max = variance_max

    def score(self, sessions: Iterable) -> dict:
        session_scores = []
        for session in sessions:
            turns = getattr(session, "turns", None)
            if turns is None and hasattr(session, "get"):
                turns = session.get("turns", [])
            responses = [turn.get("text", "") for turn in turns or [] if turn.get("role") == "assistant" and turn.get("text")]
            if len(responses) < self.min_turns:
                continue
            vectors = [normalize_vector(vector) for vector in self.embedder.embed(responses)]
            session_scores.append(_session_stability(vectors))

        if not session_scores:
            return {
                "stability": 1.0,
                "sessions": 0,
                "session_variance": 0.0,
                "mean_distance": 0.0,
                "normalized_variance": 0.0,
            }

        # Use global normalization bounds instead of within-batch normalization
        raw_variances = [score["variance"] for score in session_scores]
        rescaled_variances = _rescale_variance(
            raw_variances,
            min_variance=self.variance_min,
            max_variance=self.variance_max
        )

        # Update session scores with rescaled variances
        for i, score in enumerate(session_scores):
            score["normalized_variance"] = rescaled_variances[i]

        session_variance = _mean(score["variance"] for score in session_scores)
        normalized_variance = _mean(score["normalized_variance"] for score in session_scores)
        mean_distance = _mean(score["mean_distance"] for score in session_scores)
        stability = max(0.0, min(1.0, 1.0 - normalized_variance))

        return {
            "stability": round(stability, 3),
            "sessions": len(session_scores),
            "session_variance": round(session_variance, 4),
            "mean_distance": round(mean_distance, 4),
            "normalized_variance": round(normalized_variance, 4),
        }


def _session_stability(vectors: list[list[float]]) -> dict:
    """
    Compute stability metrics for a single session.

    Measures variance of cosine distances from the session mean embedding.
    Uses population variance (dividing by n) rather than sample variance (n-1).

    Note: For small sessions (2-3 turns), population variance tends to slightly
    underestimate the true variance compared to sample variance with Bessel's
    correction. However, since we apply empirical rescaling across sessions,
    this bias is consistent and does not affect relative comparisons.
    """
    mean_vector = normalize_vector(_mean_vector(vectors))
    distances = [cosine_distance(vector, mean_vector) for vector in vectors]
    variance = _mean((distance - _mean(distances)) ** 2 for distance in distances)
    # Normalized variance will be computed at batch level using empirical rescaling
    return {
        "variance": variance,
        "normalized_variance": variance,  # placeholder, will be rescaled in score()
        "mean_distance": _mean(distances),
    }


def _rescale_variance(variances: list[float], min_variance: float, max_variance: float) -> list[float]:
    """
    Rescale variance values using global normalization bounds.

    Uses default (or calibrated) min/max values to ensure scores are
    comparable across different evaluation runs.

    Raw variance typically ranges from 0.01-0.5 for realistic text.
    This rescales to approximately 0.1-0.9 to improve discriminative power:

    - Below global min → ~0.1 → stability ~0.9
    - At global min → ~0.1 → stability ~0.9
    - Average (midpoint) → ~0.5 → stability ~0.5
    - At global max → ~0.9 → stability ~0.1
    - Above global max → ~0.9 → stability ~0.1

    This allows the full stability scale to be utilized across runs.
    """
    if not variances:
        return []

    # Ensure valid range
    if max_variance <= min_variance:
        return [0.5 for _ in variances]

    rescaled = []
    for var in variances:
        # Normalize to [0, 1] using global bounds
        normalized = (var - min_variance) / (max_variance - min_variance)
        # Clamp to [0, 1] in case variance is outside calibration bounds
        normalized = max(0.0, min(1.0, normalized))
        # Rescale to [0.1, 0.9] range for better discriminative power
        rescaled_var = 0.1 + (normalized * 0.8)
        rescaled.append(rescaled_var)

    return rescaled


def normalize_vector(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return list(vector)
    return [value / norm for value in vector]


def _mean_vector(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    length = max(len(vector) for vector in vectors)
    totals = [0.0] * length
    for vector in vectors:
        for idx, value in enumerate(vector):
            totals[idx] += value
    count = len(vectors)
    return [value / count for value in totals]


def cosine_distance(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    length = min(len(vec_a), len(vec_b))
    if not length:
        return 1.0
    dot = sum(vec_a[i] * vec_b[i] for i in range(length))
    similarity = max(-1.0, min(1.0, dot))
    return 1 - similarity


def _mean(values: Iterable[float]) -> float:
    total = 0.0
    count = 0
    for value in values:
        total += value
        count += 1
    return total / count if count else 0.0
