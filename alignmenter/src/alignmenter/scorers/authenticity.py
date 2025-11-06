"""Authenticity metric implementation."""

from __future__ import annotations

import json
import math
import random
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional, Sequence

import logging

from alignmenter.providers.embeddings import EmbeddingProvider, load_embedding_provider
from alignmenter.utils import load_yaml

TOKEN_PATTERN = re.compile(r"[\w']+")
LOGGER = logging.getLogger(__name__)

# Default global normalization bounds (empirical values for typical embeddings)
# These can be overridden by calibration data
DEFAULT_STYLE_SIM_MIN = 0.05  # typical minimum raw cosine similarity
DEFAULT_STYLE_SIM_MAX = 0.25  # typical maximum raw cosine similarity


@dataclass
class TraitModel:
    bias: float
    token_weights: dict[str, float]
    phrase_weights: dict[str, float]


@dataclass
class PersonaProfile:
    preferred: set[str]
    avoided: set[str]
    exemplars: list[list[float]]
    trait_positive: set[str]
    trait_negative: set[str]
    weights: dict[str, float]
    trait_model: TraitModel
    style_sim_min: float = DEFAULT_STYLE_SIM_MIN
    style_sim_max: float = DEFAULT_STYLE_SIM_MAX


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

        # Rescale style_sim using global normalization bounds
        raw_style_scores = [turn.style_sim for turn in turns]
        rescaled_style_scores = rescale_similarity(
            raw_style_scores,
            min_score=self.profile.style_sim_min,
            max_score=self.profile.style_sim_max
        )

        # Recompute combined scores with rescaled style_sim
        for i, turn in enumerate(turns):
            rescaled_style = rescaled_style_scores[i]
            combined = (
                self.profile.weights["style"] * rescaled_style
                + self.profile.weights["traits"] * turn.traits
                + self.profile.weights["lexicon"] * turn.lexicon
            )
            turns[i] = AuthenticityTurn(
                style_sim=rescaled_style,
                traits=turn.traits,
                lexicon=turn.lexicon,
                score=combined
            )

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

    calibration_weights, trait_model, style_sim_min, style_sim_max = load_calibration(
        persona_path.with_suffix(".traits.json"),
        default_weights={"style": 0.3, "traits": 0.3, "lexicon": 0.4},
    )

    if trait_model is None:
        token_weights = {token: 1.0 for token in trait_positive}
        token_weights.update({token: -1.0 for token in trait_negative})
        trait_model = TraitModel(bias=0.0, token_weights=token_weights, phrase_weights={})
        LOGGER.info(
            "No calibrated trait model found for persona '%s'; using heuristic weights.",
            persona.get("id", persona_path.stem) if isinstance(persona, dict) else persona_path.stem,
        )

    return PersonaProfile(
        preferred=preferred,
        avoided=avoided,
        exemplars=exemplar_vectors,
        trait_positive=trait_positive,
        trait_negative=trait_negative,
        weights=calibration_weights,
        trait_model=trait_model,
        style_sim_min=style_sim_min,
        style_sim_max=style_sim_max,
    )


# scoring helpers

def score_turn(text: str, tokens: list[str], profile: PersonaProfile, embedder: EmbeddingProvider) -> AuthenticityTurn:
    vector = normalize_vector(embedder.embed([text])[0])
    style_sim = style_similarity(vector, profile.exemplars)
    traits_score = traits_probability(text, tokens, profile)
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


def traits_probability(text: str, tokens: Iterable[str], profile: PersonaProfile) -> float:
    token_set = set(tokens)
    logit = profile.trait_model.bias
    for token in token_set:
        logit += profile.trait_model.token_weights.get(token, 0.0)
    lowered = text.lower()
    for phrase, weight in profile.trait_model.phrase_weights.items():
        if phrase in lowered:
            logit += weight
    return sigmoid(logit)


def lexicon_score(tokens: list[str], profile: PersonaProfile) -> float:
    if not tokens:
        return 0.5
    preferred = sum(token in profile.preferred for token in tokens)
    avoided = sum(token in profile.avoided for token in tokens)

    # Density-based approach: penalize text with no brand words
    lexicon_density = (preferred + avoided) / max(1, len(tokens))

    # Balance: positive if more preferred than avoided
    if preferred + avoided == 0:
        balance = 0.0  # neutral text gets 0 balance
    else:
        balance = (preferred - avoided) / (preferred + avoided)

    # Scale balance to [0, 1] range and weight by density
    # Density * 10 means ~10% brand word usage → full weight
    normalized_balance = 0.5 + balance / 2  # maps [-1, 1] → [0, 1]
    score = normalized_balance * min(1.0, lexicon_density * 10)

    return max(0.0, min(1.0, score))


def bootstrap_ci(
    random_gen: random.Random,
    scores: list[float],
    iterations: int = 200,
    alpha: float = 0.05,
) -> tuple[Optional[float], Optional[float]]:
    if len(scores) < 2:
        return None, None

    samples = []
    for _ in range(iterations):
        resample = [random_gen.choice(scores) for _ in scores]
        samples.append(mean(resample))

    samples.sort()
    lower_idx = int((alpha / 2) * len(samples))
    upper_idx = max(lower_idx, int((1 - alpha / 2) * len(samples)) - 1)
    return samples[lower_idx], samples[upper_idx]


# shared utilities

def load_calibration(
    calibration_path: Path, default_weights: dict[str, float]
) -> tuple[dict[str, float], Optional[TraitModel], float, float]:
    """Load calibration data including weights, trait model, and normalization bounds."""
    default_min = DEFAULT_STYLE_SIM_MIN
    default_max = DEFAULT_STYLE_SIM_MAX

    if not calibration_path.exists():
        return default_weights, None, default_min, default_max
    try:
        calibration = json.loads(calibration_path.read_text())
    except json.JSONDecodeError:
        return default_weights, None, default_min, default_max

    weights: dict[str, float] = default_weights
    style_sim_min = default_min
    style_sim_max = default_max

    if isinstance(calibration, dict):
        raw_weights = calibration.get("weights") if isinstance(calibration.get("weights"), dict) else None
        if raw_weights:
            mapped = {
                key: float(raw_weights.get(key, default_weights[key]))
                for key in default_weights
                if isinstance(raw_weights.get(key, default_weights[key]), (int, float))
            }
            total = sum(mapped.values()) or 1.0
            weights = {key: value / total for key, value in mapped.items()}
        else:
            values = [calibration.get("style_weight"), calibration.get("traits_weight"), calibration.get("lexicon_weight")]
            if all(isinstance(weight, (int, float)) for weight in values):
                total = sum(values) or 1.0
                keys = ("style", "traits", "lexicon")
                weights = {key: value / total for key, value in zip(keys, values)}

        # Read normalization bounds if present
        if isinstance(calibration.get("style_sim_min"), (int, float)):
            style_sim_min = float(calibration["style_sim_min"])
        if isinstance(calibration.get("style_sim_max"), (int, float)):
            style_sim_max = float(calibration["style_sim_max"])

        trait_model = _parse_trait_model(calibration)
        return weights, trait_model, style_sim_min, style_sim_max

    return weights, None, default_min, default_max


def _parse_trait_model(calibration: dict) -> Optional[TraitModel]:
    model_data = calibration.get("trait_model")
    if isinstance(model_data, dict):
        bias = float(model_data.get("bias", 0.0))
        token_weights = {
            token.lower(): float(weight)
            for token, weight in (model_data.get("token_weights") or {}).items()
            if isinstance(weight, (int, float))
        }
        phrase_weights = {
            phrase.lower(): float(weight)
            for phrase, weight in (model_data.get("phrase_weights") or {}).items()
            if isinstance(weight, (int, float))
        }
        return TraitModel(bias=bias, token_weights=token_weights, phrase_weights=phrase_weights)

    # legacy keys
    token_weights = calibration.get("trait_weights")
    if isinstance(token_weights, dict):
        bias = float(calibration.get("trait_bias", 0.0))
        normalized = {
            token.lower(): float(weight)
            for token, weight in token_weights.items()
            if isinstance(weight, (int, float))
        }
        return TraitModel(bias=bias, token_weights=normalized, phrase_weights={})

    return None


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
        return [0.0 for _ in vector]
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


def rescale_similarity(scores: list[float], min_score: float, max_score: float) -> list[float]:
    """
    Rescale embedding similarity scores using global normalization bounds.

    Uses persona-specific (or default) min/max values to ensure scores are
    comparable across different evaluation runs.

    Raw cosine similarity typically ranges from 0.05-0.25 for realistic text.
    This rescales to approximately 0.3-0.9:

    - Below global min → ~0.3
    - At global min → ~0.3
    - Average (midpoint) → ~0.6
    - At global max → ~0.9
    - Above global max → ~0.9

    This allows on-brand content to achieve high scores while maintaining
    separation between good and bad responses across runs.
    """
    if not scores:
        return []

    # Ensure valid range
    if max_score <= min_score:
        return [0.6 for _ in scores]

    rescaled = []
    for score in scores:
        # Normalize to [0, 1] using global bounds
        normalized = (score - min_score) / (max_score - min_score)
        # Clamp to [0, 1] in case score is outside calibration bounds
        normalized = max(0.0, min(1.0, normalized))
        # Rescale to [0.3, 0.9] range for intuitive interpretation
        rescaled_score = 0.3 + (normalized * 0.6)
        rescaled.append(rescaled_score)

    return rescaled
