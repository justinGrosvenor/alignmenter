# Installation

## Install the package

```bash
pip install alignmenter
alignmenter --version
```

The 0.3 release reports `0.3.0`. The core supports Python 3.10–3.14 and does not
require torch or scikit-learn. Durable execution uses a local POSIX coordinator;
macOS and Linux are supported, while Windows and multi-host/network-filesystem
coordination are outside the 0.3 support boundary.

## Install from source

```bash
git clone https://github.com/justinGrosvenor/alignmenter.git
cd alignmenter
python -m venv .venv
source .venv/bin/activate
pip install -e 'alignmenter[test,docs]'
```

The package directory is `alignmenter/` inside the repository. Source installation
also gives you the repository's application fixtures and case studies.

## Optional dependencies

Quote bracketed requirements so your shell does not expand them.

| Extra | Purpose |
| --- | --- |
| `[test]` | Core tests, Ruff, build, and distribution validation without ML extras |
| `[docs]` | MkDocs and Material documentation builds |
| `[ml]` | torch, sentence-transformers, and transformers for local embeddings/safety |
| `[calibrate]` | scikit-learn and numpy for numeric calibration |
| `[safety]` | Compatibility alias for `[ml]` |
| `[all]` | All optional runtime dependencies |
| `[dev]` | Existing full development extra, including ML/calibration dependencies |

ML extras have their own upstream platform requirements. Local classifiers and
embeddings can download model weights on first use; they are not used by the offline
resource-task example.

## Provider credentials

The quickstart runs without credentials. Configure keys only for adapters that
actually call a provider, for example `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in the
process environment or your application's secret manager. Keep credentials out of
suite YAML, datasets, source control, and report artifacts.

Run the [quickstart](quickstart.md), or read the
[0.3 migration guide](../guides/migration-0.3.md) for existing integrations.
