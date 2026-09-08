# CLI Reference

Complete reference for every Alignmenter command.

The CLI is organized into top-level commands plus four sub-command groups:
`persona`, `dataset`, `import`, and `calibrate`. Run `alignmenter --help` or
`alignmenter <group> --help` to see the same information from your terminal.

!!! note "Optional extras"
    The default `pip install alignmenter` is lightweight and has **no** torch or
    scikit-learn. Some commands need optional dependency groups:

    - `pip install "alignmenter[ml]"` – local sentence-transformer embeddings and
      the offline safety classifier.
    - `pip install "alignmenter[calibrate]"` – the numeric calibration pipeline
      (`calibrate bounds`, `calibrate optimize`, `calibrate validate`).

    Commands that require an extra are flagged below.

---

## Command overview

| Command | Purpose | Requires |
| --- | --- | --- |
| `init` | Interactive setup of credentials, defaults, and a starter run config | — |
| `run` | Execute an evaluation run | `[ml]` for local embeddings |
| `status` | Inspect committed execution state | — |
| `capture` | Save recorded or generated answers without scoring | — |
| `resume` | Continue compatible capture with recovery preflight | — |
| `evaluate` | Evaluate saved answers with versioned rubrics and a durable shared judge budget | — |
| `evaluation-status` | Inspect saved rubric decisions, evidence, and budget usage | — |
| `export-transcripts` | Recover committed transcripts from a complete or partial run | — |
| `demo` | One-line demo run over the bundled dataset | — |
| `report` | Open a generated HTML report in the browser | — |
| `bootstrap-dataset` | Generate a synthetic dataset with safety/brand traps | — |
| `calibrate-persona` | Fit persona trait weights from labeled data | — |
| `persona scaffold` | Write a starter persona YAML | — |
| `persona export` | Export assistant turns for annotation (CSV / Label Studio) | — |
| `persona sync-gpt` | Pull a Custom GPT's instructions into a persona pack | — |
| `dataset lint` | Validate dataset schema and persona coverage | — |
| `dataset sanitize` | Strip PII from a dataset | — |
| `dataset bootstrap` | Alias of `bootstrap-dataset` | — |
| `import gpt` | Convert Custom GPT instruction text into a persona pack | — |
| `calibrate generate` | Sample candidate responses for labeling | — |
| `calibrate label` | Interactively label candidates on-brand / off-brand | — |
| `calibrate bounds` | Estimate style-similarity normalization bounds | `[calibrate]` |
| `calibrate optimize` | Grid-search component weights (style/traits/lexicon) | `[calibrate]` |
| `calibrate validate` | Cross-validate calibration and produce diagnostics | `[calibrate]` |
| `calibrate diagnose-errors` | LLM-judge analysis of false positives/negatives | judge API |
| `calibrate analyze-scenarios` | LLM-judge breakdown by scenario tag | judge API |

---

## Durable suite and release commands

| Command | Purpose |
| --- | --- |
| `init-suite --out DIR` | Write a runnable offline application example |
| `run-suite SUITE --out reports [--resume RUN]` | Capture, evaluate, compare, and export under a frozen config |
| `check RUN --out DIR [--policy YAML] [--baseline RUN]` | Apply gates to saved results and export all formats |
| `compare BASELINE CANDIDATE --out DIR` | Compare compatible saved cases and evidence |
| `review-export RUN --out JSONL` | Export immutable evidence with editable annotation fields |
| `review-import RUN --annotations JSONL` | Append validated opinions/adjudications atomically |
| `qualify RUN` | Compare machine outcomes against active human adjudications |
| `promote RUN --annotation-id UUID --out DIR` | Write a regression case with separate expectations |
| `archive-export RUN --out ZIP` | Export a verified snapshot with evidence and annotations |
| `archive-import ZIP --out DIR` | Create a read-only inspection copy |

Use `--evaluation-id` on saved checks and review export/qualification to pin a snapshot.
`compare` accepts `--baseline-id` and `--candidate-id`; `check --baseline` accepts
`--baseline-id`. Run `COMMAND --help` for all options. `evaluate` accepts repeatable
`--evaluator-factory module:function` for custom deterministic checks; `capture`
accepts `--max-target-calls`. `--version` prints the installed package version.

Release commands use exit codes 0 (pass), 2 (fail), and 3 (inconclusive). Configuration
errors also exit nonzero. The same policy decision appears in every report format.
See the [release workflow](../guides/release-workflow.md) for configuration and semantics.

## Core commands

### `alignmenter init`

Interactively configure provider credentials, embedding/judge defaults, and write
a starter run configuration.

```bash
alignmenter init [OPTIONS]
```

**Options**:

- `--env-path PATH` – Location of the environment file Alignmenter reads (default: `.env`)
- `--config-path PATH` – Path for the starter run configuration YAML (default: `configs/run.yaml`)

The wizard prompts for OpenAI access, embedding provider, default chat model
(including OpenAI, Anthropic `claude-sonnet-5`, a Custom GPT, or a local
OpenAI-compatible endpoint), and optional safety judge settings. It writes the
`.env` file, copies the bundled demo dataset/persona/keywords into your
workspace, and emits a runnable `configs/run.yaml`.

---

### `alignmenter run` (legacy)

Execute an evaluation run and write a report directory.

```bash
alignmenter run [OPTIONS]
```

**Options**:

- `--config, -c PATH` – Run configuration YAML (values here fill any option you don't pass explicitly)
- `--model PROVIDER:MODEL` – Primary chat model (e.g. `openai:gpt-4o-mini`, `anthropic:claude-sonnet-5`)
- `--dataset PATH` – Conversation dataset (`.jsonl`)
- `--persona PATH` – Persona YAML
- `--compare PROVIDER:MODEL` – Optional second model for a side-by-side run
- `--out DIR` – Output directory for run artifacts (default: `reports/`)
- `--keywords PATH` – Safety keyword configuration file
- `--embedding IDENTIFIER` – Embedding provider. `hashed` (default, zero-dependency) or, with the `[ml]` extra, `sentence-transformer:all-MiniLM-L6-v2`, or `openai:text-embedding-3-small`
- `--judge PROVIDER:MODEL` – LLM judge provider. When set, the judge is **blended into the headline authenticity score** and also fuses into safety
- `--judge-budget N` – Maximum judge calls per run
- `--generate-transcripts` – Call providers to regenerate assistant turns before scoring. By default the run **reuses** the recorded transcripts in the dataset

**Behavior notes**:

- If a threshold is configured and any metric falls below its `fail` value, `run` exits with code `2`.
- With `--generate-transcripts`, provider initialization failure aborts the run; without it, recorded transcripts are scored offline.
- Run capture is persisted incrementally. A later failure preserves committed answers;
  see [durable runs](../guides/durable-runs.md) for recovery and status semantics.

**Examples**:

```bash
# Score recorded transcripts (offline, deterministic authenticity)
alignmenter run --config configs/run.yaml

# Regenerate transcripts from the provider first
alignmenter run --config configs/run.yaml --generate-transcripts

# Judge-blended authenticity + safety
alignmenter run --config configs/run.yaml --judge anthropic:claude-sonnet-5 --judge-budget 50

# Compare two models
alignmenter run \
  --model openai:gpt-4o-mini \
  --compare anthropic:claude-sonnet-5 \
  --dataset datasets/demo_conversations.jsonl \
  --persona configs/persona/default.yaml \
  --out reports/compare
```

Thresholds live in the run config, scoped per scorer:

```yaml
thresholds:
  authenticity: {warn: 0.78, fail: 0.72}
  safety: {warn: 0.95, fail: 0.90}
```

---

### `alignmenter capture` and `alignmenter resume`

```sh
alignmenter capture --dataset conversations.jsonl [--persona persona.yaml] [--target module:factory] [--out reports]
alignmenter resume RUN_DIRECTORY [--target module:factory] [--compare-target module:factory] [--dataset conversations.jsonl] [--persona persona.yaml] [--check]
```

Capture imports recorded answers when no target is supplied. Target factories return a
`CaptureTarget`; generated resume requires the original compatible recovery declaration.
`--check` validates continuation without dispatch or database writes. Optional source
paths assert compatibility with the saved snapshots. Capture/resume never invokes
scorers; see [capture and resume](../guides/capture-recovery.md) for adapter contracts,
idempotency requirements, and database compatibility.

### `alignmenter evaluate` and `alignmenter evaluation-status`

```sh
alignmenter evaluate RUN_DIRECTORY --spec evaluations.yaml [--judge-factory module:factory] [--max-judge-calls 20] [--max-judge-cost-micros 10000] [--new-evaluation]
alignmenter evaluation-status RUN_DIRECTORY [--evaluation-id UUID] [--json] [--details]
```

Deterministic grounding requires neither a judge factory nor a budget. Generic rubrics
and faithfulness require a factory; the first judged evaluation requires an explicit
call budget. Later evaluations and
resumes share the frozen run budget; new rubric/judge/input snapshots require
`--new-evaluation`. Monetary limits require an adapter-declared cost upper bound.
Evaluation exits `0` for pass, `2` for a violation, and `3` for inconclusive; CLI/config
errors also return nonzero. Status only reads saved data and can export full evidence
with `--details`. See [durable evaluations](../guides/durable-evaluations.md) for adapter
factories, strict verdicts, coverage semantics, and the boundary with legacy scorers.
The [grounding and faithfulness guide](../guides/grounding-faithfulness.md) describes
built-in specs, evidence eligibility, saved metrics, and migration semantics.

### `alignmenter status`

Read the last committed execution state without calling providers or scorers.

```bash
alignmenter status RUN_DIRECTORY [--json]
```

`--json` emits the versioned execution summary, including planned/committed record
counts and attempt statuses. Liveness is not inferred: a hard kill may leave a
nonterminal recorded state. This command supports runs with the new durable database.

### `alignmenter export-transcripts`

Export committed transcript records, including partial runs, without new execution.

```bash
alignmenter export-transcripts RUN_DIRECTORY --out recovered.jsonl [--stream primary|compare] [--force]
```

The default stream is `primary`. Existing output files require `--force`; the durable
database itself cannot be replaced by an export. Missing answers remain absent.

---

### `alignmenter demo`

Convenience wrapper around `run` that scores the bundled demo dataset and persona,
regenerating transcripts from the chosen model.

```bash
alignmenter demo [OPTIONS]
```

**Options**:

- `--model PROVIDER:MODEL` – Demo model to evaluate (default: `openai:gpt-4o-mini`)
- `--out DIR` – Directory for demo artifacts (default: `reports/demo`)

---

### `alignmenter report`

Open a generated HTML report in your default browser.

```bash
alignmenter report [OPTIONS]
```

**Options**:

- `--last` – Open the most recent report
- `--path PATH` – Open a specific report directory
- `--reports-dir DIR` – Base directory to search when using `--last` (default: `reports`)

Either `--last` or `--path` must be supplied.

```bash
alignmenter report --last
alignmenter report --path reports/2026-07-31_14-32_alignmenter_run
```

---

### `alignmenter bootstrap-dataset`

Generate a synthetic conversation dataset seeded with deliberate safety traps and
brand-voice violations. Also available as `alignmenter dataset bootstrap` with the
same options.

```bash
alignmenter bootstrap-dataset --out PATH [OPTIONS]
```

**Options**:

- `--out PATH` – Output JSONL path for generated data *(required)*
- `--source PATH` – Optional source dataset to augment
- `--sessions INT` – Number of sessions to generate (default: `10`)
- `--turns-per-session INT` – Turns per session, user/assistant alternating (default: `6`)
- `--safety-trap-ratio FLOAT` – Fraction of sessions with safety traps (default: `0.2`)
- `--brand-trap-ratio FLOAT` – Fraction of sessions with brand violations (default: `0.2`)
- `--persona-id TEXT` – Persona identifier annotated on each turn (default: `default_v1`)
- `--seed INT` – Random seed for reproducibility (default: `42`)

---

### `alignmenter calibrate-persona`

Fit persona-specific **trait weights** from labeled data. This trains a
token/phrase-weight logistic model (pure Python — no `[calibrate]` extra needed)
and writes a `<persona>.traits.json` file that the authenticity scorer loads
automatically.

```bash
alignmenter calibrate-persona --persona-path PATH --dataset PATH [OPTIONS]
```

**Options**:

- `--persona-path PATH` – Persona YAML containing the `id` to calibrate *(required)*
- `--dataset PATH` – Labeled JSONL with `persona_id`, `text`, and `label` (0=off-brand, 1=on-brand) *(required)*
- `--out PATH` – Output path for the generated `.traits.json` (default: `<persona>.traits.json`)
- `--min-samples INT` – Minimum labeled examples required (default: `25`)
- `--learning-rate FLOAT` – Learning rate for logistic regression (default: `0.1`)
- `--epochs INT` – Training epochs (default: `300`)
- `--l2 FLOAT` – L2 regularization strength (default: `0.0`)

See [Persona Annotation](../persona_annotation.md) for the full labeling workflow.

---

## `persona` commands

### `alignmenter persona scaffold`

Write a starter persona YAML template.

```bash
alignmenter persona scaffold --name NAME [OPTIONS]
```

**Options**:

- `--name TEXT` – Display name for the persona *(required)*
- `--out PATH` – Path for the generated YAML (default: `configs/persona/<slug>.yaml`)
- `--force` – Overwrite an existing file

The emitted template is the canonical persona schema
(`id`, `display_name`, `exemplars`, `lexicon.preferred`/`lexicon.avoid`,
`style_rules`, `safety_rules`). See the [Persona Guide](../guides/persona.md).

---

### `alignmenter persona export`

Export assistant turns from a dataset for annotation.

```bash
alignmenter persona export [OPTIONS]
```

**Options**:

- `--dataset PATH` – Dataset file to export from (default: bundled `demo_conversations.jsonl`)
- `--out PATH` – Output path (default: `persona_export.csv`)
- `--persona-id TEXT` – Filter to a single persona
- `--format TEXT` – `csv` (default) or `labelstudio` (JSON tasks)

---

### `alignmenter persona sync-gpt`

Pull instructions from a Custom GPT into a persona pack (requires `OPENAI_API_KEY`
and Custom GPT API access).

```bash
alignmenter persona sync-gpt GPT_ID [OPTIONS]
```

**Arguments / options**:

- `GPT_ID` – Custom GPT identifier (`gpt://...`) *(required argument)*
- `--out PATH` – Where to write the synced persona YAML
- `--force` – Overwrite the target file if it exists

---

## `dataset` commands

### `alignmenter dataset lint`

Validate a dataset's schema and persona coverage.

```bash
alignmenter dataset lint PATH [OPTIONS]
```

**Arguments / options**:

- `PATH` – Dataset JSONL file to validate *(required argument)*
- `--persona-dir PATH` – Directory containing persona YAML files (default: bundled persona directory)
- `--strict` – Additional checks: user/assistant coverage, `turn_index` sequencing, and `scenario:*` tag coverage

Required fields per record: `session_id`, `turn_index` (int), `role`, `text`
(non-empty), `tags` (list), `persona_id`. Exits with code `1` on any error.

---

### `alignmenter dataset sanitize`

Remove PII and sensitive data from a dataset.

```bash
alignmenter dataset sanitize PATH [OPTIONS]
```

**Arguments / options**:

- `PATH` – Input dataset JSONL *(required argument)*
- `--out PATH` – Output path (default: `<input>_sanitized.jsonl`)
- `--in-place` – Overwrite the input file
- `--use-hashing / --no-use-hashing` – Use stable hashes for replacements instead of generic placeholders (default: on)
- `--dry-run` – Show results without writing output

```bash
alignmenter dataset sanitize datasets/prod.jsonl --out datasets/clean.jsonl
alignmenter dataset sanitize datasets/prod.jsonl --dry-run
```

---

### `alignmenter dataset bootstrap`

Identical to [`alignmenter bootstrap-dataset`](#alignmenter-bootstrap-dataset).

---

## `import` commands

### `alignmenter import gpt`

Convert a Custom GPT instructions text file into a persona pack offline (no API
call — it parses the text heuristically).

```bash
alignmenter import gpt --instructions PATH --name NAME --out PATH [OPTIONS]
```

**Options**:

- `--instructions PATH` – Path to the instructions text file *(required)*
- `--name TEXT` – Display name for the persona *(required)*
- `--out PATH` – Where to write the persona YAML *(required)*
- `--force` – Overwrite the output file if it exists

---

## `calibrate` commands

The calibration toolkit tunes the authenticity scorer against your labeled data.
A typical flow is `generate` → `label` → `bounds` → `optimize` →
`calibrate-persona`, with `validate` / `diagnose-errors` / `analyze-scenarios` for
diagnostics. See [Persona Annotation](../persona_annotation.md) and the
[Calibration Guide](../guides/calibration.md).

### `alignmenter calibrate generate`

Sample candidate responses from an existing dataset for labeling.

```bash
alignmenter calibrate generate --dataset PATH --persona PATH --output PATH [OPTIONS]
```

**Options**:

- `--dataset PATH` – Input JSONL dataset *(required)*
- `--persona PATH` – Persona YAML *(required)*
- `--output PATH` – Output unlabeled candidates JSONL *(required)*
- `--num-samples INT` – Number of candidates to generate (default: `50`)
- `--strategy TEXT` – Sampling strategy: `diverse` (default), `random`, `edge_cases`
- `--seed INT` – Random seed (default: `42`)

---

### `alignmenter calibrate label`

Interactively label candidates as on-brand (1) or off-brand (0). Writes each label
immediately so progress is never lost.

```bash
alignmenter calibrate label --input PATH --persona PATH --output PATH [OPTIONS]
```

**Options**:

- `--input PATH` – Unlabeled candidates JSONL *(required)*
- `--persona PATH` – Persona YAML (shown for context) *(required)*
- `--output PATH` – Output labeled JSONL *(required)*
- `--append` – Append to (and de-duplicate against) existing labeled data
- `--labeler TEXT` – Name of the person labeling (recorded on each row)

---

### `alignmenter calibrate bounds`

Estimate style-similarity normalization bounds (the `style_sim_min`/`style_sim_max`
percentiles used to rescale embedding cosine into a presentable band).

!!! warning "Requires `[calibrate]`"
    `pip install "alignmenter[calibrate]"` (needs numpy).

```bash
alignmenter calibrate bounds --labeled PATH --persona PATH --output PATH [OPTIONS]
```

**Options**:

- `--labeled PATH` – Labeled JSONL data *(required)*
- `--persona PATH` – Persona YAML *(required)*
- `--output PATH` – Output bounds report JSON *(required)*
- `--embedding IDENTIFIER` – Embedding provider override (`sentence-transformer:*` needs `[ml]`)
- `--percentile-low FLOAT` – Lower percentile for the min bound (default: `5.0`)
- `--percentile-high FLOAT` – Upper percentile for the max bound (default: `95.0`)

---

### `alignmenter calibrate optimize`

Grid-search the style / traits / lexicon blend weights to maximize ROC-AUC on your
labeled data.

!!! warning "Requires `[calibrate]`"
    `pip install "alignmenter[calibrate]"` (needs numpy + scikit-learn).

```bash
alignmenter calibrate optimize --labeled PATH --persona PATH --output PATH [OPTIONS]
```

**Options**:

- `--labeled PATH` – Labeled JSONL data *(required)*
- `--persona PATH` – Persona YAML *(required)*
- `--output PATH` – Output weights report JSON *(required)*
- `--bounds PATH` – Bounds report JSON from `calibrate bounds` (for normalization)
- `--embedding IDENTIFIER` – Embedding provider override
- `--grid-step FLOAT` – Grid search step size (default: `0.1`)

---

### `alignmenter calibrate validate`

Cross-validate the calibration (train/test split) and produce diagnostics, with an
optional LLM-judge sample for agreement analysis.

!!! warning "Requires `[calibrate]`"
    `pip install "alignmenter[calibrate]"` (needs numpy + scikit-learn).

```bash
alignmenter calibrate validate --labeled PATH --persona PATH --output PATH [OPTIONS]
```

**Options**:

- `--labeled PATH` – Labeled JSONL data *(required)*
- `--persona PATH` – Persona YAML (with its `.traits.json` calibration) *(required)*
- `--output PATH` – Output diagnostics report JSON *(required)*
- `--embedding IDENTIFIER` – Embedding provider override
- `--train-split FLOAT` – Fraction of data used for training (default: `0.8`)
- `--seed INT` – Random seed for the split (default: `42`)
- `--judge PROVIDER:MODEL` – Judge provider (e.g. `anthropic:claude-sonnet-5`)
- `--judge-sample FLOAT` – Fraction of sessions to judge, 0.0–1.0 (default: `0.0`)
- `--judge-strategy TEXT` – Sampling strategy: `stratified` (default), `random`, `errors`, `extremes`
- `--judge-budget INT` – Maximum judge API calls

---

### `alignmenter calibrate diagnose-errors`

Use an LLM judge to explain calibration false positives and false negatives.
`--judge` is required.

```bash
alignmenter calibrate diagnose-errors --labeled PATH --persona PATH --output PATH --judge PROVIDER:MODEL [OPTIONS]
```

**Options**:

- `--labeled PATH` – Labeled JSONL data *(required)*
- `--persona PATH` – Persona YAML (with its `.traits.json`) *(required)*
- `--output PATH` – Output error analysis JSON *(required)*
- `--judge PROVIDER:MODEL` – Judge provider *(required)*
- `--embedding IDENTIFIER` – Embedding provider override
- `--judge-budget INT` – Maximum judge API calls

---

### `alignmenter calibrate analyze-scenarios`

Group sessions by `scenario:*` tag and judge a sample from each to see which
scenarios perform well or poorly. `--judge` is required.

```bash
alignmenter calibrate analyze-scenarios --dataset PATH --persona PATH --output PATH --judge PROVIDER:MODEL [OPTIONS]
```

**Options**:

- `--dataset PATH` – Conversation dataset JSONL *(required)*
- `--persona PATH` – Persona YAML *(required)*
- `--output PATH` – Output scenario analysis JSON *(required)*
- `--judge PROVIDER:MODEL` – Judge provider *(required)*
- `--embedding IDENTIFIER` – Embedding provider override
- `--per-scenario INT` – Sessions to judge per scenario tag (default: `3`)
- `--judge-budget INT` – Maximum judge API calls

---

## Configuration

### Run config file

Run configurations are YAML. Only `model` is strictly required; everything else
falls back to defaults or environment variables.

```yaml
# configs/run.yaml
run_id: alignmenter_run
model: openai:gpt-4o-mini
dataset: datasets/demo_conversations.jsonl
persona: persona/default.yaml
keywords: safety_keywords.yaml
embedding: hashed            # or sentence-transformer:all-MiniLM-L6-v2 with [ml]

scorers:
  safety:
    offline_classifier: auto  # try the ML classifier, fall back to heuristic
    judge:
      provider: anthropic:claude-sonnet-5
      budget: 50

thresholds:
  authenticity: {warn: 0.78, fail: 0.72}
  safety: {warn: 0.95, fail: 0.90}

report:
  out_dir: reports
  include_raw: true
```

Thresholds are scoped per scorer. If a score falls below its `fail` value,
`alignmenter run` exits with status code `2`.

### Environment variables

- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` – Provider credentials (set only what you use)
- `ALIGNMENTER_DEFAULT_MODEL` – Default `provider:model` for `run` (default: `openai:gpt-4o-mini`)
- `ALIGNMENTER_EMBEDDING_PROVIDER` – Embedding provider (default: `hashed`)
- `ALIGNMENTER_JUDGE_PROVIDER` – Judge provider for authenticity + safety
- `ALIGNMENTER_JUDGE_BUDGET` / `_USD` – Budget guardrails (calls or dollars)
- `ALIGNMENTER_SAFETY_CLASSIFIER` – Offline classifier identifier (default: `auto`)
- `ALIGNMENTER_CUSTOM_GPT_ID` – Default Custom GPT identifier for `openai-gpt:` runs

---

## Exit codes

- `0` – Success
- `1` – Command/configuration error (missing files, invalid provider, judge failure, etc.)
- `2` – A metric fell below its `fail` threshold (run marked as failed)

---

## Next steps

- **[Metrics Reference](metrics.md)** – Detailed scoring formulas
- **[Persona Annotation](../persona_annotation.md)** – The labeling/calibration workflow
- **[Offline Safety](../offline_safety.md)** – The local safety classifier
- **[Configuration Guide](config.md)** – Config file options
