"""Alignmenter package scaffold."""

import os

# Hugging Face tokenizers will warn loudly when forked after parallelism is enabled.
# Default to disabling parallel threads unless the user explicitly overrides it.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from .config import get_settings

__version__ = "0.0.4"
__all__ = ["get_settings", "__version__", "app"]


class _AppProxy:
    """Lazily import the Typer app when first accessed."""

    def _resolve(self):
        from .cli import app as cli_app

        return cli_app

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)

    def __getattr__(self, item):
        return getattr(self._resolve(), item)


app = _AppProxy()
