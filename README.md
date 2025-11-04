<p align="center">
  <img src="https://raw.githubusercontent.com/justinGrosvenor/alignmenter/main/assets/alignmenter-banner.png" alt="Alignmenter" width="800">
</p>

<p align="center">
  <strong>Persona-aligned evaluation for conversational AI</strong>
</p>

<p align="center">
  <a href="#overview">Overview</a> •
  <a href="#quickstart">Quickstart</a> •
  <a href="#repository-structure">Repository</a> •
  <a href="#documentation">Documentation</a> •
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
- **Offline-first**: Works without constant API calls (optional LLM judge for higher accuracy)
- **Budget-aware**: Built-in cost tracking and guardrails
- **Reproducible**: Deterministic scoring, full audit trails
- **Privacy-focused**: Local models available, sanitize production data before evaluation

---

## Quickstart

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/alignmenter.git
cd alignmenter

# Navigate to the Python package
cd alignmenter

# Create virtual environment
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install the CLI
pip install -e .[dev]

# Optional: Install offline safety classifier
pip install -e .[dev,safety]
```

### Install from PyPI

```bash
pip install alignmenter
alignmenter init
alignmenter run --config configs/run.yaml --no-generate
```

### Run Your First Evaluation

```bash
# Set API key (for embeddings and optional judge)
export OPENAI_API_KEY="your-key-here"

# Run demo evaluation (regenerates transcripts via the selected provider)
alignmenter run \
  --model openai:gpt-4o-mini \
  --dataset datasets/demo_conversations.jsonl \
  --persona configs/persona/default.yaml

# Reuse recorded transcripts instead of calling the provider
alignmenter run --config configs/run.yaml --no-generate

# View interactive report
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

See **[alignmenter/README.md](alignmenter/README.md)** for comprehensive documentation, API usage, and examples.

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

## Documentation

### Getting Started
- **[Complete CLI Guide](alignmenter/README.md)** - Installation, usage, API reference
- **[Quickstart Tutorial](alignmenter/README.md#quickstart)** - Run your first evaluation in 2 minutes

### Deep Dives
- **[Persona Annotation Workflow](docs/persona_annotation.md)** - How to label data and train trait models
- **[Offline Safety Classifier](docs/offline_safety.md)** - Using distilled-safety-roberta without API calls
- **[Dataset Management](alignmenter/datasets/README.md)** - Provenance, licensing, anonymization

### Reference
- **[Product Requirements](docs/alignmenter_requirements.md)** - Full specification
- **[Competitive Analysis](docs/competitive_landscape.md)** - vs OpenAI Evals, LangSmith, Arize Phoenix
- **[Architecture Diagram](alignmenter/README.md#architecture)** - System design overview

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
- **PII sanitization**: Built-in scrubbing with `alignmenter sanitize-dataset`
- **Offline mode**: Works without internet using local models

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

### Current (v0.0.1)
- ✅ Three-dimensional scoring (authenticity, safety, stability)
- ✅ Multi-provider support (OpenAI, Anthropic, local)
- ✅ HTML report cards with interactive charts
- ✅ Offline safety classifier (distilled-safety-roberta)
- ✅ Budget guardrails and cost tracking
- ✅ PII sanitization tools

### Upcoming (v0.1.0)
- [ ] Web dashboard for team collaboration
- [ ] Hosted evaluation pipelines (CI/CD SaaS)
- [ ] Multi-language support (non-English personas)
- [ ] Real-time monitoring and alerts
- [ ] Advanced trait models (neural networks)

### Future (v1.0.0)
- [ ] Enterprise SSO and RBAC
- [ ] Synthetic test case generation
- [ ] Fine-tuning integrations
- [ ] Custom metric plugins
- [ ] Batch processing optimizations

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
git clone https://github.com/yourusername/alignmenter.git
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

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for detailed guidelines.

---

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
  url={https://github.com/yourusername/alignmenter},
  license={Apache-2.0}
}
```

---

## License

**Apache License 2.0**

The CLI, scorers, and supporting libraries are licensed under the [Apache License 2.0](LICENSE). This includes all code in the `alignmenter/` directory.

Hosted and proprietary cloud components are not part of this repository and are subject to separate commercial terms.

See [LICENSE](LICENSE) for the full text.

---

## Support

### Documentation
- **[Complete Guide](alignmenter/README.md)** - Comprehensive CLI documentation
- **[API Reference](alignmenter/src/alignmenter/)** - Python package reference
- **[Examples](alignmenter/README.md#usage-examples)** - Common workflows

### Get Help
- **Issues**: [GitHub Issues](https://github.com/yourusername/alignmenter/issues)
- **Email**: support@alignmenter.com
- **Enterprise Support**: Contact sales@alignmenter.com

---

<p align="center">
  <a href="https://github.com/yourusername/alignmenter/stargazers">⭐ Star us on GitHub</a> •
  <a href="https://twitter.com/alignmenter">🐦 Follow on Twitter</a> •
  <a href="https://alignmenter.com">🌐 Visit Website</a>
</p>
