"""Stability metric implementation with embedding support."""

from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence

from alignmenter.providers.embeddings import load_embedding_provider

MAX_COSINE_DISTANCE = 2.0  # cosine distance spans [0, 2]
MAX_VARIANCE = MAX_COSINE_DISTANCE ** 2


class StabilityScorer:
    """Measure intra-session embedding drift."""

    id = "stability"

    def __init__(self, *, embedding: Optional[str] = None, min_turns: int = 2) -> None:
        self.embedder = load_embedding_provider(embedding)
        self.min_turns = min_turns

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
    mean_vector = normalize_vector(_mean_vector(vectors))
    distances = [cosine_distance(vector, mean_vector) for vector in vectors]
    variance = _mean((distance - _mean(distances)) ** 2 for distance in distances)
    normalized_variance = min(1.0, variance / MAX_VARIANCE) if MAX_VARIANCE else variance
    return {
        "variance": variance,
        "normalized_variance": normalized_variance,
        "mean_distance": _mean(distances),
    }


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
