# Durable grounding and faithfulness

Use these evaluators on captured answers from Atlas or another retrieval application.
They run through `evaluate`, share its saved evidence and judge ledger, and produce
typed assessments that can be inspected without re-running a scorer. The older
`alignmenter run --scorers grounding,faithfulness` path retains its legacy semantics.

## Run the checks

Grounding needs no judge adapter or budget:

```sh
alignmenter capture --dataset docs/plans/fixtures/atlas-observed-failures.jsonl --out reports
alignmenter evaluate reports/<run-directory> --spec docs/plans/fixtures/atlas-grounding.yaml
alignmenter evaluation-status reports/<run-directory> --details > grounding-review.json
```

The checked-in Atlas specs are drafts. An otherwise passing draft exits `3`
(inconclusive); a violation exits `2`. Grounding measures a limited form of traceability,
so a passing grounding check cannot establish that an Atlas answer is practically useful.

Faithfulness requires a [judge adapter](durable-evaluations.md#judge-adapters):

```sh
alignmenter evaluate reports/<run-directory> \
  --spec docs/plans/fixtures/atlas-faithfulness.yaml \
  --judge-factory my_eval.judge:make_judge --max-judge-calls 20 --new-evaluation
alignmenter evaluation-status reports/<run-directory> --details > faithfulness-review.json
```

`--new-evaluation` is required here because the capture already has a different
grounding evaluation. A deterministic evaluation leaves the budget unconfigured unless
one is explicitly supplied. The first judged evaluation freezes the shared run budget;
later evaluations reuse its remaining limits. Grounding continues even when the judge
budget is exhausted and never reserves a call. A deterministic CLI spec does not load
a judge factory, even if one was supplied.

Mix the evaluators in one spec when convenient:

```yaml
id: product-evidence
revision: draft-1
qualification: draft
criteria:
  - id: traceability
    revision: v1
    evaluator: grounding
  - id: practical_faithfulness
    revision: draft-1
    evaluator: faithfulness
    min_correctness: 7
    rubric: Respect the user's stated resources and solve their actual task.
```

Built-ins default to `evidence_requirement: context` and
`allow_not_applicable: true`. Those requirements cannot be relaxed to conversation-only
or forced applicability. `complete_context` is accepted, but current legacy captures
have unknown completeness and cannot meet it. Only faithfulness accepts
`min_correctness` (an integer from 0 through 10, default 7). Grounding rejects rubric text
because it has no judge to interpret it. Generic rubric criteria retain their existing
configuration and strict verdict schema.

The same contract is available from Python:

```python
from pathlib import Path
from alignmenter.execution.evaluation import evaluate_saved, evaluation_summary
from alignmenter.schemas.evaluation import Criterion, EvaluationSpec

spec = EvaluationSpec(
    id="traceability", revision="draft-1",
    criteria=(Criterion(id="grounding", revision="v1", evaluator="grounding"),),
)
evaluation_id = evaluate_saved(Path("reports/my-capture"), spec)
report = evaluation_summary(Path("reports/my-capture"), evaluation_id, details=True)
```

## Visible evidence contract

Both built-ins require the nearest preceding user question in the same session and a
readable retrieval collection. The first present key in `excerpts`, `passages`,
`documents`, `sources`, `context` must contain a list. Each item must be a nonblank string
or an object with a nonblank `text`, `content`, or `body` field, checked in that order.
A title alone is metadata, not supporting text.

`None`, `{}`, an unrecognized collection, or any malformed item yields
`missing_evidence`. An explicit `{"excerpts": []}` is a valid empty retrieval result.
Malformed items are not dropped: dropping one could change the meaning of numbered
citations. Multiple collection aliases are not merged. Normalize different retrieval
formats in the capture adapter and retain the original evidence there.

Passage IDs are `passage:1`, `passage:2`, etc., preserving the saved list order. A provider
document ID is retained separately when available. The nearest user question keeps its
`turn:<ordinal>` ID. Earlier assistant assertions are conversation history, not independent
support for a new claim. A context object's potentially stale `question` field does not
override the actual saved user turn. Full passages reach the judge without truncation.
Their presence does not establish complete retrieval, independent truth, or relevance.

## What grounding measures

Grounding extracts recognized numeric quantities with units and resolves numeric
citations such as `[1]` and `[1,3]`. Each quantity records its exact answer text, normalized
value/bounds, and one of `source`, `question`, `unmatched`, or `ambiguous`. Matches retain
the supporting source ID and exact quote. A question-supplied value is counted as
traceable with explicit question provenance.

The parser preserves signs, distinguishes Celsius and Fahrenheit, and supports exact
conversions among the implemented SI length, mass, volume, temperature, and fixed time
units. Arithmetic is rational, without fuzzy floating-point tolerances. Temperature and
time relationships are based on the [NIST conversion tables](https://www.nist.gov/pml/special-publication-811/nist-guide-si-appendix-b-conversion-factors/nist-guide-si-appendix-b9).

Ranges and inequality bounds must match as expressions: `5–10 minutes` does not
automatically support `7 minutes` or `10 minutes`; `at least 5 minutes` is distinct from
`5 minutes` and `more than 5 minutes`. Such differences are reported as unmatched,
not asserted to be semantic contradictions.

Recognized fractions, scientific notation, comma-formatted numbers, approximate values,
compound units such as `mg/kg`, reversed ranges, and some unsupported bounds become
`ambiguous` and make the result `needs_review`. They are not reduced to a conveniently
matching numeric suffix. Bare numbers, spelled-out quantities, unknown units, arbitrary
mathematical expressions, and nonnumeric citation conventions are outside this parser's
coverage. Cups, gallons, months, and years can match their own units but are not converted
using regional or variable-length assumptions. See `evaluators/grounding.py` for the
implemented vocabulary; this is not a general dimensional-analysis system.

An unmatched quantity or unresolved citation produces `violated`. Otherwise ambiguity
produces `needs_review`; measurable matches produce `met`; no recognized quantities or
citations produces `not_applicable`. Missing capture/evidence is handled before parsing.

This is a traceability proxy: a matching number can refer to the wrong object, and a
valid citation can point to an irrelevant passage. Faithfulness and product behavior
rubrics provide complementary semantic checks. Neither deterministic grounding nor
a judge verdict by itself establishes clinical validity for AverCare.

## What faithfulness measures

The judge must return every field in `FaithfulnessVerdict`: exact answer claim quotes,
each claim's support status and evidence, integer correctness, whether it answers the
question, explicit abstention state and appropriateness, danger flag/reason, reasoning,
and an explicit reason for any empty claim list. Unknown/missing fields, duplicate JSON
keys or claim quotes, coerced booleans/scores, fabricated references/quotes, and incomplete
replies become `invalid`. There is no automatic JSON repair or second judge call.

Supported and contradicted claims require quotes from the provided passages or nearest
user question. A quote from the answer itself cannot serve as independent support.
Unsupported claims may have no evidence. Quote checks establish provenance, not whether
the judge extracted every claim or interpreted the sources correctly.

The criterion is violated by any unsupported/contradicted claim, dangerous advice,
correctness below `min_correctness`, an inappropriate abstention, or failure to answer
without an appropriate abstention. A danger flag therefore cannot be hidden by perfect
claim support or a high correctness score. An appropriate abstention may meet the
criterion but contributes no fictional supported claims. A nonfactual answer can be
`not_applicable` when it has no other violation; its explicit empty-claim explanation
is retained for review.

Raw replies commit before validation. Interruption after that commit reuses the reply;
interruption after assessment commit reuses the assessment. Unknown remote outcomes
retain their reservation and are never automatically resent. These are the same
[durability and budget rules](durable-evaluations.md#budget-and-recovery-semantics) as
generic rubric evaluations.

## Metrics and migration

Reports include the following metrics under `metrics`, both overall and per criterion,
stream, tag, and persona. Every metric includes its numerator, denominator, aggregation,
unit, direction, and value. No denominator means `value: null`.

| Metric | Definition |
| --- | --- |
| `grounding.quantity_traceability` | Source- or question-matched quantities / recognized quantities, including ambiguous ones |
| `grounding.citation_resolution` | Resolved numbered references / numbered references |
| `grounding.question_quantities` | Count attributed to user input; denominator is assessed answers |
| `grounding.ambiguous_quantities` | Count needing interpretation; denominator is assessed answers |
| `faithfulness.claim_support` | Supported claims / all extracted claims, weighted by claims across answers |
| `faithfulness.correctness` | Mean 0–10 correctness over applicable assessed answers |
| `faithfulness.answers_question` | Answered questions / applicable assessed answers |
| `faithfulness.dangerous_answers` | Count flagged dangerous; denominator is valid assessments |
| `faithfulness.appropriate_abstentions` | Appropriate abstentions / abstentions |

Coverage retains missing capture, missing evidence, invalid judgments, budget blocking,
and `needs_review` in the unavailable population. No applicable results produces an
inconclusive decision. A reviewed evaluation passes only with at least one met result,
no violations, and no unavailable applicable results. Drafts cannot pass.

These metrics intentionally differ from legacy scores: no perfect empty populations,
no silent malformed-JSON defaults, no clamp of invalid correctness scores, explicit
0–10 correctness units, and claim-weighted support instead of an average of answer-level
ratios. Old `run` results are not numerically interchangeable with these assessments.
Other legacy scorers and their budgets are unchanged; the durable budget scope is
`durable_evaluations` and includes all judged criteria on this capture.

New evaluations record engine revision `evaluators-v2`, including frozen metric
descriptors and case identities. Saved `rubric-v1` and `evaluators-v1` evaluations
remain inspectable. To continue work under the new engine, explicitly create a new
evaluation; unchanged generic rubric requests can reuse previously saved raw replies
within the original budget. Digests verify the saved wire representation before new
optional schema defaults are added. The additive records use evaluation table version 1;
no capture data or old results are rewritten.

## Qualification work

The repository's mutation tests cover sign/unit/range errors, empty/malformed evidence,
question provenance, fabricated judge evidence, abstention/danger decisions, mixed
budgets, and process-kill recovery. Their mocked judgments validate software behavior;
they do not measure judge quality.
The [validation record](../plans/alignmenter-evidence-validation.md) documents the built-wheel
Atlas smoke test and its limits.

The [Atlas grounding draft](../plans/fixtures/atlas-grounding.yaml),
[faithfulness draft](../plans/fixtures/atlas-faithfulness.yaml), and
[behavior rubric draft](../plans/fixtures/atlas-rubrics.yaml) can be run against the
[saved observed failures](../plans/fixtures/atlas-observed-failures.jsonl). Inspect full
inputs, assessments, and raw replies with `evaluation-status --details`. Product review
must label expected behavior, claim support, practical correctness, appropriate abstention,
and consequential errors before these can become reviewed release gates. Judge agreement,
claim-extraction coverage, and threshold selection remain qualification work. Synthetic
regression fixtures are not a substitute for that review or a clinical gold set.
