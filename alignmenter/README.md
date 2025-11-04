<p align="center">
  <img src="../assets/alignmenter-banner.png" alt="Alignmenter" width="800">
</p>

<p align="center">
  <strong>Persona-aligned evaluation for conversational AI</strong>
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> •
  <a href="#features">Features</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#documentation">Documentation</a> •
  <a href="#license">License</a>
</p>

---

## Overview

**Alignmenter** is a lightweight, production-ready evaluation toolkit for auditing conversational AI systems across three core dimensions:

- **🎨 Authenticity**: Does the assistant stay on-brand?
- **🛡️ Safety**: Does it avoid harmful or policy-violating outputs?
- **⚖️ Stability**: Are responses consistent across sessions?

Unlike generic LLM evaluation frameworks, Alignmenter is purpose-built for **persona alignment**—ensuring your AI assistant speaks with your unique voice while staying safe and stable.

## Quickstart

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/alignmenter.git
cd alignmenter

# Create virtual environment
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install with dev dependencies
pip install -e .[dev]

# Optional: Install with offline safety classifier
pip install -e .[dev,safety]
```

### Install from PyPI

```bash
pip install alignmenter
alignmenter init
alignmenter run --config configs/run.yaml --no-generate
```

> **Note**: The `safety` extra includes `transformers` for the offline safety classifier (ProtectAI/distilled-safety-roberta). Without it, Alignmenter falls back to a lightweight heuristic classifier. See [docs/offline_safety.md](../docs/offline_safety.md) for details.

### Run Your First Evaluation

```bash
# Set API key (for embedding and judge models)
export OPENAI_API_KEY="your-key-here"

# Run evaluation on demo dataset (regenerates transcripts via the provider)
alignmenter run \
  --model openai:gpt-4o-mini \
  --dataset datasets/demo_conversations.jsonl \
  --persona configs/persona/default.yaml

# Reuse existing transcripts without hitting the provider
alignmenter run --config configs/run.yaml --no-generate

# View interactive HTML report
alignmenter report --last
```

**Output:**
```
Loading dataset: 60 turns across 10 sessions
✓ Brand voice score: 0.82 (range: 0.78-0.86)
✓ Safety score: 0.97
✓ Consistency score: 0.94
Report written to: reports/demo/2025-11-03T00-14-01_alignmenter_run/index.html
```

## Features

### 🎯 Three-Dimensional Scoring

#### Authenticity
- **Embedding similarity**: Measures semantic alignment with persona examples
- **Trait model**: Logistic regression on linguistic features (trained via calibration)
- **Lexicon matching**: Enforces preferred/avoided vocabulary
- **Bootstrap CI**: Statistical confidence intervals for reliability

#### Safety
- **Keyword classifier**: Fast pattern matching for common violations
- **LLM judge**: GPT-4 as a safety oracle with budget controls
- **Offline classifier**: ProtectAI's distilled-safety-roberta (no API calls)
- **Fused scoring**: Weighted ensemble of rule-based + model-based signals
- **Adversarial testing**: Built-in safety traps in demo datasets

#### Stability
- **Cosine variance**: Detects semantic drift across conversation turns
- **Session clustering**: Identifies divergent response patterns
- **Temporal analysis**: Tracks consistency over time

### 📊 Rich Reporting

- **Interactive HTML**: Grade-based report cards with charts (Chart.js)
- **JSON export**: Machine-readable results for CI/CD pipelines
- **CSV downloads**: Per-metric exports for spreadsheet analysis
- **Turn-level explorer**: Drill down into individual responses

### 🔧 Production-Ready

- **Multi-provider support**: OpenAI, Anthropic, local (vLLM, Ollama)
- **Budget guardrails**: Halt runs at 90% of judge API budget
- **Cost projection**: Estimate expenses before execution
- **Reproducibility**: Logs Python version, model, seed, timestamps
- **PII sanitization**: Built-in scrubbing for production data

### 🚀 Developer Experience

- **CLI-first**: Simple commands for evaluation, calibration, reporting
- **YAML configuration**: Declarative persona packs and run configs
- **Python API**: Programmatic access for custom workflows
- **Comprehensive tests**: 69+ unit tests with pytest
- **Type safety**: Full type hints throughout

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Alignmenter CLI                          │
│  alignmenter run / report / calibrate / bootstrap / sanitize    │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                          Runner                                 │
│  Orchestrates evaluation: load data → score → report            │
└─────────────────────────────────────────────────────────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
   │ Authenticity │    │    Safety    │    │  Stability   │
   │    Scorer    │    │    Scorer    │    │    Scorer    │
   └──────────────┘    └──────────────┘    └──────────────┘
           │                   │                   │
           │                   │                   │
   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
   │  Embeddings  │    │  LLM Judge   │    │   Cosine     │
   │  Trait Model │    │  Keywords    │    │  Variance    │
   │   Lexicon    │    │  Fusion      │    │  Clustering  │
   └──────────────┘    └──────────────┘    └──────────────┘
                               │
                               ▼
           ┌───────────────────────────────────────┐
           │         Reporting Layer               │
           │  HTML / JSON / CSV / Interactive UI   │
           └───────────────────────────────────────┘
```

### Key Components

| Component | Purpose | Key Files |
|-----------|---------|-----------|
| **CLI** | Command-line interface | `src/alignmenter/cli.py` |
| **Runner** | Orchestration engine | `src/alignmenter/runner.py` |
| **Scorers** | Metric computation | `src/alignmenter/scorers/` |
| **Providers** | LLM/embedding backends | `src/alignmenter/providers/` |
| **Reporters** | Output generation | `src/alignmenter/reporting/` |
| **Datasets** | JSONL conversation data | `datasets/` |
| **Personas** | Brand voice definitions | `configs/persona/` |

## Documentation

- **[Persona Annotation Guide](../docs/persona_annotation.md)**: How to label data and calibrate trait models
- **[Offline Safety Classifier](../docs/offline_safety.md)**: Using distilled-safety-roberta without API calls
- **[Datasets README](datasets/README.md)**: Data provenance, licensing, and anonymization
- **[Requirements](../docs/alignmenter_requirements.md)**: Full product specification

## Usage Examples

### Evaluate Multiple Models

```bash
# Compare GPT-4 vs Claude
alignmenter run \
  --model openai:gpt-4 \
  --compare anthropic:claude-3-5-sonnet-20241022 \
  --dataset datasets/demo_conversations.jsonl \
  --persona configs/persona/default.yaml
```

### Custom Judge and Embeddings

```bash
# Use Claude as safety judge, local embeddings
alignmenter run \
  --model openai:gpt-4o-mini \
  --judge anthropic:claude-3-5-sonnet-20241022 \
  --embedding sentence-transformer:all-MiniLM-L6-v2 \
  --dataset datasets/demo_conversations.jsonl \
  --persona configs/persona/default.yaml
```

### Bootstrap Synthetic Dataset

```bash
# Generate 50 conversations with adversarial traps
alignmenter bootstrap-dataset \
  --out datasets/my_test.jsonl \
  --sessions 50 \
  --safety-trap-ratio 0.15 \
  --brand-trap-ratio 0.20 \
  --seed 42
```

### Calibrate Persona Traits

```bash
# Train trait model from labeled data
alignmenter calibrate-persona \
  --persona-path configs/persona/mybot.yaml \
  --dataset annotations.jsonl \
  --out configs/persona/mybot.traits.json \
  --epochs 300
```

### Sanitize Production Data

```bash
# Remove PII before evaluation
alignmenter sanitize-dataset \
  --input prod_logs.jsonl \
  --out datasets/sanitized.jsonl \
  --hash-session-ids \
  --scrub-patterns "email|phone|ssn"
```

## Persona Configuration

Define your brand voice in YAML:

```yaml
# configs/persona/mybot.yaml
id: mybot
name: "MyBot Assistant"
description: "Professional, evidence-driven, technical"

voice:
  tone: ["professional", "precise", "measured"]
  formality: "business_casual"

  # Preferred vocabulary
  lexicon:
    preferred:
      - "baseline"
      - "signal"
      - "alignment"
      - "evidence-based"
    avoided:
      - "lol"
      - "bro"
      - "hype"
      - "vibes"

# Example on-brand responses (for embedding similarity)
examples:
  - "Our baseline analysis indicates a 15% improvement in alignment metrics."
  - "The signal-to-noise ratio suggests this approach is viable."
  - "Let's establish a clear baseline before proceeding."

# Trait model weights (generated by calibration)
traits:
  weights: [0.12, -0.34, 0.08, ...]  # Learned from annotations
  vocabulary: ["baseline", "signal", ...]
```

## API Usage

```python
from alignmenter.runner import Runner
from alignmenter.config import RunConfig

# Load configuration
config = RunConfig.from_yaml("configs/run/my_eval.yaml")

# Execute evaluation
runner = Runner(config)
results = runner.execute()

# Access scores
print(f"Authenticity: {results['scores']['authenticity']['mean']:.3f}")
print(f"Safety: {results['scores']['safety']['fused_judge']:.3f}")
print(f"Stability: {results['scores']['stability']['session_variance']:.3f}")

# Generate reports
from alignmenter.reporting import HTMLReporter, JSONReporter

html_reporter = HTMLReporter()
html_reporter.write(
    run_dir=results["run_dir"],
    summary=results["summary"],
    scores=results["scores"],
    sessions=results["sessions"],
)
```

## CI/CD Integration

```yaml
# .github/workflows/eval.yml
name: Persona Evaluation

on: [push, pull_request]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Alignmenter
        run: pip install -e .

      - name: Run Evaluation
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          alignmenter run \
            --model openai:gpt-4o-mini \
            --dataset datasets/ci_test.jsonl \
            --persona configs/persona/default.yaml \
            --judge-budget 100

      - name: Upload Report
        uses: actions/upload-artifact@v3
        with:
          name: evaluation-report
          path: reports/
```

## Development

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src/alignmenter --cov-report=html

# Specific test file
pytest tests/test_scorers.py -v
```

### Code Quality

```bash
# Type checking
mypy src/

# Linting
ruff check src/

# Formatting
black src/ tests/
```

### Local Development

```bash
# Install in editable mode with dev dependencies
pip install -e .[dev]

# Run from source
python -m alignmenter.cli run --help

# Generate report from last run
make report-last
```

## Roadmap

- [ ] Web dashboard for team collaboration
- [ ] Hosted evaluation pipelines (CI/CD SaaS)
- [ ] Multi-language support (non-English personas)
- [ ] Offline safety model (no API required)
- [ ] Cost/latency tracking in scorers
- [ ] Competitive landscape analysis
- [ ] Metric cards and ablation studies

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Areas we'd love help with:**
- Additional persona packs (different brand voices)
- Language support beyond English
- Integration with other LLM providers
- Performance optimizations for large datasets

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.

## Citation

If you use Alignmenter in research, please cite:

```bibtex
@software{alignmenter2024,
  title={Alignmenter: A Framework for Persona-Aligned Conversational AI Evaluation},
  author={Alignmenter Contributors},
  year={2024},
  url={https://github.com/yourusername/alignmenter}
}
```

## Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/yourusername/alignmenter/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/alignmenter/discussions)

---

<p align="center">
  Made with ❤️ by the Alignmenter team
</p>
