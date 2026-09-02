# Changelog

All notable changes to Alignmenter are documented here. This project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

Retrieval-augmented assistants can now be scored on what matters for them: is
the answer in the documents, is it right, and could it hurt someone.

### Added
- **`grounding` scorer** (offline, deterministic). Every quantity in an answer
  must appear in the passages the provider attached to the turn; unsupported
  figures are split into *invented* (no figure in that unit in the passages)
  and *contradicted* (a different figure was given). Citations past the end of
  the excerpt list are invalid. Enable with `scorers.grounding.enabled: true`
  or `--grounding`.
- **`faithfulness` scorer** (LLM judge). Per answer: claims labelled
  supported / unsupported / contradicted with evidence, a 0–10 correctness
  rating, abstention handling, and a `dangerous` flag with a reason. Budget and
  cost caps as for the safety judge. Enable with `scorers.faithfulness` or
  `--faithfulness`; set `domain` so the judge knows what "dangerous" means for
  your product.
- **`dangerous` threshold.** `thresholds.dangerous.fail: 0` fails the run (exit
  code 2) if any answer was flagged. Gate on this, not on the mean.
- **Local judges.** `local:<base_url>|<model>` runs the judge against any
  OpenAI-compatible endpoint (llama-server, vLLM, Ollama, LM Studio).
- **Custom scorers from config and CLI.** `scorers.custom: [module:Class]` /
  `--custom-scorer` load product-owned scorers beside the built-ins (the loader
  existed; it was not wired to a run).
- Grounding and faithfulness scorecards, thresholds, and an HTML section that
  lists the answers behind each number, dangerous ones first.
- `datasets/grounded_demo.jsonl` and the *RAG Evaluation* guide.

### Fixed
- A threshold of `0` was treated as unset (`warn`/`fail` were read through
  `or`), so a zero-tolerance gate could never fail. Thresholds now distinguish
  "not set" from `0`.

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
