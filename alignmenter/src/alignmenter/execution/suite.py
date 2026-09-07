"""Capture, evaluate, compare, and export a frozen suite for SDK and CI use."""

from __future__ import annotations

import json
from importlib import import_module
from importlib.metadata import version
from pathlib import Path

import yaml

from alignmenter.evaluators.custom import BUILTINS, evaluator_registry, load_evaluators
from alignmenter.evaluators.metrics import builtin_descriptor
from alignmenter.execution.comparison import compare_saved
from alignmenter.execution.evaluation import evaluate_saved, evaluation_summary
from alignmenter.execution.gates import validate_policy
from alignmenter.execution.recovery import resume_capture
from alignmenter.providers.callable import CaptureTarget
from alignmenter.reporting.durable import export_evaluation
from alignmenter.runner import RunConfig, Runner
from alignmenter.schemas.evaluation import JudgeContract
from alignmenter.schemas.suite import SuiteSpec
from alignmenter.storage.runs import RunStore


def _factory(value):
    module, separator, name = value.partition(":")
    if not separator or not module or not name.isidentifier():
        raise ValueError("Adapter factory must be module.path:function_name")
    return getattr(import_module(module), name)()


def load_suite(path):
    path = Path(path).resolve()
    suite = SuiteSpec.model_validate(yaml.safe_load(path.read_text()))
    data = suite.model_dump(mode="json")
    for key in ("dataset", "persona", "baseline"):
        if data[key] is not None:
            data[key] = str((path.parent / data[key]).resolve())
            if not Path(data[key]).exists():
                raise ValueError(f"Suite {key} path does not exist")
    return SuiteSpec.model_validate(data)


def run_suite(path, *, out_dir=Path("reports"), resume=None):
    """Run one frozen suite. Target exceptions retain partial data and non-green artifacts.

    Factories are explicit application code and must not dispatch work in constructors.
    Custom deterministic evaluators must not call remote inference services.
    """
    suite = load_suite(path)
    evaluators = tuple(load_evaluators(suite.evaluator_factories))
    registry = evaluator_registry(evaluators, suite.evaluation.criteria)
    descriptors = tuple(builtin_descriptor(name) if name in BUILTINS else registry[name].descriptor
                        for name in sorted({c.evaluator for c in suite.evaluation.criteria}))
    validate_policy(suite.policy, suite.evaluation, descriptors)
    records = [json.loads(line) for line in Path(suite.dataset).read_text().splitlines() if line.strip()]
    tags = {t for r in records for t in (r.get("tags") or []) if isinstance(t, str)}
    for gate in suite.policy.gates:
        if gate.tag is not None and gate.tag not in tags:
            raise ValueError(f"Unknown gate tag: {gate.tag}")
    judge = _factory(suite.judge_factory) if suite.judge_factory else None
    if judge is not None and (not isinstance(getattr(judge, "contract", None), JudgeContract)
                              or not callable(getattr(judge, "evaluate", None))):
        raise ValueError("Judge factory must return a JudgeContract and evaluate(request)")
    if judge is not None:
        JudgeContract.model_validate_json(judge.contract.model_dump_json())
        if suite.judge_budget is not None and suite.judge_budget.max_cost_micros is not None and judge.contract.max_cost_micros_per_call is None:
            raise ValueError("Monetary budgets require an adapter-declared cost upper bound")
    if suite.baseline is not None:
        baseline = evaluation_summary(Path(suite.baseline), suite.baseline_evaluation_id, details=True)
        expected_judge = judge.contract.model_dump(mode="json") if judge is not None else None
        if (baseline["spec"] != suite.evaluation.model_dump(mode="json") or baseline["judge"] != expected_judge
                or baseline["manifest"]["evaluators"] != [d.model_dump(mode="json") for d in descriptors]
                or baseline["manifest"]["package_version"] != version("alignmenter")
                or baseline["manifest"]["engine_revision"] != "evaluators-v2"):
            raise ValueError("Baseline evaluator configuration is incompatible; rescore it before running this suite")
        suite = SuiteSpec.model_validate({**suite.model_dump(mode="json"), "baseline_evaluation_id": baseline["evaluation_id"]})
    target = _factory(suite.target_factory) if suite.target_factory else None
    if target is not None and not isinstance(target, CaptureTarget):
        raise ValueError("Target factory must return a CaptureTarget")
    snapshot = {"configuration": suite.model_dump(mode="json"),
                "evaluators": [d.model_dump(mode="json") for d in descriptors],
                "judge": judge.contract.model_dump(mode="json") if judge is not None else None}
    capture_error = None
    if resume is None:
        runner = Runner(RunConfig(model=target.model if target else "recorded", dataset_path=Path(suite.dataset),
                                  persona_path=Path(suite.persona or ""), run_id=suite.id,
                                  report_out_dir=Path(out_dir), max_target_calls=suite.max_target_calls),
                        scorers=[], provider=target.provider if target else None,
                        suite_snapshot=snapshot)
        try:
            run_dir = runner.capture()
        except Exception as exc:
            if runner.run_dir is None or not RunStore(runner.run_dir).path.exists():
                raise
            run_dir, capture_error = runner.run_dir, type(exc).__name__
    else:
        run_dir = Path(resume)
        if RunStore(run_dir).manifest().suite != snapshot:
            raise ValueError("Suite configuration differs from the frozen run")
        try:
            resume_capture(run_dir, targets={"primary": target} if target else {},
                           dataset_path=Path(suite.dataset), persona_path=Path(suite.persona) if suite.persona else None)
        except Exception as exc:
            # Resume failures must not trigger evaluation with changed target configuration.
            from alignmenter.execution.recovery import ResumeError
            if isinstance(exc, ResumeError):
                raise
            capture_error = type(exc).__name__
    evaluation_id = evaluate_saved(run_dir, suite.evaluation, judge, budget=suite.judge_budget,
                                    evaluators=evaluators, new_evaluation=resume is not None)
    comparison = compare_saved(Path(suite.baseline), run_dir, baseline_id=suite.baseline_evaluation_id,
                                candidate_id=evaluation_id) if suite.baseline else None
    report = export_evaluation(run_dir, run_dir / "review", evaluation_id=evaluation_id,
                               policy=suite.policy, comparison=comparison, force=True)
    return {"run_dir": str(run_dir), "evaluation_id": str(evaluation_id), "decision": report["gate_report"]["decision"],
            "capture_error": capture_error, "artifacts": str(run_dir / "review")}
