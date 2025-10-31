"""I/O helpers for Alignmenter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Read newline-delimited JSON into a list of dicts."""

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"JSONL file not found: {p}")

    records: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no} of {p}: {exc}") from exc
    return records


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    """Write JSON payload to disk with indentation."""

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
