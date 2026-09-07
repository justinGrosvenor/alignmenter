# Alignmenter 0.3.0 release acceptance

Status: local release candidate ready, 2026-09-07. The user requested sustained work until the next
version is ready to release. This is the acceptance boundary for that version; the
broader Alignmenter Next roadmap remains in `alignmenter-next-delivery.md`.

0.3.0 delivers an installable SDK/CLI workflow for durable application evaluation,
saved comparisons, human review, regression maintenance, and CI. Atlas's preserved
failures are real integration evidence. Draft expectations and mocked judge responses
are not represented as independent human qualification.

## Required for this release

- Durable capture/recovery and judged/deterministic evaluation, preserving the existing
  interruption, evidence, strict parsing, and shared-budget guarantees.
- Application-owned evaluator registration with frozen descriptors and generic saved
  metrics, reports, comparisons, and gates; no renderer edits for a custom metric.
- Matched saved comparisons with explicit case revisions, evaluator compatibility,
  missing/added/removed populations, and honest uncertainty limits.
- Versioned absolute and regression gates; identical decisions in CLI, JSON, HTML,
  Markdown, and JUnit. Missing required work cannot yield a green CI result.
- Offline evidence reports; append-only human annotation exchange; explicit
  adjudication, evaluator qualification against references, and regression promotion
  with source lineage and split groups preserved.
- A documented SDK and noninteractive suite/CI entry point, runnable offline example,
  and portable capture/evaluation inspection artifacts.
- 0.3.0 version consistency, changelog, migration/deprecation guidance, lightweight
  wheel and source distribution, dependency and package checks, supported-Python
  validation, marketing checks, and an end-to-end release rehearsal.

## Explicit limits

Physical-device replay, multi-host scheduling, distributed budgets, a hosted review UI,
automatic prompt optimization, and the full calibration overhaul are subsequent roadmap
work. Legacy APIs remain recognizable and their older semantics must be visible;
new release workflows use durable records and explicit coverage.

Atlas judge qualification needs actual judge outputs and independent product-owner
labels. AverCare additionally needs a selected application workflow. The release ships
tools to perform and preserve that review, plus draft Atlas inputs; it must not claim
those external dependencies have been fulfilled. Publishing a package or tag is a
separate action from preparing and validating the release artifacts.

## Completion record

All release requirements above are implemented. See the
[application release workflow](../guides/release-workflow.md),
[SDK reference](../reference/sdk.md), and [migration guide](../guides/migration-0.3.md).
The local branch is `release/0.3.0`. No tag, remote push, deployment, or PyPI publication
has been performed as part of preparing this candidate.

### Validation

| Check | Result |
| --- | --- |
| Python 3.10.21 | 352 tests passed |
| Python 3.11.16 | 352 tests passed |
| Python 3.12.14 | 352 tests passed |
| Python 3.13.15 | 352 tests passed |
| Python 3.14.6 | 352 tests passed |
| Python 3.12 with calibration dependencies | 352 tests passed |
| Python lint | Ruff passed |
| Wheel and source distribution | Built; Twine validation passed; license and source-test fixtures verified |
| Installed wheel and source rehearsals | Passed in separate minimal environments; no torch/sklearn; pip check passed |
| Saved gates | Frozen policy and pinned baseline retained on inspection; non-green decisions agree across all formats |
| Python dependency audit | No known vulnerabilities in installed dependencies; unpublished Alignmenter 0.3.0 itself has no PyPI advisory record and was skipped |
| Documentation | Strict MkDocs build passed |
| Marketing | Next 16.3.4 / React 19.2.8 static export passed on Node 22; ESLint passed with one existing external SVG image warning |
| Marketing dependency audit | Zero known vulnerabilities |
| CI definitions | Python 3.10–3.14, calibration, distributions, docs, and site checks configured; YAML/shell syntax checked locally |

Tests exercise real SQLite and process termination around capture and judge commit
boundaries, plus malformed/absent evidence, shared budgets, strict plugin outputs,
saved comparisons, append-only annotations, archives, and CI decisions. Provider
boundaries are mocked; these tests do not qualify any product judge. Local tests ran
on macOS. Linux validation is configured in GitHub Actions and awaits a push; remote
CI is not claimed to have run.

The installed-package rehearsal runs a passing baseline and an engineered failing
candidate, verifies paired regressions and the saved policy, exports all review formats,
round-trips a read-only archive, and verifies that synthetic annotations do not count
as human references. Its source is `scripts/release_smoke.py`.

### Artifacts

Local artifacts are under `reports/release-0.3.0/` (ignored by Git):

- `dist/alignmenter-0.3.0-py3-none-any.whl`
- `dist/alignmenter-0.3.0.tar.gz` and `dist/SHA256SUMS`
- `validation.json`, including test runtimes, audit scope, hashes, and rehearsal paths
- `wheel-final/rehearsal.json` and `source-final/rehearsal.json`
- `atlas/grounding/index.html`, `atlas/faithfulness/index.html`, and `atlas/rehearsal.json`

Distribution SHA-256 digests:

```text
ea264c82f0cd50cfb70d0fd27ac989e4f12493305ff24e6ef74b0f54b04ba9f0  alignmenter-0.3.0-py3-none-any.whl
1e7c578b7072d81abcd53fdd8b1cb7b7d6008b9fda9f04f51563bd8d792ecddb  alignmenter-0.3.0.tar.gz
```

All 81 Python source files in the wheel and its package README were compared with the
final working tree. CI repeats installation and the release rehearsal from both
formats. The tag publish workflow checks tag, runtime, and distribution version identity
before testing, building, and uploading.

### Product qualification boundary

The final installed-wheel Atlas rehearsal preserves the two observed failures.
Grounding reports one not-applicable answer and one citation-only met answer (4/4
references resolve); quantity traceability is unavailable because no quantities were
present. The draft decision remains inconclusive. Faithfulness with an explicit
zero-call budget reports two budget-blocked cases, zero calls, and zero human
references. This validates evidence preservation and honest coverage, not the practical
quality of either answer.

Actual Atlas judge outputs and independent owner adjudications remain necessary
before product release gates can be qualified. AverCare additionally needs a selected
workflow. These external requirements and the explicit roadmap limits above are not
represented as completed features or used as reasons to manufacture labels.
