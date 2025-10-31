"""Authenticity metric implementation with small composable helpers."""

from __future__ import annotations

import json
import math
import random
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional

from alignmenter.utils import load_yaml, stable_hash


TOKEN_PATTERN = re.compile(r"[\w']+")


@dataclass
class PersonaProfile:
    preferred: set[str]
    avoided: set[str]
    exemplars: list[dict[int, float]]
    trait_positive: set[str]
    trait_negative: set[str]
    weights: dict[str, float]


def _coerce_weights(calibration_path: Path, default: dict[str, float]) -> dict[str, float]:
    if not calibration_path.exists():
        return default
    try:
        calibration = json.loads(calibration_path.read_text())
    except json.JSONDecodeError:
        return default
    values = [calibration.get("style_weight"), calibration.get("traits_weight"), calibration.get("lexicon_weight")]
    if not all(isinstance(weight, (int, float)) for weight in values):
        return default
    total = sum(values)
    if not total:
        return default
    keys = ("style", "traits", "lexicon")
    return {key: value / total for key, value in zip(keys, values)}


def load_persona_profile(persona_path: Path) -> PersonaProfile:
    persona = load_yaml(persona_path) or {}
    lexicon = persona.get("lexicon", {}) if isinstance(persona, dict) else {}
    preferred = {word.lower() for word in lexicon.get("preferred", []) or []}
    avoided = {word.lower() for word in lexicon.get("avoid", []) or []}

    exemplar_texts = persona.get("exemplars", []) or []
    exemplar_vectors = [text_to_vector(text) for text in exemplar_texts if isinstance(text, str)]
    if not exemplar_vectors and preferred:
        exemplar_vectors = [text_to_vector(" ".join(sorted(preferred)))]

    trait_positive = {
        token.lower()
        for token in persona.get("style_rules", {}).get("preferred", []) or []
        if isinstance(token, str)
    }
    trait_negative = avoided.copy()

    weights = _coerce_weights(persona_path.with_suffix(".traits.json"), {"style": 0.6, "traits": 0.25, "lexicon": 0.15})

    return PersonaProfile(
        preferred=preferred,
        avoided=avoided,
        exemplars=exemplar_vectors,
        trait_positive=trait_positive,
        trait_negative=trait_negative,
        weights=weights,
    )


class AuthenticityScorer:
    """Compute persona authenticity based on embeddings, traits, and lexicon."""

    id = "authenticity"

    def __init__(self, persona_path: Path, seed: int = 42) -> None:
        self.profile = load_persona_profile(persona_path)
        self.random = random.Random(seed)

    def score(self, sessions: Iterable) -> dict:
        turns = []
        preferred_hits = 0
        avoid_hits = 0
        token_total = 0

        for text in iter_assistant_text(sessions):
            tokens = tokenize(text)
            token_total += len(tokens)
            preferred_hits += sum(token in self.profile.preferred for token in tokens)
            avoid_hits += sum(token in self.profile.avoided for token in tokens)
            turns.append(score_turn(text, tokens, self.profile))

        if not turns:
            return empty_summary()

        summary = summarise_turns(turns, token_total, preferred_hits, avoid_hits)
        ci_low, ci_high = bootstrap_ci(self.random, [turn.score for turn in turns])
        summary.ci95_low = ci_low
        summary.ci95_high = ci_high
        payload = asdict(summary)
        for key in ("mean", "style_sim", "traits", "lexicon", "ci95_low", "ci95_high"):
            if payload[key] is not None:
                payload[key] = round(payload[key], 3)
        return payload


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


def empty_summary() -> dict:
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


def score_turn(text: str, tokens: list[str], profile: PersonaProfile) -> AuthenticityTurn:
    style_sim = style_similarity(text, profile.exemplars)
    traits_score = traits_score_from_tokens(tokens, profile)
    lex_score = lexicon_score(tokens, profile)
    combined = (
        profile.weights["style"] * style_sim
        + profile.weights["traits"] * traits_score
        + profile.weights["lexicon"] * lex_score
    )
    return AuthenticityTurn(style_sim=style_sim, traits=traits_score, lexicon=lex_score, score=combined)


def summarise_turns(turns: list[AuthenticityTurn], tokens: int, preferred_hits: int, avoid_hits: int) -> AuthenticitySummary:
    return AuthenticitySummary(
        mean=mean(turn.score for turn in turns),
        style_sim=mean(turn.style_sim for turn in turns),
        traits=mean(turn.traits for turn in turns),
        lexicon=mean(turn.lexicon for turn in turns),
        turns=len(turns),
        tokens=tokens,
        preferred_hits=preferred_hits,
        avoid_hits=avoid_hits,
    )


def style_similarity(text: str, exemplars: list[dict[int, float]]) -> float:
    vector = text_to_vector(text)
    sims = [cosine_similarity(vector, exemplar) for exemplar in exemplars]
    if not sims:
        return 0.0
    return max(0.0, min(1.0, sum(sims) / len(sims)))


def traits_score_from_tokens(tokens: Iterable[str], profile: PersonaProfile) -> float:
    token_set = set(tokens)
    positives = len(token_set & profile.preferred) + len(token_set & profile.trait_positive)
    negatives = len(token_set & profile.avoided) + len(token_set & profile.trait_negative)
    delta = positives - negatives
    return sigmoid(delta)


def lexicon_score(tokens: list[str], profile: PersonaProfile) -> float:
    if not tokens:
        return 0.5
    preferred = sum(token in profile.preferred for token in tokens)
    avoided = sum(token in profile.avoided for token in tokens)
    total = max(1, preferred + avoided)
    balance = (preferred - avoided) / total
    return max(0.0, min(1.0, 0.5 + balance / 2))


def bootstrap_ci(random_gen: random.Random, scores: list[float], iterations: int = 200) -> tuple[Optional[float], Optional[float]]:
    if len(scores) < 2:
        return None, None
    samples = [mean(random_gen.choice(scores) for _ in scores) for _ in range(iterations)]
    samples.sort()
    lower = samples[int(0.025 * len(samples))]
    upper = samples[int(0.975 * len(samples)) - 1]
    return lower, upper


def iter_assistant_text(sessions: Iterable) -> Iterable[str]:
    for session in sessions:
        turns = getattr(session, "turns", None)
        if turns is None and hasattr(session, "get"):
            turns = session.get("turns", [])
        for turn in turns or []:
            if turn.get("role") == "assistant" and turn.get("text"):
                yield turn["text"]


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]


def text_to_vector(text: str) -> dict[int, float]:
    tokens = tokenize(text)
    vector: dict[int, float] = {}
    for token in tokens:
        bucket = stable_hash(token)
        vector[bucket] = vector.get(bucket, 0.0) + 1.0
    return normalize_vector(vector)


def normalize_vector(vector: dict[int, float]) -> dict[int, float]:
    norm = math.sqrt(sum(value * value for value in vector.values()))
    if not norm:
        return vector
    for index in list(vector.keys()):
        vector[index] /= norm
    return vector


def cosine_similarity(vec_a: dict[int, float], vec_b: dict[int, float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(value * vec_b.get(index, 0.0) for index, value in vec_a.items())
    return max(-1.0, min(1.0, dot))


def sigmoid(value: float) -> float:
    return 1 / (1 + math.exp(-value))


def mean(values: Iterable[float]) -> float:
    total = 0.0
    count = 0
    for value in values:
        total += value
        count += 1
    return total / count if count else 0.0


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
