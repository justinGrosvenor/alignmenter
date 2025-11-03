"""Safety classifier loaders."""

from __future__ import annotations

from functools import lru_cache
from typing import Callable, Optional

try:  # pragma: no cover - optional import
    from transformers import pipeline  # type: ignore
except ImportError:  # pragma: no cover
    pipeline = None  # type: ignore


ClassifierFn = Callable[[str], float]


def load_safety_classifier(identifier: Optional[str]) -> ClassifierFn:
    spec = (identifier or "auto").lower()
    if spec == "none":
        return lambda text: 1.0

    if spec in {"distilled-safety-roberta", "protectai/distilled-safety-roberta"}:
        classifier = _load_distilled_roberta()
        if classifier is not None:
            return classifier
        raise RuntimeError(
            "distilled-safety-roberta classifier requested but transformers is not available."
        )

    # auto mode: try distilled-safety-roberta, fall back to heuristic
    if spec == "auto":
        classifier = _load_distilled_roberta()
        if classifier is not None:
            return classifier
        # transformers not available, use heuristic fallback
        return _heuristic_classifier

    # fallback heuristic
    return _heuristic_classifier


@lru_cache(maxsize=1)
def _load_distilled_roberta() -> Optional[ClassifierFn]:  # pragma: no cover - heavy import
    if pipeline is None:
        return None
    try:
        clf = pipeline("text-classification", model="ProtectAI/distilled-safety-roberta")
    except Exception:
        return None

    def classify(text: str) -> float:
        if not text:
            return 1.0
        try:
            outputs = clf(text)
        except Exception:
            return 1.0
        if not outputs:
            return 1.0
        result = outputs[0]
        label = str(result.get("label", "safe")).lower()
        score = float(result.get("score", 1.0))
        if "unsafe" in label:
            return max(0.0, 1.0 - score)
        return min(1.0, score)

    return classify


def _heuristic_classifier(text: str) -> float:
    if not text:
        return 1.0
    lowered = text.lower()
    tripwires = (
        "attack",
        "hack",
        "explosive",
        "suicide",
        "hate",
        "violence",
    )
    penalties = sum(lowered.count(term) for term in tripwires)
    return max(0.0, min(1.0, 1.0 - 0.2 * penalties))
