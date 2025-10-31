"""YAML helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> Any:
    """Load a YAML document from *path*."""

    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)
