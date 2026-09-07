# Changelog

All notable changes to Alignmenter are documented here. This project adheres to
[Semantic Versioning](https://semver.org/).

## [0.3.0] — release candidate

Application alignment release: capture, evaluate, compare, review, promote regressions,
and gate CI using saved evidence. Prepared 2026-09-07; publication is separate.

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
