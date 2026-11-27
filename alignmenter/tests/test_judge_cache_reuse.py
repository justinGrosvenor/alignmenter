"""Cross-run reuse preserves raw failures and charges only fresh dispatches."""

import json
import sqlite3

import pytest

from alignmenter.execution.evaluation import evaluate_saved, evaluation_summary
from alignmenter.execution.leases import RunBusyError, coordinator_lease
from alignmenter.schemas.evaluation import JudgeBudget, JudgeRequest
from alignmenter.storage.evaluations import EvaluationStore

from .test_durable_evaluations import Judge, captured, reply_for, spec


def capture(root, name):
    path = root / name
    path.mkdir()
    return captured(path)


def evaluated(root, *, function=None, upper=10):
    source = capture(root, "source")
    judge = Judge(function, upper=upper)
    evaluate_saved(source, spec(), judge, budget=JudgeBudget(max_calls=3, max_cost_micros=30))
    return source, judge


def test_exact_reuse_is_free_revalidated_and_provenance_retained(tmp_path):
    source, original = evaluated(tmp_path, function=lambda r: reply_for(r, outcome="violated", cost=4))
    destination, judge = capture(tmp_path, "destination"), Judge(upper=10)
    before = EvaluationStore(source).path.read_bytes()
    options = dict(budget=JudgeBudget(max_calls=0, max_cost_micros=0), judge_cache_sources=(source,))
    evaluation = evaluate_saved(destination, spec(), judge, **options)
    store = EvaluationStore(destination)
    assert len(original.calls) == 2 and judge.calls == []
    assert evaluation_summary(destination)["counts"] == {"violated": 2}
    assert store.budget_summary()["reserved_calls"] == 0
    assert store.budget_summary()["imported_cache_calls"] == 2
    assert store.budget_summary()["known_actual_cost_micros"] == 0
    assert store.budget_summary()["accounted_cost_micros"] == 0
    assert store.cache_imports()[0].source_budget.max_calls == 3
    for reused, original_call in zip(store.calls(), EvaluationStore(source).calls(), strict=True):
        assert reused.id != original_call.id
        assert reused.reused_from.source_call_id == original_call.id
        assert reused.request == original_call.request and reused.reply == original_call.reply
    saved = store.path.read_bytes()
    assert evaluate_saved(destination, spec(), judge, **options) == evaluation
    assert store.path.read_bytes() == saved
    assert EvaluationStore(source).path.read_bytes() == before


@pytest.mark.parametrize("failure", ["invalid_quote", "unknown", "invalid_transport", "cost_bound"])
def test_failures_are_imported_without_retry_or_passing_invalid_reply(tmp_path, failure):
    def response(request):
        if failure == "unknown":
            raise TimeoutError()
        if failure == "invalid_transport":
            return {"text": 12}
        if failure == "cost_bound":
            return reply_for(request, cost=11)
        reply = reply_for(request)
        value = json.loads(reply.text)
        value["evidence"][0]["quote"] = "This quote is absent."
        return reply.model_copy(update={"text": json.dumps(value)})

    source, _ = evaluated(tmp_path, function=response)
    destination, judge = capture(tmp_path, "destination"), Judge(upper=10)
    evaluate_saved(destination, spec(), judge, budget=JudgeBudget(max_calls=0), judge_cache_sources=(source,))
    expected = "unknown_outcome" if failure == "unknown" else "invalid"
    # A cost-bound failure deliberately blocks further source dispatch too.
    count = 1 if failure == "cost_bound" else 2
    report = evaluation_summary(destination)
    assert report["counts"][expected] == count
    assert judge.calls == [] and report["budget"]["reserved_calls"] == 0
    assert all(c.reused_from is not None for c in EvaluationStore(destination).calls())


@pytest.mark.parametrize("change", ["rubric", "sample", "judge", "answer"])
def test_changed_request_or_contract_misses_and_charges_once(tmp_path, change):
    source, _ = evaluated(tmp_path)
    destination = capture(tmp_path, "destination")
    judge = Judge(upper=10, revision="v2" if change == "judge" else "v1")
    rubric = spec(sample=1 if change == "sample" else 0)
    if change == "rubric":
        rubric = rubric.model_copy(update={"criteria": tuple(c.model_copy(update={"rubric": "A changed criterion."}) for c in rubric.criteria)})
    if change == "answer":
        # A changed captured user question also changes the full judge request.
        root = tmp_path / "changed"
        root.mkdir()
        destination = captured(root, records=[{"session_id": "A", "turn_index": i, "role": role, "text": text}
                                             for i, role, text in [(1, "user", "changed question"), (2, "assistant", "old")]])
    kwargs = dict(budget=JudgeBudget(max_calls=1, max_cost_micros=10), judge_cache_sources=(source,))
    evaluate_saved(destination, rubric, judge, **kwargs)
    assert len(judge.calls) == 1
    report = evaluation_summary(destination)
    assert report["budget"]["reserved_calls"] == 1
    assert report["budget"]["accounted_cost_micros"] == 10
    evaluate_saved(destination, rubric, judge, **kwargs)
    assert len(judge.calls) == 1


def test_busy_or_running_source_blocks_without_dispatch(tmp_path):
    source, original = evaluated(tmp_path)
    destination, judge = capture(tmp_path, "destination"), Judge(upper=10)
    kwargs = dict(budget=JudgeBudget(max_calls=2), judge_cache_sources=(source,))
    with coordinator_lease(source), pytest.raises(RunBusyError):
        evaluate_saved(destination, spec(), judge, **kwargs)
    store = EvaluationStore(source)
    store.reserve(JudgeRequest(system="additional", prompt="still running"), original.contract)
    with pytest.raises(ValueError, match="original terminal"):
        evaluate_saved(destination, spec(), judge, **kwargs)
    assert judge.calls == []


def test_tampered_source_is_rejected_before_dispatch(tmp_path):
    source, _ = evaluated(tmp_path)
    with sqlite3.connect(EvaluationStore(source).path) as db:
        call_id, raw = db.execute("SELECT id,payload FROM judge_calls LIMIT 1").fetchone()
        value = json.loads(raw)
        value["reply"]["text"] = "tampered raw reply"
        db.execute("UPDATE judge_calls SET payload=? WHERE id=?", (json.dumps(value), call_id))
    destination, judge = capture(tmp_path, "destination"), Judge(upper=10)
    with pytest.raises(ValueError, match="digest mismatch"):
        evaluate_saved(destination, spec(), judge, budget=JudgeBudget(max_calls=2), judge_cache_sources=(source,))
    assert judge.calls == []


def test_source_changes_and_transitive_imports_are_rejected(tmp_path):
    source, original = evaluated(tmp_path)
    destination, judge = capture(tmp_path, "destination"), Judge(upper=10)
    kwargs = dict(budget=JudgeBudget(max_calls=0), judge_cache_sources=(source,))
    evaluate_saved(destination, spec(), judge, **kwargs)
    third = capture(tmp_path, "third")
    with pytest.raises(ValueError, match="original terminal"):
        evaluate_saved(third, spec(), judge, budget=JudgeBudget(max_calls=0), judge_cache_sources=(destination,))
    store = EvaluationStore(source)
    call, _ = store.reserve(JudgeRequest(system="additional", prompt="finished"), original.contract)
    store.finish_call(call.id, exception_type="TimeoutError")
    with pytest.raises(ValueError, match="source changed"):
        evaluate_saved(destination, spec(), judge, **kwargs)
    assert judge.calls == []


def test_import_is_atomic_on_conflicting_replies(tmp_path):
    source, _ = evaluated(tmp_path, function=lambda r: reply_for(r, outcome="violated"))
    destination, judge = capture(tmp_path, "destination"), Judge(upper=10)
    evaluate_saved(destination, spec(), judge, budget=JudgeBudget(max_calls=2))
    store = EvaluationStore(destination)
    before = store.path.read_bytes()
    with pytest.raises(ValueError, match="Conflicting raw replies"):
        evaluate_saved(destination, spec(), judge, judge_cache_sources=(source,))
    assert store.path.read_bytes() == before and store.cache_imports() == []


def test_same_run_and_duplicate_sources_are_rejected(tmp_path):
    source, judge = evaluated(tmp_path)
    for paths in ((source,), (source, source)):
        with pytest.raises(ValueError, match="distinct"):
            evaluate_saved(source, spec(), judge, judge_cache_sources=paths)


def test_legacy_version_one_source_stays_read_only_and_imports(tmp_path):
    source, _ = evaluated(tmp_path)
    with sqlite3.connect(EvaluationStore(source).path) as db:
        from alignmenter.schemas.execution import content_digest

        for call_id, raw in db.execute("SELECT id,payload FROM judge_calls").fetchall():
            value = json.loads(raw)
            value.pop("reused_from")
            db.execute("UPDATE judge_calls SET payload=?,digest=? WHERE id=?", (json.dumps(value), content_digest(value), call_id))
        db.execute("DROP TABLE judge_cache_imports")
        db.execute("UPDATE evaluation_schema SET version=1")
    before = EvaluationStore(source).path.read_bytes()
    destination, judge = capture(tmp_path, "destination"), Judge(upper=10)
    evaluate_saved(destination, spec(), judge, budget=JudgeBudget(max_calls=0), judge_cache_sources=(source,))
    assert judge.calls == [] and evaluation_summary(destination)["counts"] == {"met": 2}
    assert EvaluationStore(source).path.read_bytes() == before


def test_rehashed_imported_payload_cannot_lose_provenance(tmp_path):
    from alignmenter.schemas.execution import content_digest

    source, _ = evaluated(tmp_path)
    destination, judge = capture(tmp_path, "destination"), Judge(upper=10)
    evaluate_saved(destination, spec(), judge, budget=JudgeBudget(max_calls=0), judge_cache_sources=(source,))
    with sqlite3.connect(EvaluationStore(destination).path) as db:
        call_id, raw = db.execute("SELECT id,payload FROM judge_calls LIMIT 1").fetchone()
        value = json.loads(raw)
        value["reply"]["text"] = "tampered but rehashed"
        db.execute("UPDATE judge_calls SET payload=?,digest=? WHERE id=?", (json.dumps(value), content_digest(value), call_id))
    with pytest.raises(ValueError, match="provenance mismatch"):
        evaluation_summary(destination)


def test_mixed_cache_hits_and_misses_share_exact_fresh_budget(tmp_path):
    source, _ = evaluated(tmp_path, function=lambda r: reply_for(r, cost=4))
    root = tmp_path / "destination"
    root.mkdir()
    records = [{"session_id": session, "turn_index": i, "role": role, "text": text}
               for session in ("A", "B")
               for i, role, text in [(1, "user", "question-A" if session == "A" else "changed-B"),
                                     (2, "assistant", f"old-{session}")]]
    destination, judge = captured(root, records=records), Judge(lambda r: reply_for(r, cost=3), upper=10)
    evaluate_saved(destination, spec(), judge, budget=JudgeBudget(max_calls=1, max_cost_micros=10), judge_cache_sources=(source,))
    report = evaluation_summary(destination, details=True)
    assert report["counts"] == {"met": 2} and len(judge.calls) == 1
    assert report["budget"]["reserved_calls"] == 1
    assert report["budget"]["known_actual_cost_micros"] == 3
    assert report["budget"]["accounted_cost_micros"] == 3
    assert len(report["budget"]["cache_sources"]) == 1
    calls = {str(c.id): c for c in EvaluationStore(destination).calls()}
    assert sum(calls[r["call_id"]].reused_from is not None for r in report["results"]) == 1


def test_suite_yaml_uses_public_cache_sources_and_frozen_relative_path(tmp_path, monkeypatch):
    import yaml

    from alignmenter.execution import suite as suites
    from alignmenter.storage.runs import RunStore

    source, _ = evaluated(tmp_path)
    original = Judge(upper=10)
    monkeypatch.setattr(suites, "_factory", lambda name: original)
    config = tmp_path / "suite.yaml"
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("".join(json.dumps(r) + "\n" for r in RunStore(source).transcripts()))
    config.write_text(yaml.safe_dump({"id": "cache-example", "revision": "v1", "dataset": dataset.name,
                                     "judge_factory": "fixture:judge", "judge_budget": {"max_calls": 0},
                                     "judge_cache_sources": [str(source.relative_to(tmp_path))],
                                     "evaluation": spec().model_dump(mode="json")}))
    result = suites.run_suite(config, out_dir=tmp_path / "reports")
    assert result["decision"] == "pass" and original.calls == []
    before = EvaluationStore(result["run_dir"]).path.read_bytes()
    resumed = suites.run_suite(config, resume=result["run_dir"])
    assert resumed == result
    assert EvaluationStore(result["run_dir"]).path.read_bytes() == before
