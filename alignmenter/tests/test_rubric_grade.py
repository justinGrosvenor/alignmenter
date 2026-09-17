"""Tests for decomposed rubric grading (rubric_grade + the CLI)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

import alignmenter.rubric_grade_cli as cli_mod
from alignmenter.cli import app
from alignmenter.rubric_grade import (
    Rubric,
    build_criterion_prompt,
    extract_cases,
    grade_dataset,
    measure_agreement,
    parse_criterion_verdict,
    score_case,
)

runner = CliRunner()


class FakeJudge:
    """Judge stub: decide(prompt_json) -> verdict dict. Counts calls, no network."""

    def __init__(self, decide):
        self._decide = decide
        self.calls = 0

    def evaluate(self, prompt: str) -> dict:
        self.calls += 1
        return {"notes": json.dumps(self._decide(json.loads(prompt))), "score": 0.0}


def _met_if(criteria_met):
    """A decider that marks a criterion met iff its text is in criteria_met."""
    return lambda p: {"met": p["criterion"] in criteria_met, "confidence": 0.9, "evidence": "x"}


def _rec(sid, ti, role, text, rubrics=None):
    r = {
        "session_id": sid,
        "turn_index": ti,
        "role": role,
        "text": text,
        "tags": [],
        "persona_id": "reference",
    }
    if rubrics is not None:
        r["metadata"] = {"rubrics": rubrics}
    return r


def _case(sid, question, response, rubrics):
    return [_rec(sid, 1, "user", question, rubrics=rubrics), _rec(sid, 2, "assistant", response)]


R_EMERG = {"criterion": "Advises emergency care", "points": 10}
R_DIAG = {"criterion": "Gives a diagnosis", "points": -5}  # negative = should NOT appear


# --- Rubric.from_raw -------------------------------------------------------


def test_rubric_from_raw_valid_and_defaults():
    r = Rubric.from_raw({"criterion": "x", "points": 3, "tags": ["a", 1]})
    assert r == Rubric("x", 3.0, ("a",))
    assert Rubric.from_raw({"criterion": "y"}).points == 1.0  # default
    assert Rubric.from_raw({"criterion": "z", "points": "bad"}).points == 1.0  # tolerant


def test_rubric_from_raw_rejects_blank():
    assert Rubric.from_raw({"points": 1}) is None
    assert Rubric.from_raw({"criterion": "  "}) is None


# --- extract_cases ---------------------------------------------------------


def test_extract_cases_pulls_rubrics_and_response():
    recs = _case("s1", "chest pain?", "Call 911 now.", [R_EMERG, R_DIAG])
    cases = extract_cases(recs)
    assert len(cases) == 1
    c = cases[0]
    assert c.case_id == "s1"
    assert c.question == "chest pain?"
    assert c.response == "Call 911 now."
    assert [r.criterion for r in c.rubrics] == ["Advises emergency care", "Gives a diagnosis"]


def test_extract_cases_skips_without_rubrics_or_response():
    no_rubrics = [_rec("s1", 1, "user", "hi"), _rec("s1", 2, "assistant", "hello")]
    no_response = [_rec("s2", 1, "user", "hi", rubrics=[R_EMERG])]
    assert extract_cases(no_rubrics + no_response) == []


def test_extract_cases_multiturn_uses_last_assistant():
    recs = [
        _rec("s1", 1, "user", "q1"),
        _rec("s1", 2, "assistant", "a1"),
        _rec("s1", 3, "user", "q2", rubrics=[R_EMERG]),
        _rec("s1", 4, "assistant", "final answer"),
    ]
    cases = extract_cases(recs)
    assert cases[0].response == "final answer"
    assert cases[0].question == "q2"


# --- prompt + verdict parsing ----------------------------------------------


def test_build_prompt_is_valid_json_with_criterion_and_reply():
    p = json.loads(
        build_criterion_prompt(
            "Call 911.", Rubric("Advises emergency care"), question="chest pain?"
        )
    )
    assert p["criterion"] == "Advises emergency care"
    assert p["assistant_reply"] == "Call 911."
    assert p["user_question"] == "chest pain?"


def test_parse_verdict_variants():
    r = Rubric("c", 10)
    assert (
        parse_criterion_verdict('{"met": true, "confidence": 0.8, "evidence": "q"}', r).met is True
    )
    # fenced
    assert parse_criterion_verdict('```json\n{"met": false}\n```', r).met is False
    # prose-wrapped + non-bool met coercion
    assert parse_criterion_verdict('Sure: {"met": "yes"}', r).met is True
    # confidence clamp + evidence truncation
    v = parse_criterion_verdict(
        json.dumps({"met": True, "confidence": 5, "evidence": "e" * 500}), r
    )
    assert v.confidence == 1.0 and len(v.evidence) == 200
    # unparseable → invalid, not graded
    bad = parse_criterion_verdict("not json at all", r)
    assert bad.met is None and bad.status == "invalid"


# --- scoring ---------------------------------------------------------------


def test_score_case_healthbench_style():
    def v(pts, met):
        return parse_criterion_verdict(json.dumps({"met": met, "evidence": "x"}), Rubric("c", pts))

    assert score_case([v(10, True), v(5, True)]) == 1.0  # all positive met
    assert score_case([v(10, False), v(5, False)]) == 0.0  # none met
    # negative-point criterion met = penalty: awarded 10 + (-5) = 5 over max_positive 10 → 0.5
    assert score_case([v(10, True), v(-5, True)]) == 0.5
    assert score_case([]) is None  # nothing graded
    # only negative rubrics → no positive denominator → None
    assert score_case([v(-5, False)]) is None


def test_score_case_ignores_ungraded():
    graded = parse_criterion_verdict(json.dumps({"met": True, "evidence": "x"}), Rubric("c", 10))
    ungraded = parse_criterion_verdict("garbage", Rubric("d", 10))  # met=None
    assert score_case([graded, ungraded]) == 1.0  # ungraded excluded from denominator


# --- grade_dataset ---------------------------------------------------------


def test_grade_dataset_scores_and_counts_calls():
    recs = _case("s1", "chest pain?", "Call 911.", [R_EMERG, R_DIAG])
    judge = FakeJudge(_met_if({"Advises emergency care"}))  # emergency met, diagnosis not
    report = grade_dataset(recs, judge)
    assert report.calls == 2
    assert report.cases[0].score == 1.0  # +10 met, -5 not met → 10/10
    assert report.mean_score == 1.0


def test_grade_dataset_budget_blocks_remaining():
    recs = _case("s1", "q", "r", [R_EMERG, R_DIAG, {"criterion": "Third", "points": 1}])
    judge = FakeJudge(_met_if(set()))
    report = grade_dataset(recs, judge, max_calls=1)
    assert report.calls == 1
    assert report.budget_blocked == 2
    statuses = [v.status for v in report.cases[0].verdicts]
    assert statuses == ["graded", "budget_blocked", "budget_blocked"]


def test_grade_dataset_counts_invalid():
    recs = _case("s1", "q", "r", [R_EMERG])

    class BadJudge:
        def evaluate(self, prompt):
            return {"notes": "totally not json"}

    report = grade_dataset(recs, BadJudge())
    assert report.invalid == 1
    assert report.cases[0].score is None  # nothing graded


# --- agreement -------------------------------------------------------------


def test_measure_agreement_perfect_and_kappa():
    recs = _case("s1", "q", "r", [R_EMERG, R_DIAG])
    decider = _met_if({"Advises emergency care"})
    a = measure_agreement(recs, FakeJudge(decider), FakeJudge(decider))
    assert a.n == 2 and a.agree == 2 and a.agreement == 1.0
    assert a.kappa == 1.0
    assert a.calls_a == 2 and a.calls_b == 2


def test_measure_agreement_partial():
    # 4 criteria; judges differ on exactly one → 3/4 agreement
    rubrics = [{"criterion": f"c{i}", "points": 1} for i in range(4)]
    recs = _case("s1", "q", "r", rubrics)
    a_judge = FakeJudge(_met_if({"c0", "c1"}))
    b_judge = FakeJudge(_met_if({"c0", "c1", "c2"}))  # differs on c2
    a = measure_agreement(recs, a_judge, b_judge)
    assert a.n == 4 and a.agree == 3
    assert abs(a.agreement - 0.75) < 1e-9


# --- CLI -------------------------------------------------------------------


def test_cli_rubric_grade(tmp_path, monkeypatch):
    ds = tmp_path / "caps.jsonl"
    ds.write_text(
        "\n".join(json.dumps(r) for r in _case("s1", "chest pain?", "Call 911.", [R_EMERG, R_DIAG]))
        + "\n"
    )
    monkeypatch.setattr(
        cli_mod,
        "_make_gateway_judge",
        lambda model, base_url: FakeJudge(_met_if({"Advises emergency care"})),
    )
    out = tmp_path / "report.json"
    res = runner.invoke(
        app, ["rubric-grade", str(ds), "--judge", "anthropic/claude-haiku-4.5", "--out", str(out)]
    )
    assert res.exit_code == 0, res.output
    assert "graded 1/1 cases" in res.output
    payload = json.loads(out.read_text())
    assert payload["mode"] == "grade" and payload["mean_score"] == 1.0


def test_cli_rubric_grade_agreement(tmp_path, monkeypatch):
    ds = tmp_path / "caps.jsonl"
    ds.write_text("\n".join(json.dumps(r) for r in _case("s1", "q", "r", [R_EMERG, R_DIAG])) + "\n")
    decider = _met_if({"Advises emergency care"})
    monkeypatch.setattr(cli_mod, "_make_gateway_judge", lambda model, base_url: FakeJudge(decider))
    res = runner.invoke(
        app,
        ["rubric-grade", str(ds), "--judge", "cheap/model", "--compare-judge", "strong/model"],
    )
    assert res.exit_code == 0, res.output
    assert "agreement:" in res.output and "Cohen" in res.output
    # the JSON body (after the summary line) parses and reports agreement mode
    body = json.loads(res.output[res.output.index("{") :])
    assert body["mode"] == "agreement" and body["n"] == 2 and body["agree"] == 2


# --- hardening (review findings) -------------------------------------------


def test_extract_cases_tolerates_bad_turn_index():
    # non-int / None turn_index must not crash the sort
    recs = [
        {
            "session_id": "s1",
            "turn_index": None,
            "role": "user",
            "text": "q",
            "metadata": {"rubrics": [R_EMERG]},
        },
        {"session_id": "s1", "turn_index": "2", "role": "assistant", "text": "Call 911."},
    ]
    cases = extract_cases(recs)
    assert len(cases) == 1 and cases[0].response == "Call 911."


def test_extract_cases_falls_back_to_last_nonempty_assistant():
    recs = [
        _rec("s1", 1, "user", "q", rubrics=[R_EMERG]),
        _rec("s1", 2, "assistant", "real answer"),
        _rec("s1", 3, "assistant", "   "),  # trailing blank must not discard the case
    ]
    cases = extract_cases(recs)
    assert len(cases) == 1 and cases[0].response == "real answer"


def test_null_or_nonscalar_met_is_invalid():
    r = Rubric("c", 10)
    for raw in ('{"met": null}', '{"met": []}', '{"met": {}}'):
        v = parse_criterion_verdict(raw, r)
        assert v.status == "invalid" and v.met is None


def test_score_case_clamps_below_zero():
    def v(pts, met):
        return parse_criterion_verdict(json.dumps({"met": met, "evidence": "x"}), Rubric("c", pts))

    # +10 not met, -5 (penalty) met → awarded -5 over max_positive 10 → clamped to 0.0
    assert score_case([v(10, False), v(-5, True)]) == 0.0


def test_kappa_degenerate_constant_raters():
    rubrics = [{"criterion": f"c{i}", "points": 1} for i in range(3)]
    recs = _case("s1", "q", "r", rubrics)
    all_true = _met_if({"c0", "c1", "c2"})
    a = measure_agreement(recs, FakeJudge(all_true), FakeJudge(all_true))
    assert a.agreement == 1.0 and a.kappa == 1.0  # pe>=1 degenerate branch → 1.0
