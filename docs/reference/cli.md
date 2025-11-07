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
- `--path PATH` - Directory to initialize (default: current directory)
- `--template TEMPLATE` - Use a specific template (default, minimal, research)

**Creates**:
- `configs/` - Configuration files
- `configs/persona/` - Persona definitions
- `datasets/` - Sample conversation data
- `reports/` - Output directory

**Example**:
```bash
alignmenter init --path my-project --template research
```

---

### `alignmenter run`

Run evaluation on a dataset.

```bash
alignmenter run [OPTIONS]
```

**Options**:

Model selection:
- `--model MODEL` - Model to test (e.g., `openai:gpt-4o`, `anthropic:claude-3-5-sonnet-20241022`)
- `--config CONFIG` - Path to run configuration YAML

Dataset:
- `--dataset PATH` - Path to JSONL dataset
- `--no-generate` - Use cached responses instead of calling model

Persona:
- `--persona PATH` - Path to persona YAML
- `--persona-id ID` - Use persona from configs/persona/

Output:
- `--output-dir DIR` - Where to save reports (default: `reports/`)
- `--format FORMAT` - Output format: html, json, csv (default: html)

Thresholds:
- `--min-authenticity SCORE` - Minimum authenticity score (0.0-1.0)
- `--min-safety SCORE` - Minimum safety score (0.0-1.0)
- `--min-stability SCORE` - Minimum stability score (0.0-1.0)

**Examples**:

Basic run:
```bash
alignmenter run --model openai:gpt-4o --config configs/brand.yaml
```

With thresholds:
```bash
alignmenter run --model gpt-4o --min-authenticity 0.8 --min-safety 0.95
```

Compare models:
```bash
alignmenter run --model openai:gpt-4o --output-dir reports/gpt4
alignmenter run --model anthropic:claude-3-5-sonnet-20241022 --output-dir reports/claude
```

---

### `alignmenter report`

Open HTML report in browser.

```bash
alignmenter report [OPTIONS]
```

**Options**:
- `--last` - Open most recent report
- `--path PATH` - Open specific report directory
- `--list` - List available reports

**Examples**:
```bash
alignmenter report --last
alignmenter report --path reports/2025-11-06_14-32/
alignmenter report --list
```

---

## Calibration Commands

### `alignmenter calibrate validate`

Validate metrics with LLM judge.

```bash
alignmenter calibrate validate [OPTIONS]
```

**Options**:

Judge:
- `--judge PROVIDER:MODEL` - Judge provider (e.g., `openai:gpt-4o`)
- `--judge-sample RATE` - Sample rate (0.0-1.0) or count
- `--judge-budget AMOUNT` - Maximum spend in USD
- `--judge-strategy STRATEGY` - Sampling strategy: random, on_failure, stratified

Config:
- `--config PATH` - Path to run configuration
- `--report-dir DIR` - Report directory to validate

**Examples**:

Basic validation:
```bash
alignmenter calibrate validate --judge openai:gpt-4o --judge-sample 0.2
```

With budget control:
```bash
alignmenter calibrate validate --judge gpt-4o --judge-sample 0.3 --judge-budget 1.00
```

On failures only:
```bash
alignmenter calibrate validate --judge gpt-4o --judge-strategy on_failure
```

---

### `alignmenter calibrate diagnose-errors`

Find sessions where judge disagrees with metrics.

```bash
alignmenter calibrate diagnose-errors [OPTIONS]
```

**Options**:
- `--judge PROVIDER:MODEL` - Judge provider
- `--threshold SCORE` - Disagreement threshold (default: 0.2)
- `--output PATH` - Save results to file

**Example**:
```bash
alignmenter calibrate diagnose-errors --judge gpt-4o --threshold 0.15
```

---

### `alignmenter calibrate analyze-scenarios`

Deep dive into specific sessions.

```bash
alignmenter calibrate analyze-scenarios [OPTIONS]
```

**Options**:
- `--judge PROVIDER:MODEL` - Judge provider
- `--sessions IDS` - Comma-separated session IDs
- `--interactive` - Interactive analysis mode

**Example**:
```bash
alignmenter calibrate analyze-scenarios --judge gpt-4o --sessions session_001,session_042
```

---

## Dataset Commands

### `alignmenter dataset sanitize`

Remove PII and sensitive data from datasets.

```bash
alignmenter dataset sanitize INPUT [OPTIONS]
```

**Options**:
- `--output PATH` - Output path (default: INPUT.sanitized.jsonl)
- `--dry-run` - Preview without writing
- `--strategy STRATEGY` - Sanitization strategy: redact, replace, hash

**Example**:
```bash
alignmenter dataset sanitize datasets/prod.jsonl --output datasets/clean.jsonl
alignmenter dataset sanitize datasets/prod.jsonl --dry-run
```

---

### `alignmenter dataset convert`

Convert between dataset formats.

```bash
alignmenter dataset convert INPUT OUTPUT [OPTIONS]
```

**Options**:
- `--from-format FORMAT` - Source format: jsonl, csv, chatgpt
- `--to-format FORMAT` - Target format: jsonl, csv

**Example**:
```bash
alignmenter dataset convert chatgpt_export.json dataset.jsonl --from-format chatgpt
```

---

## Configuration

### Config File Format

Run configurations are YAML files:

```yaml
# configs/brand.yaml
model: "openai:gpt-4o"
persona: "configs/persona/brand.yaml"
dataset: "datasets/test_conversations.jsonl"

evaluation:
  min_authenticity: 0.80
  min_safety: 0.95
  min_stability: 0.85

output:
  dir: "reports/"
  format: "html"
  include_json: true
```

### Environment Variables

- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- `ALIGNMENTER_CACHE_DIR` - Cache directory (default: `~/.alignmenter/cache`)
- `ALIGNMENTER_LOG_LEVEL` - Log level: DEBUG, INFO, WARNING, ERROR

---

## Exit Codes

- `0` - Success, all thresholds met
- `1` - Evaluation failed (scores below thresholds)
- `2` - Invalid arguments or configuration
- `3` - API error or network issue
- `4` - Budget exceeded

---

## Next Steps

- **[Metrics Reference](metrics.md)** - Detailed scoring formulas
- **[Configuration Guide](config.md)** - Config file options
- **[Quick Start](../getting-started/quickstart.md)** - Usage examples
