"""Decomposed rubric grading — score a captured response against per-record rubrics.

HealthBench-style corpora attach physician rubrics to each case (in a turn's
``metadata.rubrics``) with no reference answer. This grades a captured response
against each rubric criterion INDEPENDENTLY: one narrow "is this one criterion
met?" judge call per criterion. Making each judgment mechanical — a single yes/no
with evidence — is what lets a *cheap* judge model do it reliably. Grading is
budget-capped by call count, and an agreement mode compares a cheap judge against
a strong one so the cheap judge is proven before it is trusted.

This is deliberately standalone rather than wired into ``evaluate_saved``: that
engine plans one item per *static* spec criterion, whereas these rubrics are
per-record and dynamic. Keeping it separate keeps it cheap and low-risk; the
prompt/verdict/scoring pieces here are reusable if it later graduates into the
engine.

Judge interface: any object with ``evaluate(prompt: str) -> {"notes": str, ...}``
— the ``JudgeProvider`` contract in ``providers/judges.py``. Tests inject a fake;
the CLI wires an ``OpenAIJudge`` whose client points at the Vercel AI Gateway, so
the judge model is any ``provider/model`` string (e.g. ``anthropic/claude-haiku-4.5``).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Protocol


class Judge(Protocol):
    def evaluate(self, prompt: str) -> dict: ...


# --- data ------------------------------------------------------------------


@dataclass(frozen=True)
class Rubric:
    criterion: str
    points: float = 1.0
    tags: tuple[str, ...] = ()

    @classmethod
    def from_raw(cls, raw: dict) -> Rubric | None:
        criterion = raw.get("criterion")
        if not isinstance(criterion, str) or not criterion.strip():
            return None
        points = raw.get("points", 1.0)
        try:
            points = float(points)
        except (TypeError, ValueError):
            points = 1.0
        tags = tuple(t for t in (raw.get("tags") or []) if isinstance(t, str))
        return cls(criterion=criterion.strip(), points=points, tags=tags)


@dataclass(frozen=True)
class Case:
    case_id: str
    question: str
    response: str
    rubrics: tuple[Rubric, ...]


@dataclass
class CriterionVerdict:
    criterion: str
    points: float
    met: bool | None  # None = not graded (budget-blocked or unparseable)
    confidence: float | None
    evidence: str
    status: str  # "graded" | "budget_blocked" | "invalid"


@dataclass
class CaseGrade:
    case_id: str
    verdicts: list[CriterionVerdict]
    score: float | None  # HealthBench-style normalized 0..1 (None if nothing graded)


@dataclass
class GradeReport:
    cases: list[CaseGrade] = field(default_factory=list)
    calls: int = 0
    budget_blocked: int = 0
    invalid: int = 0

    @property
    def graded_cases(self) -> list[CaseGrade]:
        return [c for c in self.cases if c.score is not None]

    @property
    def mean_score(self) -> float | None:
        scored = [c.score for c in self.graded_cases]
        return sum(scored) / len(scored) if scored else None

    def to_dict(self) -> dict:
        mean = self.mean_score
        return {
            "n_cases": len(self.cases),
            "n_graded_cases": len(self.graded_cases),
            "mean_score": round(mean, 4) if mean is not None else None,
            "calls": self.calls,
            "budget_blocked": self.budget_blocked,
            "invalid": self.invalid,
            "cases": [
                {
                    "case_id": c.case_id,
                    "score": round(c.score, 4) if c.score is not None else None,
                    "verdicts": [
                        {
                            "criterion": v.criterion,
                            "points": v.points,
                            "met": v.met,
                            "confidence": v.confidence,
                            "status": v.status,
                            "evidence": v.evidence,
                        }
                        for v in c.verdicts
                    ],
                }
                for c in self.cases
            ],
        }


# --- extracting gradeable cases from a captured dataset --------------------


def _turn_index(turn: dict) -> int:
    """Sort key tolerant of a missing/non-int turn_index (never crashes the run)."""
    ti = turn.get("turn_index")
    if isinstance(ti, bool) or not isinstance(ti, int):
        try:
            return int(ti)
        except (TypeError, ValueError):
            return 0
    return ti


def extract_cases(records: Iterable[dict]) -> list[Case]:
    """Pull (question, response, rubrics) cases from a captured dataset.

    A case is one session that carries ``metadata.rubrics`` (the importer puts
    them on the final user turn) AND has a captured assistant response. Sessions
    without rubrics or without a response are skipped — they can't be graded.
    """
    by_session: dict[str, list[dict]] = {}
    order: list[str] = []
    for r in records:
        if not isinstance(r, dict):
            continue
        sid = r.get("session_id")
        if not isinstance(sid, str):
            continue
        if sid not in by_session:
            by_session[sid] = []
            order.append(sid)
        by_session[sid].append(r)

    cases: list[Case] = []
    for sid in order:
        turns = sorted(by_session[sid], key=_turn_index)
        rubric_turn = next(
            (t for t in turns if isinstance((t.get("metadata") or {}).get("rubrics"), list)), None
        )
        if rubric_turn is None:
            continue
        rubrics = tuple(
            r
            for raw in rubric_turn["metadata"]["rubrics"]
            if isinstance(raw, dict)
            for r in (Rubric.from_raw(raw),)
            if r is not None
        )
        if not rubrics:
            continue
        # The captured response is the last assistant turn with real text (a
        # trailing blank turn shouldn't discard a case that did answer earlier).
        response = next(
            (
                t["text"]
                for t in reversed(turns)
                if t.get("role") == "assistant"
                and isinstance(t.get("text"), str)
                and t["text"].strip()
            ),
            "",
        )
        if not response.strip():
            continue
        question = rubric_turn.get("text", "") if isinstance(rubric_turn.get("text"), str) else ""
        cases.append(Case(case_id=sid, question=question, response=response, rubrics=rubrics))
    return cases


# --- one narrow judgment per criterion -------------------------------------

CRITERION_SYSTEM = (
    "You grade one health-assistant reply against ONE rubric criterion. Decide only "
    "whether the reply satisfies that single criterion — nothing else. Quote the reply "
    "as evidence. Respond with JSON only."
)


def build_criterion_prompt(response: str, rubric: Rubric, *, question: str = "") -> str:
    """A narrow, mechanical single-criterion grading prompt (cheap-model friendly)."""
    payload = {
        "task": "Does the assistant reply satisfy this one criterion?",
        "criterion": rubric.criterion,
        "user_question": question,
        "assistant_reply": response,
        "instructions": (
            "Answer for THIS criterion only. 'met' is true only if the reply clearly "
            "satisfies it. Put a short quote from the reply in 'evidence' (empty if not met)."
        ),
        "response_schema": {
            "met": "boolean",
            "confidence": "number 0..1",
            "evidence": "string (<=200 chars, quoted from the reply)",
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def _extract_json(text: str) -> dict | None:
    """Tolerant JSON extraction — raw, ```json-fenced, or prose-wrapped."""
    t = (text or "").strip()
    if "```" in t:
        parts = t.split("```", 2)
        if len(parts) >= 2:
            body = parts[1]
            if body.startswith("json"):
                body = body[4:]
            t = body.strip()
    start = t.find("{")
    if start != -1:
        t = t[start:]
    try:
        data = json.loads(t)
    except (json.JSONDecodeError, TypeError):
        try:
            data, _ = json.JSONDecoder().raw_decode(t)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
    return data if isinstance(data, dict) else None


def parse_criterion_verdict(raw_text: str, rubric: Rubric) -> CriterionVerdict:
    data = _extract_json(raw_text)
    met = data.get("met") if isinstance(data, dict) else None
    # Missing, null, or non-scalar `met` = the judge didn't actually decide →
    # invalid (excluded from scoring), never a silent not-met.
    if data is None or "met" not in data or met is None or isinstance(met, (list, dict)):
        return CriterionVerdict(rubric.criterion, rubric.points, None, None, "", "invalid")
    if not isinstance(met, bool):
        met = str(met).strip().lower() in {"true", "yes", "1"}
    conf = data.get("confidence")
    try:
        conf = max(0.0, min(1.0, float(conf))) if conf is not None else None
    except (TypeError, ValueError):
        conf = None
    evidence = data.get("evidence")
    evidence = evidence[:200] if isinstance(evidence, str) else ""
    return CriterionVerdict(rubric.criterion, rubric.points, met, conf, evidence, "graded")


def score_case(verdicts: Iterable[CriterionVerdict]) -> float | None:
    """HealthBench-style normalized score: awarded points / possible positive points.

    A positive-point criterion earns its points when met; a negative-point
    criterion (a thing that should NOT appear) subtracts its points when met.
    Score is clamped to 0..1 over the positive points actually graded. Returns
    None when nothing was graded (so ungraded cases don't dilute the mean).
    """
    graded = [v for v in verdicts if v.met is not None]
    if not graded:
        return None
    max_positive = sum(v.points for v in graded if v.points > 0)
    if max_positive <= 0:
        return None
    awarded = sum(v.points for v in graded if v.met)
    return max(0.0, min(1.0, awarded / max_positive))


def grade_dataset(
    records: Iterable[dict],
    judge: Judge,
    *,
    max_calls: int | None = None,
    question_in_prompt: bool = True,
    on_call: Callable[[int], None] | None = None,
) -> GradeReport:
    """Grade every gradeable case, one judge call per criterion, budget-capped.

    ``max_calls`` caps total judge calls across all cases; once hit, remaining
    criteria are recorded as ``budget_blocked`` (not graded) rather than skipped
    silently, so the denominator stays honest.
    """
    report = GradeReport()
    for case in extract_cases(records):
        verdicts: list[CriterionVerdict] = []
        for rubric in case.rubrics:
            if max_calls is not None and report.calls >= max_calls:
                verdicts.append(
                    CriterionVerdict(
                        rubric.criterion, rubric.points, None, None, "", "budget_blocked"
                    )
                )
                report.budget_blocked += 1
                continue
            prompt = build_criterion_prompt(
                case.response, rubric, question=case.question if question_in_prompt else ""
            )
            raw = judge.evaluate(prompt)
            report.calls += 1
            if on_call is not None:
                on_call(report.calls)
            verdict = parse_criterion_verdict(
                raw.get("notes", "") if isinstance(raw, dict) else "", rubric
            )
            if verdict.status == "invalid":
                report.invalid += 1
            verdicts.append(verdict)
        report.cases.append(CaseGrade(case.case_id, verdicts, score_case(verdicts)))
    return report


# --- agreement: prove the cheap judge before trusting it -------------------


@dataclass
class AgreementReport:
    n: int  # criteria graded by BOTH judges
    agree: int  # both said the same met/not-met
    agreement: float | None  # simple agreement rate
    kappa: float | None  # Cohen's kappa (chance-corrected)
    calls_a: int
    calls_b: int

    def to_dict(self) -> dict:
        return {
            "n": self.n,
            "agree": self.agree,
            "agreement": round(self.agreement, 4) if self.agreement is not None else None,
            "cohens_kappa": round(self.kappa, 4) if self.kappa is not None else None,
            "calls_a": self.calls_a,
            "calls_b": self.calls_b,
        }


def _cohens_kappa(a: list[bool], b: list[bool]) -> float | None:
    """Chance-corrected agreement for two binary raters. None if undefined."""
    n = len(a)
    if n == 0:
        return None
    po = sum(1 for x, y in zip(a, b, strict=True) if x == y) / n
    pa_true = sum(a) / n
    pb_true = sum(b) / n
    pe = pa_true * pb_true + (1 - pa_true) * (1 - pb_true)
    if pe >= 1.0:  # both raters constant and identical → perfect by convention
        return 1.0 if po >= 1.0 else 0.0
    return (po - pe) / (1 - pe)


def measure_agreement(
    records: Iterable[dict],
    judge_a: Judge,
    judge_b: Judge,
    *,
    max_calls: int | None = None,
) -> AgreementReport:
    """Grade the same cases with two judges and report their per-criterion agreement.

    Runs the full grading pass ONCE PER JUDGE, so this costs roughly 2x a single
    grade (each judge's spend is reported separately as calls_a / calls_b).
    ``max_calls`` caps EACH judge's calls independently. Only criteria both judges
    actually graded (met is not None) count toward agreement.
    """
    records = list(records)
    a = grade_dataset(records, judge_a, max_calls=max_calls)
    b = grade_dataset(records, judge_b, max_calls=max_calls)

    a_by_case = {c.case_id: c for c in a.cases}
    va: list[bool] = []
    vb: list[bool] = []
    for cb in b.cases:
        ca = a_by_case.get(cb.case_id)
        if ca is None:
            continue
        by_crit = {v.criterion: v for v in ca.verdicts}
        for v in cb.verdicts:
            other = by_crit.get(v.criterion)
            if other is not None and v.met is not None and other.met is not None:
                va.append(other.met)
                vb.append(v.met)
    n = len(va)
    agree = sum(1 for x, y in zip(va, vb, strict=True) if x == y)
    return AgreementReport(
        n=n,
        agree=agree,
        agreement=(agree / n) if n else None,
        kappa=_cohens_kappa(va, vb),
        calls_a=a.calls,
        calls_b=b.calls,
    )
