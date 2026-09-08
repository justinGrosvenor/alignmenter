# Executor acceptance spike

An isolated comparison of a minimal native loop and Inspect `0.3.263`, both using the
same target guards, durable ledger, and evaluation fixtures. This package is outside
Alignmenter's installed source tree and does not change its CLI or dependencies.

Read the [decision and measurements](../../docs/plans/alignmenter-next-executor-decision.md)
and the [acceptance protocol](../../docs/plans/alignmenter-next-executor.md).

## Reproduce

From the repository root, using Python 3.14.6 (the measured environment):

```sh
python3 -m venv .venv/executor-spike
.venv/executor-spike/bin/python -m pip install -r spikes/executor/requirements.lock
.venv/executor-spike/bin/python -m pytest spikes/executor/tests -q --basetemp=reports/executor-spike/acceptance-final --junitxml=reports/executor-spike/acceptance-final.xml
.venv/executor-spike/bin/python -m spikes.executor.record_results --junit reports/executor-spike/acceptance-final.xml --output docs/plans/executor-spike-results.json
.venv/bin/ruff check spikes --config alignmenter/pyproject.toml
```

The `--basetemp` directory is owned by this harness and pytest replaces it on rerun.
Use a different path to preserve an earlier set of artifacts. `requirements.txt` lists
the direct experiment dependencies; `requirements.lock` records the full measured
environment. The lock has been exercised on macOS arm64 with Python 3.14, not a cross-platform matrix.

All targets and judges are deterministic local fixtures. Worker processes reject IP
socket connections/binds through a Python audit hook; Inspect uses `mockllm/model`
without generating remote responses. No credentials or physical device are required.
The Python audit hook is a guard for these controlled fixtures, not a general sandbox.

## What is being compared

- `engine.py`: target boundary, OS file leases, safe-session restart, judge fixture,
  pure report/compare projections, and the two small execution branches.
- `store.py`: authoritative SQLite plan/attempt/observation/result/call records,
  count/cost reservations, response fencing, and verified snapshot export.
- `inspect_tasks.py`: public Inspect tasks and solvers, plus the unguarded retry probe.
- `worker.py`: child process boundary and explicit local judge execution.
- `tests/`: E01–E14 for both backends, additional checks for each, and one
  characterization of unguarded Inspect retry. These tests are separate from the core
  package's default suite because the experiment has its own optional environment.

The parent waits for a pipe barrier after an independent target acceptance or an
observation commit, then sends SIGKILL. There are no sleep-based assumptions about when
the request was accepted. The target's dispatch log is separate from the run ledger.

In the guarded Inspect option, the Alignmenter ledger is authoritative and Inspect
logs are derivative diagnostics. Fresh tasks select pending samples from the ledger;
Inspect's default retry path is not used for external application actions. That choice
is necessary to the tested integration and is included in the maintenance assessment.

The fixtures exercise contract boundaries. Their narrow support judge is not an LLM
judge; their report is JSON rather than the production HTML/CI renderer; their device
reconciliation is a local acknowledgment. The decision document lists what production
implementation still requires. Do not copy the spike wholesale into the runtime.
