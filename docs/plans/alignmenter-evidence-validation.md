# Evidence evaluator validation record

Date: 2026-09-07. Scope: the fourth production slice of
[Alignmenter Next](alignmenter-next-delivery.md), implemented by the
[durable grounding and faithfulness evaluators](../guides/grounding-faithfulness.md).
This is an engineering validation record, not product or clinical qualification.

## Atlas observation

The built wheel imported the two [preserved Atlas failures](fixtures/atlas-observed-failures.jsonl)
through the production capture path and evaluated them through the CLI. Both committed
observations remained unchanged. No target generation or remote judge inference occurred.

| Saved case | Grounding result | What it tells us |
| --- | --- | --- |
| q31, unavailable rope | `not_applicable` | The answer has no recognized quantities or numbered citations; grounding has no measurement |
| q40, week away in winter | `met` | Four numbered citations resolve; this does not establish that the proposed actions fit the user's absence |

Across these answers, quantity traceability has denominator zero and value `null`.
Citation resolution is 4/4. The overall grounding decision remains inconclusive because
the spec is a draft. These results demonstrate why the resource-constraint and practical-task
rubrics remain necessary: simple traceability does not catch the preserved behavioral failures.

The faithfulness CLI was also exercised with an explicit zero-call budget. It preserved
two `budget_blocked` results, null quality metrics, and zero reservations. This verifies
capture/spec/report integration without fabricating semantic judgments or implying that
the Atlas faithfulness rubric has been qualified.

Local detailed exports are written to
`reports/evidence-evaluators-smoke/atlas-grounding.json` and
`reports/evidence-evaluators-smoke/atlas-faithfulness.json`. The capture directory is recorded
in `reports/evidence-evaluators-smoke/run-path.txt`. Reports are ignored build artifacts;
the original saved failures and executable specs are checked-in inputs.

## Behavioral regression coverage

`alignmenter/tests/test_builtin_evaluations.py` exercises:

- Sign changes; Celsius/Fahrenheit separation and exact conversion; SI prefixes; fixed
  time conversions; range endpoints; strict/inclusive bounds; unsupported regional or
  variable-duration conversion; ambiguous notation and compound units.
- Empty versus missing/malformed retrieval, noncompacted source indices, exact quote
  provenance, question-supplied quantities, and the nearest user turn instead of stale history.
- Offline evaluations followed by an explicit judged budget, mixed criteria sharing
  one budget, immutable assessments, pure report grouping, and draft qualification.
- Malformed faithfulness fields, invented claims/evidence, explicit abstentions,
  independent danger and correctness checks, full untruncated source text, and no
  automatic repair or repeated inference for invalid results.
- Older saved wire records verifying correctly before new optional defaults are added,
  explicit engine migration, and reuse of unchanged raw rubric replies.

`alignmenter/tests/test_durable_evaluations.py` also runs fresh-process kill/restart
tests for both generic rubrics and faithfulness. Independent acceptance logs verify
behavior before dispatch, after remote acceptance, after raw-reply commit, and after
assessment commit. Existing capture, accounting, malformed-response, and legacy tests
remain in the core suite. Judge responses in these tests are transport fixtures with
explicitly synthetic labels.

Verification commands are `python -m pytest alignmenter/tests -q`,
`ruff check alignmenter`, `python -m build alignmenter --wheel --no-isolation`, and
`python -m mkdocs build --strict`. No marketing, device, paid-model, or clinical
qualification claim is implied by these checks.

## Next acceptance boundary

Keep Atlas specs at `qualification: draft` until a product owner has reviewed the case
expectations and actual judge outputs. The next useful slice is a compact review and
qualification workflow: preserve independent labels, inspect disagreements against raw
evidence, measure missed consequential failures and inappropriate abstentions, then
freeze the accepted rubric, threshold, and judge configuration for regression use.
Use the existing observed failures and draft scenario families as seeds; do not present
synthetic test replies as an independent gold set. AverCare still needs a selected real
workflow and domain-specific review before its acceptance criteria can be qualified.

## 0.3.0 installed-package follow-up

The final 0.3.0 wheel repeated this Atlas capture and evidence exercise, exported offline
HTML/JSON/Markdown/JUnit, and preserved the same draft/inconclusive boundary. The
[release acceptance record](release-0.3.0.md) records final package hashes, 352-test
Python support checks, installed wheel/source rehearsals, and remaining product labels.
The earlier slice results above remain historical evidence, not a claim that their
package version or engine revision is the current release.
