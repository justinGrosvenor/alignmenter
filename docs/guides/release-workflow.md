# Application evaluation and release checks

Alignmenter 0.3 evaluates the commitments your application makes: using available
resources, respecting user constraints, grounding advice in supplied evidence, and
avoiding dangerous recommendations. Each decision retains the captured answer,
criterion, evidence, evaluator configuration, and coverage behind it.

## Run the offline example

```bash
pip install alignmenter
alignmenter --version
alignmenter init-suite --out evals/resource-task
alignmenter run-suite evals/resource-task/suite.yaml --out reports
```

`init-suite` writes a dataset and suite YAML. The example's target is a local Python
function: it chooses resources from an available list. Its deterministic evaluator
checks a precise engineering predicate. This demonstrates the integration contract;
it is not a model benchmark or a human-qualified judge. No API key is needed.

`run-suite` prints JSON containing `run_dir`, `evaluation_id`, `decision`, and
`artifacts`. The artifact directory contains `index.html`, `evaluation.json`,
`summary.md`, and `junit.xml`. The HTML works offline and includes saved evidence.
Exit codes are **0 pass, 2 fail, 3 inconclusive**; invalid configuration also exits
nonzero. Capture exceptions preserve partial evidence and produce a non-green result
when a run has been initialized. A process kill can leave artifacts unwritten; inspect
the saved run with `status` and resume explicitly.

To exercise a failure, run the same example with its deliberately bad target variant:

```bash
ALIGNMENTER_DEMO_VARIANT=bad alignmenter run-suite evals/resource-task/suite.yaml --out reports
```

This exits 2 because the target asks for unavailable equipment. The environment flag
is part of this example adapter, not a general Alignmenter setting.

## Configure your application

Suite paths are resolved relative to the YAML file. Factories are explicitly imported
`module.path:function_name` callables; install your application package so they are
importable. They must construct adapters without dispatching work in their constructors.

```yaml
id: resource-task
revision: v1
dataset: dataset.jsonl
target_factory: alignmenter.examples.resource_task:make_target
max_target_calls: 2
evaluator_factories:
  - alignmenter.examples.resource_task:make_evaluator
evaluation:
  id: resource-constraints
  revision: v1
  qualification: reviewed
  criteria:
    - id: uses_available_resources
      revision: v1
      evaluator: resource_task
policy:
  id: resource-release
  revision: v1
  gates:
    - id: resource_success
      metric: resource_task.success
      operator: at_least
      threshold: 1
      min_denominator: 2
```

Omit `target_factory` to score recorded assistant answers. Generated suites require
`max_target_calls`; reservations include interrupted and failed attempts. Target cost
is currently unavailable, not reported as zero. Retry safety is an adapter declaration;
see [capture recovery](capture-recovery.md). Do not declare a stateful device operation
idempotent unless replay is actually safe.

For `rubric` or `faithfulness` criteria, configure `judge_factory` and
`judge_budget: {max_calls: 20}`. Monetary limits additionally require an adapter-declared
per-call upper bound. All durable judged evaluations in the same run share a ledger;
reporting, grouping, and comparison consume saved results. Unknown dispatch outcomes
retain their reservation and do not retry automatically. See
[durable evaluations](durable-evaluations.md) for judged adapters and strict evidence
contracts, and the [SDK reference](../reference/sdk.md) for application-owned evaluators.

`qualification: reviewed` is an owner's declaration about the specification. It does
not certify the evaluator or create human reference labels. Start product rubrics as
`draft`; draft results remain inconclusive unless a violation already makes them fail.

## Preserve and compare a baseline

Use the run directories and evaluation UUIDs printed by `run-suite`:

```bash
alignmenter compare BASELINE_RUN CANDIDATE_RUN --out reports/comparison \
  --baseline-id BASELINE_EVALUATION_UUID --candidate-id CANDIDATE_EVALUATION_UUID
```

For automatic regression gates, add these fields to the candidate suite:

```yaml
baseline: ../../reports/path-to-baseline-run
baseline_evaluation_id: BASELINE_EVALUATION_UUID
policy:
  id: release
  revision: v2
  regressions:
    - id: no_resource_regression
      metric: resource_task.success
      max_regression: 0
```

Pin the baseline UUID for repeatable CI decisions. When omitted, `run-suite` resolves
the latest baseline evaluation during preflight and freezes that UUID in the run.

Pairing uses `case_id` and criterion ID. Put stable `case_id` and optional
`case_revision` fields on assistant dataset records. Without an explicit ID,
Alignmenter uses the session ID and assistant-turn index. A scenario digest includes
the declared revision and planned conversation text, excluding assistant answers so
different model responses remain comparable. Related cases should share
`metadata.split_group`; its default is the logical session. Keep generated variants
in their original split group when creating training and evaluation partitions.

Changed scenarios or split groups, added/removed cases, unavailable results, and
asymmetric not-applicable outcomes are explicit. They cannot silently enter a complete
headline comparison. Both sides must have the same evaluation specification, judge
contract, evaluator descriptors, engine revision, and package version. Re-evaluate
old captures under one configuration before comparing different evaluator versions.

Metric deltas use only matched eligible pairs and each metric's owning evaluators.
The report shows denominators, missing populations, outcome transitions, and side by
side answers. A hard violation cannot be hidden by an improving average. Absolute
gates can select a criterion or a tag; combined criterion-and-tag gates are not yet
supported. Unknown metrics or tags are configuration errors; absent required metric
populations are inconclusive. Regression gates use the metric's declared direction.

### Uncertainty limits

Comparison intervals are descriptive 95% paired percentile bootstrap intervals,
resampling whole split groups with replacement (1,000 draws, seed 0 by default).
The groups must plausibly be independent. Intervals are omitted for fewer than five
groups and for count metrics. Five groups is a display minimum, not a guarantee of
reliable inference. The implementation is pure Python; SciPy's
[bootstrap reference](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html)
describes the underlying paired percentile method and alternatives. Alignmenter
does not use BCa correction, perform a significance test, or infer product-wide
quality from a selected failure queue. Regression gates compare observed deltas;
they do not interpret interval overlap as significance.

## Review and maintain regression cases

```bash
alignmenter review-export RUN --out review.jsonl --evaluation-id EVALUATION_UUID
# A reviewer edits only each row's annotation object.
alignmenter review-import RUN --annotations review.jsonl
alignmenter qualify RUN --evaluation-id EVALUATION_UUID
```

Each JSONL task contains immutable evidence, criterion, original machine result, and
an editable `annotation`. To submit a label, fill `reviewer`, `outcome` (`met`,
`violated`, or permitted `not_applicable`), `rationale`, and `provenance` (`human`,
`model`, or `synthetic`). `role` defaults to `opinion`. Use `adjudication` when a human
has resolved the reference decision. Blank outcomes remain pending. Import validates
the whole batch before appending anything, and reimporting identical IDs is idempotent.

Opinions can disagree. A correction needs a new annotation UUID and `supersedes`
pointing at the active previous annotation; history is retained. Editing an existing
ID's contents is rejected. Re-export if the underlying saved task has changed before
import. Human references can be reused across repeated judge samples or judge
configurations when the run's evidence and criterion are unchanged; changed evidence
or criteria make them stale.

Qualification compares saved machine outcomes to active **human adjudications**.
It reports reference coverage, evaluator coverage, agreement, false passes, false
failures, and disagreements by criterion and tag. Model and synthetic labels never
count as human references. Missing references remain inconclusive. Provenance is
declared by the importer, not verified identity or independence; a review queue is a
selected sample, not a population estimate. Machine outcomes remain immutable and
qualification does not silently change a suite's declaration or CI result.

```bash
alignmenter promote RUN --annotation-id ANNOTATION_UUID --out evals/regressions/case
```

Promotion requires an active human adjudication. It writes the captured conversation
prefix to `dataset.jsonl` and keeps the reference, source lineage, and dataset digest
in a separate `expectations.jsonl`. Targets never receive the expectations file.
Case identity and split group are preserved. Review the promoted case before adding
it to a suite; promotion does not automatically change an evaluation configuration.
JSONL review exchange is supported in 0.3; a hosted UI and CSV editing are deferred.

## Inspect and exchange saved work

```bash
alignmenter check RUN --out reports/saved-review --evaluation-id EVALUATION_UUID
alignmenter check RUN --policy gates.yaml --baseline BASELINE_RUN --out reports/gated
alignmenter archive-export RUN --out run.zip
alignmenter archive-import run.zip --out imported-run
alignmenter check imported-run --out reports/imported-review
```

`check` recomputes decisions from saved outcomes and does not import application
factories or call providers. By default it retains a suite run's frozen policy and
pinned baseline; use `--policy` to explicitly choose a different policy. Baseline
comparisons require the saved baseline to remain accessible, including when inspecting
an archived candidate. A missing baseline cannot silently remove a regression gate.
Output paths must be new unless `--force` is supplied.
Suite runs write their own `review` directory automatically.

Archives contain a verified SQLite snapshot, source evidence, evaluations, raw judge
replies, and annotations. They may contain sensitive application text: choose which
artifacts to share with that in mind. SHA-256 checks detect corruption, not authenticity
against a malicious sender. Import validates the archive and creates a **read-only**
inspection copy. It cannot resume capture, spend a copied budget, or accept annotations;
return review JSONL to the original run owner for import. New independent execution
needs a new run. Budgets are local to one run, not a distributed account-wide limit.

## Use in CI

Install a pinned release and your application adapter, then run the suite as a normal
failing step. Upload evidence even when the step fails:

```yaml
- run: pip install 'alignmenter==0.3.0' -e .
- run: alignmenter run-suite evals/suite.yaml --out reports
- uses: actions/upload-artifact@v4
  if: always()
  with:
    name: alignmenter-review
    path: reports/**/review/*
```

Publish `summary.md` to your job summary and ingest `junit.xml` with your CI's test
reporter if desired. HTML, JSON, Markdown, JUnit, and CLI all use the same gate decision.
Provide secrets only to jobs that deliberately execute a remote adapter. A complete
example is in `.github/examples/application-evals.yml` in the repository.
