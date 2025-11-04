"""Alignmenter package scaffold."""

import os

# Hugging Face tokenizers will warn loudly when forked after parallelism is enabled.
# Default to disabling parallel threads unless the user explicitly overrides it.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from .cli import app  # re-export for convenience
from .config import get_settings

__version__ = "0.0.4"

__all__ = ["app", "get_settings", "__version__"]
