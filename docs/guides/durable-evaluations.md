# Durable evaluations

Evaluate saved application answers against explicit behavior criteria, with a shared
judge budget and reusable results. Each criterion produces a verdict tied to a frozen
answer, conversation, rubric revision, judge configuration, and request. Reports and
breakdowns read those saved verdicts and make no judge calls.

This path supports generic rubrics and [built-in grounding and faithfulness](grounding-faithfulness.md).
Existing `alignmenter run` scorers remain available with their legacy accounting and result contracts.
Their historical calls are not retroactively included in the new budget. The budget's
reported scope is `durable_evaluations` on one capture run.

## Capture, evaluate, inspect

```sh
alignmenter capture --dataset conversations.jsonl --persona persona.yaml --out reports

alignmenter evaluate reports/<run-directory> \
  --spec rubrics.yaml --judge-factory my_eval.judge:make_judge --max-judge-calls 20

# Repeat the same command after interruption; omit budget options to reuse its limits.
alignmenter evaluate reports/<run-directory> \
  --spec rubrics.yaml --judge-factory my_eval.judge:make_judge

# These commands only read saved data; they do not load the judge factory.
alignmenter evaluation-status reports/<run-directory>
alignmenter evaluation-status reports/<run-directory> --json
alignmenter evaluation-status reports/<run-directory> --details > evaluation.json
```

`evaluate` returns an evaluation UUID. Use `evaluation-status --evaluation-id UUID` to
inspect an older evaluation; the default is the latest saved evaluation. Detailed JSON
includes the frozen inputs, exact raw replies, result reasons, and evidence citations.
It is a review export, not an importable checkpoint or a complete portable run archive.

The evaluation command exits `0` for a passing reviewed rubric, `2` for a violated
criterion, and `3` for an inconclusive evaluation. Configuration/CLI errors also return
nonzero status; inspect the error message when a command fails. The read-only status
command exits successfully when it can read the evaluation, even when its saved
decision is failing or inconclusive.

Capture and evaluation share one local coordinator lease. An active capture/resume or
evaluation process blocks a competing coordinator before it dispatches work. Read-only
summaries use one SQLite read snapshot and can be inspected while work is running.

## Versioned behavior criteria

```yaml
schema_version: 1
id: product-behavior
revision: draft-1
qualification: draft
scope: turn
streams: [primary]
sample: 0
criteria:
  - id: respects_user_constraints
    revision: draft-1
    rubric: >-
      Mark met when the answer's main steps respect the user's stated resources
      and limitations. Mark violated when an essential step contradicts them.
      Repeating a constraint in the introduction does not compensate for a
      procedure that depends on an unavailable resource.
    evidence_requirement: conversation
    allow_not_applicable: false
```

The first supported scope is **one assistant turn with its saved conversation history**.
Every planned assistant turn in the selected streams gets a result slot, including an
answer missing from an interrupted capture. The original dataset's answer is never
substituted for a missing generated answer. `streams` defaults to `[primary]`; explicitly
select `[primary, compare]` to evaluate both under the same budget. Decisions cover all
selected streams; baseline/candidate comparison policies are separate future work.

Evidence requirements are explicit:

| Requirement | Eligibility |
| --- | --- |
| `conversation` | A committed answer with its saved conversation |
| `context` | A committed answer with provided context, including an explicitly empty object |
| `complete_context` | Context declared complete by the capture contract |

This table describes generic rubric eligibility. Built-in grounding and faithfulness
also require a readable passage collection and nearest user question, as specified in
their [evidence contract](grounding-faithfulness.md#visible-evidence-contract).

Legacy observations have unknown evidence completeness, so they cannot satisfy
`complete_context`. Provided context does not establish completeness or relevance.
This evaluator sends the complete saved context without silently truncating it; an
endpoint context-limit error remains unavailable work rather than a shortened evaluation.
Future evidence selection must make its limits explicit.

The judge returns a strict JSON object:

```json
{
  "outcome": "violated",
  "rationale": "The proposed essential step conflicts with the stated constraint.",
  "evidence": [{"source_id": "answer", "quote": "an exact quote from the saved answer"}]
}
```

Allowed outcomes are `met`, `violated`, and explicitly permitted `not_applicable`.
Missing fields, unknown fields, malformed JSON, duplicate JSON keys, invented source
IDs/quotes, and truncated or refused replies do not become successful verdicts. Met and
violated verdicts require evidence. Source IDs identify `answer`, `context`, or a
`turn:<ordinal>` from the supplied conversation. Quotes are checked against those exact
saved sources; this verifies attribution, not the judge's reasoning or the claim's truth.

Conversation and retrieval content are marked as untrusted data in the judge prompt.
That prompt boundary is not proof of resistance to injection. Product/judge qualification
against reviewed adversarial and ordinary cases remains required.

An executable [Atlas rubric draft](../plans/fixtures/atlas-rubrics.yaml) covers resource
constraints, practical task usefulness, and visible source support. It complements the
[Atlas acceptance design](../plans/alignmenter-next-atlas.md); it is not a reviewed gold
set or a qualified judge. A draft rubric cannot produce a passing decision, including
in criterion/tag/persona breakdowns. A recorded violation still produces failure.
`qualification: reviewed` is an explicit owner declaration; the toolkit does not perform
or independently verify the human qualification process.

## Judge adapters

A factory is an importable zero-argument function that constructs an adapter without
making evaluation requests. For an OpenAI-compatible local judge, for example:

```python
import os
from openai import OpenAI
from alignmenter.providers.durable_judge import ChatCompletionJudge


def make_judge():
    client = OpenAI(
        base_url=os.environ["ALIGNMENTER_JUDGE_BASE_URL"],
        api_key=os.environ.get("ALIGNMENTER_LOCAL_API_KEY", "not-needed"),
    )
    return ChatCompletionJudge(
        client=client,
        model=os.environ["ALIGNMENTER_JUDGE_MODEL"],
        revision=os.environ["ALIGNMENTER_JUDGE_REVISION"],
        max_completion_tokens=2048,
        timeout=60,
        json_mode=True,
    )
```

The adapter disables SDK retries and does not fall back from JSON mode to another
request. Set `json_mode=False` explicitly if the endpoint requires it; this changes
the judge identity. The SDK provides `max_retries=0` and per-client/per-request timeout
configuration. [Official Python SDK documentation](https://developers.openai.com/api/reference/python#retries).

Unsupported endpoint/model parameters yield a recorded failure without an implicit
second request. The deployment revision must cover pinned model behavior and any custom
client/transport configuration. The adapter additionally hashes the endpoint, model,
SDK version, organization/project, timeout, token limit, and JSON mode. It cannot verify
that a deployment matches its declared revision. Custom transports must not introduce
their own hidden inference retries.

`ChatCompletionJudge` records returned usage but has no inferred pricing or monetary
upper bound. Use its call-count budget or supply a bounded-cost custom adapter. There
is no network dispatch during the repository's adapter tests: they use a mocked HTTP
transport to verify success and one request on rate-limit failure.

Custom backends implement `contract: JudgeContract` and
`evaluate(request: JudgeRequest) -> JudgeReply`, or use `CallableJudge(function, contract)`.
The contract declares a nonsecret configuration digest, model identity, at most one
outbound dispatch per invocation, and an optional cost upper bound. Disable SDK retries,
fallbacks, and implicit repair calls inside the adapter. Its well-typed reply preserves
raw text, finish reason, optional usage, and optional actual cost. Invalid transport
payloads are unavailable; a well-typed reply's raw verdict is saved before validation.

The configuration digest must cover the adapter code, deployed model, inference settings,
transport policy, and any pricing assumptions. It is an adapter-owned declaration, not
introspection of an arbitrary provider object. Credentials are not part of the snapshot.
Provider exceptions store their class, not arbitrary messages or headers.

## Budget and recovery semantics

The first judged evaluation requires an explicit `--max-judge-calls`. Deterministic
grounding alone needs no judge or budget and leaves limits unconfigured. Later evaluations on the
same capture use that frozen budget across criteria, selected streams, revisions,
intentional samples, and restarts. Report grouping never reserves a call. Existing
legacy scorer-local budgets are separate and retain their previous behavior.

Every new request is reserved in a transaction **before** dispatch. Reservations are
conservative: a crash before the request reaches the provider still consumes one call.
Completed identical requests can reuse a saved raw reply without another reservation.
The cache key includes the exact request and judge contract; different rubric requests,
judge configurations, or intentional `sample` values cannot silently share a reply.

| Saved boundary | Continuation |
| --- | --- |
| Validated verdict committed | Reuse it directly |
| Raw reply committed, verdict not committed | Validate the saved reply; no new judge call |
| Request reserved, no reply committed | Record `unknown_outcome`; retain its budget charge |
| Invalid/truncated verdict | Preserve the raw reply and invalid result; no automatic repair |
| Budget exhausted | Record `budget_blocked` for the missing decision |
| Late reply to an abandoned request | Reject it; it cannot overwrite a terminal call |

The coordinator never repeats an unknown judge outcome automatically. To request an
intentional new judgment, change `sample` and pass `--new-evaluation`. Changed rubrics,
judge configuration, engine/package identity, or capture inputs also require explicit
`--new-evaluation`. All such evaluations share the original remaining budget. Budget
top-ups are not implemented in this slice. A changed rubric qualification can reuse
unchanged judge requests while preserving the separate evaluation manifests.

Optional `--max-judge-cost-micros` uses integer millionths of USD and requires the
adapter to declare a valid maximum cost per invocation. An estimate is not an upper
bound. Unknown actual cost retains the full reservation; known actual cost replaces it
for subsequent accounting. If the provider exceeds its declared bound, the actual cost
is retained, the result is invalid, and further uncached dispatch is blocked. The toolkit
cannot undo external spend caused by a false adapter declaration.

Reports distinguish known actual cost, calls with unknown actual cost, and accounted
cost including reservations. A missing cost is never reported as a measured zero.
Unknown limits/cost bounds cannot bypass a configured monetary budget.

## Saved results and decisions

Rubric records live in the existing authoritative `run.sqlite3`. Explicit evaluation
initialization adds a transactionally created extension with its own schema version,
currently `1`, to capture database version `2`. Capture schemas, observations, and capture
state are preserved. Read-only inspection does not create extension tables. Unsupported
extension versions are rejected; version 1 capture databases remain read-only.

The extension stores evaluation manifests, frozen inputs, judge reservations/raw replies,
and immutable per-criterion results, with content digests. A captured run can have several
evaluation snapshots; inspecting an older evaluation uses its saved coverage even if
capture was later resumed. A new evaluation against the additional capture requires an
explicit new snapshot, and can reuse unchanged judge requests within the same budget.

Result states include `met`, `violated`, `not_applicable`, `missing_capture`,
`missing_evidence`, `invalid`, `budget_blocked`, `unknown_outcome`, and built-in
`needs_review` (unavailable interpretation). A not-yet-committed
result appears as `pending` in summaries. Unavailable reasons are retained for inspection.

Coverage is judged applicable items divided by planned items excluding explicit
`not_applicable` results. Met rate uses judged items only and must be read alongside
coverage. With no applicable or judged items, the corresponding rate is unavailable.
Any violation makes the decision fail. Passing requires at least one judged item, no
unavailable applicable item, and a reviewed rubric. All other cases are inconclusive.
This rule is applied consistently to the selected streams and all breakdowns.

The Python equivalents are `evaluate_saved`, `evaluation_summary`, and the typed
contracts in `alignmenter.schemas.evaluation`. `EvaluationStore` exposes saved calls,
results, manifests, and budget summaries for inspection. Its low-level mutation methods
require coordinator ownership; the public execution service acquires the lease.

Grounding and faithfulness now have typed assessments and pure saved metrics on this
path; see their [migration notes](grounding-faithfulness.md#metrics-and-migration), including
inspection of older `rubric-v1` evaluations. Remaining work includes adoption by legacy
`run`, authenticity/safety migration, broader evaluator scopes, qualified judges, budget
revisions. Saved comparison statistics, offline HTML review, human annotation, and
CI gates are available in the [0.3 release workflow](release-workflow.md).
