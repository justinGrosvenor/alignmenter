"""Public 0.3 SDK: application adapters, frozen evaluations, review, and release checks."""

from pathlib import Path

from alignmenter.evaluators.custom import DeterministicEvaluator, EvaluatorContext
from alignmenter.execution.archive import export_archive, import_archive
from alignmenter.execution.comparison import compare_saved
from alignmenter.execution.evaluation import evaluate_saved, evaluation_summary
from alignmenter.execution.recovery import resume_capture
from alignmenter.execution.review import (
    export_review,
    import_review,
    promote_regression,
    qualification_report,
)
from alignmenter.execution.suite import load_suite, run_suite
from alignmenter.providers.base import ChatResponse
from alignmenter.providers.callable import CallableProvider, CaptureTarget
from alignmenter.providers.durable_judge import CallableJudge, ChatCompletionJudge
from alignmenter.reporting.durable import export_evaluation
from alignmenter.runner import RunConfig, Runner
from alignmenter.schemas.evaluation import (
    Criterion,
    EvaluationSpec,
    JudgeBudget,
    JudgeContract,
    JudgeReply,
    JudgeRequest,
)
from alignmenter.schemas.execution import RecoveryContract, content_digest
from alignmenter.schemas.gates import GatePolicy, MetricGate, RegressionGate
from alignmenter.schemas.metrics import EvaluatorDescriptor, MetricDescriptor, MetricSample
from alignmenter.schemas.scoring import CustomAssessment, SourceQuote
from alignmenter.schemas.suite import SuiteSpec

__all__ = [
    "CallableJudge", "CallableProvider", "CaptureTarget", "ChatCompletionJudge", "ChatResponse", "Criterion",
    "CustomAssessment", "DeterministicEvaluator", "EvaluationSpec", "EvaluatorContext", "EvaluatorDescriptor",
    "GatePolicy", "JudgeBudget", "JudgeContract", "JudgeReply", "JudgeRequest", "MetricDescriptor", "MetricGate",
    "MetricSample", "RecoveryContract", "RegressionGate", "SourceQuote", "SuiteSpec", "capture_run",
    "compare_saved", "content_digest", "evaluate_saved", "evaluation_summary", "export_archive", "export_evaluation",
    "export_review", "import_archive", "import_review", "load_suite", "promote_regression", "qualification_report",
    "resume_capture", "run_suite",
]


def capture_run(dataset, *, out_dir=Path("reports"), persona=None, target: CaptureTarget | None = None,
                max_target_calls=None, label="alignmenter_run"):
    """Capture a recorded dataset or an explicit application target without running scorers."""
    return Runner(RunConfig(model=target.model if target else "recorded", dataset_path=Path(dataset),
                            persona_path=Path(persona or ""), report_out_dir=Path(out_dir), run_id=label,
                            max_target_calls=max_target_calls), scorers=[],
                  provider=target.provider if target else None).capture()
