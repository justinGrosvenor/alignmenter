# Alignmenter Next: delivery plan

Status: roadmap, updated 2026-09-07. The [0.3.0 release acceptance](release-0.3.0.md)
defines the implemented release boundary and its validation. This broader plan retains
subsequent work, including live-device recovery and independent product qualification.
Implements the
[target state](alignmenter-next.md). Confirmed direction: useful to Atlas and potentially
AverCare, retain alignment as the center, SDK/CLI/CI first, justified compatibility breaks.

Concrete M0 inputs: [Atlas acceptance design and fixtures](alignmenter-next-atlas.md)
and [executor decision protocol](alignmenter-next-executor.md). Behavior labels remain
draft pending review. The completed [backend spike](alignmenter-next-executor-decision.md)
selects evolving the native execution path with authoritative SQLite records.

First production slice implemented: versioned run/attempt/observation records, frozen
source snapshots, incremental capture in the existing runner, status and transcript
export commands, and process-kill regression tests. See the
[implemented capture contract](../guides/durable-runs.md).

Second production slice implemented: [capture-only resume](../guides/capture-recovery.md)
for recorded and explicitly compatible stateless callable targets, frozen configuration
and plan identity, bounded idempotent recovery with retained attempt history, coordinator
leases, and fresh-process CLI recovery tests. Legacy/stateful adapter recovery, physical
device leases, and broader execution budgets remain subsequent slices; this does not
mark all of M0 or M1 complete.

Third production slice implemented: [durable rubric evaluations](../guides/durable-evaluations.md)
with versioned inputs/verdicts, strict evidence references, shared judge-call/cost
reservations, raw-response recovery, pure saved summaries, and an executable Atlas rubric
draft. Existing scorers retain their legacy behavior and are not covered by this budget
ledger yet. Broader metric/scorer migration and qualified product judges remain M2/M3 work.

Fourth production slice implemented: [grounding and faithfulness](../guides/grounding-faithfulness.md)
on the durable evaluation path, with explicit missing evidence, conservative quantity
and citation checks, strict claim/correctness/abstention/danger assessments, pure metrics,
offline-only evaluations without prematurely freezing a judge budget, and executable
Atlas spec drafts. Previous `rubric-v1` records remain inspectable. Legacy `run` adoption,
remaining scorers, and human/judge qualification are still open; this does not complete M2/M3.
The [evidence validation record](alignmenter-evidence-validation.md) records the Atlas
smoke results and the next review/qualification acceptance boundary.

## 1. Delivery strategy

Build one working path through the system early: define intended behavior, import or
execute cases, persist results, evaluate, inspect failures, and resume. Expand capabilities
against Atlas and one selected AverCare workflow. Preserve valuable existing data while
replacing contracts that prevent correct or useful evaluation.

Milestones are acceptance boundaries, not estimates in weeks. Every milestone ships
reviewable code, behavior-level tests, examples, and migration notes relevant to its scope.
Calendar estimates should follow agreement on product scope and an implementation spike.

| Milestone | Outcome | Depends on | Relative scope |
| --- | --- | --- | --- |
| M0 | Application behavior specifications, contracts, qualification fixtures, backend decision | Confirmed product direction | Medium |
| M1 | Durable runs, recovery, honest execution/coverage | M0 | Large |
| M2 | Behavioral evaluation contracts, metric registration, pure aggregation | M1 | Large |
| M3 | Reliable judges, qualified alignment/task rubrics, Atlas adoption | M2 | Large |
| M4 | Saved comparisons, bounded experiments, CI, AverCare pilot | M2; M3 for judged suites | Large |
| M5 | CLI/report review, annotation exchange, regression promotion | M2, M4 | Medium |
| M6 | Deeper evaluator qualification and calibration provenance | M2, M3; M5 enhances review | Medium–large |
| M7 | Migration, packaging, documentation, complete release acceptance | M1–M6 | Medium |

M4, the inspection part of M5, and parts of M6 can be developed independently once the
result contracts stabilize. That is a dependency observation, not a requirement to use
multiple agents or change the agreed implementation workflow.

## 2. M0 — contracts and evidence

Deliver:

- Draft Atlas behavior specification plus canonical/constrained/follow-up scenario families.
- Locate AverCare and select one real workflow; inventory existing tests/traces and the
  smallest SDK/CLI/HTTP/recorded-artifact integration that provides value.
- Versioned schemas for behavior specifications, scenario families, cases, suites, target capabilities, attempts, observations,
  evaluator results, metrics, gate outcomes, and run manifests.
- A compatibility inventory of public imports, configuration keys, CLI commands,
  report formats, persona artifacts, and Atlas's custom adapter/scorers.
- Tiny deterministic targets/judges for timeout, malformed response, late response,
  rate-limit, cancellation, state recovery, and usage-accounting scenarios.
- A checked-in scorer qualification dataset with expectations and rationale.
- An imported Atlas transcript fixture and a persona fixture whose origin and limits are explicit.
- A specification of storage consistency, identity, statuses, and coverage before implementation.
- A bounded build-versus-compose spike: run the same interruption, state, evidence, and
  budget fixtures through an evolved-runner sketch and one credible existing executor
  adapter. Choose based on semantic fit and total maintenance cost; avoid a speculative
  scheduler rebuild. The storage/backend design below is proposed until this decision.
- A current provider capability inventory, verifying endpoints and declared supported
  features against official docs during implementation.

Acceptance:

- Schema validation rejects unknown metrics/gates, duplicate case revisions, invalid
  metric values, unresolved plugins, and invalid reference links before making provider calls.
- Missing context and an explicitly empty retrieved list are distinguishable.
- Case expectations never appear in the application input generated by a target adapter.
- A behavior specification expresses positive usefulness obligations, boundaries, and
  appropriate changes with context. Refusing every request cannot satisfy the Atlas fixture.
- A controlled scenario mutation distinguishes a valid change in response from a broken commitment.
- Legacy dataset conversion is deterministic and preserves original content and identity mapping.

Start with observed failures, not a minimum test count. Some existing tests explicitly
assert perfect scores for unmeasured populations; update those expectations with the
versioned semantics rather than preserving the defect for compatibility.

## 3. M1 — durable execution

Deliver:

- Durable SQLite storage selected in M0, migration mechanism, event/attempt history,
  artifact store, consistent export/import, and a coordinator with a single write boundary.
  Production implementation must settle the database/artifact commit boundary.
- Run creation before work, incremental observation persistence, lifecycle/status commands.
- Structured error classification, bounded retries, cancellation, deadlines, and resume.
- Capability-aware adapters for recorded data, Python callables, HTTP/model providers,
  plus a compatibility wrapper for the current provider protocol.
- Resource leases and ordered sessions; one active execution per physical-device lease.
- A durable call/usage ledger used by subsequent judge work as well as generation.
- An interim basic status/JSON report exposing completion and incomplete work.

Acceptance:

- Kill execution after N committed answers; restart and reuse those N without fresh calls.
- Kill between dispatch and response; recover to an explicit interrupted/unknown state.
- A second-answer timeout preserves the first answer and permits independent later cases.
- A late response cannot overwrite an expired or retried attempt.
- A case cannot start concurrently on an exclusively leased device.
- Changed target/input configuration cannot silently resume into the old run.
- A stateful session resumes from a declared safe boundary, with repeated calls accounted for.
- Regeneration does not inherit old context, usage, or generation metadata.
- Export/import survives a fresh process and verifies every referenced artifact.

Early Atlas value: run the existing 40-case suite through the durable path before
requiring the new judge or browser UI. Record adapter limitations during this transition.

## 4. M2 — behavioral evaluation contracts and aggregation

Deliver:

- Evaluator protocol with declared turn/session/case/pair/set scope and evidence requirements.
- Behavior-to-criterion links and scenario families testing role fidelity, practical usefulness,
  contextual adaptation, uncertainty, and applicable boundaries across a conversation.
- Metric descriptors: type/unit, direction, applicability, denominator, aggregation,
  uncertainty method, and version.
- Persisted results keyed to observation and evaluation input digests.
- Configured scorer registration, scorecards, slice queries, and gates without built-in name lists.
- Explicit `scored`, `not_applicable`, missing/invalid/skipped/blocked/error outcomes.
- Pure aggregation and portable reports based on stored result snapshots.
- Execution, behavior/task, and persona-continuity contracts; repaired quantity/citation
  resolution checks. Structured-output checks cover demonstrated application needs.
- Legacy scorer wrapper with visible batch-only limitations.

Acceptance:

- Repeated reporting and breakdown generation make zero provider/judge calls.
- Adding a scenario tag cannot increase judge spend or produce fresh verdicts.
- A metric plugin appears in CLI/reports/exports/gates without renderer edits.
- No eligible evaluated cases yields an unavailable aggregate, not 1.0.
- Unknown configured gates are errors; missing required values are inconclusive.
- A hard failure overrides any optional aggregate grade in every presentation surface.
- A voice/style improvement cannot erase a violation of a higher-priority product commitment.
- Unit mutations (C/F, sign, range/comparator, supported conversions) have specified outcomes.
- Question-supplied quantities carry the proper provenance instead of being charged to the corpus.

## 5. M3 — judges, rubrics, and Atlas adoption

Deliver:

- Shared judge execution service with strict schemas, durable raw verdicts, explicit
  repair attempts, persistent cache, budget reservations, and complete cost accounting.
- Faithfulness, cited-claim support, task-rubric, and persona evaluator migrations.
- Versioned criterion rubrics with expected outcomes and permitted alternatives.
- Initial judge qualification against reviewed good/bad Atlas examples, including fluent
  irrelevance, excessive abstention, unsupported certainty, and failures across follow-ups.
- Explicit evidence selection/coverage for long contexts; source IDs preserved throughout.
- Bounded escalation only where qualification reveals a need; deferred human review tasks.
- Atlas request/response IDs, reset/recovery behavior, session-state contract, and adapter migration.
- 15–20 reviewed Atlas cases drawn from the current suite and observed failures.

Acceptance:

- `{}`, string booleans, out-of-range/nonfinite scores, invalid claim enums, truncated
  responses, and fabricated evidence references cannot become successful verdicts.
- A one-call run budget permits at most one newly dispatched judge call across evaluators,
  scenarios, retries, and resume, except an explicitly configured additional budget revision.
- Cached results consume no new spend; intentional repeated judgments create distinct samples.
- A valid no-claims result requires a rubric-supported interpretation such as appropriate
  abstention; empty parsing is not equivalent to an appropriate abstention.
- Evidence beyond an early excerpt prefix remains available or the result declares its limitation.
- The winter-homestead failure fails task relevance/constraints even with no unsupported numbers.
- Injected instructions inside answers/passages do not change the judge's configured task in
  the qualification suite; failed defenses are recorded as evaluator failures.
- Atlas can ask identical questions repeatedly without consuming a stale device result.
- The old and pending Atlas prompts can be compared under the same reviewed behavior/rubric snapshot.
- Targeted pressure and irrelevant-source scenarios test preservation of the intended role
  without rewarding unnecessary refusal or penalizing useful adaptation.

Human reference labels are a real dependency. Machine-generated drafts may accelerate
authoring but cannot fulfill reviewed acceptance criteria by themselves. Domain-heavy
cases may remain explicitly unqualified until suitable review exists.

## 6. M4 — comparison, experiments, CI, and the second application

Deliver:

- Compare saved runs on matched case revisions with a common evaluator snapshot.
- Criterion-level and case-level deltas, scenario slices, added/removed case coverage.
- Paired intervals, grouped/session resampling, repeat statistics, and descriptive handling
  of small samples; metric descriptors define valid calculations.
- Experiment configurations for target variants, repeats, ordering, resource policies,
  budgets, and attribution of generation vs evaluation changes.
- Optional blinded pairwise judging as explicit saved evaluation work.
- Generic absolute and regression gates with coverage and uncertainty policies.
- CLI/CI exit contracts, JSON/HTML/JUnit artifacts, Markdown job summaries, and a plain
  noninteractive command plus example GitHub Actions workflow.
- Smoke/judged/scheduled suite profiles with explicit costs and baseline identity.
- A runnable pilot for one selected AverCare workflow, subject to repository discovery
  and reviewed fixtures; no new hosted infrastructure required.
- Structured tool-workflow assertions only if needed by that workflow; otherwise retain
  a tiny deterministic fixture to validate the adapter/result contract.

Acceptance:

- A judge/rubric change requires compatible rescoring before a release comparison.
- Mismatched case revisions, evaluator versions, or eligibility are visible and cannot
  silently share a headline regression metric.
- A high-scoring candidate with many execution failures does not win through survivor selection.
- Intentional repeats are not suppressed by generation/evaluation caches.
- Correlated turns and derived examples remain grouped in resampling.
- Budgeted experiment scheduling respects resource leases and records every variant's exposure.
- Quality/latency/cost views distinguish measured, estimated, and unknown observations.
- CI, JSON, and HTML agree on pass/fail/inconclusive, including failed hard constraints.
- Failure artifacts survive CI failure, runs are noninteractive, and JUnit carries case
  outcomes with required incomplete evaluations represented as CI failure/error.
- The AverCare pilot detects a reviewed behavior regression through its existing test or
  CI entry point. If unavailable, record the missing application dependency explicitly;
  it does not invalidate the independently completed Atlas milestone.
- Applicable tool-workflow task success can be checked directly from fixture state.

## 7. M5 — review and regression maintenance

Deliver:

- SDK/CLI queries and portable case reports for run progress, failures, evidence, and criteria.
- Side-by-side comparisons and export filters for regressions/disagreement.
- Reproducible review queues, append-only annotations, reviewer opinions, and adjudication
  through CLI and CSV/JSONL exchange with existing review tools.
- Dataset revision and regression promotion from a reviewed failure.
- Portable offline report bundles and CSV/JSONL annotation exchange.

Acceptance:

- Review a case from question through evidence and verdict without inspecting raw JSON.
- Opening/re-rendering a report never invokes a model or spends budget.
- A reviewer can correct a machine verdict without destroying the original result.
- Promoted regressions retain origin, case identity, reviewed expectations, and split group.
- Rubric revisions identify stale annotations rather than silently adopting them.
- Untrusted answer text is displayed as data and cannot execute in the browser.
- A report works offline with no CDN dependency and imports into another workspace.
- All essential inspection/export/annotation operations work without a running server.

A custom browser workspace is deferred. Reconsider it only when reviewing actual Atlas
or AverCare failures exposes friction that portable reports and annotation exchange do
not address. The core contracts permit that extension without making it a release dependency.

## 8. M6 — qualification and calibration

Deliver:

- Reusable evaluator qualification runs with human labels, criterion-level agreement,
  false-pass/false-failure analysis, repeats, cost, and coverage.
- Dataset/source lineage and grouped train/development/test policies.
- A fitting pipeline for persona weights, normalization, thresholds, vocabulary, and traits.
- Immutable calibration artifacts with training provenance and held-out diagnostics.
- Reviewed audit sampling separate from error-mining and active-learning queues.
- Migration of relevant calibration commands and case-study tooling into shared services.

Acceptance:

- An artifact trained on evaluation examples cannot be labeled held-out validated.
- Related turns/variants cannot leak across declared split groups.
- Threshold selection happens on development data; final test results remain separate.
- Every learned component is fitted within the proper training split/fold.
- Confidence intervals correspond to the reported estimator, including validated blends.
- Error-selected judgments are not presented as population quality estimates.
- Known metric counterexamples remain qualification fixtures for future versions.
- Existing persona data runs through the new fit/validate workflow with its provenance limits visible.

## 9. M7 — migration and release

Deliver:

- Versioned importers for current JSONL, persona YAML, calibration artifacts, run configs,
  saved reports, and provider/scorer compatibility wrappers.
- Migration guide showing old/new imports and commands; deprecation policy chosen explicitly.
- Lightweight core install, optional ML extras, offline fixtures, and package smoke tests.
- Updated documentation, example suites, diagrams, API reference, and metric limitations.
- A regression qualification report for the complete release, including Atlas, persona
  continuity, and the selected AverCare pilot where available.

Release acceptance:

- All milestones' required acceptance scenarios pass in an end-to-end release rehearsal.
- Import an old Atlas report and identify missing provenance without inventing it.
- Run interrupted/resumed physical-device evaluation and a comparable baseline/candidate study.
- Perform a persona fit/validation with split provenance and reviewed labels.
- Inspect, annotate, adjudicate, promote, and rerun a failure using CLI and review artifacts.
- Install core without ML dependencies; open an exported report offline.
- Integrate an application-owned evaluator without changing built-in registries/renderers.
- Migration examples preserve source artifacts and explain changed metric meanings.

## 10. Proposed module ownership

Paths are a design sketch, to settle in M0 before moving files.

| Package area | Responsibility |
| --- | --- |
| `schemas/` | Public versioned domain objects and validation |
| `datasets/` | Import, revision, selection, provenance, split groups, promotion |
| `execution/` | Planning, coordinator, attempts, leases, recovery, scheduling |
| `storage/` | Transactional records, artifacts, migration, snapshot export/import |
| `targets/` | Model/HTTP/callable/recorded target adapters and compatibility |
| `evaluation/` | Evaluator interfaces, scheduling, dependencies, registry |
| `judging/` | Provider calls, schema validation, cache, budget ledger integration |
| `metrics/` | Execution, grounding, behavior/task, persona, conversation, and application-needed structured/workflow checks |
| `analysis/` | Aggregation, comparison, statistics, gates |
| `review/` | Annotations, queues, adjudication |
| `calibration/` | Fit recipes, split-aware validation, qualification |
| `reporting/` | Portable HTML/JSON/CSV from result snapshots |
| `cli/` | Thin domain commands |
| `workspace/` | Deferred optional local API/frontend if real review needs justify it |

Keep budget/accounting in one shared service used by execution and judging, rather
than implementing a separate spending counter in each metric pack.

## 11. First implementation slices

Each slice should be independently reviewable with a concrete behavior test.

1. Review and freeze the drafted Atlas behavior specification and representative scenario expectations;
   add failing regression fixtures for interruption, absent evidence, empty verdicts,
   stale context, repeated-slice budget use, and report/gate contradiction.
2. Introduce versioned observation/result/status schemas and convert fixtures through them.
3. Implement the selected M0 backend behind the current entry point, with run creation
   and incremental persistence using the agreed authoritative storage boundary.
4. Add attempt identity, classified failures, interruption recovery, and resume for recorded/callable targets.
5. Add coverage-aware result and gate semantics, with basic report parity.
6. Introduce evaluator descriptors and persisted evaluations; make slices pure aggregation.
7. Move judge calls/cache/budgets behind the shared execution service and strict verdict contract.
8. Migrate Atlas and needed metric packs, then layer comparisons, CI, and the AverCare pilot
   on saved results. Keep behavioral alignment acceptance visible through every slice.

Avoid a long-lived parallel implementation of the entire toolkit. Compatibility adapters
should let the new contracts replace the old path in small steps. Extract reusable pieces
of the current providers, persona scorer, reporters, and calibration tools where their
behavior already matches the new contracts.

## 12. Risks and design checks

| Risk | Planned response |
| --- | --- |
| Scope expands before the first useful result | M1 must improve the current Atlas run; broader features require an application use case |
| Schemas are too narrowly shaped around Atlas | Check the selected AverCare workflow and explicit session/set scopes early |
| General plugins cannot be aggregated correctly | Metric descriptors declare aggregation and dependency scope; reject unsupported slices |
| Resume repeats side effects | Capability declarations, unique attempts, unknown-outcome recovery, explicit session replay semantics |
| Stronger judges still make systematic errors | Reviewed labels, qualification suites, disagreement review, and versioned judge evidence |
| Budget claims exceed enforceable provider behavior | Reservations, bounded output settings, explicit unknown costs, hard/soft cap distinctions |
| Improving the metric rewards a worse application | Fixed task rubrics, hard constraints, held-out cases, and case-level comparisons |
| Synthetic cases become the only success evidence | Preserve source labels, acquire reviewed real failures, and separate diagnostic vs audit samples |
| Migration preserves defective metric meaning invisibly | Version legacy outputs and explicitly change defaults/semantics |
| Frontend work blocks evaluation correctness | Defer a custom UI; ship CLI and portable artifacts at each milestone |

The Atlas behavior specification, 18 draft cases, observed failure fixtures, worked
comparison, and backend acceptance protocol are now available for review. The backend
spike is complete and the native direction selected. Remaining M0 work includes
product/domain label review, public schema/compatibility details, and the selected
AverCare workflow when its repository is available. Product/interface/
compatibility direction is settled. M0 then freezes the contracts and the first
implementation slice begins.
