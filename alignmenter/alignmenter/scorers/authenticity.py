"""Authenticity metric implementation."""

from __future__ import annotations

import json
import math
import random
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional

from alignmenter.utils import load_yaml


@dataclass
class AuthenticityTurn:
    style_sim: float
    traits: float
    lexicon: float
    score: float


@dataclass
class AuthenticitySummary:
    mean: float
    style_sim: float
    traits: float
    lexicon: float
    turns: int
    tokens: int
    preferred_hits: int
    avoid_hits: int
    ci95_low: Optional[float] = None
    ci95_high: Optional[float] = None


class AuthenticityScorer:
    """Compute persona authenticity based on embeddings, traits, and lexicon."""

    id = "authenticity"

    def __init__(self, persona_path: Path, seed: int = 42) -> None:
        persona = load_yaml(persona_path) or {}
        lexicon = persona.get("lexicon", {}) if isinstance(persona, dict) else {}
        preferred = lexicon.get("preferred", []) if isinstance(lexicon, dict) else []
        avoided = lexicon.get("avoid", []) if isinstance(lexicon, dict) else []
        self.preferred_words = {word.lower() for word in preferred}
        self.avoid_words = {word.lower() for word in avoided}

        self.exemplar_vectors = [
            _text_to_vector(text)
            for text in persona.get("exemplars", []) or []
            if isinstance(text, str)
        ] or [_text_to_vector(" ".join(preferred))]

        self.trait_tokens_positive = {
            token
            for token in persona.get("style_rules", {}).get("preferred", [])
            if isinstance(token, str)
        }
        self.trait_tokens_negative = set(self.avoid_words)

        self.weights = {
            "style": 0.6,
            "traits": 0.25,
            "lexicon": 0.15,
        }
        self.random = random.Random(seed)

        calibration_path = persona_path.with_suffix(".traits.json")
        if calibration_path.exists():
            try:
                calibration = json.loads(calibration_path.read_text())
                style = calibration.get("style_weight")
                traits = calibration.get("traits_weight")
                lexicon_weight = calibration.get("lexicon_weight")
                weights = [w for w in (style, traits, lexicon_weight) if isinstance(w, (int, float))]
                if len(weights) == 3 and sum(weights):
                    total = sum(weights)
                    self.weights = {
                        "style": weights[0] / total,
                        "traits": weights[1] / total,
                        "lexicon": weights[2] / total,
                    }
            except json.JSONDecodeError:
                pass

    def score(self, sessions: Iterable) -> dict:
        turns = []
        preferred_hits = 0
        avoid_hits = 0
        token_total = 0

        for text in _iter_assistant_text(sessions):
            tokens = _tokenize(text)
            token_total += len(tokens)
            preferred_hits += sum(1 for token in tokens if token in self.preferred_words)
            avoid_hits += sum(1 for token in tokens if token in self.avoid_words)

            style_sim = self._style_similarity(text)
            traits_score = self._traits_score(text)
            lex_score = self._lexicon_score(tokens)
            combined = (
                self.weights["style"] * style_sim
                + self.weights["traits"] * traits_score
                + self.weights["lexicon"] * lex_score
            )
            turns.append(
                AuthenticityTurn(
                    style_sim=style_sim,
                    traits=traits_score,
                    lexicon=lex_score,
                    score=combined,
                )
            )

        if not turns:
            return {
                "mean": 0.0,
                "style_sim": 0.0,
                "traits": 0.0,
                "lexicon": 0.0,
                "turns": 0,
                "tokens": 0,
                "preferred_hits": 0,
                "avoid_hits": 0,
                "ci95_low": None,
                "ci95_high": None,
            }

        summary = AuthenticitySummary(
            mean=_mean([turn.score for turn in turns]),
            style_sim=_mean([turn.style_sim for turn in turns]),
            traits=_mean([turn.traits for turn in turns]),
            lexicon=_mean([turn.lexicon for turn in turns]),
            turns=len(turns),
            tokens=token_total,
            preferred_hits=preferred_hits,
            avoid_hits=avoid_hits,
        )

        ci_low, ci_high = self._bootstrap_ci([turn.score for turn in turns])
        summary.ci95_low = ci_low
        summary.ci95_high = ci_high

        result = asdict(summary)
        for key in ("mean", "style_sim", "traits", "lexicon", "ci95_low", "ci95_high"):
            if result[key] is not None:
                result[key] = round(result[key], 3)
        return result

    def _style_similarity(self, text: str) -> float:
        vector = _text_to_vector(text)
        sims = [cosine_similarity(vector, exemplar) for exemplar in self.exemplar_vectors]
        if not sims:
            return 0.0
        return max(0.0, min(1.0, sum(sims) / len(sims)))

    def _traits_score(self, text: str) -> float:
        tokens = set(_tokenize(text))
        positives = len(tokens & self.preferred_words) + len(tokens & self.trait_tokens_positive)
        negatives = len(tokens & self.avoid_words) + len(tokens & self.trait_tokens_negative)
        delta = positives - negatives
        return round(1 / (1 + math.exp(-delta)), 5)

    def _lexicon_score(self, tokens: list[str]) -> float:
        if not tokens:
            return 0.5
        preferred = sum(1 for token in tokens if token in self.preferred_words)
        avoided = sum(1 for token in tokens if token in self.avoid_words)
        total = max(1, preferred + avoided)
        balance = (preferred - avoided) / total
        return max(0.0, min(1.0, 0.5 + balance / 2))

    def _bootstrap_ci(self, scores: list[float], iterations: int = 200) -> tuple[Optional[float], Optional[float]]:
        if len(scores) < 2:
            return None, None
        samples = []
        for _ in range(iterations):
            resample = [self.random.choice(scores) for _ in scores]
            samples.append(_mean(resample))
        samples.sort()
        lower_index = int(0.025 * len(samples))
        upper_index = int(0.975 * len(samples)) - 1
        lower = samples[lower_index]
        upper = samples[max(upper_index, lower_index)]
        return lower, upper


def _iter_assistant_text(sessions: Iterable) -> Iterable[str]:
    for session in sessions:
        turns = getattr(session, "turns", None)
        if turns is None and hasattr(session, "get"):
            turns = session.get("turns", [])
        for turn in turns or []:
            if turn.get("role") == "assistant":
                text = turn.get("text", "")
                if text:
                    yield text


TOKEN_PATTERN = re.compile(r"[\w']+")


def _tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]


def _text_to_vector(text: str) -> dict[int, float]:
    tokens = _tokenize(text)
    vector: dict[int, float] = {}
    for token in tokens:
        bucket = hash(token) % 512
        vector[bucket] = vector.get(bucket, 0.0) + 1.0
    norm = math.sqrt(sum(value * value for value in vector.values()))
    if norm:
        for key in list(vector.keys()):
            vector[key] /= norm
    return vector


def cosine_similarity(vec_a: dict[int, float], vec_b: dict[int, float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(value * vec_b.get(index, 0.0) for index, value in vec_a.items())
    return max(0.0, min(1.0, dot))


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)
