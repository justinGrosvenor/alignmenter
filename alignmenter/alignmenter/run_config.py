"""Utilities for loading run configuration files."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from alignmenter.utils import load_yaml


def _resolve(base: Path, value: Optional[str]) -> Optional[Path]:
    if not value:
        return None
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = (base / candidate).resolve()
    return candidate


def load_run_options(path: Path) -> dict[str, Any]:
    data = load_yaml(path) or {}
    base = path.parent

    options: dict[str, Any] = {}

    # Direct fields or legacy fallbacks
    options["run_id"] = data.get("run_id")
    options["model"] = data.get("model") or data.get("providers", {}).get("primary")
    options["compare_model"] = data.get("compare_model") or data.get("providers", {}).get("compare")

    dataset = data.get("dataset")
    if dataset:
        options["dataset"] = _resolve(base, dataset)

    persona = data.get("persona") or data.get("persona_pack")
    if persona:
        options["persona"] = _resolve(base, persona)

    keywords = (
        data.get("keywords")
        or data.get("keyword_lists")
        or data.get("scorers", {}).get("safety", {}).get("keyword_lists")
    )
    if keywords:
        options["keywords"] = _resolve(base, keywords)

    embedding = (
        data.get("embedding")
        or data.get("embedding_provider")
        or data.get("scorers", {}).get("authenticity", {}).get("embedding_model")
    )
    if embedding:
        options["embedding"] = embedding

    judge_section = data.get("judge")
    safety_section = data.get("scorers", {}).get("safety", {})
    if not isinstance(judge_section, dict):
        judge_section = safety_section.get("judge") if isinstance(safety_section, dict) else None

    if isinstance(judge_section, dict):
        if judge_section.get("provider"):
            options["judge_provider"] = judge_section.get("provider")
        if judge_section.get("budget") is not None:
            options["judge_budget"] = judge_section.get("budget")

    if options.get("judge_provider") is None and data.get("judge_provider"):
        options["judge_provider"] = data.get("judge_provider")
    if options.get("judge_budget") is None and data.get("judge_budget") is not None:
        options["judge_budget"] = data.get("judge_budget")

    report = data.get("report", {})
    if isinstance(report, dict):
        if report.get("out_dir"):
            options["report_out_dir"] = _resolve(base, report.get("out_dir"))
        if report.get("include_raw") is not None:
            options["include_raw"] = bool(report.get("include_raw"))

    return options
