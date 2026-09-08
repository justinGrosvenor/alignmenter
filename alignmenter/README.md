# Alignmenter

Application alignment evaluations with saved evidence, repeatable release checks,
and a lightweight Python SDK and CLI.

## Overview

Alignmenter 0.3 checks whether an assistant meets the commitments of its application:
uses the resources the user has, respects constraints, supports claims with supplied
evidence, and avoids dangerous advice. Capture answers once, evaluate them under
versioned criteria, compare a candidate with a baseline, and preserve human review.

- **Durable execution:** SQLite observations, frozen inputs, explicit recovery, and
  shared judge reservations preserve partial work across interruptions.
- **Application-owned checks:** deterministic evaluator factories and typed metrics
  work with the same grouping, reports, comparisons, and gates as builtins.
- **Evidence evaluation:** offline quantity traceability/citation checks and strict
  judged faithfulness retain the claims and source quotes behind each outcome.
- **Release decisions:** matched case comparisons, explicit coverage, absolute and
  regression gates, and consistent CLI/HTML/JSON/Markdown/JUnit results.
- **Human review:** append-only JSONL annotation exchange, adjudication, evaluator
  agreement reports, and regression promotion with case lineage and split groups.
- **Local inspection:** offline HTML and portable read-only run archives; the core
  install does not require torch or scikit-learn.

Missing work cannot produce a green release check. A draft specification cannot pass.
The legacy persona, authenticity, safety, stability, and calibration tools remain
available; new release integrations should use the durable workflow.

## Quickstart

```bash
pip install alignmenter
alignmenter --version
alignmenter init-suite --out evals/resource-task
alignmenter run-suite evals/resource-task/suite.yaml --out reports
```

The installed example uses a local target and a deterministic resource constraint.
It needs no API key. The command prints the run directory, evaluation UUID, decision,
and artifact directory. Open its `index.html` to inspect evidence. Exit codes are
**0 pass, 2 fail, 3 inconclusive**. Exercise a deliberate failure with:

```bash
ALIGNMENTER_DEMO_VARIANT=bad alignmenter run-suite evals/resource-task/suite.yaml --out reports
```

To work from this checkout, including a release candidate before publication:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e 'alignmenter[test,docs]'
```

Python 3.10–3.14 are supported for the core package. Durable execution uses a local
POSIX coordinator; Windows and multi-host/network-filesystem execution are not
supported in 0.3. Optional `[ml]` and `[calibrate]` extras retain their upstream
platform requirements.

```python
from alignmenter.sdk import run_suite, evaluation_summary

result = run_suite("evals/resource-task/suite.yaml", out_dir="reports")
summary = evaluation_summary(result["run_dir"], details=True)
```

See the [release workflow](https://docs.alignmenter.com/guides/release-workflow/),
[SDK reference](https://docs.alignmenter.com/reference/sdk/), and
[0.3 migration guide](https://docs.alignmenter.com/guides/migration-0.3/).
In the repository, these sources are under `docs/guides/` and `docs/reference/`.

The example is an engineering fixture, not evidence of model quality. Atlas integration
fixtures preserve real failures, with product rubrics still marked draft. Actual judge
qualification needs independent human references and saved model outputs. AverCare
qualification awaits a selected application workflow. Hosted review, physical-device
replay, distributed budgets, and automatic optimization remain roadmap work.

## Legacy persona documentation

The sections below describe the retained persona/scorer APIs. Their older scores,
reports, and scorer-local budgets do not use the new durable contracts. See the
linked migration guide when integrating them into release checks.

## Legacy persona features

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

## 📚 Documentation

**Full documentation available at [docs.alignmenter.com](https://docs.alignmenter.com)**

Quick links:
- **[Quick Start Guide](https://docs.alignmenter.com/getting-started/quickstart/)** - Get started in 5 minutes
- **[Installation](https://docs.alignmenter.com/getting-started/installation/)** - Install and setup
- **[CLI Reference](https://docs.alignmenter.com/reference/cli/)** - Complete command reference
- **[Persona Guide](https://docs.alignmenter.com/guides/persona/)** - Configure your brand voice
- **[Calibration Guide](https://docs.alignmenter.com/guides/calibration/)** - Advanced calibration workflow
- **[Safety Guide](https://docs.alignmenter.com/guides/safety/)** - Offline safety classifier
- **[LLM Judges](https://docs.alignmenter.com/guides/llm-judges/)** - Qualitative analysis
- **[Contributing](https://docs.alignmenter.com/contributing/)** - How to contribute

---

## Case Studies

- **[Wendy's Twitter Voice](../docs/case-studies/wendys-twitter.md)** - End-to-end calibration example using the included case-study assets. *(Available when running from the source repo; not included in the PyPI wheel.)*

---

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
alignmenter dataset sanitize prod_logs.jsonl \
  --out datasets/sanitized.jsonl \
  --no-use-hashing
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

## Legacy API usage

`Runner` coordinates transcript preparation, scoring, and report generation.
It takes a `RunConfig` plus a list of scorers, and `execute()` returns the
path to the timestamped report directory (JSON + HTML are written for you).

Runs now persist source snapshots and each captured answer before scoring. If execution
fails, `runner.run_dir` identifies the saved work. Use `alignmenter status RUN_DIRECTORY`
and `alignmenter export-transcripts RUN_DIRECTORY --out recovered.jsonl` to inspect and
recover committed records. `runner.capture()` and `alignmenter capture` save answers
without scoring; `alignmenter resume` continues compatible capture with explicit adapter
recovery contracts. See the [durable run guide](../docs/guides/durable-runs.md) and
[capture/recovery guide](../docs/guides/capture-recovery.md) for the contracts and limits.

`alignmenter evaluate RUN_DIRECTORY --spec rubrics.yaml --judge-factory module:factory
--max-judge-calls 20` evaluates saved answers with versioned behavior criteria, a shared
durable judge budget, and reusable replies/verdicts. `alignmenter evaluation-status
RUN_DIRECTORY --details` exports the saved evidence and decisions without more judge
calls. This path also supports [grounding and faithfulness](../docs/guides/grounding-faithfulness.md)
with typed evidence, explicit missing-data states, and saved metrics. A grounding-only
spec needs no judge factory or budget. Existing `run` scorers retain their legacy behavior;
see [durable evaluations](../docs/guides/durable-evaluations.md) for the accounting boundary.

```python
import json
from pathlib import Path

from alignmenter.runner import RunConfig, Runner
from alignmenter.scorers.authenticity import AuthenticityScorer
from alignmenter.scorers.safety import SafetyScorer
from alignmenter.scorers.stability import StabilityScorer

config = RunConfig(
    model="openai:gpt-4o-mini",
    dataset_path=Path("datasets/demo_conversations.jsonl"),
    persona_path=Path("configs/persona/default.yaml"),
)

# Pass a judge to AuthenticityScorer/SafetyScorer to blend LLM judgment in;
# omit it (as here) for a fully offline, deterministic run.
scorers = [
    AuthenticityScorer(persona_path=config.persona_path, embedding="hashed"),
    SafetyScorer(keyword_path=Path("configs/safety_keywords.yaml")),
    StabilityScorer(embedding="hashed"),
]

# generate_transcripts=False reuses recorded transcripts (no provider calls).
runner = Runner(config, scorers, generate_transcripts=False)
run_dir = runner.execute()  # -> Path to reports/<timestamp>_<run_id>/

results = json.loads((run_dir / "results.json").read_text())
primary = results["scores"]["primary"]
auth = primary["authenticity"]
print(f"Authenticity: {auth['mean']:.3f}  (basis: {auth['basis']})")
print(f"Safety:       {primary['safety']['score']:.3f}")
print(f"Stability:    {primary['stability']['stability']:.3f}")
```

## Legacy CI integration

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
        run: pip install alignmenter

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

## Earlier persona roadmap

### Completed ✅
- Three-dimensional scoring (authenticity, safety, stability)
- Multi-provider support (OpenAI, Anthropic, local models)
- HTML report cards with interactive charts
- Offline safety classifier (distilled-safety-roberta)
- LLM judges for qualitative analysis
- Budget guardrails and cost tracking
- PII sanitization tools
- Calibration workflow and diagnostics

### In Progress 🚧
- Multi-language support (non-English personas)
- Batch processing optimizations
- Additional embedding providers

### Future Considerations 💭
- Synthetic test case generation
- Custom metric plugins
- Advanced trait models (neural networks)

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
  year={2025},
  url={https://github.com/justinGrosvenor/alignmenter},
  license={Apache-2.0}
}
```

## Support

- **Documentation**: [docs.alignmenter.com](https://docs.alignmenter.com)
- **Issues**: [GitHub Issues](https://github.com/justinGrosvenor/alignmenter/issues)
- **Discussions**: [GitHub Discussions](https://github.com/justinGrosvenor/alignmenter/discussions)

---

<p align="center">
  Made with ❤️ by the Alignmenter team
</p>
