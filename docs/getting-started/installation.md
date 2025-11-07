# Installation

## Install from PyPI

The easiest way to install Alignmenter is from PyPI:

```bash
pip install alignmenter
```

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

### Safety Classifier

For offline safety checking without API calls:

```bash
pip install alignmenter[safety]
```

This installs the `distilled-safety-roberta` model for local safety classification.

!!! info "Model Download"
    The safety model (~82MB) downloads automatically on **first use** from Hugging Face Hub.

    - **First run**: 10-30 seconds
    - **Subsequent runs**: Instant (cached locally)

    For CI/CD pipelines, see the [Safety Guide](../guides/safety.md#cicd-caching) for caching instructions to avoid re-downloading on every build.

### Development Tools

For contributing or running tests:

```bash
pip install alignmenter[dev]
```

This includes pytest, ruff, black, and other development tools.

### All Dependencies

To install everything:

```bash
pip install alignmenter[dev,safety]
```

## Verify Installation

Check that Alignmenter is installed correctly:

```bash
alignmenter --version
```

You should see output like:
```
alignmenter version 0.3.0
```

## Set API Keys

Alignmenter needs an OpenAI API key for embeddings (used in authenticity scoring):

```bash
export OPENAI_API_KEY="your-key-here"
```

For Anthropic models:

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
