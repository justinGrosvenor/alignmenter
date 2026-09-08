# Durable run capture

`alignmenter run` now creates its durable execution records before calling a chat
provider. Each returned answer, its observed context/usage, and its successful attempt
are committed together before the progress callback runs. A later generation, scorer,
or reporter failure leaves that committed work available.

## Inspect and recover captured transcripts

Use the run directory printed on a handled failure, or the directory under your chosen
`--out` path after a hard kill:

```sh
alignmenter status reports/<run-directory>
alignmenter status reports/<run-directory> --json
alignmenter export-transcripts reports/<run-directory> --out recovered.jsonl
alignmenter export-transcripts reports/<run-directory> --stream compare --out comparison.jsonl
```

These commands read saved records without invoking providers or scorers. Export refuses
to replace an existing file unless `--force` is supplied. A partial export contains only
committed records; it may end with a user turn whose assistant answer was never captured.
It never substitutes an old dataset answer for a failed generation.

`status` reports the **last committed state**, not process liveness. An abrupt kill can
leave a run and its active attempt marked `running`; the JSON result includes
`liveness: "not_checked"`. Handled interruptions finalize the run as `interrupted`.
A legacy provider exception leaves its attempt `unknown_outcome` because that interface
cannot prove whether the external action stopped. Returned but invalid responses are
classified separately as failed attempts.

Recorded inputs and adapters with explicit recovery contracts now support
[capture-only resume](capture-recovery.md). Legacy providers do not acquire retry or
session-replay guarantees automatically. Re-running `run` creates a new directory and
starts fresh work. Successful execution means the pipeline completed; quality thresholds
remain separate from execution status. Capture-only completion has status `captured`.

## Saved records

| Artifact | Meaning |
| --- | --- |
| `run.sqlite3` | Authoritative manifest, planned inputs, attempts, observations, committed transcript records, and state history |
| `manifest.json` | Human-readable snapshot of the versioned manifest |
| `run.json` | Existing report metadata, with a reference to the durable database |
| `transcripts/*.jsonl` | Derived completed or partial transcript exports |
| Existing score/report files | Outputs from the current scoring and reporting pipeline |

The database uses transactions and SQLite `synchronous=FULL`. Small source and observation
payloads are stored inline in this first implementation, so they share the same commit
boundary. A generated answer and the successful attempt cannot be committed separately.
The process-kill tests exercise this boundary through the real runner.

Source snapshots preserve parsed dataset records in canonical JSON and persona bytes
when available. The dataset digest identifies those record values and their original
order, rather than the source file's whitespace. Changing or deleting the source files
after run creation does not replace the saved inputs.

Primary and comparison streams have separate identities and transcript files, including
when both use the same model identifier. Every generated turn gets a unique local
attempt ID. Compatible retries retain the original request ID. The legacy provider
receives its existing message interface; local IDs alone do not establish app-side
request echo or idempotency guarantees.

## Evidence and provenance

An observation stores the provider's exact text; the legacy transcript retains its
existing whitespace trimming. Missing context is `None` with `context_status: missing`.
An explicitly returned empty context is `{}` with `context_status: provided`. A context
containing `excerpts: []` remains distinct from both. None of these legacy captures
asserts complete evidence: `evidence_completeness` is `unknown`.

Regenerating an answer replaces its old context, usage, generation identity, and baseline
metadata. Case metadata is preserved, and `baseline_text` records the answer actually
being replaced. Missing usage remains unavailable in the observation.
Provider responses must contain string text and JSON-compatible context/usage; invalid
responses are recorded as failed attempts rather than successful empty answers.

The manifest explicitly lists the configuration and capability gaps in legacy providers
and scorers. It does not introspect provider objects or store credentials. Failure records
store the exception class and classification; callers still receive the original exception.
The `include_raw` option continues to control the extra legacy `raw.json` file, while
transcripts and durable capture remain part of every run.

This change does not alter the existing scorers, judge budgets, threshold semantics, or
breakdown computation. The new [durable rubric path](durable-evaluations.md) adds versioned
verdicts and pure aggregation separately. Legacy scorer migration, qualified judges,
stateful recovery, and physical-device leases remain subsequent delivery slices.

## Python API

```python
from pathlib import Path
from alignmenter.storage import RunStore

store = RunStore(Path("reports/<run-directory>"))
summary = store.summary()
observations = store.observations()
attempts = store.attempts()
committed_records = store.transcripts("primary")
manifest = store.manifest()
original_dataset = store.source_artifact(manifest.dataset_digest)
```

`Runner.run_dir` is available once a run directory is created, including when `execute()`
later raises. Execution models live in `alignmenter.schemas.execution`; their
`schema_version` is currently `1`; new databases use version `2`. Version 1 databases
remain readable but are not reopened for writes. Unknown schema/database versions are
rejected rather than silently migrated. The typed JSON contract requires Pydantic 2.5 or newer.
