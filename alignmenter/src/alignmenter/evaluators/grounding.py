"""Conservative quantity traceability and citation resolution, not semantic entailment.

Supported quantities retain signs, bounds and units. Exact SI conversions use rational
arithmetic. Recognized but unsupported notation stays ambiguous instead of passing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from alignmenter.evaluators.evidence import supporting_sources
from alignmenter.schemas.scoring import (
    CitationFinding,
    EvidenceBundle,
    GroundingAssessment,
    QuantityFinding,
    SourceQuote,
)

# Each entry maps to (dimension, scale, offset); base = value * scale + offset.
UNITS: dict[str, tuple[str, Fraction, Fraction]] = {}


def _unit(names, dimension, scale=1, offset=0):
    for name in names.split("|"):
        UNITS[name.casefold()] = (dimension, Fraction(scale), Fraction(offset))


_unit("mm|millimeter|millimeters|millimetre|millimetres", "length", "0.001")
_unit("cm|centimeter|centimeters|centimetre|centimetres", "length", "0.01")
_unit("m|meter|meters|metre|metres", "length")
_unit("km|kilometer|kilometers|kilometre|kilometres", "length", 1000)
_unit("mcg|µg|μg|microgram|micrograms", "mass", "0.000001")
_unit("mg|milligram|milligrams", "mass", "0.001")
_unit("g|gram|grams", "mass")
_unit("kg|kilogram|kilograms", "mass", 1000)
_unit("ml|milliliter|milliliters|millilitre|millilitres", "volume", "0.001")
_unit("l|liter|liters|litre|litres", "volume")
_unit("s|sec|secs|second|seconds", "time")
_unit("min|mins|minute|minutes", "time", 60)
_unit("h|hr|hrs|hour|hours", "time", 3600)
_unit("day|days", "time", 86400)
_unit("week|weeks", "time", 604800)
_unit("°c|c|celsius|degrees celsius", "temperature", 1, "273.15")
_unit("°f|f|fahrenheit|degrees fahrenheit", "temperature", Fraction(5, 9), Fraction(45967, 180))
_unit("k|kelvin", "temperature")
_unit("%|percent", "ratio", "0.01")
for singular in ("drop", "part", "cup", "tsp", "tbsp", "gallon", "month", "year"):
    _unit(f"{singular}|{singular}s", singular)

UNIT = "(?:" + "|".join(re.escape(u).replace(r"\ ", r"\s+").replace("°", r"°\s*") for u in sorted(UNITS, key=len, reverse=True)) + ")"
NUMBER = r"[+−-]?(?:(?:\d+(?:\.\d+)?|\.\d+)(?:[,/]\d+(?:\.\d+)?)*(?:[eE][+−-]?\d+)?|[¼½¾⅓⅔⅛⅜⅝⅞])"
PREFIX = r"(?:(?:no|not)\s+(?:more|less)\s+than|at\s+(?:least|most)|less\s+than|more\s+than|up\s+to|over|under|above|below|minimum|maximum|between|about|approximately|around|roughly|nearly|almost|[<>]=?|[≤≥~≈±])"
QUANTITY = re.compile(
    rf"(?<![\w.])(?:(?P<prefix>{PREFIX})\s*)?(?P<a>{NUMBER})"
    rf"(?:\s*(?P<first_unit>{UNIT})?\s*(?P<range>to|and|[-–—])\s*(?P<b>{NUMBER}))?"
    rf"\s*(?P<unit>{UNIT})"
    rf"(?P<suffix>(?:\s*/\s*[a-zµμ]+(?:\^?\d+)?|\s+per\s+[a-z]+|[²³]|\^[23]|\s+or\s+(?:more|less))?)(?![\w°])",
    re.IGNORECASE,
)
CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


@dataclass(frozen=True)
class Quantity:
    quote: str
    signature: str | None


def _normal_unit(value):
    return re.sub(r"°\s+", "°", re.sub(r"\s+", " ", value.casefold()))


def _signature(match):
    first, last = match["a"], match["b"]
    if match["suffix"] or re.search(r"[,/eE¼½¾⅓⅔⅛⅜⅝⅞]", first + (last or "")):
        return None
    prefix = " ".join((match["prefix"] or "").casefold().split())
    operator = {
        "": "eq", "between": "range", "at least": "ge", "no less than": "ge", "not less than": "ge", "minimum": "ge", ">=": "ge", "≥": "ge",
        "at most": "le", "no more than": "le", "not more than": "le", "maximum": "le", "up to": "le", "<=": "le", "≤": "le",
        "over": "gt", "above": "gt", "more than": "gt", ">": "gt", "under": "lt", "below": "lt", "less than": "lt", "<": "lt",
    }.get(prefix)
    if operator is None or (operator == "range" and last is None):
        return None
    dimension, scale, offset = UNITS[_normal_unit(match["unit"])]
    value = Fraction(first.replace("−", "-")) * scale + offset
    if last is not None:
        if prefix not in {"", "between"} or (match["range"].casefold() == "and" and prefix != "between"):
            return None
        d1, s1, o1 = UNITS[_normal_unit(match["first_unit"] or match["unit"])]
        if d1 != dimension:
            return None
        value = Fraction(first.replace("−", "-")) * s1 + o1
        end = Fraction(last.replace("−", "-")) * scale + offset
        return f"{dimension}:range:{value}:{end}" if value <= end else None
    return f"{dimension}:{operator}:{value}"


def quantities(text: str) -> list[Quantity]:
    return [Quantity(m.group(), _signature(m)) for m in QUANTITY.finditer(text)]


def assess_grounding(data: EvidenceBundle) -> GroundingAssessment:
    sources = supporting_sources(data)
    found = [(source_id, q) for source_id, text in sources.items() for q in quantities(text)
             if q.signature is not None]
    findings = []
    for q in quantities(data.answer):
        match = next(((s, evidence) for s, evidence in found if evidence.signature == q.signature), None) if q.signature else None
        status = ("question" if match[0] == data.question_source_id else "source") if match else "unmatched" if q.signature else "ambiguous"
        findings.append(QuantityFinding(quote=q.quote, normalized=q.signature, status=status,
                                        evidence=SourceQuote(source_id=match[0], quote=match[1].quote) if match else None))
    citations = [CitationFinding(quote=m.group(), index=int(n),
                                 source_id=f"passage:{int(n)}" if f"passage:{int(n)}" in sources else None)
                 for m in CITATION.finditer(data.answer) for n in m[1].split(",")]
    return GroundingAssessment(quantities=findings, citations=citations)
