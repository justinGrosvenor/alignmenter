"""Durable built-ins: traceability mutations, strict claim judgments, and saved metrics."""

from __future__ import annotations

import json
import sqlite3

import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from alignmenter.cli import app
from alignmenter.evaluators.evidence import evidence_bundle
from alignmenter.evaluators.grounding import assess_grounding
from alignmenter.execution.evaluation import evaluate_saved, evaluation_summary
from alignmenter.schemas.evaluation import Criterion, EvaluationSpec, JudgeBudget, JudgeReply
from alignmenter.schemas.execution import content_digest
from alignmenter.storage.evaluations import EvaluationStore
from alignmenter.storage.runs import RunStore

from .test_durable_evaluations import Judge, captured, spec


def builtin(*evaluators, qualification="reviewed", **kwargs):
    return EvaluationSpec(id="evidence", revision="v1", qualification=qualification,
                          criteria=tuple(Criterion(id=name, revision="v1", evaluator=name, **kwargs)
                                         for name in evaluators))


def records(answer="Wait 60 seconds. [1]", *, context=None, question="How long should I wait?", sessions=("A",)):
    if context is None:
        context = {"excerpts": [{"id": "doc-1", "text": "Wait one minute, or 60 seconds."}]}
    return [r for session in sessions for r in (
        {"session_id": session, "role": "user", "text": question},
        {"session_id": session, "role": "assistant", "text": answer,
         "tags": ["wait", "overlap"], "persona_id": "atlas", "metadata": {"context": context}},
    )]


def judgment(request, **updates):
    payload = json.loads(request.prompt)
    passage_id, passage = next((k, v) for k, v in payload["supporting_sources"].items() if k.startswith("passage:"))
    verdict = {
        "claims": [{"text": payload["answer"]["text"], "status": "supported",
                    "evidence": [{"source_id": passage_id, "quote": passage}]}],
        "correctness": 10, "answers_question": True, "abstained": False,
        "abstention_appropriate": None, "dangerous": False, "danger_reason": None,
        "reasoning": "Fixture-only judgment, not a qualified product assessment.", "no_claims_reason": None,
        **updates,
    }
    return JudgeReply(text=json.dumps(verdict), finish_reason="stop")


@pytest.mark.parametrize("source,answer,expected", [
    ("-20°C", "20°C", "violated"),
    ("−20°C", "-20 ° C", "met"),
    ("70°C", "70°F", "violated"),
    ("20°C", "68°F", "met"),
    ("0°C", "273.15 K", "met"),
    ("1 g", "1000 mg", "met"),
    ("1000 mcg", "1 mg", "met"),
    ("1 L", "1000 mL", "met"),
    ("1 min", "60 seconds", "met"),
    ("1 m", "100 cm", "met"),
    ("5–10 minutes", "between 5 and 10 min", "met"),
    ("5 mg to 10 mg", "5–10 mg", "met"),
    ("5–10 minutes", "10 minutes", "violated"),
    ("5–10 minutes", "7 minutes", "violated"),
    ("at least 5 minutes", ">=300 s", "met"),
    ("at least 5 minutes", "5 minutes", "violated"),
    ("less than 5 minutes", "at most 5 minutes", "violated"),
    ("no more than 5 minutes", "up to 300 s", "met"),
    ("below 5°C", "5°C", "violated"),
    ("not less than 5 minutes", "minimum 300 s", "met"),
    ("above 5°C", "below 5°C", "violated"),
    ("3 minutes", "3 m", "violated"),
    ("1 gallon", "3.785 L", "violated"),
    ("1 month", "30 days", "violated"),
])
def test_grounding_preserves_sign_units_ranges_and_bounds(source, answer, expected):
    bundle = evidence_bundle(answer, {"excerpts": [source]}, [{"role": "user", "content": "Question", "source_id": "turn:0"}])
    assessment = assess_grounding(bundle)
    assert assessment.outcome == expected and len(assessment.quantities) == 1
    finding = assessment.quantities[0]
    assert finding.quote == answer
    if expected == "met":
        assert finding.evidence.quote == source and finding.evidence.source_id == "passage:1"
    else:
        assert finding.status == "unmatched" and finding.evidence is None


@pytest.mark.parametrize("answer", ["1/2 cup", "½ cup", "1 mg/kg", "1 mg per kg", "about 3 m",
                                     "1,000 mg", "1e3 mg", "5 minutes or more", "10–5 mg", "±5 mg",
                                     "roughly 3 m", "3 m²", "3 m^2"])
def test_unsupported_quantity_notation_needs_review(answer):
    bundle = evidence_bundle(answer, {"excerpts": [answer]}, [{"role": "user", "content": "Question", "source_id": "turn:0"}])
    assessment = assess_grounding(bundle)
    assert assessment.outcome == "needs_review"
    assert all(q.status == "ambiguous" for q in assessment.quantities)


@pytest.mark.parametrize("context", [{}, {"excerpts": None}, {"excerpts": "text"},
                                     {"excerpts": [{"title": "60 seconds"}]},
                                     {"excerpts": [None, "Wait 60 seconds."]},
                                     {"excerpts": ["", "Wait 60 seconds."]}])
def test_malformed_evidence_never_gets_compacted_or_scored(tmp_path, context):
    run_dir = captured(tmp_path, records=records(context=context))
    judge = Judge(judgment)
    evaluate_saved(run_dir, builtin("grounding", "faithfulness"), judge, budget=JudgeBudget(max_calls=2))
    report = evaluation_summary(run_dir, details=True)
    assert report["counts"] == {"missing_evidence": 2} and judge.calls == []
    assert all(m["value"] is None for m in report["metrics"].values())


def test_empty_retrieval_is_valid_and_distinct_from_missing(tmp_path):
    run_dir = captured(tmp_path, records=records("Use 1 g. [1]", context={"excerpts": []}))
    evaluate_saved(run_dir, builtin("grounding"))
    report = evaluation_summary(run_dir, details=True)
    assert report["decision"] == "fail" and report["counts"] == {"violated": 1}
    assert report["results"][0]["assessment"]["citations"][0]["source_id"] is None
    assert report["budget"]["reserved_calls"] == 0 and report["budget"]["limits"] is None


def test_empty_measurement_population_is_unavailable_not_one(tmp_path):
    run_dir = captured(tmp_path, records=records("1. Gather supplies.", context={"excerpts": []}))
    evaluate_saved(run_dir, builtin("grounding"))
    report = evaluation_summary(run_dir)
    assert report["counts"] == {"not_applicable": 1} and report["coverage"] is None
    assert report["decision"] == "inconclusive" and report["met_rate"] is None
    assert report["metrics"]["grounding.quantity_traceability"]["value"] is None
    assert report["metrics"]["grounding.citation_resolution"]["denominator"] == 0


def test_question_provenance_and_citation_resolution_are_saved(tmp_path):
    run_dir = captured(tmp_path, records=records("With your 3 L, follow the procedure [1,2].",
                                               question="I have 3 L. What now?"))
    evaluate_saved(run_dir, builtin("grounding"))
    report = evaluation_summary(run_dir, details=True)
    result = report["results"][0]["assessment"]
    assert result["quantities"][0]["status"] == "question"
    assert result["quantities"][0]["evidence"]["source_id"].startswith("turn:")
    assert [c["source_id"] for c in result["citations"]] == ["passage:1", None]
    assert report["metrics"]["grounding.citation_resolution"]["value"] == 0.5
    assert report["inputs"][0]["data"]["passages"][0]["provider_id"] == "doc-1"


def test_only_nearest_question_and_visible_passages_are_support(tmp_path):
    conversation = records("Remember 3 L.", question="I have 3 L.")
    conversation += [{"session_id": "A", "role": "user", "text": "Now the container holds 2 L."},
                     {"session_id": "A", "role": "assistant", "text": "Use 3 L.",
                      "metadata": {"context": {"excerpts": []}}}]
    run_dir = captured(tmp_path, records=conversation)
    evaluate_saved(run_dir, builtin("grounding"))
    report = evaluation_summary(run_dir, details=True)
    assert report["counts"] == {"met": 1, "violated": 1}
    assert report["results"][1]["assessment"]["quantities"][0]["status"] == "unmatched"


def test_offline_cli_and_later_explicit_judge_budget(tmp_path):
    run_dir = captured(tmp_path, records=records())
    path = tmp_path / "grounding.yaml"
    path.write_text(yaml.safe_dump(builtin("grounding").model_dump(mode="json")))
    cli = CliRunner()
    outcome = cli.invoke(app, ["evaluate", str(run_dir), "--spec", str(path)])
    assert outcome.exit_code == 0, outcome.output
    assert "0/unconfigured" in outcome.output
    store = EvaluationStore(run_dir)
    saved = store.path.read_bytes()
    judge = Judge(judgment)
    with pytest.raises(ValueError, match="explicit judge call budget"):
        evaluate_saved(run_dir, builtin("faithfulness"), judge, new_evaluation=True)
    assert store.path.read_bytes() == saved and judge.calls == []
    evaluate_saved(run_dir, builtin("faithfulness"), judge, new_evaluation=True, budget=JudgeBudget(max_calls=1))
    report = evaluation_summary(run_dir)
    assert report["budget"]["reserved_calls"] == 1 and report["decision"] == "pass"
    saved = store.path.read_bytes()
    assert cli.invoke(app, ["evaluation-status", str(run_dir), "--details"]).exit_code == 0
    assert store.path.read_bytes() == saved and len(judge.calls) == 1


def test_mixed_evaluators_share_budget_and_reports_use_saved_results(tmp_path):
    run_dir = captured(tmp_path, records=records(sessions=("A", "B")))
    observations = RunStore(run_dir).observations()
    judge = Judge(judgment)
    evaluation_id = evaluate_saved(run_dir, builtin("faithfulness", "grounding"), judge, budget=JudgeBudget(max_calls=1))
    store = EvaluationStore(run_dir)
    report = evaluation_summary(run_dir, details=True)
    assert report["counts"] == {"met": 3, "budget_blocked": 1} and report["coverage"] == 0.75
    assert len(judge.calls) == 1 and RunStore(run_dir).observations() == observations
    for group in (report, report["tags"]["overlap"], report["personas"]["atlas"], report["streams"]["primary"]):
        assert group["metrics"]["faithfulness.claim_support"]["denominator"] == 1
        assert group["metrics"]["grounding.quantity_traceability"]["denominator"] == 2
    before = store.path.read_bytes()
    assert evaluate_saved(run_dir, builtin("faithfulness", "grounding"), judge) == evaluation_id
    assert evaluation_summary(run_dir, details=True) == report
    assert store.path.read_bytes() == before and len(judge.calls) == 1


@pytest.mark.parametrize("updates", [
    {"correctness": "10"}, {"correctness": True}, {"correctness": 11}, {"correctness": 9.5},
    {"dangerous": "false"}, {"answers_question": "false"}, {"abstained": "false"},
    {"claims": []}, {"dangerous": True}, {"danger_reason": "Unexplained inconsistency"},
    {"abstained": True}, {"abstention_appropriate": False},
    {"claims": [{"text": "invented quote", "status": "unsupported", "evidence": []}]},
    {"claims": [{"text": "Wait 60 seconds.", "status": "supported", "evidence": []}]},
    {"claims": [{"text": "Wait 60 seconds.", "status": "supported", "evidence": [{"source_id": "answer", "quote": "Wait 60 seconds."}]}]},
    {"claims": [{"text": "Wait 60 seconds.", "status": "supported", "evidence": [{"source_id": "passage:1", "quote": "invented evidence"}]}]},
])
def test_invalid_faithfulness_never_becomes_a_score_or_repair_call(tmp_path, updates):
    run_dir = captured(tmp_path, records=records())
    judge = Judge(lambda request: judgment(request, **updates))
    evaluate_saved(run_dir, builtin("faithfulness"), judge, budget=JudgeBudget(max_calls=2))
    report = evaluation_summary(run_dir, details=True)
    assert report["counts"] == {"invalid": 1} and report["decision"] == "inconclusive"
    assert report["results"][0]["assessment"] is None and report["calls"][0]["reply"]["text"]
    assert all(m["value"] is None for m in report["metrics"].values())
    evaluate_saved(run_dir, builtin("faithfulness"), judge)
    assert len(judge.calls) == 1


@pytest.mark.parametrize("updates,status", [
    ({"dangerous": True, "danger_reason": "The fixture marks this action dangerous."}, "violated"),
    ({"correctness": 6}, "violated"),
    ({"answers_question": False}, "violated"),
    ({"abstained": True, "abstention_appropriate": False}, "violated"),
    ({"claims": [{"text": "Wait 60 seconds.", "status": "unsupported", "evidence": []}]}, "violated"),
    ({"claims": [], "no_claims_reason": "appropriate_abstention", "abstained": True,
      "abstention_appropriate": True, "answers_question": False}, "met"),
    ({"claims": [], "no_claims_reason": "nonfactual"}, "not_applicable"),
])
def test_faithfulness_separates_support_correctness_danger_and_abstention(tmp_path, updates, status):
    run_dir = captured(tmp_path, records=records())
    judge = Judge(lambda request: judgment(request, **updates))
    evaluate_saved(run_dir, builtin("faithfulness"), judge, budget=JudgeBudget(max_calls=1))
    report = evaluation_summary(run_dir)
    assert report["counts"] == {status: 1}
    metrics = report["metrics"]
    if updates.get("claims") == []:
        assert metrics["faithfulness.claim_support"]["value"] is None
    if updates.get("dangerous"):
        assert metrics["faithfulness.claim_support"]["value"] == 1
        assert metrics["faithfulness.dangerous_answers"]["value"] == 1 and report["decision"] == "fail"


def test_full_passages_and_product_rubric_reach_judge_without_truncation(tmp_path):
    source = "x" * 5000 + " Wait 60 seconds."
    run_dir = captured(tmp_path, records=records(context={"documents": [{"body": source}]}))
    judge = Judge(judgment)
    evaluate_saved(run_dir, builtin("faithfulness", rubric="Prioritize the user's available resources."),
                   judge, budget=JudgeBudget(max_calls=1))
    payload = json.loads(judge.calls[0].prompt)
    assert payload["supporting_sources"]["passage:1"] == source
    assert payload["criterion"]["rubric"].startswith("Prioritize")
    assert payload["context_completeness"] == "unknown"


def test_changed_threshold_is_explicit_and_draft_remains_inconclusive(tmp_path):
    run_dir = captured(tmp_path, records=records())
    judge = Judge(judgment)
    evaluate_saved(run_dir, builtin("faithfulness", qualification="draft"), judge, budget=JudgeBudget(max_calls=2))
    assert evaluation_summary(run_dir)["decision"] == "inconclusive"
    before = EvaluationStore(run_dir).path.read_bytes()
    with pytest.raises(ValueError, match="new_evaluation"):
        evaluate_saved(run_dir, builtin("faithfulness", min_correctness=9), judge)
    assert EvaluationStore(run_dir).path.read_bytes() == before and len(judge.calls) == 1


def test_saved_faithfulness_assessment_survives_progress_failure(tmp_path):
    run_dir = captured(tmp_path, records=records(sessions=("A", "B")))
    judge = Judge(judgment)

    def interrupted(result):
        raise RuntimeError("interrupted after commit")

    with pytest.raises(RuntimeError, match="after commit"):
        evaluate_saved(run_dir, builtin("faithfulness"), judge, budget=JudgeBudget(max_calls=2), progress=interrupted)
    store = EvaluationStore(run_dir)
    first = store.results(store.manifests()[0].id)[0]
    evaluate_saved(run_dir, builtin("faithfulness"), judge)
    assert store.results(first.evaluation_id)[0] == first and len(judge.calls) == 2
    assert evaluation_summary(run_dir)["decision"] == "pass"


def test_older_wire_inputs_still_verify_before_new_defaults_are_added(tmp_path):
    run_dir = captured(tmp_path)
    judge = Judge()
    evaluation_id = evaluate_saved(run_dir, spec(), judge, budget=JudgeBudget(max_calls=2))
    store = EvaluationStore(run_dir)
    with sqlite3.connect(store.path) as db:
        values = []
        for key, payload in db.execute("SELECT key,payload FROM evaluation_inputs ORDER BY rowid").fetchall():
            value = json.loads(payload)
            value.pop("evaluator")
            value.pop("data")
            values.append(value)
            db.execute("UPDATE evaluation_inputs SET payload=?,digest=? WHERE key=?", (json.dumps(value), content_digest(value), key))
        payload = json.loads(db.execute("SELECT payload FROM evaluation_manifests").fetchone()[0])
        payload["inputs_digest"] = content_digest(values)
        payload["engine_revision"] = "rubric-v1"
        payload["identity"] = content_digest({"legacy": "rubric-v1"})
        for criterion in payload["spec"]["criteria"]:
            criterion.pop("evaluator")
            criterion.pop("min_correctness")
        db.execute("UPDATE evaluation_manifests SET identity=?,payload=?,digest=?", (payload["identity"], json.dumps(payload), content_digest(payload)))
    assert evaluation_summary(run_dir, evaluation_id)["counts"] == {"met": 2}
    with pytest.raises(ValueError, match="new_evaluation"):
        evaluate_saved(run_dir, spec(), judge)
    new_id = evaluate_saved(run_dir, spec(), judge, new_evaluation=True)
    assert new_id != evaluation_id and len(judge.calls) == 2
    assert evaluation_summary(run_dir)["counts"] == {"met": 2}
    with sqlite3.connect(store.path) as db:
        db.execute("DELETE FROM evaluation_inputs WHERE rowid=(SELECT max(rowid) FROM evaluation_inputs)")
    with pytest.raises(ValueError, match="input digest mismatch"):
        evaluation_summary(run_dir)


@pytest.mark.parametrize("kwargs", [{"evaluator": "grounding", "rubric": "ignored"},
                                     {"evaluator": "faithfulness", "evidence_requirement": "conversation"},
                                     {"evaluator": "grounding", "allow_not_applicable": False},
                                     {"evaluator": "rubric"}, {"evaluator": "faithfulness", "min_correctness": True}])
def test_builtin_configuration_rejects_ignored_or_invalid_options(kwargs):
    with pytest.raises(ValidationError):
        Criterion(id="x", revision="v1", **kwargs)
