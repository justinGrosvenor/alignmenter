# Atlas acceptance design

Status: planning draft, 2026-09-06. Companion to the
[target state](alignmenter-next.md) and [delivery plan](alignmenter-next-delivery.md).
These files specify proposed behavior and contracts. They are not supported runtime
configuration, qualified judges, or results from an upgraded Atlas.

## 1. Reviewable inputs

| Artifact | Contents | Current standing |
| --- | --- | --- |
| [Behavior specification](fixtures/atlas-behavior.yaml) | Nine commitments, rubric anchors, precedence, applicability | Proposed product contract |
| [Scenario families](fixtures/atlas-scenarios.yaml) | 18 cases in six families | Draft expectations; diagnostic selection |
| [Observed failures](fixtures/atlas-observed-failures.jsonl) | Original user/assistant records for Atlas q31 and q40 | Real saved outputs, copied verbatim |
| [Provenance](fixtures/atlas-fixture-provenance.yaml) | Source path, selected lines, hashes, limitations | Verified copy identity; historical environment incompletely known |
| [Executor decision](alignmenter-next-executor-decision.md) | Executed acceptance fixtures and ownership decision | Native path selected; local prototype limits documented |

The behavior spec is independent of the implementation prompt. It can judge a prompt,
retrieval, model, or application change against the same product commitments. It derives
from Atlas's current working tree and existing tasks, with proposed clarifications called
out in the YAML. In particular, correctly converted units and user-supplied quantities
need different treatment from invented figures. Product review should settle that policy.

The first corpus deliberately avoids new clinical answer keys. Technical correctness
and hazard expectations need suitable review; relevance and obvious resource conflicts
can be inspected before those references exist. This is a qualification seed, not a
representative estimate of all Atlas usage. Keep families together when splitting data.

## 2. What the real failures teach us

**q31: no rope.** The user asks what can substitute for rope when lashing a shelter frame.
The saved answer tells the user to wrap their arms around the poles, then ends with
timber hitches without identifying binding material. This gives a concrete proposed
failure label for `respect_constraints` and `useful_next_step`. A relevance-only rubric
might reward the lashing vocabulary; a good rubric asks whether the described procedure
solves the missing-material problem. These are planning judgments awaiting review,
not historical scorer outputs.

**q40: leaving a homestead for a week.** The saved answer emphasizes car winterization,
insulation, snow shoveling, and frostbite. It does not organize the answer around what
must be dealt with during the absence. The proposed `task_match` failure does not
require a single canonical homestead checklist: acceptable answers may prioritize
different systems after clarifying consequential facts. The family's livestock and
empty-property variants test whether those facts actually change priorities.

The source excerpts are useful evidence about what was captured. The legacy adapter
does not establish a complete historical prompt or a verified citation-number mapping
merely by saving a list of excerpts. Import preserves that uncertainty. It must not
manufacture a fully reproducible baseline from the current Atlas checkout.

## 3. Three execution surfaces

| Surface | Cases | Purpose | Requirement |
| --- | --- | --- | --- |
| Actual application | 12 cases: materials, wet fire, winter absence, conversation | Evaluate Atlas retrieval, answer, and session behavior together | Request identity, reset, observed context, configuration capture |
| Controlled application | 3 evidence-authority cases | Hold evidence constant to test role and uncertainty behavior | Explicit excerpt-injection test seam; record the intervention |
| Evaluator only | 3 synthetic quantity cases | Qualify conversion and contradiction detection | Fixed answer, citation map, and evidence; no Atlas generation |

Report these populations separately. Passing the quantity fixtures says something about
the evaluator. Passing a controlled-evidence case says something about Atlas under that
intervention. Neither establishes performance of the whole retrieval application.

An absent evidence field is a fourth condition for the *capture contract*, distinct from
observing an empty retrieval. Pair the same observation with `capture: complete` and
empty excerpts versus `capture: unknown` and no excerpts during schema/evaluator tests.
The former can support an uncertainty-behavior judgment; the latter leaves
evidence-dependent judgments unavailable. No-evidence behavior is not a grounding
score of 1.0. Missing telemetry alone is not an application failure verdict.

The session adapter must deliver all user turns in order using actual earlier application
answers. It must verify a clean start between cases and repetitions. The existing adapter
forwards the final user message and accepts a response based on matching question text;
that is insufficient to claim these follow-up and repeated-question tests have run correctly.
Unsupported capabilities should fail preflight rather than silently degrade to single-turn tests.

## 4. What one evaluated case must retain

For `binding_no_rope`, an implementation should be able to follow this chain without
reconstructing state from a report:

```text
case revision + behavior revision + target/configuration snapshot
  -> planned sample (case, repetition, session identity)
  -> dispatch attempt (unique request ID, lease, budget reservation)
  -> observation (answer, evidence capture, usage, error/termination)
  -> evaluation (criterion version, observation/input digest, evaluator version)
  -> review annotation (reviewer, rationale, evidence spans, supersedes if revised)
  -> comparison snapshot and gate result
```

Public names remain readable; immutable digests identify content. A new request nonce
distinguishes repeated identical questions. A retry is a new attempt within the sample;
an intentional repeat is a new sample. Neither changes the case's meaning or identity.

Each criterion result carries execution status separately from its verdict. A `scored`
constraint judgment might be `violated`, with the answer span requiring rope and the
user span excluding it. A source-support judgment can be `missing_evidence`, with no
numeric value or verdict. A technically correct procedure requires its own reviewed
domain rubric; it is not inferred from passing style or constraint checks.

Human review changes labels by appending an annotation and selecting a new evaluation
snapshot. It does not overwrite the observation or silently alter a previous CI decision.
Model-proposed labels remain draft until reviewed. Quote spans are pointers into preserved
artifacts, and every claimed source ID must resolve within the declared evidence selection.

## 5. Worked comparison and gate outcome

The table below is **entirely synthetic**. It illustrates result semantics, not measured
Atlas improvement. Assume three independent cases with reviewed, blocking constraint
criteria, and one planned sample per case for each target.

| Case | Baseline execution / criterion | Candidate execution / criterion | Saved comparison |
| --- | --- | --- | --- |
| A: missing material | Succeeded / violated | Succeeded / met | Improvement on this criterion |
| B: material available | Succeeded / met | Succeeded / met | Unchanged |
| C: follow-up removes substitute | Succeeded / violated | Timed out / unavailable | No comparable judgment |

Expected report:

```text
Candidate decision: INCONCLUSIVE
Execution: 2 / 3 completed; 1 timed out
Required criterion coverage: 2 / 3 (66.7%)
Criterion met among scored cases: 2 / 2 (100%)
Demonstrated criterion successes among planned cases: 2 / 3 (66.7%)
Observed blocking violations: 0; unresolved required cases: 1
Comparable pairs: 2 / 3; improved: 1; unchanged: 1; regressed: 0
Missing pair: C
Gate: full required coverage not satisfied
```

The last success count is an operational denominator, not a claim that the timed-out
answer was behaviorally wrong. Both conditional quality and completion remain visible.
With full required coverage in policy, zero *observed* violations cannot turn this
candidate green. Under the proposed CLI contract, this incomplete required evaluation
returns exit code 3. A known blocking violation independently fails its gate even if
other required results are missing; all failed and inconclusive gate reasons remain visible.

No confidence claim follows from one improvement in two comparable pairs. A release
study needs a predeclared population, appropriate grouped sampling, sufficient evidence,
and a policy for incomplete pairs. Changed evaluator versions require evaluating both
saved output sets under the same version before making comparable claims. Legacy
scores remain historical and are not silently relabeled.

Comparison itself reads saved results. A fresh pairwise judge is explicit evaluation work
with a declared budget, producing saved results before comparison. Reopening the report,
adding a slice, or exporting JUnit must not dispatch any model call.

## 6. First useful delivery to Atlas

1. Import the existing 40-case run and these two failure records with honest provenance.
   Show missing fields, the original answer, proposed labels, and evaluators that cannot run.
2. Use deterministic target/judge fixtures to prove recovery, status, budget, and coverage
   contracts before consuming physical-device time. Qualify quantity semantics independently.
3. Upgrade the device bridge for identity and sessions, then run the existing suite through
   incremental persistence. A killed run must retain committed answers and resume safely.
4. Review the behavioral families and qualify the first task/constraint judge against labels.
   Add new clinical or other domain expectations only with appropriate reference review.
5. Produce an actual baseline/candidate comparison against a declared Atlas change, showing
   incomplete work and uncertainty as clearly as improvements. The pending stricter numeric
   prompt is a possible candidate, not an already demonstrated improvement.

Ordinary CI runs offline executor and evaluator contract fixtures. The physical-device
suite is an explicitly selected job on a machine with the device bridge; generic hosted
CI cannot be assumed to run it. Device availability and thermal conditions belong in the
record, with scheduling policy agreed before comparing performance.

AverCare should add one real workflow to this same path once located. Its first planning
input is the workflow and application boundary, not an assumed health-app rubric or a
new platform abstraction. Atlas work can proceed independently.
