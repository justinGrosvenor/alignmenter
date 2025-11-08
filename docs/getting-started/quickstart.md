# Quick Start

This guide will walk you through running your first Alignmenter evaluation in under 5 minutes.

## Prerequisites

- Alignmenter installed with safety extras ([Installation Guide](installation.md))
  - `pip install "alignmenter[safety]"` (PyPI) or `pip install -e .[dev,safety]` (repo checkout)
- OpenAI API key set in environment

## 1. Initialize Project

Create a new project directory:

```bash
alignmenter init
```

This creates sample configs, datasets, and personas you can use right away.

## 2. Run Your First Test

Run an evaluation with the demo dataset (reuses the bundled transcripts):

```bash
alignmenter run --config configs/run.yaml --embedding sentence-transformer:all-MiniLM-L6-v2
```

Want fresh transcripts from your provider? Add `--generate-transcripts`:

```bash
alignmenter run --config configs/run.yaml --generate-transcripts --embedding sentence-transformer:all-MiniLM-L6-v2
```

You'll see output like:

```
Loading dataset: 60 turns across 10 sessions
Running model: openai:gpt-4o-mini
✓ Brand voice score: 0.83 (range: 0.79-0.87)
✓ Safety score: 0.95
✓ Consistency score: 0.88
Report written to: reports/2025-11-06_14-32/index.html
```

!!! success
    The test typically completes in ~10 seconds with the demo dataset.

## 3. View the Report

Open the interactive HTML report:

```bash
alignmenter report --last
```

This opens the most recent report in your browser. You'll see:

- **Overall score** with letter grade (A/B/C)
- **Metric breakdown** for authenticity, safety, and stability
- **Interactive charts** showing score distributions
- **Session details** with individual conversation analysis
- **Export options** to CSV/JSON

## 4. Test Different Models

Compare GPT-4 vs Claude:

```bash
# Test with GPT-4
alignmenter run --model openai:gpt-4o --config configs/brand.yaml --generate-transcripts --embedding sentence-transformer:all-MiniLM-L6-v2

# Test with Claude
alignmenter run --model anthropic:claude-3-5-sonnet-20241022 --config configs/brand.yaml --generate-transcripts --embedding sentence-transformer:all-MiniLM-L6-v2
```

## 5. Add LLM Judge Analysis (Optional)

Get qualitative feedback from an LLM judge:

```bash
alignmenter calibrate validate \
  --labeled case-studies/wendys-twitter/labeled.jsonl \
  --persona configs/persona/wendys-twitter.yaml \
  --output reports/wendys-calibration.json \
  --judge openai:gpt-4o --judge-sample 0.2
```

This analyzes 20% of your sessions with GPT-4 and provides:
- Human-readable explanations of brand voice alignment
- Agreement rate with quantitative metrics
- Detailed reasoning for each score
- Cost tracking (typically $0.03-$0.10 for demo dataset)

## Common Workflows

### Test Before Deploying

```bash
# Run full test suite
alignmenter run --model openai:gpt-4o-mini --config configs/prod.yaml --generate-transcripts

# (Thresholds live in configs/prod.yaml)
alignmenter run --config configs/prod.yaml
```

Add thresholds to your run config:

```yaml
scorers:
  authenticity:
    threshold_fail: 0.80
  safety:
    threshold_fail: 0.95
```

### Compare Model Versions

```bash
# Baseline
alignmenter run --model openai:gpt-4o --config configs/brand.yaml --out reports/baseline --generate-transcripts

# After prompt changes
alignmenter run --model openai:gpt-4o --config configs/brand-v2.yaml --out reports/v2 --generate-transcripts

# Compare reports manually or diff the JSON exports
```

### Sanitize Production Data

```bash
# Preview sanitization (dry run)
alignmenter dataset sanitize datasets/prod_logs.jsonl --dry-run

# Actually sanitize
alignmenter dataset sanitize datasets/prod_logs.jsonl --out datasets/sanitized.jsonl
```

## Next Steps

- **[Core Concepts](concepts.md)** - Understand the metrics and scoring
- **[Persona Configuration](../guides/persona.md)** - Customize your brand voice
- **[CLI Reference](../reference/cli.md)** - Full command documentation
- **[Calibration Guide](../guides/calibration.md)** - Advanced LLM judge usage

## Troubleshooting

### "No API key found"

Set your OpenAI API key:
```bash
export OPENAI_API_KEY="sk-..."
```

### "Module not found: sentence-transformers"

The authenticity scorer requires sentence-transformers:
```bash
pip install sentence-transformers
```

### Tests are slow

Runs reuse existing transcripts by default. Only add `--generate-transcripts` when you explicitly want to call the provider:
```bash
alignmenter run --config configs/brand.yaml --generate-transcripts
```

### Need help?

File an issue on [GitHub](https://github.com/justinGrosvenor/alignmenter/issues) or check the [CLI Reference](../reference/cli.md).
