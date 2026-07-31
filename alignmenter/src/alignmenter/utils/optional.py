"""Helpers for optional dependency groups.

The core install is intentionally lightweight (no torch, no scikit-learn).
Features that need heavier libraries live behind extras and raise a clear,
actionable error when the extra is not installed.
"""

from __future__ import annotations


class MissingDependencyError(RuntimeError):
    """Raised when a feature needs an optional dependency group that is absent."""


def missing_dependency(feature: str, extra: str, packages: str) -> MissingDependencyError:
    """Build a friendly error pointing at the extra that provides *packages*."""

    return MissingDependencyError(
        f"{feature} requires the optional '{extra}' dependencies ({packages}). "
        f"Install them with:  pip install 'alignmenter[{extra}]'"
    )
