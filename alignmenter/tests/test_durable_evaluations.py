"""Durable rubric evaluation, shared budgets, strict verdicts, and pure reports."""

from __future__ import annotations

import json
import os
import selectors
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest
import yaml
from openai import OpenAI
from typer.testing import CliRunner

from alignmenter.cli import app
from alignmenter.execution.evaluation import evaluate_saved, evaluation_summary, plan_evaluation
from alignmenter.providers.base import ChatResponse
from alignmenter.providers.durable_judge import ChatCompletionJudge
from alignmenter.schemas.evaluation import (
    Criterion,
    EvaluationManifest,
    EvaluationSpec,
    JudgeBudget,
    JudgeContract,
    JudgeReply,
    JudgeRequest,
)
from alignmenter.schemas.execution import content_digest
from alignmenter.storage.evaluations import BudgetBlocked, EvaluationStore
from alignmenter.storage.runs import RunStore

from .test_durable_execution import Provider, make_runner


def spec(*, criteria=1, qualification="reviewed", evidence="conversation", allow_na=False, sample=0):
    return EvaluationSpec(id="behavior", revision="v1", qualification=qualification, sample=sample,
                          criteria=tuple(Criterion(id=f"criterion-{i}", revision="v1",
                                                    rubric="Address the user's practical question.",
                                                    evidence_requirement=evidence,
                                                    allow_not_applicable=allow_na)
                                         for i in range(criteria)))


def reply_for(request, *, outcome="met", cost=None):
    payload = json.loads(request.prompt)
    return JudgeReply(finish_reason="stop", actual_cost_micros=cost, text=json.dumps({
        "outcome": outcome, "rationale": "Fixture verdict grounded in the saved answer.",
        "evidence": [{"source_id": "answer", "quote": payload["answer"]["text"]}],
    }))


class Judge:
    def __init__(self, function=None, *, upper=None, revision="v1"):
        self.contract = JudgeContract(model="fixture:judge", configuration_digest=content_digest({"revision": revision}),
                                      max_cost_micros_per_call=upper)
        self.function = function or reply_for
        self.calls = []

    def evaluate(self, request):
        self.calls.append(request)
        return self.function(request)


def captured(tmp_path, *, records=None):
    return make_runner(tmp_path, scorers=[], records=records).capture()


def test_one_run_budget_shared_by_criteria_reports_and_resume(tmp_path):
    run_dir, judge, rubric = captured(tmp_path), Judge(), spec(criteria=2)
    evaluation_id = evaluate_saved(run_dir, rubric, judge, budget=JudgeBudget(max_calls=1))
    store = EvaluationStore(run_dir)
    assert len(judge.calls) == 1
    assert len(store.results(evaluation_id)) == 4
    report = evaluation_summary(run_dir, details=True)
    assert report["counts"] == {"met": 1, "budget_blocked": 3}
    assert report["coverage"] == 0.25 and report["decision"] == "inconclusive"
    assert report["budget"]["calls_with_unknown_actual_cost"] == 1
    assert report["budget"]["accounted_cost_micros"] is None
    saved = store.path.read_bytes()
    assert evaluate_saved(run_dir, rubric, judge) == evaluation_id
    assert evaluation_summary(run_dir, details=True) == report
    assert len(judge.calls) == 1 and store.path.read_bytes() == saved
    assert report["results"][0]["verdict"]["outcome"] == "met"
    assert report["calls"][0]["reply"]["text"] == reply_for(judge.calls[0]).text


def test_saved_verdict_survives_progress_failure_and_rebuilds_slices(tmp_path):
    records = [{"session_id": session, "turn_index": index, "role": role, "text": text,
                "tags": ["scenario:one", "scenario:overlap"], "persona_id": "atlas"}
               for session in ("A", "B") for index, role, text in
               [(0, "user", "question"), (1, "assistant", f"answer-{session}")]]
    run_dir, judge = captured(tmp_path, records=records), Judge()

    def interrupt(result):
        raise RuntimeError("after durable verdict")

    with pytest.raises(RuntimeError, match="durable"):
        evaluate_saved(run_dir, spec(), judge, budget=JudgeBudget(max_calls=2), progress=interrupt)
    store = EvaluationStore(run_dir)
    original = store.results(store.manifests()[0].id)[0]
    assert evaluation_summary(run_dir)["counts"] == {"met": 1, "pending": 1}
    evaluation_id = evaluate_saved(run_dir, spec(), judge)
    assert store.results(evaluation_id)[0] == original
    summary = evaluation_summary(run_dir)
    assert summary["decision"] == "pass" and len(judge.calls) == 2
    for _ in range(3):
        summary = evaluation_summary(run_dir)
        assert summary["tags"]["scenario:overlap"]["judged"] == 2
        assert summary["personas"]["atlas"]["judged"] == 2
    assert len(judge.calls) == 2


@pytest.mark.parametrize("raw", [
    "{}", "[]", "not JSON", '{"outcome": true}',
    '{"outcome":"met","rationale":"x","evidence":[],"score":NaN}',
    '{"outcome":"met","rationale":"x","evidence":[]}',
    '{"outcome":"met","rationale":"x","evidence":[],"outcome":"violated"}',
    '{"outcome":"met","rationale":"x","evidence":[{"source_id":"invented","quote":"x"}]}',
    '{"outcome":"met","rationale":"x","evidence":[{"source_id":"answer","quote":"invented"}]}',
    '{"outcome":"met","rationale":3,"evidence":[]}',
    '{"outcome":"met","rationale":"x","evidence":"not a list"}',
])
def test_invalid_judgments_are_saved_raw_without_becoming_successes(tmp_path, raw):
    run_dir = captured(tmp_path)
    judge = Judge(lambda request: JudgeReply(text=raw, finish_reason="stop"))
    evaluation_id = evaluate_saved(run_dir, spec(), judge, budget=JudgeBudget(max_calls=2))
    store = EvaluationStore(run_dir)
    assert {r.status for r in store.results(evaluation_id)} == {"invalid"}
    assert all(c.reply.text == raw for c in store.calls())
    report = evaluation_summary(run_dir)
    assert report["met_rate"] is None and report["coverage"] == 0 and report["decision"] == "inconclusive"
    evaluate_saved(run_dir, spec(), judge)
    assert len(judge.calls) == 2


@pytest.mark.parametrize("finish", ["length", "refusal", "other"])
def test_truncated_or_refused_valid_json_is_not_a_valid_verdict(tmp_path, finish):
    run_dir = captured(tmp_path)
    judge = Judge(lambda request: reply_for(request).model_copy(update={"finish_reason": finish}))
    evaluate_saved(run_dir, spec(), judge, budget=JudgeBudget(max_calls=2))
    assert evaluation_summary(run_dir)["counts"] == {"invalid": 2}


def test_not_applicable_is_explicit_and_empty_coverage_is_unavailable(tmp_path):
    run_dir = captured(tmp_path)
    judge = Judge(lambda request: JudgeReply(text=json.dumps({"outcome": "not_applicable",
                                                            "rationale": "Not applicable under the rubric.",
                                                            "evidence": []}), finish_reason="stop"))
    evaluate_saved(run_dir, spec(allow_na=True), judge, budget=JudgeBudget(max_calls=2))
    report = evaluation_summary(run_dir)
    assert report["counts"] == {"not_applicable": 2}
    assert report["applicable"] == 0 and report["coverage"] is None and report["met_rate"] is None
    assert report["decision"] == "inconclusive"
    evaluate_saved(run_dir, spec(), judge, new_evaluation=True)
    assert evaluation_summary(run_dir)["counts"] == {"budget_blocked": 2}
    assert len(judge.calls) == 2


@pytest.mark.parametrize("change", ["judge", "rubric", "sample", "budget"])
def test_incompatible_evaluation_does_not_mutate_or_dispatch(tmp_path, change):
    run_dir, judge, rubric = captured(tmp_path), Judge(), spec()
    evaluate_saved(run_dir, rubric, judge, budget=JudgeBudget(max_calls=4))
    if change == "judge":
        judge.contract = Judge(revision="v2").contract
    if change == "rubric":
        rubric = spec(criteria=2)
    if change == "sample":
        rubric = spec(sample=1)
    options = {"budget": JudgeBudget(max_calls=9)} if change == "budget" else {}
    before = RunStore(run_dir).path.read_bytes()
    with pytest.raises(ValueError, match="changed|differs"):
        evaluate_saved(run_dir, rubric, judge, **options)
    assert RunStore(run_dir).path.read_bytes() == before and len(judge.calls) == 2


def test_explicit_new_evaluation_uses_same_budget_and_reuses_unchanged_requests(tmp_path):
    run_dir, judge = captured(tmp_path), Judge()
    original = evaluate_saved(run_dir, spec(qualification="draft"), judge, budget=JudgeBudget(max_calls=3))
    report = evaluation_summary(run_dir)
    assert report["decision"] == "inconclusive"
    assert report["criteria"]["criterion-0"]["decision"] == "inconclusive"
    revised = evaluate_saved(run_dir, spec(), judge, new_evaluation=True)
    assert revised != original and len(judge.calls) == 2
    assert evaluation_summary(run_dir)["decision"] == "pass"
    repeated = evaluate_saved(run_dir, spec(sample=1), judge, new_evaluation=True)
    assert repeated != revised and len(judge.calls) == 3
    assert evaluation_summary(run_dir)["counts"] == {"met": 1, "budget_blocked": 1}
    assert evaluation_summary(run_dir, original)["decision"] == "inconclusive"


def test_failed_capture_remains_in_denominator_without_using_old_answer(tmp_path):
    runner = make_runner(tmp_path, Provider([ChatResponse(text="new-A"), TimeoutError()]), scorers=[])
    with pytest.raises(TimeoutError):
        runner.capture()
    judge = Judge()
    evaluate_saved(runner.run_dir, spec(), judge, budget=JudgeBudget(max_calls=2))
    report = evaluation_summary(runner.run_dir, details=True)
    assert report["counts"] == {"met": 1, "missing_capture": 1} and report["coverage"] == 0.5
    assert len(judge.calls) == 1 and "old-B" not in judge.calls[0].prompt
    missing = next(i for i in report["inputs"] if i["unavailable"] == "missing_capture")
    assert missing["observation_id"] is None and missing["request"] is None


@pytest.mark.parametrize("requirement", ["context", "complete_context"])
def test_missing_required_evidence_never_calls_judge(tmp_path, requirement):
    run_dir, judge = captured(tmp_path), Judge()
    evaluate_saved(run_dir, spec(evidence=requirement), judge, budget=JudgeBudget(max_calls=2))
    assert judge.calls == [] and evaluation_summary(run_dir)["counts"] == {"missing_evidence": 2}


def test_known_actual_cost_releases_unused_reservation_but_unknown_cost_does_not(tmp_path):
    run_dir, judge = captured(tmp_path), Judge(lambda request: reply_for(request, cost=20), upper=60)
    evaluate_saved(run_dir, spec(), judge, budget=JudgeBudget(max_calls=5, max_cost_micros=80))
    report = evaluation_summary(run_dir)
    assert len(judge.calls) == 2 and report["budget"]["accounted_cost_micros"] == 40
    assert report["budget"]["calls_with_unknown_actual_cost"] == 0
    unknown = Judge(upper=60, revision="unknown-price")
    evaluate_saved(run_dir, spec(sample=1), unknown, new_evaluation=True)
    assert unknown.calls == [] and evaluation_summary(run_dir)["counts"] == {"budget_blocked": 2}


def test_unknown_judge_outcome_keeps_cost_reservation_and_is_never_retried(tmp_path):
    def timeout(request):
        raise TimeoutError("sensitive message must not enter records")

    run_dir, judge = captured(tmp_path), Judge(timeout, upper=60)
    evaluate_saved(run_dir, spec(), judge, budget=JudgeBudget(max_calls=5, max_cost_micros=80))
    report = evaluation_summary(run_dir, details=True)
    assert report["counts"] == {"unknown_outcome": 1, "budget_blocked": 1}
    assert report["budget"]["accounted_cost_micros"] == 60
    assert report["budget"]["calls_with_unknown_actual_cost"] == 1
    assert "sensitive message" not in json.dumps(report)
    evaluate_saved(run_dir, spec(), judge)
    assert len(judge.calls) == 1


def test_exceeded_adapter_cost_bound_is_recorded_and_blocks_more_dispatch(tmp_path):
    run_dir, judge = captured(tmp_path), Judge(lambda request: reply_for(request, cost=70), upper=60)
    evaluate_saved(run_dir, spec(), judge, budget=JudgeBudget(max_calls=5, max_cost_micros=100))
    report = evaluation_summary(run_dir)
    assert report["counts"] == {"invalid": 1, "budget_blocked": 1}
    assert report["budget"]["accounted_cost_micros"] == 70
    assert report["budget"]["cost_bound_violations"] == 1 and len(judge.calls) == 1


def test_monetary_cap_without_upper_bound_rolls_back_initialization(tmp_path):
    run_dir, judge = captured(tmp_path), Judge()
    before = RunStore(run_dir).path.read_bytes()
    with pytest.raises(ValueError, match="upper bound"):
        evaluate_saved(run_dir, spec(), judge, budget=JudgeBudget(max_calls=1, max_cost_micros=0))
    assert judge.calls == [] and RunStore(run_dir).path.read_bytes() == before


def test_atomic_reservation_allows_only_one_contender_to_take_last_call(tmp_path):
    run_dir, rubric, judge = captured(tmp_path), spec(), Judge()
    store = EvaluationStore(run_dir)
    inputs = plan_evaluation(store, rubric)
    store.initialize(EvaluationManifest(run_id=store.manifest().id, identity="1" * 64,
                                       spec=rubric, judge=judge.contract,
                                       inputs_digest=content_digest([i.model_dump(mode="json") for i in inputs]),
                                       package_version="fixture"), inputs, JudgeBudget(max_calls=1))

    def reserve(number):
        try:
            return store.reserve(JudgeRequest(system="fixture", prompt=str(number)), judge.contract)[1]
        except BudgetBlocked:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve, [1, 2])) == [False, True]
    assert len(store.calls()) == 1
    store.abandon_calls()
    with pytest.raises(BudgetBlocked):
        store.reserve(JudgeRequest(system="fixture", prompt="third"), judge.contract)


def test_http_judge_disables_sdk_retries_and_never_falls_back(tmp_path):
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(429, json={"error": {"message": "fixture rate limit", "type": "rate_limit_error"}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenAI(api_key="fixture-unused", base_url="http://fixture.invalid/v1", http_client=http_client, max_retries=7)
        judge = ChatCompletionJudge(client=client, model="fixture-model", revision="fixture-v1", timeout=1)
        run_dir = captured(tmp_path)
        evaluate_saved(run_dir, spec(), judge, budget=JudgeBudget(max_calls=1))
    assert len(requests) == 1 and requests[0]["response_format"] == {"type": "json_object"}
    assert requests[0]["max_completion_tokens"] == 2048
    assert evaluation_summary(run_dir)["counts"] == {"unknown_outcome": 1, "budget_blocked": 1}


def test_read_only_cli_details_include_evidence_without_loading_judge(tmp_path):
    run_dir = captured(tmp_path)
    evaluate_saved(run_dir, spec(), Judge(lambda request: reply_for(request, outcome="violated")),
                   budget=JudgeBudget(max_calls=2))
    before = RunStore(run_dir).path.read_bytes()
    result = CliRunner().invoke(app, ["evaluation-status", str(run_dir), "--details"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["decision"] == "fail" and report["results"][0]["verdict"]["evidence"]
    assert RunStore(run_dir).path.read_bytes() == before
    with sqlite3.connect(RunStore(run_dir).path) as db:
        db.execute("UPDATE evaluation_results SET digest=?", ("0" * 64,))
    with pytest.raises(ValueError, match="digest"):
        evaluation_summary(run_dir)


@pytest.mark.parametrize("pause", ["before_dispatch", "after_accept", "after_raw", "after_result"])
@pytest.mark.parametrize("evaluator", ["rubric", "faithfulness"])
def test_process_kill_preserves_budget_and_never_repeats_completed_judge_work(tmp_path, pause, evaluator):
    records = [{"session_id": name, "role": role, "text": text,
                "metadata": {"context": {"excerpts": ["Wait 60 seconds."]}}}
               for name in ("A", "B") for role, text in [("user", "How long?"), ("assistant", f"Wait 60 seconds, {name}.")]]
    run_dir = captured(tmp_path, records=records)
    rubric = spec() if evaluator == "rubric" else EvaluationSpec(
        id="faithfulness", revision="v1", qualification="reviewed",
        criteria=(Criterion(id="faithfulness", revision="v1", evaluator="faithfulness"),))
    spec_path = tmp_path / "rubric.yaml"
    spec_path.write_text(yaml.safe_dump(rubric.model_dump(mode="json")))
    data = Path(__file__).parent / "data"
    env = {**os.environ, "ALIGNMENTER_TEST_JUDGE_ROOT": str(tmp_path),
           "ALIGNMENTER_TEST_JUDGE_PAUSE": pause,
           "PYTHONPATH": str(data) + os.pathsep + os.environ.get("PYTHONPATH", "")}
    with (tmp_path / "stderr").open("w") as err:
        process = subprocess.Popen([sys.executable, str(data / "durable_evaluation_worker.py"),
                                    str(run_dir), str(spec_path)],
                                   env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            assert selector.select(20), "Worker barrier timeout"
            assert os.read(process.stdout.fileno(), 4096).strip() == b"READY", (tmp_path / "stderr").read_text()
            store = EvaluationStore(run_dir)
            first = store.calls()[0]
            assert store.budget_summary()["reserved_calls"] == 1
            cli = [sys.executable, "-c", "from alignmenter.cli import app; app()", "evaluate", str(run_dir),
                   "--spec", str(spec_path), "--judge-factory", "durable_evaluation_judge:make_judge"]
            busy = subprocess.run(cli, env=env, capture_output=True, text=True, timeout=20)
            assert busy.returncode != 0 and "active coordinator" in busy.stderr
            process.kill()
            assert process.wait(timeout=10) != 0
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            selector.close()
            process.stdin.close()
            process.stdout.close()
    env.pop("ALIGNMENTER_TEST_JUDGE_PAUSE")
    resumed = subprocess.run(cli, env=env, capture_output=True, text=True, timeout=20)
    saved_reply = pause in {"after_raw", "after_result"}
    assert resumed.returncode == (0 if saved_reply else 3), resumed.stderr
    summary = evaluation_summary(run_dir)
    assert summary["counts"] == ({"met": 2} if saved_reply else {"unknown_outcome": 1, "met": 1})
    assert summary["budget"]["reserved_calls"] == 2
    accepted = (tmp_path / "accepted.jsonl").read_text().splitlines()
    assert len(accepted) == (1 if pause == "before_dispatch" else 2)
    if saved_reply:
        assert store.calls()[0] == first
    else:
        assert store.calls()[0].status == "unknown_outcome"
        assert store.calls()[0].exception_type == "AbandonedCoordinator"
    before = store.path.read_bytes()
    again = subprocess.run(cli, env=env, capture_output=True, text=True, timeout=20)
    assert again.returncode == resumed.returncode
    assert store.path.read_bytes() == before
    assert (tmp_path / "accepted.jsonl").read_text().splitlines() == accepted


def test_no_assistant_cases_cannot_report_perfect_quality(tmp_path):
    run_dir = captured(tmp_path, records=[{"session_id": "A", "role": "user", "text": "question"}])
    judge = Judge()
    evaluate_saved(run_dir, spec(), judge, budget=JudgeBudget(max_calls=0))
    summary = evaluation_summary(run_dir)
    assert summary["planned"] == 0 and summary["decision"] == "inconclusive"
    assert summary["met_rate"] is None and summary["coverage"] is None and judge.calls == []


def test_changed_comparison_and_primary_share_one_budget(tmp_path):
    from .test_durable_execution import Scorer

    runner = make_runner(tmp_path, compare_scorers=[Scorer()])
    runner.config.compare_model = "fixture:comparison"
    run_dir = runner.capture()
    rubric = spec().model_copy(update={"streams": ("primary", "compare")})
    judge = Judge()
    evaluate_saved(run_dir, rubric, judge, budget=JudgeBudget(max_calls=1))
    report = evaluation_summary(run_dir)
    # Identical answer/context requests can share one saved judge response across streams.
    assert report["planned"] == 4 and report["counts"] == {"met": 2, "budget_blocked": 2}
    assert set(report["streams"]) == {"primary", "compare"} and len(judge.calls) == 1


def test_call_limits_and_single_dispatch_contract_are_strict():
    from pydantic import ValidationError

    for invalid in (True, "1", -1, 1.5):
        with pytest.raises(ValidationError):
            JudgeBudget(max_calls=invalid)
    with pytest.raises(ValidationError):
        JudgeContract(model="fixture", configuration_digest="0" * 64, max_dispatches_per_request=True)


def test_present_context_does_not_imply_complete_evidence(tmp_path):
    records = [{"session_id": "A", "role": "assistant", "text": "answer",
                "metadata": {"context": {"excerpts": ["visible source"]}}}]
    run_dir, judge = captured(tmp_path, records=records), Judge()
    evaluate_saved(run_dir, spec(evidence="complete_context"), judge, budget=JudgeBudget(max_calls=1))
    report = evaluation_summary(run_dir, details=True)
    assert judge.calls == [] and report["counts"] == {"missing_evidence": 1}
    assert "complete_context" in report["results"][0]["reason"]


def test_late_judge_reply_cannot_replace_an_abandoned_request(tmp_path):
    run_dir, rubric, judge = captured(tmp_path), spec(), Judge()
    evaluate_saved(run_dir, rubric, judge, budget=JudgeBudget(max_calls=3))
    store = EvaluationStore(run_dir)
    request = JudgeRequest(system="fixture", prompt="late")
    call, fresh = store.reserve(request, judge.contract)
    assert fresh
    store.abandon_calls()
    with pytest.raises(ValueError, match="terminal"):
        store.finish_call(call.id, reply=JudgeReply(text="late", finish_reason="stop"))
    assert store.calls()[-1].status == "unknown_outcome"
    assert store.budget_summary()["reserved_calls"] == 3


def test_http_judge_success_preserves_raw_reply_and_usage(tmp_path):
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        answer = json.loads(body["messages"][-1]["content"])["answer"]["text"]
        text = json.dumps({"outcome": "met", "rationale": "Fixture evidence.",
                           "evidence": [{"source_id": "answer", "quote": answer}]})
        return httpx.Response(200, json={
            "id": "fixture", "object": "chat.completion", "created": 0, "model": "fixture-model",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        })

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenAI(api_key="fixture-unused", base_url="http://fixture.invalid/v1", http_client=http_client)
        judge = ChatCompletionJudge(client=client, model="fixture-model", revision="fixture-v1")
        run_dir = captured(tmp_path)
        evaluate_saved(run_dir, spec(), judge, budget=JudgeBudget(max_calls=2))
    report = evaluation_summary(run_dir, details=True)
    assert report["decision"] == "pass" and len(requests) == 2
    assert report["calls"][0]["reply"]["usage"]["total_tokens"] == 30
    assert report["budget"]["calls_with_unknown_actual_cost"] == 2


def test_evaluate_cli_returns_failure_exit_code_for_a_saved_violation(tmp_path, monkeypatch):
    run_dir = captured(tmp_path)
    rubric_path = tmp_path / "rubric.yaml"
    rubric_path.write_text(yaml.safe_dump(spec().model_dump(mode="json")))
    monkeypatch.syspath_prepend(str(Path(__file__).parent / "data"))
    monkeypatch.setenv("ALIGNMENTER_TEST_JUDGE_ROOT", str(tmp_path))
    monkeypatch.setenv("ALIGNMENTER_TEST_JUDGE_OUTCOME", "violated")
    result = CliRunner().invoke(app, ["evaluate", str(run_dir), "--spec", str(rubric_path),
                                      "--judge-factory", "durable_evaluation_judge:make_judge",
                                      "--max-judge-calls", "2"])
    assert result.exit_code == 2, result.output
    assert "Decision: fail" in result.output
    assert evaluation_summary(run_dir)["counts"] == {"violated": 2}
