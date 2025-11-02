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
        if judge_section.get("budget_usd") is not None:
            options["judge_budget_usd"] = judge_section.get("budget_usd")
        if judge_section.get("price_per_1k_input") is not None:
            options["judge_price_per_1k_input"] = judge_section.get("price_per_1k_input")
        if judge_section.get("price_per_1k_output") is not None:
            options["judge_price_per_1k_output"] = judge_section.get("price_per_1k_output")
        if judge_section.get("estimated_tokens_per_call") is not None:
            options["judge_estimated_tokens_per_call"] = judge_section.get("estimated_tokens_per_call")
        if judge_section.get("estimated_prompt_tokens_per_call") is not None:
            options["judge_estimated_prompt_tokens_per_call"] = judge_section.get("estimated_prompt_tokens_per_call")
        if judge_section.get("estimated_completion_tokens_per_call") is not None:
            options["judge_estimated_completion_tokens_per_call"] = judge_section.get("estimated_completion_tokens_per_call")
        if judge_section.get("offline_classifier"):
            options["safety_classifier"] = judge_section.get("offline_classifier")

    if options.get("judge_provider") is None and data.get("judge_provider"):
        options["judge_provider"] = data.get("judge_provider")
    if options.get("judge_budget") is None and data.get("judge_budget") is not None:
        options["judge_budget"] = data.get("judge_budget")
    for alias, key in (
        ("judge_budget_usd", "judge_budget_usd"),
        ("judge_price_per_1k_input", "judge_price_per_1k_input"),
        ("judge_price_per_1k_output", "judge_price_per_1k_output"),
        ("judge_estimated_tokens_per_call", "judge_estimated_tokens_per_call"),
    ):
        if options.get(alias) is None and data.get(key) is not None:
            options[alias] = data.get(key)

    safety_section = data.get("scorers", {}).get("safety", {})
    if isinstance(safety_section, dict) and safety_section.get("offline_classifier") and options.get("safety_classifier") is None:
        options["safety_classifier"] = safety_section.get("offline_classifier")
    if options.get("safety_classifier") is None and data.get("safety_classifier"):
        options["safety_classifier"] = data.get("safety_classifier")

    report = data.get("report", {})
    if isinstance(report, dict):
        if report.get("out_dir"):
            options["report_out_dir"] = _resolve(base, report.get("out_dir"))
        if report.get("include_raw") is not None:
            options["include_raw"] = bool(report.get("include_raw"))

    return options
