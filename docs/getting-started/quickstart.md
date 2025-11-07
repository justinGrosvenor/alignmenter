# Quick Start

This guide will walk you through running your first Alignmenter evaluation in under 5 minutes.

## Prerequisites

- Alignmenter installed ([Installation Guide](installation.md))
- OpenAI API key set in environment

## 1. Initialize Project

Create a new project directory:

```bash
alignmenter init
```

This creates sample configs, datasets, and personas you can use right away.

## 2. Run Your First Test

Run an evaluation with the demo dataset:

```bash
alignmenter run --model openai-gpt:brand-voice --config configs/brand.yaml
```

You'll see output like:

```
Loading test dataset: 60 conversation turns
Running model: openai-gpt:brand-voice
Computing metrics...
✓ Brand Authenticity: 0.83 (strong match to reference voice)
✓ Safety: 0.95 (2 keyword flags, 0 critical)
✓ Stability: 0.88 (consistent tone across sessions)
Report saved: reports/2025-11-06_14-32/index.html
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
alignmenter run --model openai:gpt-4o --config configs/brand.yaml

# Test with Claude
alignmenter run --model anthropic:claude-3-5-sonnet-20241022 --config configs/brand.yaml
```

## 5. Add LLM Judge Analysis (Optional)

Get qualitative feedback from an LLM judge:

```bash
alignmenter calibrate validate --judge openai:gpt-4o --judge-sample 0.2
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
alignmenter run --model openai-gpt:prod-bot --config configs/prod.yaml

# Check if scores meet thresholds
alignmenter run --config configs/prod.yaml --min-authenticity 0.80 --min-safety 0.95
```

### Compare Model Versions

```bash
# Baseline
alignmenter run --model openai:gpt-4o --config configs/brand.yaml --output-dir reports/baseline

# After prompt changes
alignmenter run --model openai:gpt-4o --config configs/brand-v2.yaml --output-dir reports/v2

# Compare reports manually or diff the JSON exports
```

### Sanitize Production Data

```bash
# Preview sanitization (dry run)
alignmenter dataset sanitize datasets/prod_logs.jsonl --dry-run

# Actually sanitize
alignmenter dataset sanitize datasets/prod_logs.jsonl --output datasets/sanitized.jsonl
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

Use `--no-generate` to reuse cached transcripts:
```bash
alignmenter run --config configs/brand.yaml --no-generate
```

### Need help?

File an issue on [GitHub](https://github.com/justinGrosvenor/alignmenter/issues) or check the [CLI Reference](../reference/cli.md).
