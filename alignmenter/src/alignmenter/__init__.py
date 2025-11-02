"""Alignmenter package scaffold."""

from .cli import app  # re-export for convenience
from .config import get_settings

__all__ = ["app", "get_settings"]
