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
