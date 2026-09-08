# Capture and resume

Capture saves application answers and their evidence before evaluation. Use it for
expensive targets, product-owned Python adapters, or importing recorded application
transcripts. A capture completes with status `captured`; this does not mean it passed
an evaluation. Scorers, judges, and reporters are not invoked by capture or resume.

## CLI

```sh
# Import recorded answers, without calling an application.
alignmenter capture --dataset conversations.jsonl --persona persona.yaml --out reports

# Generate answers through an installed/importable product adapter.
alignmenter capture --dataset conversations.jsonl --target my_eval.target:make_target

# Check the interrupted run before doing more work.
alignmenter resume reports/<run-directory> --target my_eval.target:make_target --check

# Continue missing capture using the frozen inputs and compatible target.
alignmenter resume reports/<run-directory> --target my_eval.target:make_target
alignmenter export-transcripts reports/<run-directory> --out captured.jsonl
```

Omit `--target` when resuming recorded inputs or when every generated answer is already
committed. For an existing comparison run, pass `--compare-target module:factory` for
the incomplete comparison stream. Every incomplete generated stream is checked before
any stream dispatches new work. The standalone `capture` command creates a primary
stream; comparison capture is available through the existing SDK runner configuration.

Resume uses verified source snapshots, so the original dataset and persona files may
have moved or been deleted. Optional `--dataset PATH` and `--persona PATH` assert that
current files still match; they do not replace the frozen inputs. Changed target identity,
capabilities, configuration digest, or installed Alignmenter package version blocks
continuation. Use a new run for an intentional target change.

`--check` acquires the coordinator lock and performs preflight without writing the database
or calling the target. The target factory is still imported and constructed. Factories
must configure their adapter without making application requests. A successful check
does not reserve the run after it exits; resume checks again when it acquires the lock.
Preflight and execution errors return a nonzero exit status for CI.

## Python adapter contract

A target factory returns a `CaptureTarget`. This example wraps a product's existing
answer function; replace the import and configuration with the actual application.

```python
from alignmenter.providers.base import ChatResponse
from alignmenter.providers.callable import CallableProvider, CaptureTarget
from alignmenter.schemas.execution import RecoveryContract, content_digest
from my_app import answer_conversation


def make_target():
    # Include all behavior-affecting configuration, excluding credentials.
    configuration = {
        "app_revision": "your-build-or-commit",
        "model_revision": "your-pinned-model",
        "prompt_digest": "your-prompt-content-digest",
        "retrieval_revision": "your-index-and-retriever-revision",
        "generation": {"temperature": 0},
    }

    def chat(messages, *, request_id):
        # This example makes no idempotency promise and does not use request_id.
        response = answer_conversation(messages, **configuration["generation"])
        return ChatResponse(text=response.text, context=response.context)

    contract = RecoveryContract(
        configuration_digest=content_digest(configuration),
        session_state="stateless",
        interrupted_request="refuse",
        max_attempts=3,
    )
    return CaptureTarget("product:local", CallableProvider(chat, contract))
```

`stateless` promises that each request contains its complete conversation state; the
adapter does not depend on an unrecorded application session. Resume reconstructs the
messages from the committed conversation, including system instructions and prior
generated answers. The default `refuse` policy permits continuation after a committed
answer but blocks a previously dispatched request whose answer was not committed.

The configuration digest is an **adapter-owned declaration**. Include application and
adapter code revisions, model revision, prompts, retrieval configuration/data, tools,
generation settings, and other behavior-affecting inputs. The runner cannot discover
omitted settings or verify that a running deployment matches a declared revision.
It stores the digest, not a dump of the provider object or credentials. The Alignmenter
package-version check does not fingerprint unversioned edits to an editable installation.

To declare `interrupted_request="idempotent"`, the target must durably deduplicate the
provided `request_id`, associate it with exactly those messages, and return the original
response on repetition, including across process restarts. The wrapper only forwards
the ID; it does not implement this guarantee. Ordinary repeated model calls or sending
an otherwise unsupported request header do not establish idempotency.

Custom chat providers can expose the same typed `recovery_contract` attribute and
accept `chat(messages, request_id=...)`. Legacy providers without that declaration keep
their existing `chat(messages)` interface. Their incomplete generated streams cannot
be resumed automatically. `session_state="opaque"` explicitly records an unsupported
session-recovery contract.

```python
from pathlib import Path
from alignmenter.execution.recovery import resume_capture
from alignmenter.runner import RunConfig, Runner

target = make_target()
runner = Runner(
    RunConfig(model=target.model, dataset_path=Path("conversations.jsonl"),
              persona_path=Path("persona.yaml")),
    scorers=[], provider=target.provider,
)
run_dir = runner.capture()

# After interruption, reconstruct the target from the same configuration.
summary = resume_capture(Path("reports/<interrupted-run>"),
                         targets={"primary": make_target()})
```

`Runner.run_dir` identifies saved work when capture raises. `resume_capture(...,
check_only=True)` exposes CLI preflight to Python callers. A fully captured run is a
no-op; its previous scoring/reporting failure remains visible and is not reclassified
as evaluation success.

## Recovery guarantees and limits

| Boundary | Behavior |
| --- | --- |
| Answer committed | Reuse the same observation, attempt, and transcript record |
| Missing turn never dispatched | Call the compatible stateless adapter with a new request ID |
| Dispatched answer not committed | Require idempotent recovery; reuse the request ID and exact messages |
| Retry | Append a new attempt; retain failed/unknown attempts and enforce the frozen per-turn limit |
| Abandoned `running` attempt | Reclassify as `unknown_outcome` when an accepted resume starts under the lock |
| Late response from an earlier attempt | Cannot replace the active attempt or a committed answer |
| Scoring/reporting failed after capture | Leave that failure recorded; make no evaluation calls |
| Competing coordinator | Fail before dispatch while the other process holds the run lock |

Each resume invocation makes at most one new attempt for each missing turn, stops on
the first execution failure, and never resets the attempt limit. Preflight rejects
incompatible or unsupported work before mutating the database. A rejected preflight
can therefore leave an abandoned attempt's last recorded state as `running`; `status`
continues to report saved state with `liveness: "not_checked"`.

The coordinator lock covers fresh runs and resumed runs and is released by the OS on
process death. Keep `coordinator.lock` in place. This is a lease on one run directory
on a local filesystem. It is not a cross-machine lease or an exclusive physical-device
lease across different runs. Process-kill acceptance tests currently qualify this path
on macOS; the Windows lock branch has not been exercised in this environment.

The acceptance tests use an independent target database to distinguish transport
attempts from accepted target requests. They kill a runner before acceptance, after
acceptance, and after commit, then resume through a fresh CLI process. Additional tests
cover changed configuration, full conversation reconstruction, primary/comparison
preflight, retry limits, corrupt saved data, and stale attempt rejection.

New run databases use **database version 2**, allowing multiple attempts per turn.
The JSON record schema remains version 1 with optional recovery/plan-identity fields.
Version 1 databases remain readable through `status`, `export-transcripts`, and `RunStore`;
they are not silently migrated or reopened. Export their saved transcripts into a new
recorded run when needed. Unknown database versions are rejected. Export/import does
not claim to preserve the original run's complete attempt history.

Stateful reset/replay, physical-device leases, and portable run migration remain planned.
[Durable rubric evaluations](durable-evaluations.md) now provide shared judge budgets
and saved verdicts through a separate evaluation command. Atlas's current device
adapter has not yet established the session and request-identity guarantees needed
for automatic recovery. Its captured answers remain available for inspection/export.

To evaluate a completed capture with the current scoring pipeline, export it and run
`alignmenter run --dataset captured.jsonl --persona persona.yaml` without
`--generate-transcripts`. This explicitly creates a new evaluation and can call its
configured judges. For versioned rubric results and reusable raw judge replies, use
`alignmenter evaluate` directly on the saved run instead.
