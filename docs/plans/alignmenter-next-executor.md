# Execution backend decision protocol

Status: protocol completed by the 2026-09-06 executable spike. This document preserves
the acceptance questions; the [decision and measurements](alignmenter-next-executor-decision.md)
select the native execution path for the first release.

## 1. Decision to make

Compare two bounded implementations of the same fixture suite:

- **Evolve Alignmenter:** preserve usable providers and adapters, add a small durable
  execution path behind current entry points, and use one authoritative call ledger.
- **Compose with Inspect:** use Inspect's execution and sample/log facilities behind
  Alignmenter's public contracts, with an Atlas target bridge and explicit semantic mapping.

Prefer composition if it meets the required contracts through documented interfaces with
less ongoing maintenance. Prefer evolving the runner if composition would require a
parallel scheduler, competing authoritative histories, or pervasive patches to the backend.
This was the decision rule applied in the completed spike.

Keep Alignmenter's ownership clear: behavior specs, scenario relations, evidence and
coverage meanings, judge qualification, application adapters, review, and release policy.
An external executor need not natively name every Alignmenter status if a lossless mapping
and a small extension can preserve their meaning.

## 2. Evidence available now

| Capability | Documented or observed evidence | What remains to prove |
| --- | --- | --- |
| Completed-sample reuse | Inspect documents stable sample IDs and retry into a new log | Map retries into one visible Alignmenter run without overwriting history |
| Abrupt crash recovery | Inspect documents a sample buffer and recovery of unflushed records | Commit acknowledgment, retention, and export must meet our durability contract |
| Custom application execution | Inspect supports custom solver functions and state | Atlas device lease, request identity, reset, and unknown-outcome handling |
| Deferred evaluation | Inspect supports scoring saved logs | Immutable evaluation snapshots, explicit coverage, pure downstream reporting |
| Execution limits | Inspect documents token, cost, time, and custom limits | Run-wide reservations across target/judge/retry work, including external calls |
| Current Alignmenter path | Inspection reproduced late persistence and repeated scoring during breakdowns | Smallest correction that supplies the same accepted contracts |

Sources: [Inspect logs and retry identity](https://inspect.aisi.org.uk/eval-logs.html),
[crash recovery](https://inspect.aisi.org.uk/handling-errors.html),
[custom solvers](https://inspect.aisi.org.uk/solvers.html),
[saved-log scoring](https://inspect.aisi.org.uk/scoring-workflow.html), and
[execution limits](https://inspect.aisi.org.uk/setting-limits.html).

Two distinctions matter for the spike. Inspect's documented sample buffer has limited
retention (three days after process exit), so recovery availability must be tested against
the durable record promised by Alignmenter, including a delayed restart. Its documented
sample cost checks around model generation do not by themselves establish a durable
run-wide reservation guarantee for arbitrary external Atlas or judge calls. These are
integration questions, not assertions that Inspect cannot support the required behavior.
[Recovery details](https://inspect.aisi.org.uk/handling-errors.html),
[limit semantics](https://inspect.aisi.org.uk/setting-limits.html).

The subsequent executable spike pinned Inspect 0.3.263. Its results and limitations are
recorded in the [decision note](alignmenter-next-executor-decision.md); documentation
availability alone was not treated as a passing acceptance test.

## 3. Identical acceptance harness

Use deterministic local targets and judges, a separate dispatch counter that survives
coordinator death, and a fake single-device resource. Inject faults at named boundaries,
including process termination; raised Python exceptions alone do not test crash recovery.
Disable real provider calls. Use event barriers rather than timing-dependent sleeps.

| ID | Fixture and interruption | Required observable result |
| --- | --- | --- |
| E01 | Create run; fail before first dispatch | Durable planned population and configuration; zero calls |
| E02 | Commit answer A; kill process during B; restart | A reused with identical artifact; B has explicit attempt history; C can proceed |
| E03 | Target accepts B; coordinator dies before response | Unknown outcome retained; no blind replay for a target lacking idempotency |
| E04 | Response to expired attempt arrives after retry begins | Original request ID retained; old response cannot replace the selected new attempt |
| E05 | Two runners compete for one fake device | Only one active resource holder; takeover reconciles target state before dispatch |
| E06 | Identical question text in two repetitions | Distinct request IDs and observations; no stale-file acceptance |
| E07 | Die during turn two of a stateful case | Restore a declared checkpoint or restart from a safe session boundary; account for replay |
| E08 | Two evaluators race for one remaining judge call; resume afterward | At most one new dispatch; durable reservation and retry accounting; other work unavailable |
| E09 | Cached judgment plus deliberate repeated judgment | Cache hit costs zero new calls; deliberate repeat remains a separate sampled call |
| E10 | Missing context, empty retrieval, malformed verdict, timeout | Four distinguishable outcomes; no unavailable required result becomes a pass |
| E11 | Render, slice, compare, export twice with providers disabled | Identical selected verdicts, zero new calls, all missing/failed populations retained |
| E12 | Export partial run; remove working directory; import in fresh process | Referenced artifacts verified; committed observations and recovery history survive |
| E13 | Change target configuration and attempt resume | Reject incompatible continuation or create an explicitly linked new run |
| E14 | Reuse an attempt slot for new generation without returned context | Old evidence and usage cannot attach to the new observation |

E08 tests an enforceable **dispatch-count** cap. Add a deterministic token/cost fixture
to distinguish reservation bounds from actual final usage: unknown provider cost remains
unknown, and a soft estimate must not be labeled a hard monetary cap. SDK-internal retries
must be disabled, intercepted, or explicitly counted for a strict dispatch guarantee.

E02's commit means a documented acknowledgment that survives the declared crash model,
not merely a returned model answer. E12 includes recovery after transient backend buffers
would expire. A checkpoint, artifact, or log path that only exists in the original working
directory does not satisfy the portable recovery contract.

## 4. Prototype boundaries and deliverable

Build only enough of each option to run the harness: one target adapter, one judge,
one stateful session, a minimal result projection, and snapshot export/import. Reuse the
same fixture definitions and dispatch recorder. Do not build a full renderer, provider
catalog, plugin marketplace, or production migration within this spike.

For every E01–E14 row, record **pass**, **fail**, or **not tested**, with commands, pinned
versions, retained artifacts, and code references. A backend is eligible only when required
semantics pass; ease of setup cannot compensate for a silent wrong result. Conditional
capabilities are acceptable when declared accurately and supported by the Atlas path.

Compare eligible options on:

- Amount and complexity of production-owned code, including adapters and duplicate state.
- Documented extension points versus private hooks or a maintained fork.
- Number of authoritative lifecycle and budget writers; recovery/export consistency.
- Core installation footprint and offline operation.
- Diagnostics for failed attempts and incomplete observations.
- Migration effort for current provider, persona, custom-scorer, and Atlas integrations.
- Ability to support one verified AverCare workflow without changing result meanings.

Record implementation effort and rough code volume as evidence, without treating fewer
lines as automatic superiority. The final decision note states the selected option,
failed alternatives, known limitations, storage ownership, and the first production slice.
If neither option passes, identify the smallest missing mechanism and repeat its failing
fixtures; do not resolve the decision by quietly weakening the acceptance contract.

## 5. Consequences for implementation

The proposed SQLite/artifact design in the target state is provisional. The chosen
implementation may use a backend's durable storage plus a rebuildable Alignmenter index,
or an Alignmenter store with immutable backend artifacts. In either case, declare the
single authority for each record and the commit/recovery boundary. Avoid dual writes
that can each claim success while disagreeing after a crash.

The backend decision is now complete. Backend choice should not delay reviewing Atlas behavior,
freezing observed failures, or defining statuses and coverage; those are shared contracts.
The first production acceptance remains an interrupted Atlas-style run that preserves
completed work and tells the truth about everything it could not measure.
