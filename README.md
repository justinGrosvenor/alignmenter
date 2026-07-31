<p align="center">
  <img src="https://alignmenter-branding.s3.us-west-2.amazonaws.com/alignmenter-banner.png" alt="Alignmenter" width="800">
</p>

<p align="center">
  <a href="https://pypi.org/project/alignmenter/"><img src="https://badge.fury.io/py/alignmenter.svg" alt="PyPI version"></a>
  <a href="https://pepy.tech/project/alignmenter"><img src="https://pepy.tech/badge/alignmenter" alt="Downloads"></a>
  <a href="https://github.com/justinGrosvenor/alignmenter/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-blue.svg" alt="License"></a>
</p>

<p align="center">
  <strong>Persona-aligned evaluation for conversational AI</strong>
</p>

<p align="center">
  <a href="https://docs.alignmenter.com"><strong>📚 Documentation</strong></a> •
  <a href="#overview">Overview</a> •
  <a href="#quickstart">Quickstart</a> •
  <a href="https://docs.alignmenter.com/getting-started/quickstart/">Quick Start Guide</a> •
  <a href="#contributing">Contributing</a> •
  <a href="#license">License</a>
</p>

---

## Overview

**Alignmenter** is a production-ready evaluation toolkit for teams shipping AI copilots and chat experiences. Ensure your AI stays on-brand, safe, and stable across model updates.

### Three-Dimensional Evaluation

- **🎨 Authenticity** – Does the AI match your brand voice? Measures semantic similarity, linguistic traits, and lexicon compliance.
- **🛡️ Safety** – Does it avoid harmful outputs? Combines keyword rules, LLM judges, and offline ML classifiers.
- **⚖️ Stability** – Are responses consistent? Detects semantic drift and variance across sessions.

### Why Alignmenter?

Unlike generic LLM evaluation frameworks, Alignmenter is **purpose-built for persona alignment**:

- **Persona packs**: Define your brand voice in YAML with examples, lexicon, and traits
- **Judge-blended, offline-capable**: When an LLM judge is configured, brand-voice scores blend the judge's holistic rating with deterministic signals; with no key, it falls back to a fully offline deterministic score (clearly labeled)
- **Budget-aware**: Built-in cost tracking and guardrails
- **Reproducible**: Deterministic scoring, full audit trails
- **Lightweight core**: No `torch` or `scikit-learn` in the default install — heavy local models are opt-in extras

---

## Quickstart

### Installation

**Option 1 · PyPI (recommended for most users)**

```bash
pip install alignmenter          # lightweight core — no torch / scikit-learn
alignmenter init
alignmenter run --config configs/run.yaml
```

Use this path when you want to try Alignmenter quickly, run it in CI, or install it inside a production environment. Add optional extras when you need them: `alignmenter[ml]` for local embeddings and the offline safety classifier, `alignmenter[calibrate]` for the persona calibration pipeline.

**Option 2 · From Source (for case studies & contributing)**

```bash
git clone https://github.com/justinGrosvenor/alignmenter.git
cd alignmenter
pip install -e ./alignmenter[dev,safety]
```

This installs the CLI plus the case-study assets under `alignmenter/case-studies/`, which are excluded from the PyPI wheel. Ideal when you want to reproduce the Wendy's walkthrough or contribute code.

### Run Your First Evaluation

```bash
# Set API key (for embeddings and optional judge)
export OPENAI_API_KEY="your-key-here"

# Run demo evaluation (regenerates transcripts via the selected provider)
alignmenter run \
  --model openai:gpt-4o-mini \
  --dataset datasets/demo_conversations.jsonl \
  --persona configs/persona/default.yaml

# Reuse recorded transcripts (default behavior)
alignmenter run --config configs/run.yaml

# For higher-fidelity local embeddings, install alignmenter[ml] and pass:
#   --embedding sentence-transformer:all-MiniLM-L6-v2

# View interactive report
alignmenter report --last

# Sanitize a dataset (dry run shows sample output)
alignmenter dataset sanitize datasets/demo_conversations.jsonl --dry-run

# Generate fresh transcripts (requires provider access + API keys)
alignmenter run --config configs/run.yaml --generate-transcripts
```

**Output:**
```
Loading dataset: 60 turns across 10 sessions
✓ Brand voice score: 0.82 (range: 0.78-0.86)
✓ Safety score: 0.97
✓ Consistency score: 0.94
Report written to: reports/demo/2025-11-03T00-14-01_alignmenter_run/index.html
```

## 📚 Documentation

**Full documentation available at [docs.alignmenter.com](https://docs.alignmenter.com)**

Quick links:
- **[Quick Start Guide](https://docs.alignmenter.com/getting-started/quickstart/)** - Get started in 5 minutes
- **[Installation](https://docs.alignmenter.com/getting-started/installation/)** - Install and setup
- **[CLI Reference](https://docs.alignmenter.com/reference/cli/)** - All commands
- **[Persona Guide](https://docs.alignmenter.com/guides/persona/)** - Configure your brand voice
- **[LLM Judges](https://docs.alignmenter.com/guides/llm-judges/)** - Qualitative analysis
- **[Contributing](https://docs.alignmenter.com/contributing/)** - How to contribute

---

## Case Studies

- **[Wendy's Twitter Voice](docs/case-studies/wendys-twitter.md)** - Full calibration walkthrough, reproduction steps, and diagnostics for a high-sass social persona. *(Requires installing from this repo so the `case-studies/` assets are present.)*

---

## Repository Structure

```
alignmenter/
├── alignmenter/           # 🐍 Main Python package (CLI, scorers, reporters)
│   ├── src/alignmenter/   # Source code
│   ├── tests/             # Test suite (69+ tests)
│   ├── configs/           # Example configs and persona packs
│   ├── datasets/          # Demo conversation data
│   ├── scripts/           # Utility scripts (bootstrap, calibrate, sanitize)
│   └── README.md          # 📖 Complete CLI documentation
│
├── docs/                  # 📚 Documentation and specifications
│   ├── persona_annotation.md      # Annotation workflow guide
│   ├── offline_safety.md          # Offline safety classifier docs
│   ├── alignmenter_requirements.md # Product specification
│   └── competitive_landscape.md   # vs OpenAI Evals, LangSmith
│
├── assets/                # 🎨 Branding assets
│   ├── alignmenter-banner.png
│   ├── alignmenter-transparent.png
│   └── alignmenter.png
│
├── marketing/             # 🌐 Next.js marketing website
│
└── LICENSE                # Apache 2.0
```

### Package Overview

The core evaluation toolkit lives in **`alignmenter/`**:

| Component | Description |
|-----------|-------------|
| **CLI** | `alignmenter run`, `calibrate-persona`, `bootstrap-dataset`, etc. |
| **Scorers** | Authenticity, safety, and stability metric engines |
| **Providers** | OpenAI, Anthropic, local (vLLM, Ollama) integrations |
| **Reporters** | HTML report cards, JSON exports, CSV downloads |
| **Datasets** | Demo conversations, sanitization tools |
| **Personas** | Brand voice definitions (YAML format) |

---

## Key Features

### 🎯 Persona-First Design

Define your brand voice declaratively:

```yaml
# configs/persona/mybot.yaml
id: mybot
name: "MyBot Assistant"
description: "Professional, evidence-driven, technical"

voice:
  tone: ["professional", "precise", "measured"]
  formality: "business_casual"

  lexicon:
    preferred:
      - "baseline"
      - "signal"
      - "alignment"
    avoided:
      - "lol"
      - "bro"
      - "hype"

examples:
  - "Our baseline analysis indicates a 15% improvement."
  - "The signal-to-noise ratio suggests this approach is viable."
```

### 📊 Interactive Reports

- **Report cards** with overall grades (A/B/C)
- **Interactive charts** (Chart.js visualizations)
- **Calibration diagnostics** (bootstrap confidence intervals, judge agreement)
- **Reproducibility section** (Python version, model, timestamps)
- **Export to CSV/JSON** for custom analysis

### 🔧 Production-Ready

- **Multi-provider support**: OpenAI, Anthropic, vLLM, Ollama
- **Budget guardrails**: Halt at 90% of judge API budget
- **Cost projection**: Estimate expenses before execution
- **PII sanitization**: Built-in scrubbing with `alignmenter dataset sanitize`
- **Offline fallback**: With no API key, scoring runs fully offline on the deterministic path (results labeled `basis: deterministic`); add the `[ml]` extra for local embedding/classifier models

### 🧪 Developer Experience

- **CLI-first**: Simple commands for all workflows
- **Python API**: Programmatic access for custom pipelines
- **Type-safe**: Full type hints throughout
- **Well-tested**: 69+ unit tests with pytest
- **CI/CD ready**: GitHub Actions examples included

---

## Use Cases

### 🏢 Enterprise AI Teams
- **Pre-deployment testing**: Verify brand voice before shipping
- **Regression testing**: Catch drift when updating models
- **A/B testing**: Compare GPT-4 vs Claude vs fine-tuned models
- **Compliance audits**: Generate safety scorecards for regulators

### 🚀 Startups Building AI Products
- **Rapid iteration**: Test persona changes in CI/CD
- **Budget constraints**: Use offline classifiers to reduce API costs
- **Multi-tenant**: Different personas for different customers
- **Quality assurance**: Automated checks on every release

### 🎓 Research & Academia
- **Persona fidelity studies**: Measure alignment with human raters
- **Safety benchmarks**: Compare classifier performance
- **Ablation studies**: Test impact of different scoring components
- **Reproducible results**: Deterministic scoring with fixed seeds

---

## Roadmap

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

---

## Contributing

We welcome contributions from the community!

### Ways to Contribute

- **🐛 Bug Reports**: File issues with reproducible examples
- **✨ Feature Requests**: Propose new scorers, providers, or workflows
- **📝 Documentation**: Improve guides, add examples
- **🧪 Tests**: Expand test coverage
- **🎨 Persona Packs**: Share brand voice configs for common use cases

### Development Workflow

```bash
# Fork and clone
git clone https://github.com/justinGrosvenor/alignmenter.git
cd alignmenter/alignmenter

# Install with dev dependencies
pip install -e .[dev,safety]

# Run tests
pytest

# Run linter
ruff check src/ tests/

# Format code
black src/ tests/

# Submit PR
# - Keep functions small and composable
# - Add tests for new features
# - Update documentation
```

## Community

- **GitHub Issues**: [Report bugs and request features](https://github.com/justinGrosvenor/alignmenter/issues)
- **Twitter**: [@alignmenter](https://twitter.com/alignmenter)
---

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

---

## Open Source Model

Alignmenter is built as **open core**:

**Open Source (Apache 2.0):**
- CLI and all evaluation tools
- Scorers, reporters, and providers
- Persona packs and datasets
- Documentation and examples

**Proprietary (Hosted Service):**
- Web dashboard and team features
- Audit trails and compliance reports
- Managed infrastructure
- Enterprise support

💡 **Get Started**: Use the open-source CLI today. Contact us for hosted features.

---

## License

**Apache License 2.0**

The CLI, scorers, and supporting libraries are licensed under the [Apache License 2.0](LICENSE). This includes all code in the `alignmenter/` directory.

Hosted and proprietary cloud components are not part of this repository and are subject to separate commercial terms.

See [LICENSE](LICENSE) for the full text.

---

## Support

### Documentation
- **[docs.alignmenter.com](https://docs.alignmenter.com)** - Full documentation site
- **[CLI Reference](https://docs.alignmenter.com/reference/cli/)** - Complete command reference
- **[Guides](https://docs.alignmenter.com/guides/persona/)** - Step-by-step tutorials

### Get Help
- **Issues**: [GitHub Issues](https://github.com/justinGrosvenor/alignmenter/issues)
- **Email**: support@alignmenter.com
- **Enterprise Support**: Contact sales@alignmenter.com

---

<p align="center">
  <a href="https://github.com/justinGrosvenor/alignmenter/stargazers">⭐ Star us on GitHub</a> •
  <a href="https://twitter.com/alignmenter">🐦 Follow on Twitter</a> •
  <a href="https://alignmenter.com">🌐 Visit Website</a>
</p>
