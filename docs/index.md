# Alignmenter

**Application alignment evaluations with saved evidence, human review, and CI gates.**

Check whether your assistant meets the commitments of its application: respects
constraints, uses available resources, supports claims, and avoids dangerous advice.
Alignmenter 0.3 captures answers once and preserves the evidence behind each outcome.

```bash
pip install alignmenter
alignmenter init-suite --out evals/resource-task
alignmenter run-suite evals/resource-task/suite.yaml --out reports
```

This example runs offline with a local target and a deterministic resource check.
The command prints its run directory and HTML/JSON/Markdown/JUnit artifact paths.
Exit codes are **0 pass, 2 fail, 3 inconclusive**. Missing work and draft specifications
cannot produce a green release check.

- Capture and explicitly resume under frozen application and recovery contracts.
- Evaluate saved answers with strict judged criteria or application-owned checks.
- Compare matched cases against a baseline, retaining missing populations and evidence.
- Review disagreements, append human adjudications, and promote regression cases.
- Apply one versioned gate policy across SDK, CLI, and CI reports.

The Python core is lightweight; heavy ML dependencies are optional. Reports can be
inspected offline without model or application calls. Legacy persona and calibration
APIs remain available with their older contracts.

Start with the [quickstart](getting-started/quickstart.md), then configure the
[application release workflow](guides/release-workflow.md) or use the
[Python SDK](reference/sdk.md). Existing users should read the
[0.3 migration guide](guides/migration-0.3.md).

An executable fixture demonstrates engineering behavior, not model quality. Atlas's
preserved failures and draft rubrics are integration inputs; independent product-owner
labels and actual judge outputs are still needed for qualification.
