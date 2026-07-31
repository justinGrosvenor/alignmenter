# Installation

## Install from PyPI

The easiest way to install Alignmenter is from PyPI:

```bash
pip install alignmenter
```

The core install is intentionally **lightweight** — no torch, no scikit-learn. The
default scoring path (hashed embeddings + optional LLM judge + keyword safety) runs
on this alone. Heavier local-model features live behind optional extras (below).

**Requires Python 3.10–3.13.**

## Install from Source

For development or to get the latest features:

```bash
# Clone the repository
git clone https://github.com/justinGrosvenor/alignmenter.git
cd alignmenter

# Create virtual environment
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install the CLI
pip install -e .
```

## Optional Dependencies

Alignmenter ships a small set of extras. Quote the bracketed name so your shell
does not glob it: `pip install "alignmenter[ml]"`.

| Extra | Adds | Enables |
| --- | --- | --- |
| `[ml]` | torch, sentence-transformers, transformers | Local sentence-transformer embeddings **and** the offline safety classifier |
| `[calibrate]` | scikit-learn, numpy | The numeric calibration pipeline (`calibrate bounds`, `calibrate optimize`, `calibrate validate`) |
| `[safety]` | (alias of `[ml]`) | Back-compat name for the offline safety classifier |
| `[all]` | `[ml]` + `[calibrate]` | Everything runtime-optional |
| `[dev]` | `[all]` + pytest, ruff, build, twine | Contributing and running tests |

### Local embeddings and offline safety

```bash
pip install "alignmenter[ml]"
```

This is the only extra that pulls in torch. It provides the
`sentence-transformer:all-MiniLM-L6-v2` embedding provider and the offline safety
classifier (`ProtectAI/distilled-safety-roberta`).

!!! info "Model Download"
    The safety model (~82MB) downloads automatically on **first use** from Hugging Face Hub.

    - **First run**: 10-30 seconds
    - **Subsequent runs**: Instant (cached locally)

    For CI/CD pipelines, see the [Safety Guide](../guides/safety.md#cicd-caching) for caching instructions to avoid re-downloading on every build. More detail in [Offline Safety](../offline_safety.md).

### Persona calibration

```bash
pip install "alignmenter[calibrate]"
```

Needed for the numeric calibration steps. (Interactive labeling, candidate
generation, and `calibrate-persona` trait fitting are pure-Python and work without
this extra.)

### Everything

```bash
pip install "alignmenter[all]"   # runtime extras
pip install "alignmenter[dev]"   # runtime extras + test/lint tooling
```

## Verify Installation

Check that Alignmenter is installed correctly:

```bash
alignmenter --version
```

You should see output like:
```
alignmenter version 0.2.0
```

## Set API Keys

API keys are only needed for the features that call a provider. The default
embedding provider is `hashed` (zero-dependency, offline), so you can run
deterministic evaluations with **no key at all**.

Set a key when you want to generate transcripts, use OpenAI embeddings, or enable
an LLM judge:

```bash
export OPENAI_API_KEY="your-key-here"
```

For Anthropic models (e.g. the `anthropic:claude-sonnet-5` judge):

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

!!! tip
    Add these to your `~/.bashrc` or `~/.zshrc` to make them permanent.

## Initialize Project

Create a new Alignmenter project:

```bash
alignmenter init
```

This creates:
- `configs/` - Configuration files and persona definitions
- `datasets/` - Sample conversation data
- `reports/` - Output directory for test results

## Next Steps

Now that you have Alignmenter installed, check out the [Quick Start Guide](quickstart.md) to run your first test.
