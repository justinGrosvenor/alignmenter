"""Authenticity metric implementation."""

from __future__ import annotations

import json
import math
import random
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional, Sequence

from alignmenter.providers.embeddings import EmbeddingProvider, load_embedding_provider
from alignmenter.utils import load_yaml

TOKEN_PATTERN = re.compile(r"[\w']+")


@dataclass
class PersonaProfile:
    preferred: set[str]
    avoided: set[str]
    exemplars: list[list[float]]
    trait_positive: set[str]
    trait_negative: set[str]
    weights: dict[str, float]


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
    """Compute persona authenticity using embeddings, traits, and lexicon."""

    id = "authenticity"

    def __init__(self, persona_path: Path, *, embedding: Optional[str] = None, seed: int = 42) -> None:
        self.embedder = load_embedding_provider(embedding)
        self.profile = load_persona_profile(persona_path, self.embedder)
        self.random = random.Random(seed)

    def score(self, sessions: Iterable) -> dict:
        turns: list[AuthenticityTurn] = []
        preferred_hits = 0
        avoid_hits = 0
        token_total = 0

        for text in iter_assistant_text(sessions):
            tokens = tokenize(text)
            token_total += len(tokens)
            preferred_hits += sum(token in self.profile.preferred for token in tokens)
            avoid_hits += sum(token in self.profile.avoided for token in tokens)
            turns.append(score_turn(text, tokens, self.profile, self.embedder))

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


def load_persona_profile(persona_path: Path, embedder: EmbeddingProvider) -> PersonaProfile:
    persona = load_yaml(persona_path) or {}
    lexicon = persona.get("lexicon", {}) if isinstance(persona, dict) else {}
    preferred = {word.lower() for word in lexicon.get("preferred", []) or []}
    avoided = {word.lower() for word in lexicon.get("avoid", []) or []}

    exemplar_texts = [text for text in persona.get("exemplars", []) or [] if isinstance(text, str)]
    if not exemplar_texts and preferred:
        exemplar_texts = [" ".join(sorted(preferred))]
    if not exemplar_texts:
        exemplar_texts = ["persona"]
    exemplar_vectors = [normalize_vector(vector) for vector in embedder.embed(exemplar_texts)]

    trait_positive = {
        token.lower()
        for token in persona.get("style_rules", {}).get("preferred", []) or []
        if isinstance(token, str)
    }
    trait_negative = avoided.copy()

    weights = coerce_weights(
        persona_path.with_suffix(".traits.json"),
        {"style": 0.6, "traits": 0.25, "lexicon": 0.15},
    )

    return PersonaProfile(
        preferred=preferred,
        avoided=avoided,
        exemplars=exemplar_vectors,
        trait_positive=trait_positive,
        trait_negative=trait_negative,
        weights=weights,
    )


# scoring helpers

def score_turn(text: str, tokens: list[str], profile: PersonaProfile, embedder: EmbeddingProvider) -> AuthenticityTurn:
    vector = normalize_vector(embedder.embed([text])[0])
    style_sim = style_similarity(vector, profile.exemplars)
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


# component calculations

def style_similarity(vector: Sequence[float], exemplars: list[list[float]]) -> float:
    sims = [cosine_similarity(vector, exemplar) for exemplar in exemplars]
    if not sims:
        return 0.0
    return max(0.0, min(1.0, sum(sims) / len(sims)))


def traits_score_from_tokens(tokens: Iterable[str], profile: PersonaProfile) -> float:
    token_set = set(tokens)
    positives = len(token_set & profile.preferred) + len(token_set & profile.trait_positive)
    negatives = len(token_set & profile.avoided) + len(token_set & profile.trait_negative)
    return sigmoid(positives - negatives)


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
    samples = []
    for _ in range(iterations):
        resample = [random_gen.choice(scores) for _ in scores]
        samples.append(mean(resample))
    samples.sort()
    lower = samples[int(0.025 * len(samples))]
    upper = samples[int(0.975 * len(samples)) - 1]
    return lower, upper


# shared utilities

def coerce_weights(calibration_path: Path, default: dict[str, float]) -> dict[str, float]:
    if not calibration_path.exists():
        return default
    try:
        calibration = json.loads(calibration_path.read_text())
    except json.JSONDecodeError:
        return default
    values = [calibration.get("style_weight"), calibration.get("traits_weight"), calibration.get("lexicon_weight")]
    if not all(isinstance(weight, (int, float)) for weight in values):
        return default
    total = sum(values) or 1.0
    keys = ("style", "traits", "lexicon")
    return {key: value / total for key, value in zip(keys, values)}


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


def normalize_vector(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return list(vector)
    return [value / norm for value in vector]


def cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    length = min(len(vec_a), len(vec_b))
    if not length:
        return 0.0
    dot = sum(vec_a[i] * vec_b[i] for i in range(length))
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
