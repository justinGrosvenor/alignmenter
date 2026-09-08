"""Metric scorer registry scaffold."""

from .authenticity import AuthenticityScorer
from .faithfulness import FaithfulnessScorer
from .grounding import GroundingScorer
from .safety import SafetyScorer
from .stability import StabilityScorer

__all__ = [
    "AuthenticityScorer",
    "FaithfulnessScorer",
    "GroundingScorer",
    "SafetyScorer",
    "StabilityScorer",
    "load_custom_scorer",
]


def load_custom_scorer(spec: str, **kwargs: object) -> object:
    """Instantiate a scorer from a ``module.path:ClassName`` specifier.

    The three built-in dimensions cannot cover every product. A retrieval-augmented
    assistant needs to know whether answers are grounded in the passages it retrieved;
    a support bot may care about resolution rate. Those scorers live with the product,
    not here — this is the seam that lets a run load them.

    The class must expose ``id`` and ``score(sessions) -> dict``, like the built-ins.
    """

    from importlib import import_module

    if ":" not in spec:
        raise ValueError(
            f"Custom scorer must be given as 'module.path:ClassName', got {spec!r}."
        )
    module_path, _, class_name = spec.partition(":")
    try:
        module = import_module(module_path)
    except ImportError as exc:  # pragma: no cover - surfaced to the user verbatim
        raise ValueError(f"Could not import custom scorer module {module_path!r}: {exc}") from exc
    try:
        factory = getattr(module, class_name)
    except AttributeError as exc:
        raise ValueError(f"{module_path!r} has no attribute {class_name!r}.") from exc
    scorer = factory(**kwargs)
    if not hasattr(scorer, "id") or not hasattr(scorer, "score"):
        raise ValueError(f"Custom scorer {spec!r} must expose 'id' and 'score(sessions)'.")
    return scorer
