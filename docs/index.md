# Alignmenter

**Automated testing for AI chatbots.** Measure brand voice, safety, and consistency across model versions.

## Overview

Alignmenter is a production-ready evaluation toolkit for teams shipping AI copilots and chat experiences. Ensure your AI stays on-brand, safe, and stable across model updates.

### Three Core Metrics

- **🎨 Authenticity** – Does the AI match your brand voice? Measures semantic similarity, linguistic traits, and lexicon compliance.
- **🛡️ Safety** – Does it avoid harmful outputs? Combines keyword rules, LLM judges, and offline ML classifiers.
- **⚖️ Stability** – Are responses consistent? Detects semantic drift and variance across sessions.

### Why Alignmenter?

Unlike generic LLM evaluation frameworks, Alignmenter is **purpose-built for persona alignment**:

- **Persona packs**: Define your brand voice in YAML with examples, lexicon, and traits
- **Local-first**: Works without constant API calls (optional LLM judge for qualitative analysis)
- **Budget-aware**: Built-in cost tracking and guardrails
- **Reproducible**: Deterministic scoring, full audit trails
- **Privacy-focused**: Local models available, sanitize production data before evaluation

## Quick Example

```bash
# Install
pip install alignmenter

# Initialize project
alignmenter init

# Run test (regenerate transcripts)
alignmenter run --config configs/run.yaml --generate-transcripts

# Default run (reuses cached transcripts)
alignmenter run --config configs/run.yaml

# View report
alignmenter report --last
```

**Output:**
```
Loading dataset: 60 turns across 10 sessions
Running model: openai:gpt-4o-mini
✓ Brand voice score: 0.83 (range: 0.79-0.87)
✓ Safety score: 0.95
✓ Consistency score: 0.88
Report written to: reports/2025-11-06_14-32/index.html
```

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
- **Offline mode**: Works without internet using local models

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
- **Reproducible results**: Deterministic scoring with fixed seeds

## Getting Started

Ready to start testing your AI chatbot? Check out the [Installation Guide](getting-started/installation.md) or jump to the [Quick Start](getting-started/quickstart.md).

## Community & Support

- **GitHub**: [justinGrosvenor/alignmenter](https://github.com/justinGrosvenor/alignmenter)
- **Issues**: [Report bugs and request features](https://github.com/justinGrosvenor/alignmenter/issues)
- **License**: Apache 2.0

---

<div class="text-center">
  <strong>⭐ Star us on <a href="https://github.com/justinGrosvenor/alignmenter">GitHub</a></strong>
</div>
