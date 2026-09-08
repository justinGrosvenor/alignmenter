# Quick Start

Use Python 3.10–3.14 on macOS or Linux for the durable workflow. The example needs no
API key or local model download.

## Install and run

```bash
pip install alignmenter
alignmenter --version
alignmenter init-suite --out evals/resource-task
alignmenter run-suite evals/resource-task/suite.yaml --out reports
```

The generated suite uses an installed Python target that chooses available resources.
Its deterministic evaluator checks that exact constraint. A successful run exits 0 and
prints JSON with its `run_dir`, `evaluation_id`, `decision`, and `artifacts` directory.
Open `index.html` in that directory. `evaluation.json`, `summary.md`, and `junit.xml`
carry the same decision for automation.

## See a regression

```bash
ALIGNMENTER_DEMO_VARIANT=bad alignmenter run-suite evals/resource-task/suite.yaml --out reports
```

The example's bad variant requires unavailable equipment and exits 2. This is a
purposefully engineered failure, not an AI quality benchmark.

Compare the saved run directories printed by the two commands:

```bash
alignmenter compare BASELINE_RUN CANDIDATE_RUN --out reports/comparison
```

The offline report pairs answers by case and shows why they failed. Inspection and
comparison do not execute either the target or evaluator again.

## Connect your application

Replace the suite's target and evaluator factories with your own importable Python
adapters, or omit the target to evaluate recorded assistant answers. Start new product
criteria as `qualification: draft` and supply human references before making claims
about judge reliability. Inconclusive work exits 3, so CI cannot mistake it for a pass.

The [release workflow](../guides/release-workflow.md) covers suite configuration,
judged criteria, budgets, human review, regression promotion, and CI. The
[SDK reference](../reference/sdk.md) includes adapter examples. Existing persona users
can keep using `init` and `run`; see the [migration guide](../guides/migration-0.3.md)
and [CLI reference](../reference/cli.md) for their compatibility limits.
