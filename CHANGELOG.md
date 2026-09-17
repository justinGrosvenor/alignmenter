# Changelog

All notable changes to Alignmenter are documented here. This project adheres to
[Semantic Versioning](https://semver.org/).

## [0.3.4] — 2026-09-17

### Added

- Decomposed rubric grading: `alignmenter rubric-grade <dataset> --judge <model>`
  grades captured responses against per-record `metadata.rubrics` (as imported from
  HealthBench) with ONE narrow "is this criterion met?" judge call per criterion —
  making each judgment mechanical so a *cheap* gateway model can do it reliably.
  Budget-capped by call count; HealthBench-style normalized scoring (awarded /
  possible-positive points); a null/non-scalar verdict is excluded, never a silent
  not-met. `--compare-judge <model>` runs an agreement check (per-criterion match
  rate + Cohen's kappa) so the cheap judge is proven before it is trusted. New
  `rubric_grade.py` + `rubric_grade_cli.py`; judge is any Vercel AI Gateway
  `provider/model`, auth via `AI_GATEWAY_API_KEY`.

## [0.3.3] — 2026-09-17

### Added

- Dataset importers on the `dataset` sub-app: `import <source> <input> --out`
  adapts public eval corpora into Alignmenter turn records. First adapter:
  **HealthBench** (OpenAI, MIT) — rows carry physician rubrics but no reference
  answer, so each becomes a prompt session with the rubrics riding the final user
  turn's `metadata` for a later rubric evaluator. Importers never download
  (corpora are user-fetched/licensed); `--sample`/`--seed`/`--no-stratify`/
  `--manifest`. Sampling is session-level and stratified by the source's axis so a
  small sample keeps topic coverage; ids are deduped/disambiguated and selection is
  input-order-invariant for a fixed seed. New `importers/` package.
- `dataset sample` — down-sample a dataset to N whole units (session|group|persona),
  optionally pre-filtered by tag (`--filter-tag`, repeatable OR). The change-aware
  selection primitive: a random seeded subset for regular runs, or
  `--filter-tag tool:<name>` for a change-scoped subset.

## [0.3.2] — 2026-09-17

### Added

- Dataset-management commands on the `dataset` sub-app: `stats` (coverage — record/
  session counts, role balance, tag + persona histograms), `validate` (schema
  validator; lenient by default, `--strict` adds turn_index+tags+persona_id and an
  assistant turn per session; complements the existing `lint`), `dedupe` (drop
  content-identical records), `merge`
  (concatenate datasets, optional `--dedupe` / `--namespace-sessions`), `split`
  (group-aware train/holdout — a case and its variants never straddle the boundary),
  and `manifest` (a content-addressed `DatasetManifest` with provenance, plus
  `--verify`). New `schemas/dataset.py` (`DatasetManifest`, `ProvenanceEntry`,
  `build_manifest`, `dataset_digest`, `validate_records`).

## [0.3.1] — 2026-09-17

### Added

- GitHub pull-request comment reporter: `export_evaluation` now also writes
  `comment.md`, a sticky Markdown body (verdict badge, blocking issues first,
  gate and metric tables, baseline deltas, collapsed breakdowns) that opens with
  a `<!-- alignmenter:report -->` marker so a CI step can update one comment.
- `--allow-inconclusive` flag on `run-suite` and `check`: an inconclusive
  decision exits 0 so a deterministic, offline pull-request gate stays green
  while a spec is still `draft`; a genuine `fail` still exits non-zero.

## [0.3.0] — 2026-09-07

Application alignment release: capture, evaluate, compare, review, promote regressions,
and gate CI using saved evidence.

### Added

- Durable SQLite capture with frozen source snapshots, transactional observations,
  local coordinator leases, interrupted-attempt accounting, and explicit safe resume.
- Durable rubric, grounding, and faithfulness evaluators with typed evidence and strict
  parsing. Missing, invalid, truncated, uncertain, and budget-blocked work stays visible.
- One run-wide durable judge ledger, reservations before dispatch, raw response reuse,
  and separate target call caps. Unknown target cost remains unavailable.
- Application-owned deterministic evaluator factories, frozen metric descriptors,
  finite numerator/denominator aggregation, criterion/tag grouping, and public SDK.
- Matched saved comparisons with case revision and split-group checks, explicit missing
  populations, hard regressions, and descriptive paired cluster bootstrap intervals.
- Versioned absolute/regression policies and consistent pass/fail/inconclusive decisions
  across CLI, offline HTML, JSON, Markdown, and JUnit.
- Append-only review exchange, human adjudication, evaluator/reference agreement and
  false-pass reporting, and regression promotion with separate expectations and lineage.
- Verified read-only run archives that cannot fork the original execution budget.
- `init-suite`, `run-suite`, `check`, `compare`, review, qualification, promotion, and
  archive commands; installed offline resource-constraint example and CI rehearsal.
- Atlas preserved-failure fixtures and draft application commitments, with provenance
  and qualification limits recorded in the repository plans.

### Changed

- New release integrations use the durable SDK/CLI. Legacy persona/scorer APIs remain
  available with their existing semantics and scorer-local budgets; migration is explicit.
- Durable grounding measures traceability, not semantic entailment. Zero-population
  metrics are unavailable; ambiguous recognized quantities require review. Strict
  faithfulness rejects unsupported claims and unsafe/incorrect advice without allowing
  empty responses to become perfect scores.
- New `evaluators-v2` manifests freeze evaluator descriptors and case identities.
  Older capture and evaluation records remain inspectable; comparisons require a
  common package, engine, judge, and evaluator configuration.
- Unified runtime/distribution/CLI version; Python 3.10–3.14 core validation, lightweight
  `[test]` and `[docs]` extras, wheel/source rehearsals, and release-tag identity checks.
- Marketing dependencies and static build workflow updated, with npm lockfile and
  standalone ESLint configuration.

### Legacy additions retained

- Legacy grounding/faithfulness scorers, local compatible judges, custom scorer loading,
  evidence report sections, and the RAG example remain available.
- Zero thresholds are no longer treated as unset in legacy run configuration.

### Limits

- Product judge qualification requires real outputs and independent owner labels;
  draft Atlas fixtures and synthetic tests do not provide that qualification.
- Durable execution uses local POSIX leases. Device replay, distributed scheduling and
  budgets, broader evaluator scopes, hosted review, and automatic optimization are deferred.

## [0.2.0] — 2026-07-31

Modernization release. The headline change is that the LLM judge is now a
first-class part of authenticity scoring, and the heavy machine-learning
dependencies are optional.

### Changed
- **Judge-blended authenticity.** When an LLM judge is configured, the headline
  authenticity score blends the judge's holistic brand-voice rating with the
  deterministic (embedding + trait + lexicon) score (default 60% judge / 40%
  deterministic). With no judge configured, scoring falls back to the
  deterministic score alone. The scores payload now exposes `basis`
  (`blended` | `deterministic`), `deterministic_mean`, `judge_mean`,
  `judge_weight`, and `judge_sessions` so the basis of every number is explicit.
- **Lightweight core install.** `pip install alignmenter` no longer pulls in
  `torch` or `scikit-learn`. Local embeddings and the offline safety classifier
  move to the `[ml]` extra; the persona calibration pipeline moves to
  `[calibrate]`. `[safety]` remains as a back-compat alias for `[ml]`.
- Refreshed default judge model identifiers (e.g. `anthropic:claude-sonnet-5`)
  and the cost `PRICING_TABLE` for current model rates.
- OpenAI judge calls now use JSON mode with a graceful fallback; judge score
  parsing tolerates markdown-fenced and prose-wrapped JSON.
- Python support declared for 3.10–3.13. CI now runs a version matrix, a `ruff`
  lint gate, and a core-only-install job that asserts `torch`/`scikit-learn`
  are absent from the default install.

### Fixed
- Corrected the Python API example in the package README (the previous
  `RunConfig.from_yaml` / `Runner(config)` snippet did not run).
- Replaced the deprecated `datetime.utcnow()` call.

### Removed
- Generated documentation site output (`site/`) is no longer committed; it is
  built by the docs workflow and now git-ignored.

### Migration notes
- If you relied on `pip install alignmenter` giving you `sentence-transformers`
  or the offline safety classifier, install `alignmenter[ml]`. For the
  `calibrate*` commands, install `alignmenter[calibrate]`.
- No code changes are required for existing runs; deterministic-only behavior is
  preserved when no judge is configured.
