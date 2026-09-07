# Python SDK

Import the supported 0.3 entry points from `alignmenter.sdk`. Use the execution
services to acquire coordinator leases and preserve transactional boundaries; direct
storage mutation is a lower-level interface requiring coordinator ownership.

## Run or inspect a suite

```python
from alignmenter.sdk import run_suite, evaluation_summary, export_evaluation

result = run_suite("evals/suite.yaml", out_dir="reports")
summary = evaluation_summary(result["run_dir"], details=True)
export_evaluation(result["run_dir"], "saved-review")
assert summary["budget"]["target"]["scope"] == "capture_run"
```

`run_suite` returns paths, the evaluation UUID, a gate decision, and an optional
capture exception class. It does not turn non-green results into Python exceptions;
the CLI maps them to exit codes. Invalid configuration raises an exception. The
summary's `decision` describes the evaluation; exported `gate_report.decision`
additionally applies the selected policy and optional comparison.
When no policy is supplied, export retains the suite's frozen policy and baseline.

## Capture an application target

```python
from alignmenter.sdk import (
    CallableProvider, CaptureTarget, ChatResponse, RecoveryContract,
    capture_run, content_digest,
)

def respond(messages, *, request_id):
    # Replace this with your application entry point. Preserve retrieved evidence.
    return ChatResponse(text="Use the available tarp.", context={"excerpts": []})

target = CaptureTarget("my-app:v1", CallableProvider(respond, RecoveryContract(
    configuration_digest=content_digest({"application_revision": "v1"}),
    session_state="stateless",
    interrupted_request="idempotent",
    max_attempts=2,
)))
run = capture_run("dataset.jsonl", target=target, max_target_calls=20)
```

The recovery declarations above fit the shown pure function. Real adapters must
describe their own state and retry semantics truthfully. Include model, prompt,
retrieval, transport/retry settings, and application revision in the configuration
identity where they affect behavior. The stable request ID lets an adapter implement
idempotency. `capture_run` without a target saves recorded assistant answers.

## Register a deterministic evaluator

```python
from alignmenter.sdk import (
    CustomAssessment, DeterministicEvaluator, EvaluatorDescriptor,
    MetricDescriptor, MetricSample, SourceQuote, content_digest,
)

def make_evaluator():
    def assess(context):
        limit = context.config.get("max_characters", 200)
        met = len(context.answer) <= limit
        return CustomAssessment(
            outcome="met" if met else "violated",
            rationale=f"The answer must contain at most {limit} characters.",
            evidence=[SourceQuote(source_id="answer", quote=context.answer)] if context.answer else [],
            metrics={"my_app.concise": MetricSample(numerator=int(met), denominator=1)},
        )

    return DeterministicEvaluator(EvaluatorDescriptor(
        id="my_app_conciseness", revision="v1",
        configuration_digest=content_digest({"implementation": "conciseness-v1"}),
        metrics=(MetricDescriptor(
            id="my_app.concise", revision="v1", unit="fraction",
            direction="higher", aggregation="ratio",
            description="Answers within the configured character limit",
        ),),
    ), assess)
```

Reference this factory in `evaluator_factories`, set the criterion's `evaluator` to
`my_app_conciseness`, and optionally set `config: {max_characters: 200}`. A metric name
is application-owned; builtin namespaces are reserved. Increment revisions when
implementation or meaning changes. The descriptor digest is an adapter declaration,
not automatic source-code hashing. Criterion config is frozen separately.

`EvaluatorContext` contains `answer`, the saved conversation, optional context,
criterion config, and addressable source text. Evaluators receive a copy and return
a typed `CustomAssessment` with `met`, `violated`, `not_applicable`, or `needs_review`.
All registered metrics must be returned, with finite values. A ratio sample uses its
observed numerator and denominator; an empty denominator must have numerator zero and
aggregates to an unavailable value. `mean` aggregates totals/counts, and `count` sums
integer counts. Direction is `higher`, `lower`, or `neutral`.

Evidence quotes must match saved source text exactly. Invalid returns and exceptions
become saved `invalid` results with a sanitized exception class. Plugins are trusted
local application code, not a sandbox. Deterministic evaluators must not call model
APIs; judged criteria must use the shared judge service. Registration makes custom
metrics available to saved reports, grouping, comparisons, and gates without renderer
changes or later plugin imports.

## Other entry points

| Service | Purpose |
| --- | --- |
| `evaluate_saved(run, spec, judge=None, *, budget=None, evaluators=(), new_evaluation=False)` | Evaluate a frozen capture with typed criteria and a shared judge ledger |
| `compare_saved(baseline, candidate, *, baseline_id=None, candidate_id=None)` | Compare compatible saved case populations |
| `export_evaluation(run, out, *, policy=None, comparison=None, evaluation_id=None, force=False)` | Export HTML, JSON, Markdown, and JUnit using one gate decision |
| `export_review(run, out, *, evaluation_id=None, force=False)` | Export JSONL review tasks |
| `import_review(run, annotations)` | Validate and atomically append annotations |
| `qualification_report(run, evaluation_id=None)` | Compare machine results with human adjudications |
| `promote_regression(run, annotation_id, out)` | Write a case and separate expectations with source lineage |
| `export_archive(run, out, *, force=False)` / `import_archive(archive, out)` | Exchange verified read-only inspection copies |
| `resume_capture(run, *, targets=..., dataset_path=..., persona_path=...)` | Explicit recovery under the original frozen contracts |

`Criterion`, `EvaluationSpec`, `JudgeBudget`, `JudgeContract`, `JudgeRequest`,
`JudgeReply`, `CallableJudge`, `ChatCompletionJudge`, `SuiteSpec`, `GatePolicy`,
`MetricGate`, and `RegressionGate` are also exported. See
[durable evaluations](../guides/durable-evaluations.md) for the judge contract and
[the release workflow](../guides/release-workflow.md) for comparison and review semantics.
