# Execution backend decision

Status: selected engineering direction, 2026-09-06 local date. Executable spike complete.
Implements the [decision protocol](alignmenter-next-executor.md). Measurements were
recorded on 2026-09-07 UTC; see the exact environment and source hashes in
[machine-readable results](executor-spike-results.json).

## 1. Decision

**Evolve Alignmenter's execution path for the first release.** Use a small coordinator
with authoritative SQLite records and explicit adapter capabilities. Preserve useful
provider interfaces, then replace the current late-persistence path incrementally.
The spike does not become the production implementation unchanged.

Keep Inspect optional for a later demonstrated workflow. Do not add it to Alignmenter's
core install or maintain two production schedulers now. This decision concerns the
current Atlas-oriented execution path; it is not a general ranking of evaluation frameworks.

## 2. Evidence

The reproducible harness in `spikes/executor/` exercised both options against
the same external-target and judge fixtures. Both needed the shared durable state,
resource, request identity, recovery, evidence, and budget mechanisms to meet the contract.

| Acceptance | Native loop + shared guards | Inspect + shared guards |
| --- | --- | --- |
| E01: frozen plan before dispatch | Pass | Pass |
| E02: committed answer survives SIGKILL | Pass | Pass |
| E03: uncertain action is not blindly replayed | Pass | Pass |
| E04: old response cannot replace a new attempt | Pass | Pass |
| E05: two runs share exclusive device ownership | Pass | Pass |
| E06: identical questions have distinct identities | Pass | Pass |
| E07: stateful restart preserves safe boundaries | Pass | Pass |
| E08: racing judges and resumed work share the cap | Pass | Pass |
| E09: cache hits and intentional repeats are distinct | Pass | Pass |
| E10: absent/empty evidence, invalid verdict, timeout | Pass | Pass |
| E11: saved projection/comparison/export makes no calls | Pass | Pass |
| E12: partial run resumes without original logs or buffers | Pass | Pass |
| E13: changed configuration cannot silently resume | Pass | Pass |
| E14: new output does not inherit old context or judgment | Pass | Pass |

Additional tests cover a judge accepted immediately before SIGKILL, conservative unknown
cost accounting, bounded cost reservations with actual-use settlement, strict booleans,
export tampering, and a kill immediately after the final answer commit. Every table
result is scoped to these deterministic local fixtures.
The saved JUnit and source hashes identify the measured implementation.

From the repository root, reproduce the measured environment and acceptance checks with:

```sh
python3 -m venv .venv/executor-spike
.venv/executor-spike/bin/python -m pip install -r spikes/executor/requirements.lock
.venv/executor-spike/bin/python -m pytest spikes/executor/tests -q
```

`spikes/executor/README.md` also explains how to preserve JUnit output and regenerate
the measurement snapshot. The lock was exercised with Python 3.14.6 on macOS arm64.

The final-answer boundary test initially exposed a defect in the shared prototype:
saving the answer and marking its sample complete in separate transactions replayed
the completed answer after a kill. Committing those transitions together fixed both
backends. The regression remains in the harness and is part of the production contract.

An independent **unguarded Inspect retry probe** also made real subprocess kills. It
dispatched A and B, killed the coordinator after the external target accepted B, then
called `eval_retry`. The external dispatch counter changed as follows:

| Sample | Before retry | After retry |
| --- | --- | --- |
| A, completed | 1 | 1 |
| B, accepted but outcome not recorded | 1 | 2 |
| C, not started | 0 | 1 |

Completed-sample reuse worked, and the original log remained unchanged. Default retry
also repeated the uncertain external request. That can be appropriate for a replayable
model sample, but an application adapter must declare whether it is safe. The guarded
Inspect prototype therefore uses the Alignmenter ledger to decide what may run again.
The finding is about the tested default configuration, not every possible Inspect integration.

## 3. Why choose the native path when both passed?

For the current workload, the native branch is a sequential loop over pending samples.
Inspect adds task/solver mapping and diagnostic logs, while the tested integration still
uses our ledger for pending work, selected attempts, unknown outcomes, budgets, and export.
It does not remove enough owned machinery to justify becoming a core dependency yet.

The native prototype's execution/storage layer uses the Python standard library.
The measured Inspect dependency closure contains 79 installed distributions, approximately
188.5 MiB of package-recorded files on this machine. This excludes some incidental files
and is an environment measurement rather than a portable package-size guarantee. Inspect's
broader facilities can justify that footprint for other workloads; Atlas currently needs
one leased device and reliable saved evaluation.

This is an inference from the implemented integrations and the present application needs.
The experiment did not compare parallel model throughput, large agent graphs, remote
sandboxes, or every Inspect extension point. A real AverCare workflow that benefits from
those facilities could justify an optional adapter through the same public contracts.

## 4. Ownership and implementation boundary

| Concern | Selected owner |
| --- | --- |
| Frozen plans, attempts, selected observations, usage reservations, result history | Alignmenter transactional store |
| Large immutable evidence and raw-response payloads | Content-addressed artifacts referenced from committed records |
| Dispatch eligibility, bounded retries, deadlines, cancellation, resources | Small Alignmenter coordinator plus capability-aware target adapters |
| Device request correlation, reset, idle acknowledgment | Atlas bridge adapter and app-side hook |
| Rubric semantics, evaluator identity, coverage, release decisions | Alignmenter evaluation/analysis contracts |
| CLI, SDK, portable reports, CI | Consumers of the same services and saved snapshots |

The experiment stored its small payloads inline in SQLite to keep export/recovery
testable without implementing a production artifact service. Production must define
the database/artifact commit boundary and garbage-collection policy before large payloads move out.

The first production change should introduce versioned observation/attempt/status
contracts and durable run creation behind the existing entry point. Add the timeout and
interruption fixtures as runtime regressions. Preserve the existing `ChatResponse`
text/context/usage seam through a compatibility adapter, with capabilities declared
explicitly rather than inferred from the legacy protocol.

## 5. Limits and remaining M0 work

The prototype uses dictionary fixtures and a deliberately narrow schema; it does not
provide production migrations, robust concurrent initialization, general plugin schemas,
real judge qualification, or a complete report renderer. It is outside the installed package.

File locking was exercised for sibling runs on one macOS host. Production needs a
configured resource namespace. The target acknowledges reset locally; real device
quiescence, deadlines, cancellation, and uncertain side effects still need app-side tests.
The declared safe-restart flag is a fixture capability, not a claim about current Atlas.

Cost tests use synthetic integer tariffs and declared output bounds. They distinguish
reservations, actual costs, unavailable prices, and exceeded bounds. A hard monetary
guarantee requires a provider whose complete usage is actually bounded and observed;
the spike makes no such claim about a real provider.

The selected backend resolves this part of M0. Still needed: product/domain review of
the Atlas expectation labels, public schema/compatibility details, and the AverCare
workflow once its repository is available. Atlas durability work can proceed using
deterministic fixtures while behavioral labels are reviewed.
