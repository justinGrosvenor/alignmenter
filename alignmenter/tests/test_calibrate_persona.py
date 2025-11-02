"""Tests for persona calibration CLI helper."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from typer import BadParameter


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def _load_calibrator() -> object:
    root = _locate_repo_root()
    script_path = root / "src" / "alignmenter" / "scripts" / "calibrate_persona.py"
    if not script_path.exists():
        script_path = root / "scripts" / "calibrate_persona.py"
    spec = importlib.util.spec_from_file_location("calibrate_persona", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules.setdefault("calibrate_persona", module)
    spec.loader.exec_module(module)
    return module


def _locate_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        legacy = parent / "scripts" / "calibrate_persona.py"
        src_path = parent / "src" / "alignmenter" / "scripts" / "calibrate_persona.py"
        if legacy.exists() or src_path.exists():
            return parent
    raise RuntimeError("Could not locate scripts/calibrate_persona.py")


def test_calibrate_filters_by_persona(tmp_path: Path) -> None:
    calibrate_persona = _load_calibrator()
    persona_path = tmp_path / "persona.yaml"
    persona_path.write_text("id: demo_v1\n", encoding="utf-8")

    dataset_path = tmp_path / "samples.jsonl"
    _write_jsonl(
        dataset_path,
        [
            {"text": "On-brand tone with precision", "label": 1, "persona_id": "demo_v1"},
            {"text": "Off-brand slang", "label": 0, "persona_id": "demo_v1"},
            {"text": "Other persona data", "label": 0, "persona_id": "other_v1"},
        ],
    )

    out_path = tmp_path / "weights.json"
    calibrate_persona.calibrate(
        persona_path=str(persona_path),
        dataset=str(dataset_path),
        out=str(out_path),
        min_samples=2,
        epochs=20,
        learning_rate=0.05,
    )

    payload = json.loads(out_path.read_text())
    assert payload["trait_model"]["token_weights"], "expected non-empty coefficients"
    assert all(
        token not in payload["trait_model"]["token_weights"]
        for token in {"other", "persona"}
    )


def test_calibrate_errors_when_no_matching_persona(tmp_path: Path) -> None:
    calibrate_persona = _load_calibrator()
    persona_path = tmp_path / "persona.yaml"
    persona_path.write_text("id: demo_v1\n", encoding="utf-8")

    dataset_path = tmp_path / "samples.jsonl"
    _write_jsonl(
        dataset_path,
        [
            {"text": "Other voice", "label": 1, "persona_id": "other"},
        ],
    )

    with pytest.raises(BadParameter):
        calibrate_persona.calibrate(
            persona_path=str(persona_path),
            dataset=str(dataset_path),
            min_samples=1,
            epochs=5,
        )
