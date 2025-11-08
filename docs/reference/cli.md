# CLI Reference

Complete reference for all Alignmenter commands.

## Global Options

Available for all commands:

```bash
--help               Show help message
--version            Show version number
--verbose, -v        Enable verbose logging
--quiet, -q          Suppress non-error output
```

## Core Commands

### `alignmenter init`

Initialize a new Alignmenter project.

```bash
alignmenter init [OPTIONS]
```

**Options**:
- `--env-path PATH` - Where to write the `.env` file (default: `./.env`)
- `--config-path PATH` - Where to write the starter run config (default: `./configs/run.yaml`)

**Creates**:
- `.env` – Stores provider credentials and defaults
- `configs/run.yaml` – Run configuration referenced by `alignmenter run`

**Example**:
```bash
alignmenter init --env-path .env --config-path configs/run.yaml
```

---

### `alignmenter run`

Run evaluation on a dataset.

```bash
alignmenter run [OPTIONS]
```

**Options**:

Core inputs:
- `--config PATH` – Run configuration YAML (overrides everything else when provided)
- `--model PROVIDER:MODEL` – Primary chat model (e.g., `openai:gpt-4o-mini`)
- `--dataset PATH` – Conversation dataset (`.jsonl`)
- `--persona PATH` – Persona YAML
- `--compare PROVIDER:MODEL` – Optional second model for side-by-side runs

Safety + embeddings:
- `--keywords PATH` – Safety keyword list (defaults to `configs/safety_keywords.yaml`)
- `--embedding IDENTIFIER` – Embedding provider (e.g., `sentence-transformer:all-MiniLM-L6-v2` or `hashed`)
- `--judge PROVIDER:MODEL` – Safety judge provider
- `--judge-budget N` – Limit judge calls per run

Output + execution:
- `--out DIR` – Directory for run artifacts (default: `reports/`)
- `--generate-transcripts` – Call providers to regenerate assistant turns (default reuses recorded transcripts)

**Examples**:

Basic cached run:
```bash
alignmenter run --config configs/run.yaml
```

Regenerate transcripts via provider:
```bash
alignmenter run --config configs/run.yaml --generate-transcripts
```

Compare two models (writes separate report dirs):
```bash
alignmenter run \
  --model openai:gpt-4o-mini \
  --compare anthropic:claude-3-5-sonnet-20241022 \
  --dataset datasets/demo_conversations.jsonl \
  --persona configs/persona/default.yaml \
  --out reports/compare
```

Thresholds for authenticity/safety/stability are defined inside the run config:

```yaml
scorers:
  authenticity:
    threshold_warn: 0.78
    threshold_fail: 0.72
```

---

### `alignmenter report`

Open HTML report in browser.

```bash
alignmenter report [OPTIONS]
```

**Options**:
- `--last` – Open the most recent report
- `--path PATH` – Open a specific report directory
- `--reports-dir DIR` – Base directory to search (default: `reports/`)

**Examples**:
```bash
alignmenter report --last
alignmenter report --path reports/2025-11-06_14-32_alignmenter_run
alignmenter report --reports-dir reports/prod
```

---

## Calibration Commands

### `alignmenter calibrate validate`

Validate metrics with LLM judge.

```bash
alignmenter calibrate validate [OPTIONS]
```

**Options**:
- `--labeled PATH` – Labeled JSONL with authenticity annotations *(required)*
- `--persona PATH` – Persona YAML that produced the labels *(required)*
- `--output PATH` – Where to write the diagnostics JSON *(required)*
- `--embedding IDENTIFIER` – Embedding provider override
- `--train-split FLOAT` – Train/test split (default `0.8`)
- `--seed INT` – Random seed (default `42`)
- `--judge PROVIDER:MODEL` – Judge provider (optional)
- `--judge-sample FLOAT` – Fraction of sessions to judge (default `0.0`)
- `--judge-strategy STRATEGY` – Sampling strategy (`random`, `stratified`, `errors`, `extremes`)
- `--judge-budget INT` – Maximum judge calls

**Examples**:

Validate with judge sampling:
```bash
alignmenter calibrate validate \
  --labeled case-studies/wendys-twitter/labeled.jsonl \
  --persona configs/persona/wendys-twitter.yaml \
  --output reports/wendys-calibration.json \
  --judge openai:gpt-4o --judge-sample 0.2
```

Offline-only validation:
```bash
alignmenter calibrate validate \
  --labeled data/labeled.jsonl \
  --persona configs/persona/brand.yaml \
  --output reports/brand-calibration.json
```

---

### `alignmenter calibrate diagnose-errors`

Find sessions where judge disagrees with metrics.

```bash
alignmenter calibrate diagnose-errors [OPTIONS]
```

**Options**:
- `--labeled PATH` – Labeled JSONL *(required)*
- `--persona PATH` – Persona YAML *(required)*
- `--output PATH` – Output diagnostics JSON *(required)*
- `--embedding IDENTIFIER` – Embedding provider override
- `--judge PROVIDER:MODEL` – Judge provider *(required)*
- `--judge-budget INT` – Maximum judge calls

**Example**:
```bash
alignmenter calibrate diagnose-errors \
  --labeled case-studies/wendys-twitter/labeled.jsonl \
  --persona configs/persona/wendys-twitter.yaml \
  --output reports/wendys-errors.json \
  --judge anthropic:claude-3-5-sonnet-20241022
```

---

### `alignmenter calibrate analyze-scenarios`

Deep dive into specific sessions.

```bash
alignmenter calibrate analyze-scenarios [OPTIONS]
```

**Options**:
- `--dataset PATH` – Conversation dataset *(required)*
- `--persona PATH` – Persona YAML *(required)*
- `--output PATH` – Output JSON *(required)*
- `--embedding IDENTIFIER` – Embedding provider override
- `--judge PROVIDER:MODEL` – Judge provider *(required)*
- `--per-scenario INT` – Samples per scenario tag (default `3`)
- `--judge-budget INT` – Maximum judge calls

**Example**:
```bash
alignmenter calibrate analyze-scenarios \
  --dataset datasets/demo_conversations.jsonl \
  --persona configs/persona/default.yaml \
  --output reports/demo-scenarios.json \
  --judge openai:gpt-4o --per-scenario 5
```

---

## Dataset Commands

### `alignmenter dataset sanitize`

Remove PII and sensitive data from datasets.

```bash
alignmenter dataset sanitize INPUT [OPTIONS]
```

**Options**:
- `--out PATH` - Output path (default: <input>_sanitized.jsonl)
- `--in-place` - Overwrite the input file
- `--dry-run` - Preview without writing
- `--use-hashing/--no-use-hashing` - Stable hashes vs generic placeholders

**Examples**:
```bash
alignmenter dataset sanitize datasets/prod.jsonl --out datasets/clean.jsonl
alignmenter dataset sanitize datasets/prod.jsonl --dry-run
alignmenter dataset sanitize datasets/prod.jsonl --in-place --no-use-hashing
```

---

## Configuration

### Config File Format

Run configurations are YAML files:

```yaml
# configs/run.yaml
run_id: brand_voice_demo
model: openai:gpt-4o-mini
dataset: datasets/demo_conversations.jsonl
persona: configs/persona/default.yaml
keywords: configs/safety_keywords.yaml
embedding: sentence-transformer:all-MiniLM-L6-v2

scorers:
  authenticity:
    threshold_warn: 0.78
    threshold_fail: 0.72
  safety:
    offline_classifier: auto

report:
  out_dir: reports
  include_raw: true
```

Thresholds are scoped per scorer; if a score falls below `threshold_fail`, `alignmenter run` exits with status code `2`.

### Environment Variables

- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` – Provider credentials (only set what you use)
- `ALIGNMENTER_DEFAULT_MODEL` – Default `provider:model` used by `alignmenter run`
- `ALIGNMENTER_EMBEDDING_PROVIDER` – Embedding provider (e.g., `hashed`, `sentence-transformer:all-MiniLM-L6-v2`)
- `ALIGNMENTER_JUDGE_PROVIDER` – Judge provider for safety scoring
- `ALIGNMENTER_JUDGE_BUDGET` / `_USD` – Budget guardrails (calls or dollars)
- `ALIGNMENTER_CUSTOM_GPT_ID` – Default Custom GPT identifier for `openai-gpt:` runs
- `ALIGNMENTER_CACHE_DIR` – Cache directory (default: `~/.cache/alignmenter`)
- `ALIGNMENTER_LOG_LEVEL` – Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`

---

## Exit Codes

- `0` – Success
- `1` – Command/configuration error (missing files, invalid provider, judge failure, etc.)
- `2` – Metrics fell below `threshold_fail` (run marked as failed)

---

## Next Steps

- **[Metrics Reference](metrics.md)** - Detailed scoring formulas
- **[Configuration Guide](config.md)** - Config file options
- **[Quick Start](../getting-started/quickstart.md)** - Usage examples
