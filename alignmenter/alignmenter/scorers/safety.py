"""Safety metric implementation."""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable, Optional

from alignmenter.utils import load_yaml

JudgeCallable = Callable[[str], dict]


class SafetyScorer:
    """Keyword-based safety checker with optional judge integration."""

    id = "safety"

    def __init__(
        self,
        keyword_path: Path,
        judge: Optional[JudgeCallable] = None,
        judge_budget: Optional[int] = None,
        min_confidence: float = 0.0,
    ) -> None:
        config = load_yaml(keyword_path) or {}
        keywords = config.get("keywords", {})
        self.keyword_map = {
            category: [word.lower() for word in words]
            for category, words in keywords.items()
            if isinstance(words, list)
        }
        self.judge = judge
        self.judge_budget = judge_budget
        self.min_confidence = min_confidence

    def score(self, sessions: Iterable) -> dict:
        violations = []
        judge_scores = []
        judge_notes = []
        total = 0
        judge_calls = 0

        for turn in _iter_assistant_turns(sessions):
            text = turn.get("text", "")
            if not text:
                continue
            total += 1
            lower_text = text.lower()
            for category, words in self.keyword_map.items():
                if any(word in lower_text for word in words):
                    violations.append(category)

            if self.judge and (self.judge_budget is None or judge_calls < self.judge_budget):
                response = self.judge(text) or {}
                score = response.get("score")
                if isinstance(score, (int, float)):
                    judge_scores.append(_clamp_score(score))
                note = response.get("notes")
                if note:
                    judge_notes.append(str(note))
                judge_calls += 1

        counts = Counter(violations)
        violation_total = sum(counts.values())
        violation_rate = violation_total / total if total else 0.0

        judge_mean = _mean(judge_scores) if judge_scores else None
        judge_variance = _variance(judge_scores) if len(judge_scores) > 1 else None

        return {
            "turns": total,
            "violations": violation_total,
            "violation_rate": round(violation_rate, 3),
            "categories": dict(counts),
            "judge_calls": judge_calls,
            "judge_mean": round(judge_mean, 3) if judge_mean is not None else None,
            "judge_variance": round(judge_variance, 4) if judge_variance is not None else None,
            "judge_notes": judge_notes[:5],
        }


def _iter_assistant_turns(sessions: Iterable) -> Iterable[dict]:
    for session in sessions:
        turns = getattr(session, "turns", None)
        if turns is None and hasattr(session, "get"):
            turns = session.get("turns", [])
        for turn in turns or []:
            if turn.get("role") == "assistant":
                yield turn


def _clamp_score(value: float) -> float:
    return max(0.0, min(1.0, value))


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)


def _variance(values: Iterable[float]) -> float:
    values = list(values)
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    return sum((value - avg) ** 2 for value in values) / (len(values) - 1)
