"""Stability metric implementation."""

from __future__ import annotations

from statistics import mean
from typing import Iterable


class StabilityScorer:
    """Compute intra-session response stability."""

    id = "stability"

    def score(self, sessions: Iterable) -> dict:
        per_session_means = []

        for session in sessions:
            turns = getattr(session, "turns", None) or session.get("turns", [])
            lengths = [len(turn.get("text", "")) for turn in turns if turn.get("role") == "assistant" and turn.get("text")]
            if lengths:
                per_session_means.append(mean(lengths))

        if not per_session_means:
            return {"stability": 1.0, "sessions": 0, "variance": 0.0}

        overall_mean = mean(per_session_means)
        variance = mean((value - overall_mean) ** 2 for value in per_session_means)

        normalized = 1.0
        if overall_mean:
            normalized = max(0.0, min(1.0, 1 - variance / (overall_mean + 1e-6)))

        return {
            "stability": round(normalized, 3),
            "sessions": len(per_session_means),
            "variance": round(variance, 3),
        }
