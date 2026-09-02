"""Grounding: are the figures in an answer traceable to the passages the model was shown?

Retrieval-augmented assistants fail in one specific, dangerous way — they state a quantity
("5 drops", "40 minutes", "2 parts ash") that the retrieved passages never contained. This
scorer is a deterministic, offline check for exactly that class of claim, plus citation
validity: a ``[n]`` that points past the end of the excerpt list is the same failure wearing
a different hat.

It reads the retrieval context the provider attached to each assistant turn
(``metadata["context"]``, see :class:`alignmenter.providers.base.ChatResponse`). Excerpts may
be dicts with ``text`` (and optional ``title`` / ``section``) or plain strings, under any of
the keys ``excerpts``, ``passages``, ``documents``, ``sources``, ``context``.

Unsupported quantities are split two ways, because they need different fixes:

* **invented** — the passages gave no figure in that unit at all. The model filled a gap.
  That is a prompt problem ("say the library does not specify").
* **contradicted** — the passages gave a figure in that unit and the answer's differs. That
  is a comprehension or retrieval problem.

This is a proxy, not truth: it does not judge whether the answer is correct or whether the
right passages were retrieved. Pair it with :class:`~alignmenter.scorers.faithfulness.FaithfulnessScorer`
for that.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

#: Quantities worth checking: a number, optionally followed by a unit. Bare integers are
#: usually layout (list numbering, ordinals); the claims a reader acts on carry units.
_NUMBER = re.compile(
    r"(?<![\w.])(\d+(?:[.,]\d+)?)\s*"
    r"(%|°|degrees?|°?[CF]\b|minutes?|mins?\b|hours?|hrs?\b|days?|weeks?|months?|years?|"
    r"seconds?|secs?\b|millimet(?:er|re)s?|mm\b|centimet(?:er|re)s?|cm\b|met(?:er|re)s?|m\b|"
    r"kilomet(?:er|re)s?|km\b|miles?|feet|foot|ft\b|inch(?:es)?|in\b|yards?|"
    r"litres?|liters?|l\b|millilit(?:er|re)s?|ml\b|gallons?|quarts?|pints?|cups?|"
    r"tablespoons?|tbsp\b|teaspoons?|tsp\b|grams?|g\b|kilograms?|kg\b|milligrams?|mg\b|"
    r"micrograms?|mcg\b|µg\b|pounds?|lbs?\b|ounces?|oz\b|drops?|parts?|times|x\b|"
    r"volts?|v\b|amps?|amperes?|a\b|watts?|w\b|ohms?|hz\b|hertz|psi\b|bar\b|"
    r"calories|kcal\b|mmol|mg/dl|bpm\b|rpm\b|knots?|nm\b)?",
    re.IGNORECASE,
)
_CITATION = re.compile(r"\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\]")
_LIST_MARKER = re.compile(r"(?m)^\s*\d+[.)]\s+")

_UNIT_ALIASES = {
    "degrees": "deg", "degree": "deg", "°": "deg", "°c": "deg", "°f": "deg", "c": "deg", "f": "deg",
    "minutes": "min", "minute": "min", "mins": "min", "min": "min",
    "hours": "hr", "hour": "hr", "hrs": "hr", "hr": "hr",
    "seconds": "sec", "second": "sec", "secs": "sec", "sec": "sec",
    "days": "day", "day": "day", "weeks": "week", "week": "week",
    "months": "month", "month": "month", "years": "year", "year": "year",
    "litres": "l", "liters": "l", "litre": "l", "liter": "l", "l": "l",
    "millilitres": "ml", "milliliters": "ml", "millilitre": "ml", "milliliter": "ml", "ml": "ml",
    "millimeters": "mm", "millimetres": "mm", "millimeter": "mm", "millimetre": "mm", "mm": "mm",
    "centimeters": "cm", "centimetres": "cm", "centimeter": "cm", "centimetre": "cm", "cm": "cm",
    "meters": "m", "metres": "m", "meter": "m", "metre": "m", "m": "m",
    "kilometers": "km", "kilometres": "km", "kilometer": "km", "kilometre": "km", "km": "km",
    "miles": "mile", "mile": "mile", "yards": "yd", "yard": "yd",
    "feet": "ft", "foot": "ft", "ft": "ft", "inches": "in", "inch": "in", "in": "in",
    "gallons": "gal", "gallon": "gal", "quarts": "qt", "quart": "qt", "pints": "pt", "pint": "pt",
    "cups": "cup", "cup": "cup", "tablespoons": "tbsp", "tablespoon": "tbsp", "tbsp": "tbsp",
    "teaspoons": "tsp", "teaspoon": "tsp", "tsp": "tsp",
    "grams": "g", "gram": "g", "g": "g", "kilograms": "kg", "kilogram": "kg", "kg": "kg",
    "milligrams": "mg", "milligram": "mg", "mg": "mg",
    "micrograms": "mcg", "microgram": "mcg", "mcg": "mcg", "µg": "mcg",
    "pounds": "lb", "pound": "lb", "lbs": "lb", "lb": "lb",
    "ounces": "oz", "ounce": "oz", "oz": "oz",
    "drops": "drop", "drop": "drop", "parts": "part", "part": "part",
    "times": "x", "x": "x", "%": "%",
    "volts": "v", "volt": "v", "v": "v", "amps": "a", "amp": "a", "amperes": "a", "ampere": "a", "a": "a",
    "watts": "w", "watt": "w", "w": "w", "ohms": "ohm", "ohm": "ohm", "hz": "hz", "hertz": "hz",
    "psi": "psi", "bar": "bar", "calories": "kcal", "kcal": "kcal", "mmol": "mmol",
    "mg/dl": "mg/dl", "bpm": "bpm", "rpm": "rpm", "knots": "kn", "knot": "kn", "nm": "nm",
}

_EXCERPT_KEYS = ("excerpts", "passages", "documents", "sources", "context")


def strip_formatting(text: str) -> str:
    """Remove digits that are layout rather than claims: citation markers and list numbering."""

    return _LIST_MARKER.sub("", _CITATION.sub(" ", text or ""))


def canonical_unit(unit: str) -> str:
    return _UNIT_ALIASES.get(unit.strip().lower(), unit.strip().lower())


def extract_quantities(text: str) -> list[tuple[str, str]]:
    """``(value, unit)`` pairs in *text*; values normalised so ``1.0`` and ``1,0`` compare equal."""

    out: list[tuple[str, str]] = []
    for match in _NUMBER.finditer(strip_formatting(text)):
        raw = match.group(1).replace(",", ".")
        # Normalise 1.0 -> 1 so restatements compare equal, but never touch integers:
        # "30".rstrip("0") is "3", which would turn a correct quantity into a violation.
        value = raw.rstrip("0").rstrip(".") if "." in raw else raw
        unit = canonical_unit((match.group(2) or "").rstrip("."))
        out.append((value, unit))
    return out


def excerpt_text(context: dict[str, Any]) -> str:
    """Flatten whatever the provider attached as retrieval context into one string."""

    parts: list[str] = []
    for key in _EXCERPT_KEYS:
        items = context.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                for field in ("title", "section", "text", "content", "body"):
                    value = item.get(field)
                    if value:
                        parts.append(str(value))
        if parts:
            break
    return "\n".join(parts)


def excerpt_count(context: dict[str, Any]) -> int:
    for key in _EXCERPT_KEYS:
        items = context.get(key)
        if isinstance(items, list):
            return len(items)
    return 0


def iter_grounded_turns(sessions: Iterable) -> list[tuple[dict, dict]]:
    """``(turn, context)`` for assistant turns that carry retrieval context."""

    pairs: list[tuple[dict, dict]] = []
    for session in sessions:
        turns = getattr(session, "turns", None)
        if turns is None and hasattr(session, "get"):
            turns = session.get("turns", [])
        for turn in turns or []:
            if (turn.get("role") or "") != "assistant":
                continue
            context = (turn.get("metadata") or {}).get("context")
            if isinstance(context, dict):
                pairs.append((turn, context))
    return pairs


def question_for(turn: dict, context: dict, session_turns: list[dict] | None = None) -> str:
    """The user question this answer replies to: from the context if the provider recorded it,
    else the nearest preceding user turn."""

    for key in ("question", "query", "prompt"):
        value = context.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if session_turns:
        index = next((i for i, t in enumerate(session_turns) if t is turn), None)
        if index is not None:
            for prior in reversed(session_turns[:index]):
                if (prior.get("role") or "") == "user" and prior.get("text"):
                    return str(prior["text"]).strip()
    return ""


class GroundingScorer:
    """Fraction of quantities in each answer that appear in the passages it was given.

    Reported ``score`` is supported ÷ checked across all grounded turns. ``details`` carries
    the invented/contradicted split, citation validity, and the worst offenders so a reader
    can go straight to the answers that need fixing.
    """

    id = "grounding"

    def __init__(self, *, units_only: bool = True, max_violations: int = 20) -> None:
        # Only quantities carrying a unit are judged by default. A bare integer in prose is
        # nearly always layout or an ordinal; the claims that hurt someone carry units, and
        # scoring the rest buries them in noise.
        self.units_only = units_only
        self.max_violations = max_violations

    def score(self, sessions: Iterable) -> dict:
        supported = total = 0
        citations = bad_citations = 0
        invented_total = contradicted_total = 0
        turns_checked = 0
        violations: list[dict[str, Any]] = []

        session_list = list(sessions)
        for turn, context in iter_grounded_turns(session_list):
            answer = turn.get("text") or ""
            source = excerpt_text(context)
            if not answer.strip():
                continue
            turns_checked += 1

            source_numbers = set(extract_quantities(source))
            source_values = {value for value, _ in source_numbers}
            source_units = {unit for _, unit in source_numbers if unit}

            unsupported: list[str] = []
            invented: list[str] = []
            contradicted: list[str] = []
            for value, unit in extract_quantities(answer):
                if self.units_only and not unit:
                    continue
                total += 1
                if (value, unit) in source_numbers or (not unit and value in source_values):
                    supported += 1
                    continue
                rendered = f"{value}{(' ' + unit) if unit else ''}"
                unsupported.append(rendered)
                (contradicted if unit and unit in source_units else invented).append(rendered)

            count = excerpt_count(context)
            for match in _CITATION.finditer(answer):
                for ref in match.group(1).split(","):
                    citations += 1
                    try:
                        if not 1 <= int(ref) <= count:
                            bad_citations += 1
                    except ValueError:
                        bad_citations += 1

            if unsupported:
                owner = next((s for s in session_list if turn in _turns_of(s)), None)
                violations.append(
                    {
                        "session_id": getattr(owner, "session_id", None)
                        or (owner.get("session_id") if isinstance(owner, dict) else None),
                        "question": question_for(turn, context, _turns_of(owner) if owner else None),
                        "unsupported_quantities": unsupported,
                        "invented": invented,
                        "contradicted": contradicted,
                        "excerpts": count,
                    }
                )
            invented_total += len(invented)
            contradicted_total += len(contradicted)

        score = supported / total if total else 1.0
        citation_validity = 1.0 - (bad_citations / citations) if citations else 1.0
        violations.sort(key=lambda v: -len(v["unsupported_quantities"]))
        return {
            "score": round(score, 4),
            "turns": turns_checked,
            "quantities_checked": total,
            "quantities_supported": supported,
            "invented": invented_total,
            "contradicted": contradicted_total,
            "citations": citations,
            "invalid_citations": bad_citations,
            "citation_validity": round(citation_validity, 4),
            "violations": violations[: self.max_violations],
        }


def _turns_of(session: Any) -> list[dict]:
    turns = getattr(session, "turns", None)
    if turns is None and hasattr(session, "get"):
        turns = session.get("turns", [])
    return list(turns or [])
