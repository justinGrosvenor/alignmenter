"""Stability metric implementation."""

from __future__ import annotations

import math
from typing import Iterable

from alignmenter.utils import stable_hash


class StabilityScorer:
    """Compute intra-session embedding drift and variance stability."""

    id = "stability"

    def __init__(self, min_turns: int = 2) -> None:
        self.min_turns = min_turns

    def score(self, sessions: Iterable) -> dict:
        session_scores = []
        for session in sessions:
            turns = getattr(session, "turns", None)
            if turns is None and hasattr(session, "get"):
                turns = session.get("turns", [])
            vectors = [
                _text_to_vector(turn.get("text", ""))
                for turn in turns or []
                if turn.get("role") == "assistant" and turn.get("text")
            ]
            if len(vectors) < self.min_turns:
                continue
            session_scores.append(_session_stability(vectors))

        if not session_scores:
            return {
                "stability": 1.0,
                "sessions": 0,
                "session_variance": 0.0,
                "mean_distance": 0.0,
            }

        session_variance = _mean(score["variance"] for score in session_scores)
        mean_distance = _mean(score["mean_distance"] for score in session_scores)
        stability = _normalize(session_variance)

        return {
            "stability": round(stability, 3),
            "sessions": len(session_scores),
            "session_variance": round(session_variance, 4),
            "mean_distance": round(mean_distance, 4),
        }


def _text_to_vector(text: str) -> dict[int, float]:
    tokens = [token.lower() for token in text.split() if token]
    vector: dict[int, float] = {}
    for token in tokens:
        bucket = stable_hash(token)
        vector[bucket] = vector.get(bucket, 0.0) + 1.0
    norm = math.sqrt(sum(value * value for value in vector.values()))
    if norm:
        for key in list(vector.keys()):
            vector[key] /= norm
    return vector


def _session_stability(vectors: list[dict[int, float]]) -> dict:
    mean_vector = _mean_vector(vectors)
    distances = [
        cosine_distance(vector, mean_vector)
        for vector in vectors
    ]
    variance = _mean((distance - _mean(distances)) ** 2 for distance in distances)
    return {
        "variance": variance,
        "mean_distance": _mean(distances),
    }


def _mean_vector(vectors: list[dict[int, float]]) -> dict[int, float]:
    if not vectors:
        return {}
    accumulator: dict[int, float] = {}
    for vector in vectors:
        for index, value in vector.items():
            accumulator[index] = accumulator.get(index, 0.0) + value
    count = len(vectors)
    for index in list(accumulator.keys()):
        accumulator[index] /= count
    norm = math.sqrt(sum(value * value for value in accumulator.values()))
    if norm:
        for index in list(accumulator.keys()):
            accumulator[index] /= norm
    return accumulator


def cosine_distance(vec_a: dict[int, float], vec_b: dict[int, float]) -> float:
    if not vec_a or not vec_b:
        return 1.0
    dot = sum(value * vec_b.get(index, 0.0) for index, value in vec_a.items())
    similarity = max(-1.0, min(1.0, dot))
    return 1 - similarity


def _normalize(variance: float) -> float:
    return 1 / (1 + variance)


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)
