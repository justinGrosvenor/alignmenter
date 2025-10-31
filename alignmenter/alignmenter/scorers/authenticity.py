"""Authenticity metric implementation."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional

from alignmenter.utils import load_yaml


@dataclass
class AuthenticityResult:
    mean: float
    preferred_hits: int
    avoid_hits: int
    turns: int
    tokens: int
    ci95_low: Optional[float] = None
    ci95_high: Optional[float] = None


class AuthenticityScorer:
    """Compute a persona-based authenticity score."""

    id = "authenticity"

    def __init__(self, persona_path: Path) -> None:
        persona = load_yaml(persona_path)
        lexicon = persona.get("lexicon", {}) if persona else {}
        preferred = lexicon.get("preferred", []) if isinstance(lexicon, dict) else []
        avoided = lexicon.get("avoid", []) if isinstance(lexicon, dict) else []
        self.preferred_words = {word.lower() for word in preferred}
        self.avoid_words = {word.lower() for word in avoided}

    def score(self, sessions: Iterable) -> dict:
        preferred_hits = 0
        avoid_hits = 0
        turns = 0
        tokens = 0

        for turn_text in _iter_assistant_text(sessions):
            turns += 1
            words = _tokenize(turn_text)
            tokens += len(words)
            preferred_hits += sum(1 for token in words if token in self.preferred_words)
            avoid_hits += sum(1 for token in words if token in self.avoid_words)

        mean = 0.5
        if tokens:
            balance = preferred_hits - avoid_hits
            mean = 0.5 + balance / (2 * max(tokens, 1))
            mean = max(0.0, min(1.0, mean))

        result = AuthenticityResult(
            mean=round(mean, 3),
            preferred_hits=preferred_hits,
            avoid_hits=avoid_hits,
            turns=turns,
            tokens=tokens,
        )
        return asdict(result)


def _iter_assistant_text(sessions: Iterable) -> Iterable[str]:
    for session in sessions:
        turns = getattr(session, "turns", None) or session.get("turns", [])
        for turn in turns:
            if turn.get("role") == "assistant":
                text = turn.get("text", "")
                if text:
                    yield text


def _tokenize(text: str) -> list[str]:
    return [token.strip(".,!?;:\"'\n\t").lower() for token in text.split() if token]
