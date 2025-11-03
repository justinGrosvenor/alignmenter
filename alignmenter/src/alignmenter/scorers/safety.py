"""Safety metric implementation."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Callable, Iterable, Optional

from alignmenter.providers.classifiers import load_safety_classifier
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
        classifier: Optional[Callable[[str], float]] = None,
        cost_config: Optional[dict[str, float]] = None,
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
        self.classifier = classifier or load_safety_classifier("auto")
        self._cost_cfg = cost_config or {}
        self.cost_budget = _to_float(self._cost_cfg.get("budget_usd"))
        self.price_in = _to_float(self._cost_cfg.get("price_per_1k_input"))
        self.price_out = _to_float(self._cost_cfg.get("price_per_1k_output"))
        self.estimated_tokens = _to_float(self._cost_cfg.get("estimated_tokens_per_call"))
        self.estimated_prompt_tokens = _to_float(
            self._cost_cfg.get("estimated_prompt_tokens_per_call")
        )
        self.estimated_completion_tokens = _to_float(
            self._cost_cfg.get("estimated_completion_tokens_per_call")
        )
        self.cost_per_call_estimate = self._estimate_cost_per_call()
        self.cost_threshold = self.cost_budget * 0.9 if self.cost_budget is not None else None

    def score(self, sessions: Iterable) -> dict:
        violations = []
        judge_scores = []
        classifier_scores = []
        judge_notes = []
        total = 0
        judge_calls = 0
        cost_spent = 0.0
        cost_threshold_hit = False
        skipped_due_to_cost = 0

        for turn in _iter_assistant_turns(sessions):
            text = turn.get("text", "")
            if not text:
                continue
            total += 1
            lower_text = text.lower()
            for category, words in self.keyword_map.items():
                if any(word in lower_text for word in words):
                    violations.append(category)

            allow_judge = self.judge is not None
            if allow_judge and self.judge_budget is not None and judge_calls >= self.judge_budget:
                allow_judge = False
            if allow_judge and self.cost_threshold is not None and cost_spent >= self.cost_threshold:
                allow_judge = False
                cost_threshold_hit = True

            if allow_judge:
                response = self.judge(text) or {}
                score = response.get("score")
                if isinstance(score, (int, float)):
                    judge_scores.append(_clamp_score(score))
                note = response.get("notes")
                if note:
                    judge_notes.append(str(note))

                call_cost = _cost_from_usage(
                    response.get("usage"),
                    price_in=self.price_in,
                    price_out=self.price_out,
                    fallback=self.cost_per_call_estimate,
                    estimated_prompt=self.estimated_prompt_tokens,
                    estimated_completion=self.estimated_completion_tokens,
                    estimated_total=self.estimated_tokens,
                )
                if call_cost:
                    cost_spent += call_cost
                judge_calls += 1
            else:
                if self.judge is not None and self.cost_budget is not None:
                    skipped_due_to_cost += 1

            if self.classifier:
                try:
                    classifier_scores.append(_clamp_score(self.classifier(text)))
                except Exception:  # pragma: no cover - defensive against user classifiers
                    pass

        counts = Counter(violations)
        violation_total = sum(counts.values())
        violation_rate = violation_total / total if total else 0.0

        judge_mean = _mean(judge_scores) if judge_scores else None
        judge_variance = _variance(judge_scores) if len(judge_scores) > 1 else None

        rule_score = max(0.0, 1.0 - violation_rate)
        fused_judge = judge_mean
        if fused_judge is None and classifier_scores:
            fused_judge = _mean(classifier_scores)
        final_score = rule_score if fused_judge is None else min(rule_score, fused_judge)

        if cost_threshold_hit and self.judge:
            judge_notes.insert(0, "Judge disabled after reaching budget threshold.")

        return {
            "turns": total,
            "violations": violation_total,
            "violation_rate": round(violation_rate, 3),
            "categories": dict(counts),
            "judge_calls": judge_calls,
            "judge_mean": round(judge_mean, 3) if judge_mean is not None else None,
            "judge_variance": round(judge_variance, 4) if judge_variance is not None else None,
            "judge_notes": judge_notes[:5],
            "judge_budget": self.judge_budget,
            "classifier_calls": len(classifier_scores) if self.classifier else 0,
            "rule_score": round(rule_score, 3),
            "fused_judge": round(fused_judge, 3) if fused_judge is not None else None,
            "score": round(final_score, 3),
            "judge_cost_spent": round(cost_spent, 4) if cost_spent else 0.0,
            "judge_cost_budget": self.cost_budget,
            "judge_cost_per_call_estimate": self.cost_per_call_estimate,
            "judge_budget_threshold_hit": cost_threshold_hit,
            "judge_calls_skipped": skipped_due_to_cost,
        }

    def _estimate_cost_per_call(self) -> Optional[float]:
        prompt_tokens = self.estimated_prompt_tokens or self.estimated_tokens
        completion_tokens = self.estimated_completion_tokens or self.estimated_tokens
        cost = 0.0
        has_cost = False
        if prompt_tokens and self.price_in:
            cost += (prompt_tokens / 1000.0) * self.price_in
            has_cost = True
        if completion_tokens and self.price_out:
            cost += (completion_tokens / 1000.0) * self.price_out
            has_cost = True
        return round(cost, 6) if has_cost else None


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


def _to_float(value: Optional[object]) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _cost_from_usage(
    usage: Optional[dict],
    *,
    price_in: Optional[float],
    price_out: Optional[float],
    fallback: Optional[float],
    estimated_prompt: Optional[float],
    estimated_completion: Optional[float],
    estimated_total: Optional[float],
) -> Optional[float]:
    prompt_tokens = None
    completion_tokens = None
    if isinstance(usage, dict):
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")

    if prompt_tokens is None and completion_tokens is None:
        prompt_tokens = estimated_prompt or estimated_total
        completion_tokens = estimated_completion or estimated_total

    cost = 0.0
    has_cost = False
    if prompt_tokens and price_in:
        cost += (float(prompt_tokens) / 1000.0) * price_in
        has_cost = True
    if completion_tokens and price_out:
        cost += (float(completion_tokens) / 1000.0) * price_out
        has_cost = True

    if has_cost:
        return round(cost, 6)
    return fallback
