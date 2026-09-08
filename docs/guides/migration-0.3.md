# Migrating to 0.3

0.3 adds a durable application evaluation workflow alongside the existing persona
toolkit. Python 3.10–3.14 are supported for the core package. `alignmenter --version`,
`alignmenter.__version__`, and distribution metadata now agree on `0.3.0`.

## Choose the durable path for new integrations

| Existing usage | New integration |
| --- | --- |
| `init`, `run --config`, legacy HTML | `init-suite`, `run-suite`, offline review artifacts |
| Provider regeneration mixed with scoring | `capture`, explicit `resume`, then `evaluate` |
| Legacy `module:Class` scorer | Explicit `DeterministicEvaluator` factory with typed outcomes and metric descriptors |
| Per-scorer judge budgets | One durable judge ledger per run, reserved before dispatch |
| Thresholds on summary averages | Required outcomes and coverage plus versioned absolute/regression gates |
| Rerun to investigate an answer | Inspect saved evidence, `compare`, and `review-export` |

The old CLI commands, persona packs, providers, scorer plugins, and calibration tools
remain available. Their contracts are retained for compatibility but are deprecated
as the integration path for new release checks; there is no removal date in 0.3.
Legacy authenticity/safety/stability do not yet emit the new durable assessment
contract. Legacy reports and scorer-local budgets must not be interpreted as the new
shared-ledger guarantees. Wrapping a remote scorer as a deterministic evaluator would
bypass those guarantees; implement a judged adapter and criterion instead.

## Evidence semantics changed on the durable path

Durable grounding is a quantity traceability and citation resolution check. A matched
quantity is not proof that an answer is semantically correct. Unsupported recognized
syntax yields `needs_review`; missing or malformed context is unavailable. An explicit
empty passage list is valid captured evidence. No quantities means an unavailable
quantity rate, not a perfect score. Citation-only answers can still be evaluated.

Durable faithfulness requires one complete typed JSON verdict with exact source
quotes. Invalid, truncated, refused, missing, or budget-blocked work cannot become an
empty perfect score. Unsupported claims, dangerous advice, and insufficient correctness
produce violations. Abstentions and no-claim answers have explicit states. See
[grounding and faithfulness](grounding-faithfulness.md) for the detailed contract.

All required violations fail a release check. Passing requires complete applicable
coverage, a reviewed specification, and a nonempty assessed population. An empty
denominator is reported as unavailable. Changing a numeric gate cannot hide a hard
failure. `qualification: reviewed` is a declaration, not independent evaluator validation.

## Preserve old work

Capture database version 1 remains readable but cannot be resumed. New captures use
version 2, with separately versioned evaluation and annotation extensions. Old
`rubric-v1` and `evaluators-v1` evaluations remain inspectable. New evaluations use
`evaluators-v2`, freezing descriptors, metrics, case revisions, and split groups.
Missing fields in old records do not rewrite their saved wire digests.

Use an explicit new evaluation snapshot to change a spec, judge, or plugin descriptor.
Re-evaluate both saved captures with the same package and evaluator configuration
before comparing them. Reports never execute plugins. Resume validates frozen inputs,
target contracts, and suite configuration; starting a new suite invocation normally
creates a new run with a separate budget. A zero/exhausted budget is not permission
to retry an uncertain external call.

Review annotations are append-only and separate from machine verdicts. Correct them
with a new UUID and `supersedes`, not an edit to history. Imported run archives are
inspection copies and cannot fork a live run's execution or budget.

## Development and platform limits

Use `pip install -e 'alignmenter[test,docs]'` from the repository root for core tests
and documentation. `[dev]` retains the heavier optional ML dependencies for existing
contributors. ML extras have their own upstream platform constraints and may download
models on first use. The durable coordinator uses local POSIX file leases; Windows
durable execution and shared/network-filesystem coordination are not supported in
this release. Core release validation covers macOS locally and Linux in CI.

Atlas's preserved failures and draft commitments ship as integration fixtures in the
repository. Actual judge qualification still requires model outputs and independent
product-owner labels. AverCare needs a selected workflow before application-specific
qualification. Physical-device replay, session/set evaluators, distributed budgets,
hosted review, and automatic optimization remain roadmap work.
