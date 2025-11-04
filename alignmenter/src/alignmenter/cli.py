"""Command-line interface scaffold for Alignmenter."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import requests
import typer
import yaml

from alignmenter.config import get_settings
from alignmenter.providers import load_chat_provider
from alignmenter.providers.base import parse_provider_model
from alignmenter.providers.classifiers import load_safety_classifier
from alignmenter.providers.judges import load_judge_provider
from alignmenter.providers.openai import OpenAICustomGPTProvider
from alignmenter.run_config import load_run_options
from alignmenter.runner import RunConfig, Runner
from alignmenter.scorers.authenticity import AuthenticityScorer
from alignmenter.scorers.safety import SafetyScorer
from alignmenter.scorers.stability import StabilityScorer
app = typer.Typer(help="Alignmenter — audit your model's alignment signals.")

persona_app = typer.Typer(help="Persona helper commands.")
dataset_app = typer.Typer(help="Dataset helper commands.")
import_app = typer.Typer(help="Import helpers.")

app.add_typer(persona_app, name="persona")
app.add_typer(dataset_app, name="dataset")
app.add_typer(import_app, name="import")


@import_app.command("gpt")
def import_gpt(
    instructions: Path = typer.Option(..., "--instructions", help="Path to instructions text file."),
    name: str = typer.Option(..., "--name", help="Display name for the persona."),
    out: Path = typer.Option(..., "--out", help="Where to write the persona YAML."),
    allow_overwrite: bool = typer.Option(False, "--force", help="Overwrite the output file if it exists."),
) -> None:
    """Import Custom GPT instructions into a persona pack."""

    if not instructions.exists():
        raise typer.BadParameter(f"Instructions file not found: {instructions}")
    if out.exists() and not allow_overwrite:
        raise typer.BadParameter(f"Persona file {out} already exists. Use --force to overwrite.")

    text = instructions.read_text(encoding="utf-8").strip()
    if not text:
        raise typer.BadParameter("Instructions file is empty.")

    typer.echo("Parsing GPT instructions...")
    persona_doc = _persona_from_instructions(name, text)

    _ensure_parent(out)
    with out.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(persona_doc, handle, sort_keys=False)

    typer.secho(f"Imported persona written to {out}", fg=typer.colors.GREEN)


PACKAGE_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PACKAGE_ROOT.parent  # e.g., .../site-packages or repo /src
REPO_ROOT = SOURCE_ROOT.parent if SOURCE_ROOT.name == "src" else SOURCE_ROOT
PACKAGE_NAME = PACKAGE_ROOT.name
PROJECT_ROOT = REPO_ROOT

DATA_DIR = PACKAGE_ROOT / "data"
CONFIGS_DIR = DATA_DIR / "configs"
PERSONA_DIR = CONFIGS_DIR / "persona"
DATASETS_DIR = DATA_DIR / "datasets"
SAFETY_KEYWORDS = CONFIGS_DIR / "safety_keywords.yaml"

MODEL_BASE_CHOICES: list[dict[str, Any]] = [
    {
        "id": "openai-gpt4o-mini",
        "label": "OpenAI GPT-4o mini",
        "value": "openai:gpt-4o-mini",
        "description": "Fast, production-ready default with balanced cost",
    },
    {
        "id": "openai-gpt-4.1-mini",
        "label": "OpenAI GPT-4.1 mini",
        "value": "openai:gpt-4.1-mini",
        "description": "Higher quality OpenAI model with vision + tools",
    },
    {
        "id": "anthropic-claude-sonnet",
        "label": "Anthropic Claude 3.5 Sonnet",
        "value": "anthropic:claude-3-5-sonnet-20241022",
        "description": "Anthropic's flagship for nuanced brand copy",
    },
]

MODEL_OPTION_CUSTOM_GPT = {
    "id": "custom-gpt",
    "label": "OpenAI Custom GPT (requires gpt:// ID)",
    "value": None,
    "description": "Use a GPT Builder persona for brand voice benchmarking",
}

MODEL_OPTION_LOCAL = {
    "id": "local-endpoint",
    "label": "Local endpoint (OpenAI-compatible)",
    "value": None,
    "description": "Point to your own server (e.g. vLLM, Ollama) with a model name",
}

MODEL_OPTION_MANUAL = {
    "id": "manual",
    "label": "Manual entry",
    "value": None,
    "description": "Type a custom provider:model string",
}

EMBEDDING_CHOICES: list[dict[str, Any]] = [
    {
        "id": "hashed",
        "label": "Deterministic hashed embeddings (offline default)",
        "value": "hashed",
        "description": "No external calls; great for demos and CI",
    },
    {
        "id": "st-all-minilm",
        "label": "Sentence Transformers: all-MiniLM-L6-v2",
        "value": "sentence-transformer:all-MiniLM-L6-v2",
        "description": "Lightweight English encoder for style similarity",
    },
    {
        "id": "openai-embed-small",
        "label": "OpenAI text-embedding-3-small",
        "value": "openai:text-embedding-3-small",
        "description": "Affordable OpenAI embeddings for higher accuracy",
    },
    {
        "id": "openai-embed-large",
        "label": "OpenAI text-embedding-3-large",
        "value": "openai:text-embedding-3-large",
        "description": "Highest fidelity OpenAI embeddings",
    },
    {
        "id": "manual",
        "label": "Manual entry",
        "value": None,
        "description": "Type any embedding provider identifier",
    },
]


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _resolve_path(candidate: str | Path) -> Path:
    path = Path(candidate)
    if path.exists():
        return path
    if not path.is_absolute():
        normalized = path
        if normalized.parts and normalized.parts[0] == PACKAGE_NAME:
            normalized = Path(*normalized.parts[1:])
        search_roots = [DATA_DIR, REPO_ROOT]
        for root in search_roots:
            fallback = root / normalized
            if fallback.exists():
                return fallback
    raise typer.BadParameter(f"Path not found: {candidate}")


def _prompt_choice(
    title: str,
    options: list[dict[str, Any]],
    *,
    default_index: Optional[int] = None,
) -> dict[str, Any]:
    while True:
        typer.echo(f"{title}:")
        for idx, option in enumerate(options, start=1):
            line = f"  {idx}. {option['label']}"
            description = option.get("description")
            if description:
                line += f" — {description}"
            typer.echo(line)

        prompt_label = "Select option"
        default_value: Optional[str] = None
        if default_index is not None:
            prompt_label += f" [{default_index + 1}]"
            default_value = str(default_index + 1)

        choice_raw = typer.prompt(
            prompt_label,
            default=default_value if default_value is not None else "",
            show_default=False,
        ).strip()

        if not choice_raw:
            if default_index is not None:
                return options[default_index]
            typer.secho("Please choose an option by number.", fg=typer.colors.YELLOW)
            continue

        try:
            choice_idx = int(choice_raw) - 1
        except ValueError:
            typer.secho("Please enter the number of an option.", fg=typer.colors.YELLOW)
            continue

        if 0 <= choice_idx < len(options):
            return options[choice_idx]

        typer.secho("Invalid selection. Try again.", fg=typer.colors.YELLOW)


def _find_model_default_index(model_identifier: Optional[str], choices: list[dict[str, Any]]) -> Optional[int]:
    if not model_identifier:
        return None
    if model_identifier.startswith("openai-gpt:"):
        for idx, option in enumerate(choices):
            if option.get("id") == "custom-gpt":
                return idx
    if model_identifier.startswith("local:"):
        for idx, option in enumerate(choices):
            if option.get("id") == "local-endpoint":
                return idx
    for idx, option in enumerate(choices):
        if option.get("value") == model_identifier:
            return idx
    return None


def _extract_custom_gpt_id(model_identifier: Optional[str]) -> Optional[str]:
    if not model_identifier:
        return None
    if model_identifier.startswith("openai-gpt:"):
        return model_identifier.split(":", 1)[1]
    return None


def _parse_local_identifier(identifier: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not identifier or not identifier.startswith("local:"):
        return None, None
    body = identifier.split(":", 1)[1]
    endpoint, sep, model = body.partition("|")
    return (endpoint or None), (model or None)


@app.command()
def init(
    env_path: Path = typer.Option(
        Path(".env"),
        help="Location for the environment file Alignmenter reads (defaults to project .env).",
    ),
    config_path: Path = typer.Option(
        Path("configs/run.yaml"),
        help="Path for a starter run configuration YAML.",
    ),
) -> None:
    """Interactively configure provider credentials and defaults."""

    typer.secho("Alignmenter setup", fg=typer.colors.CYAN, bold=True)
    typer.echo("Answer a few questions to wire up providers, budgets, and defaults.")

    cwd = Path.cwd()
    env_path = env_path if env_path.is_absolute() else cwd / env_path
    config_path = config_path if config_path.is_absolute() else cwd / config_path

    settings = get_settings()
    env_entries = _load_env(env_path)
    active_env_key = os.getenv("OPENAI_API_KEY") or settings.openai_api_key or ""

    use_openai = typer.confirm(
        "Configure OpenAI access?", default=bool(env_entries.get("OPENAI_API_KEY") or settings.openai_api_key)
    )

    openai_key = ""
    store_openai_in_file = False
    existing_env_key = env_entries.get("OPENAI_API_KEY")
    if use_openai:
        if existing_env_key:
            typer.echo("Found an existing OpenAI key in alignmenter/.env. Leave blank to keep it or enter a new key.")
        elif active_env_key:
            typer.echo("Detected OPENAI_API_KEY in your shell environment. Leave blank to keep using that value.")
        else:
            typer.echo("Provide an OpenAI API key (or leave blank if you plan to export OPENAI_API_KEY manually).")

        openai_input = typer.prompt(
            "OpenAI API key",
            default="" if active_env_key and not existing_env_key else (existing_env_key or ""),
            show_default=False,
        ).strip()

        if openai_input:
            openai_key = openai_input
            store_openai_in_file = typer.confirm(
                "Save this OpenAI key to alignmenter/.env for future runs?",
                default=bool(existing_env_key),
            )
            if not store_openai_in_file:
                typer.secho(
                    "The key will not be written to disk. Export OPENAI_API_KEY in your shell before running Alignmenter.",
                    fg=typer.colors.YELLOW,
                )
        else:
            if existing_env_key:
                openai_key = existing_env_key
                store_openai_in_file = True
            elif active_env_key:
                openai_key = active_env_key
                store_openai_in_file = False
                typer.secho(
                    "Using OPENAI_API_KEY from your environment. Run commands in the same shell to keep using it.",
                    fg=typer.colors.BLUE,
                )
            else:
                openai_key = ""
                store_openai_in_file = False

    embedding_default = env_entries.get("ALIGNMENTER_EMBEDDING_PROVIDER") or settings.embedding_provider or "hashed"
    embedding_default_index = next(
        (idx for idx, option in enumerate(EMBEDDING_CHOICES) if option.get("value") == embedding_default),
        None,
    )
    embedding_choice = _prompt_choice(
        "Embedding provider",
        EMBEDDING_CHOICES,
        default_index=embedding_default_index,
    )
    if embedding_choice.get("id") == "manual":
        embedding_provider = typer.prompt(
            "Embedding provider identifier",
            default=embedding_default,
        ).strip()
        if not embedding_provider:
            embedding_provider = embedding_default or "hashed"
    else:
        embedding_provider = str(embedding_choice.get("value"))

    custom_gpt_id = ""
    if use_openai:
        custom_gpt_id = typer.prompt(
            "Default Custom GPT id (gpt://...), leave blank to skip",
            default=env_entries.get("ALIGNMENTER_CUSTOM_GPT_ID") or settings.custom_gpt_id or "",
            show_default=False,
        ).strip()

    previous_model = env_entries.get("ALIGNMENTER_DEFAULT_MODEL") or settings.default_model
    if not custom_gpt_id:
        custom_gpt_id = _extract_custom_gpt_id(previous_model) or ""
    if custom_gpt_id:
        suggested_model = f"openai-gpt:{custom_gpt_id}"
    elif previous_model:
        suggested_model = previous_model
    else:
        suggested_model = "openai:gpt-4o-mini"

    model_choices = [*MODEL_BASE_CHOICES]
    model_choices.append(MODEL_OPTION_CUSTOM_GPT)
    model_choices.append(MODEL_OPTION_LOCAL)
    model_choices.append(MODEL_OPTION_MANUAL)

    default_model_index = _find_model_default_index(suggested_model, model_choices)
    selected_model_option = _prompt_choice(
        "Default chat model",
        model_choices,
        default_index=default_model_index,
    )

    custom_gpt_env_value: Optional[str] = None
    if selected_model_option.get("id") == "custom-gpt":
        custom_gpt_id = typer.prompt(
            "Custom GPT identifier (gpt://...)",
            default=custom_gpt_id,
            show_default=False,
        ).strip()
        if not custom_gpt_id:
            typer.secho("No Custom GPT id provided. Falling back to OpenAI GPT-4o mini.", fg=typer.colors.YELLOW)
            default_model = "openai:gpt-4o-mini"
            custom_gpt_env_value = None
        else:
            default_model = f"openai-gpt:{custom_gpt_id}"
            custom_gpt_env_value = custom_gpt_id
    elif selected_model_option.get("id") == "local-endpoint":
        default_endpoint, default_local_model = _parse_local_identifier(previous_model)
        endpoint = typer.prompt(
            "Local endpoint URL",
            default=default_endpoint or "http://localhost:8000/v1/chat/completions",
        ).strip()
        local_model = typer.prompt(
            "Local model name",
            default=default_local_model or "llama3",
        ).strip()
        if not endpoint or not local_model:
            typer.secho("Endpoint and model are required. Using manual entry fallback.", fg=typer.colors.YELLOW)
            default_model = typer.prompt(
                "Provider:model identifier",
                default=suggested_model,
            ).strip()
        else:
            default_model = f"local:{endpoint}|{local_model}"
        custom_gpt_id = ""
        custom_gpt_env_value = None
    elif selected_model_option.get("id") == "manual":
        default_model = typer.prompt(
            "Provider:model identifier",
            default=suggested_model,
        ).strip()
        custom_gpt_id = ""
        custom_gpt_env_value = None
    else:
        default_model = str(selected_model_option.get("value"))
        custom_gpt_id = ""
        custom_gpt_env_value = None

    use_judge = typer.confirm(
        "Enable safety judge?",
        default=bool(env_entries.get("ALIGNMENTER_JUDGE_PROVIDER") or settings.judge_provider),
    )

    judge_provider = None
    judge_budget_calls: Optional[int] = None
    judge_budget_usd: Optional[float] = None
    judge_price_in: Optional[float] = None
    judge_price_out: Optional[float] = None
    judge_tokens: Optional[int] = None

    if use_judge:
        judge_provider = typer.prompt(
            "Judge provider (provider:model)",
            default=env_entries.get("ALIGNMENTER_JUDGE_PROVIDER")
            or settings.judge_provider
            or "openai:gpt-4o-mini",
        ).strip()
        judge_budget_calls = _prompt_optional_int(
            "Maximum judge calls per run (blank for none)",
            env_entries.get("ALIGNMENTER_JUDGE_BUDGET") or settings.judge_budget,
        )
        judge_budget_usd = _prompt_optional_float(
            "Judge budget in USD (blank for none)",
            env_entries.get("ALIGNMENTER_JUDGE_BUDGET_USD") or settings.judge_budget_usd,
        )
        judge_price_in = _prompt_optional_float(
            "Price per 1K prompt tokens (USD)",
            env_entries.get("ALIGNMENTER_JUDGE_PRICE_PER_1K_INPUT") or settings.judge_price_per_1k_input,
        )
        judge_price_out = _prompt_optional_float(
            "Price per 1K completion tokens (USD)",
            env_entries.get("ALIGNMENTER_JUDGE_PRICE_PER_1K_OUTPUT") or settings.judge_price_per_1k_output,
        )
        judge_tokens = _prompt_optional_int(
            "Estimated tokens per judge call",
            env_entries.get("ALIGNMENTER_JUDGE_ESTIMATED_TOKENS_PER_CALL")
            or settings.judge_estimated_tokens_per_call,
        )

    env_updates: dict[str, Optional[str]] = {
        "OPENAI_API_KEY": openai_key if (use_openai and store_openai_in_file and openai_key) else None,
        "ALIGNMENTER_DEFAULT_MODEL": default_model or None,
        "ALIGNMENTER_EMBEDDING_PROVIDER": embedding_provider or None,
        "ALIGNMENTER_JUDGE_PROVIDER": judge_provider or None,
        "ALIGNMENTER_JUDGE_BUDGET": str(judge_budget_calls) if judge_budget_calls is not None else None,
        "ALIGNMENTER_JUDGE_BUDGET_USD": _format_float(judge_budget_usd),
        "ALIGNMENTER_JUDGE_PRICE_PER_1K_INPUT": _format_float(judge_price_in),
        "ALIGNMENTER_JUDGE_PRICE_PER_1K_OUTPUT": _format_float(judge_price_out),
        "ALIGNMENTER_JUDGE_ESTIMATED_TOKENS_PER_CALL": str(judge_tokens) if judge_tokens is not None else None,
        "ALIGNMENTER_CUSTOM_GPT_ID": custom_gpt_env_value or None,
    }

    _write_env(env_path, env_updates, existing=env_entries)
    if openai_key:
        os.environ["OPENAI_API_KEY"] = openai_key
    get_settings.cache_clear()

    _write_run_config(
        config_path,
        model=default_model,
        embedding=embedding_provider,
        judge_provider=judge_provider,
        judge_budget=judge_budget_calls,
        judge_budget_usd=judge_budget_usd,
        judge_price_in=judge_price_in,
        judge_price_out=judge_price_out,
        judge_tokens=judge_tokens,
    )

    typer.secho(f"✓ Environment updated -> {env_path}", fg=typer.colors.GREEN)
    typer.secho(f"✓ Run config written -> {config_path}", fg=typer.colors.GREEN)
    display_path = _relative_to_cwd(config_path)
    typer.echo(f"Next: run `alignmenter run --config {display_path}`")

@app.command()
def run(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="Path to run configuration YAML."),
    model: Optional[str] = typer.Option(None, help="Primary model identifier (provider:model-id)."),
    dataset: Optional[str] = typer.Option(None, help="Path to conversation dataset."),
    persona: Optional[str] = typer.Option(None, help="Persona pack to evaluate against."),
    compare: Optional[str] = typer.Option(
        None, help="Optional secondary model identifier for diff runs."
    ),
    out: Optional[str] = typer.Option(None, help="Output directory for run artifacts."),
    keywords: Optional[str] = typer.Option(None, help="Safety keyword configuration file."),
    embedding: Optional[str] = typer.Option(None, help="Embedding provider identifier (e.g. 'sentence-transformer:all-MiniLM-L6-v2')."),
    judge: Optional[str] = typer.Option(None, help="Safety judge provider identifier (e.g. 'openai:gpt-4o-mini')."),
    judge_budget: Optional[int] = typer.Option(None, help="Maximum LLM judge calls per run."),
    generate_transcripts: bool = typer.Option(
        True,
        "--generate/--no-generate",
        help="Call the model to generate fresh transcripts before scoring.",
    ),
) -> None:
    """Execute an evaluation run."""

    settings = get_settings()
    config_options: dict[str, object] = {}
    if config:
        config_path = _resolve_path(config)
        config_options = load_run_options(config_path)
    inputs, run_config = _prepare_run_inputs(
        settings=settings,
        config_options=config_options,
        model=model,
        dataset=dataset,
        persona=persona,
        keywords=keywords,
        out=out,
        compare=compare,
        judge=judge,
        judge_budget=judge_budget,
        embedding=embedding,
    )

    assistant_turns = _lazy_assistant_turn_counter(inputs.dataset_path)
    _maybe_warn_about_cost(inputs, assistant_turns)

    regenerate, provider, compare_provider_obj = _initialise_providers(
        inputs.model_identifier,
        inputs.compare_identifier,
        generate_transcripts,
    )

    safety_classifier = load_safety_classifier(inputs.classifier_identifier)
    judge_provider = _initialise_judge_provider(inputs.judge_identifier)
    scorers, compare_scorers = _build_scorers_for_run(
        inputs,
        safety_classifier=safety_classifier,
        judge_provider=judge_provider,
    )

    primary_progress, compare_progress = _build_progress_managers(
        inputs,
        regenerate,
        assistant_turns,
    )

    with primary_progress as primary_cb, compare_progress as compare_cb:
        runner = Runner(
            config=run_config,
            scorers=scorers,
            compare_scorers=compare_scorers,
            provider=provider,
            compare_provider=compare_provider_obj,
            generate_transcripts=regenerate,
            compare_generate=regenerate,
            progress_callback=primary_cb,
            compare_progress_callback=compare_cb,
        )

        try:
            run_dir = runner.execute()
        except Exception as exc:  # noqa: BLE001 - present friendly message
            typer.secho(f"Run failed: {exc}", fg=typer.colors.RED)
            raise typer.Exit(code=1) from exc

    _print_run_summary(run_dir)
    report_path = run_dir / "index.html"
    target = report_path if report_path.exists() else run_dir
    typer.echo(f"Report written to: {_humanize_path(target)}")
    if sys.stdin.isatty() and sys.stdout.isatty():
        _offer_report_open(run_dir)
    else:
        typer.echo(f"Open in browser: alignmenter report --path {_humanize_path(run_dir)}")


@app.command()
def demo(
    model: str = typer.Option("openai:gpt-4o-mini", help="Demo model to evaluate."),
    out: str = typer.Option("reports/demo", help="Directory for demo artifacts."),
) -> None:
    """Convenience wrapper around run for demo datasets."""
    typer.secho("Running demo evaluation...")
    run(
        model=model,
        config=None,
        dataset=str(DATASETS_DIR / "demo_conversations.jsonl"),
        persona=str(PERSONA_DIR / "default.yaml"),
        compare=None,
        out=out,
        keywords=str(SAFETY_KEYWORDS),
        embedding=None,
        judge=None,
        judge_budget=None,
    )


@app.command()
def report(
    last: bool = typer.Option(False, "--last", help="Open the most recent report."),
    path: Optional[str] = typer.Option(None, "--path", help="Path to specific report directory."),
    reports_dir: str = typer.Option("reports", help="Base reports directory."),
) -> None:
    """Open or view reports."""
    import platform
    import subprocess

    if not last and not path:
        raise typer.BadParameter("Either --last or --path must be specified.")

    if path:
        report_dir = Path(path)
    else:
        # Find most recent report
        reports_base = Path(reports_dir)
        if not reports_base.exists():
            raise typer.BadParameter(f"Reports directory not found: {reports_base}")

        subdirs = [d for d in reports_base.iterdir() if d.is_dir()]
        if not subdirs:
            raise typer.BadParameter(f"No reports found in {reports_base}")

        # Sort by modification time, most recent first
        report_dir = max(subdirs, key=lambda d: d.stat().st_mtime)

    html_path = report_dir / "index.html"
    if not html_path.exists():
        raise typer.BadParameter(f"No HTML report found at {html_path}")

    typer.secho(f"Opening report: {html_path}", fg=typer.colors.GREEN)

    # Open in browser
    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            subprocess.run(["open", str(html_path)], check=True)
        elif system == "Linux":
            subprocess.run(["xdg-open", str(html_path)], check=True)
        elif system == "Windows":
            subprocess.run(["start", str(html_path)], shell=True, check=True)
        else:
            typer.echo(f"Could not open browser. Please open: {html_path}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        typer.echo(f"Could not open browser. Please open: {html_path}")


def _slugify(name: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in name)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_") or "persona"


@persona_app.command("scaffold")
def persona_scaffold(
    name: str = typer.Option(..., "--name", help="Display name for the persona."),
    out: Optional[Path] = typer.Option(None, "--out", help="Path for the generated YAML."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files."),
) -> None:
    """Generate a starter persona YAML template."""

    slug = _slugify(name)
    default_dir = Path("configs/persona")
    target = out or (default_dir / f"{slug}.yaml")
    if not target.is_absolute():
        target = Path.cwd() / target
    _ensure_parent(target)

    if target.exists() and not force:
        raise typer.BadParameter(f"Persona file {target} already exists. Use --force to overwrite.")

    content = (
        f"id: {slug}_v1\n"
        f"display_name: {name}\n"
        "exemplars:\n"
        "  - \"Describe tone, humor, and formality expectations.\"\n"
        "  - \"Add another exemplar guiding brevity or vocabulary.\"\n"
        "lexicon:\n"
        "  preferred: [\"signal\", \"precision\"]\n"
        "  avoid: [\"lol\", \"super hyped\"]\n"
        "style_rules:\n"
        "  sentence_length: {max_avg: 16}\n"
        "  contractions: {allowed: true}\n"
        "  emojis: {allowed: false}\n"
        "safety_rules:\n"
        "  disallowed_topics: []\n"
        "  brand_notes: \"Add extra guardrails here.\"\n"
    )

    target.write_text(content)
    typer.echo(f"Persona template written to {target}")


@persona_app.command("export")
def persona_export(
    dataset: Path = typer.Option(
        DATASETS_DIR / "demo_conversations.jsonl",
        "--dataset",
        help="Dataset file to export from (JSONL).",
    ),
    out: Path = typer.Option(Path("persona_export.csv"), "--out", help="Output CSV path."),
    persona_id: Optional[str] = typer.Option(None, "--persona-id", help="Filter to a single persona."),
    format: str = typer.Option(
        "csv",
        "--format",
        help="Export format: 'csv' (default) or 'labelstudio'.",
    ),
) -> None:
    """Export assistant turns for persona annotation."""

    from alignmenter.utils.io import read_jsonl  # avoid circular import

    records = read_jsonl(dataset)
    if persona_id:
        records = [r for r in records if r.get("persona_id") == persona_id]

    assistant_turns = [
        r
        for r in records
        if r.get("role") == "assistant" and r.get("text")
    ]

    if not assistant_turns:
        raise typer.BadParameter("No assistant turns found matching criteria.")

    export_format = format.lower()
    _ensure_parent(out)

    if export_format == "csv":
        import csv

        with out.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["persona_id", "session_id", "turn_index", "text", "tags"],
            )
            writer.writeheader()
            for turn in assistant_turns:
                writer.writerow(
                    {
                        "persona_id": turn.get("persona_id", ""),
                        "session_id": turn.get("session_id", ""),
                        "turn_index": turn.get("turn_index", ""),
                        "text": turn.get("text", ""),
                        "tags": ";".join(turn.get("tags", [])),
                    }
                )
    elif export_format == "labelstudio":
        tasks = []
        for turn in assistant_turns:
            tasks.append(
                {
                    "data": {
                        "persona_id": turn.get("persona_id", ""),
                        "session_id": turn.get("session_id", ""),
                        "turn_index": turn.get("turn_index", ""),
                        "text": turn.get("text", ""),
                        "tags": turn.get("tags", []),
                    }
                }
            )

        with out.open("w", encoding="utf-8") as handle:
            json.dump(tasks, handle, indent=2, ensure_ascii=False)
    else:
        raise typer.BadParameter("Unsupported format. Choose 'csv' or 'labelstudio'.")

    typer.echo(f"Exported {len(assistant_turns)} turns to {out} ({export_format})")


@persona_app.command("sync-gpt")
def persona_sync_gpt(
    gpt_id: str = typer.Argument(..., help="Custom GPT identifier (gpt://...)"),
    out: Optional[Path] = typer.Option(None, "--out", help="Where to write the synced persona YAML."),
    force: bool = typer.Option(False, "--force", help="Overwrite the target file if it exists."),
) -> None:
    """Pull instructions from a Custom GPT into a persona pack."""

    model_identifier = f"openai-gpt:{gpt_id}"
    target = out if out is not None else _default_gpt_persona_path(gpt_id)
    target = target if target.is_absolute() else Path.cwd() / target
    persona_path = _sync_custom_gpt(
        model_identifier,
        default_persona=PERSONA_DIR / "default.yaml",
        output_path=target,
        force=force,
        silent=False,
    )
    typer.secho(f"✓ Persona synced to {persona_path}", fg=typer.colors.GREEN)


@dataset_app.command("lint")
def dataset_lint(
    path: Path = typer.Argument(..., help="Dataset JSONL file to validate."),
    persona_dir: Optional[Path] = typer.Option(
        PERSONA_DIR, "--persona-dir", help="Directory containing persona YAML files."
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Enable additional checks (sequencing, role coverage, scenario tags).",
    ),
) -> None:
    """Validate dataset schema and persona coverage."""

    from alignmenter.utils.io import read_jsonl

    records = read_jsonl(path)
    required_fields = {"session_id", "turn_index", "role", "text", "tags", "persona_id"}
    errors: list[str] = []
    persona_ids: set[str] = set()
    sessions: dict[str, list[dict]] = {}

    for idx, record in enumerate(records):
        missing = required_fields - record.keys()
        if missing:
            errors.append(f"Record {idx} missing fields: {sorted(missing)}")
        if not isinstance(record.get("turn_index"), int):
            errors.append(f"Record {idx} turn_index must be int")
        if not isinstance(record.get("tags"), list):
            errors.append(f"Record {idx} tags must be list")
        if not isinstance(record.get("text"), str) or not record.get("text"):
            errors.append(f"Record {idx} text must be non-empty string")
        persona = record.get("persona_id")
        if persona:
            persona_ids.add(persona)
        session_id = record.get("session_id")
        if session_id:
            sessions.setdefault(session_id, []).append(record)

    missing_persona_files: set[str] = set()
    if persona_dir:
        persona_dir = persona_dir.resolve()
        available = {p.stem for p in persona_dir.glob("*.yaml")}
        for pid in persona_ids:
            base = pid.split("_")[0]
            if base not in available and pid not in available:
                missing_persona_files.add(pid)

    if missing_persona_files:
        errors.append(
            "Persona definitions missing for: " + ", ".join(sorted(missing_persona_files))
        )

    if strict:
        for session_id, turns in sessions.items():
            roles = {t.get("role") for t in turns}
            if "assistant" not in roles or "user" not in roles:
                errors.append(f"Session {session_id} must include user and assistant turns")
            sorted_turns = sorted(turns, key=lambda t: t.get("turn_index", -1))
            base_index = sorted_turns[0].get("turn_index", 0)
            for offset, record in enumerate(sorted_turns):
                expected = base_index + offset
                if record.get("turn_index") != expected:
                    errors.append(
                        f"Session {session_id} turn_index sequence broken at {record.get('turn_index')}"
                    )
                    break
            if not any(
                isinstance(tag, str) and tag.startswith("scenario:")
                for turn in turns
                for tag in turn.get("tags", [])
            ):
                errors.append(f"Session {session_id} missing scenario:* tag coverage")

    if errors:
        for err in errors:
            typer.secho(err, fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.echo(
        f"Dataset lint passed ({len(records)} records, personas: {', '.join(sorted(persona_ids)) or 'none'})"
    )


def _load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        entries[key.strip()] = value.strip()
    return entries


def _write_env(path: Path, updates: dict[str, Optional[str]], *, existing: dict[str, str]) -> None:
    merged = dict(existing)
    for key, value in updates.items():
        if value is None or value == "":
            merged.pop(key, None)
        else:
            merged[key] = value

    lines = ["# Alignmenter environment configuration"]
    for key in sorted(merged):
        lines.append(f"{key}={merged[key]}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_run_config(
    path: Path,
    *,
    model: str,
    embedding: str,
    judge_provider: Optional[str],
    judge_budget: Optional[int],
    judge_budget_usd: Optional[float],
    judge_price_in: Optional[float],
    judge_price_out: Optional[float],
    judge_tokens: Optional[int],
) -> None:
    dataset_default = DATASETS_DIR / "demo_conversations.jsonl"
    persona_default = PERSONA_DIR / "default.yaml"
    keywords_default = SAFETY_KEYWORDS

    base_dir = path.parent
    reports_dir = (base_dir / ".." / "reports").resolve()

    dataset_workspace = (base_dir.parent / "datasets" / dataset_default.name).resolve()
    persona_workspace = (base_dir / "persona" / persona_default.name).resolve()
    keywords_workspace = (base_dir / keywords_default.name).resolve()

    for source, destination in [
        (dataset_default, dataset_workspace),
        (persona_default, persona_workspace),
        (keywords_default, keywords_workspace),
    ]:
        if destination.exists():
            continue
        _ensure_parent(destination)
        shutil.copy2(source, destination)

    safety_section: dict[str, Any] = {"offline_classifier": "auto"}
    if judge_provider:
        judge_cfg: dict[str, Any] = {"provider": judge_provider}
        if judge_budget is not None:
            judge_cfg["budget"] = judge_budget
        if judge_budget_usd is not None:
            judge_cfg["budget_usd"] = float(judge_budget_usd)
        if judge_price_in is not None:
            judge_cfg["price_per_1k_input"] = float(judge_price_in)
        if judge_price_out is not None:
            judge_cfg["price_per_1k_output"] = float(judge_price_out)
        if judge_tokens is not None:
            judge_cfg["estimated_tokens_per_call"] = judge_tokens
        safety_section["judge"] = judge_cfg

    config = {
        "run_id": "alignmenter_run",
        "model": model,
        "dataset": _relpath_for_config(dataset_workspace, base_dir),
        "persona": _relpath_for_config(persona_workspace, base_dir),
        "keywords": _relpath_for_config(keywords_workspace, base_dir),
        "embedding": embedding,
        "scorers": {"safety": safety_section},
        "report": {"out_dir": _relpath_for_config(reports_dir, base_dir), "include_raw": True},
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)


def _relpath_for_config(target: Path, base_dir: Path) -> str:
    target_abs = Path(target)
    if not target_abs.is_absolute():
        target_abs = (Path.cwd() / target_abs).resolve()
    else:
        target_abs = target_abs.resolve()

    base_abs = Path(base_dir)
    base_abs = base_abs.resolve()
    try:
        return target_abs.relative_to(base_abs).as_posix()
    except ValueError:
        rel = os.path.relpath(target_abs, base_abs)
        return Path(rel).as_posix()


def _format_float(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    return (f"{value:.6f}".rstrip("0").rstrip("."))


def _prompt_optional_int(message: str, default: Optional[Any]) -> Optional[int]:
    default_str = "" if default in (None, "") else str(default)
    while True:
        raw = typer.prompt(message, default=default_str)
        raw = raw.strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            typer.secho("Please enter an integer or leave blank.", fg=typer.colors.RED)


def _prompt_optional_float(message: str, default: Optional[Any]) -> Optional[float]:
    default_str = "" if default in (None, "") else str(default)
    while True:
        raw = typer.prompt(message, default=default_str)
        raw = raw.strip()
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            typer.secho("Please enter a number or leave blank.", fg=typer.colors.RED)


def _build_judge_cost_config(options: dict[str, object], settings: Any) -> dict[str, float]:
    def _coerce_float(value: object) -> Optional[float]:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _coerce_int(value: object) -> Optional[int]:
        try:
            if value is None or value == "":
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    cost = {
        "budget_usd": _coerce_float(options.get("judge_budget_usd") or settings.judge_budget_usd),
        "price_per_1k_input": _coerce_float(
            options.get("judge_price_per_1k_input") or settings.judge_price_per_1k_input
        ),
        "price_per_1k_output": _coerce_float(
            options.get("judge_price_per_1k_output") or settings.judge_price_per_1k_output
        ),
        "estimated_tokens_per_call": _coerce_int(
            options.get("judge_estimated_tokens_per_call") or settings.judge_estimated_tokens_per_call
        ),
        "estimated_prompt_tokens_per_call": _coerce_int(
            options.get("judge_estimated_prompt_tokens_per_call")
            or settings.judge_estimated_prompt_tokens_per_call
        ),
        "estimated_completion_tokens_per_call": _coerce_int(
            options.get("judge_estimated_completion_tokens_per_call")
            or settings.judge_estimated_completion_tokens_per_call
        ),
    }

    cost["cost_per_call_estimate"] = _estimate_cost_per_call(cost)
    return {key: value for key, value in cost.items() if value is not None}


def _estimate_cost_per_call(cost: dict[str, float]) -> Optional[float]:
    price_in = cost.get("price_per_1k_input")
    price_out = cost.get("price_per_1k_output")
    prompt_tokens = cost.get("estimated_prompt_tokens_per_call")
    completion_tokens = cost.get("estimated_completion_tokens_per_call")
    total_tokens = cost.get("estimated_tokens_per_call")

    if prompt_tokens is None and completion_tokens is None:
        prompt_tokens = total_tokens
        completion_tokens = total_tokens

    cost_total = 0.0
    has_cost = False
    if prompt_tokens and price_in:
        cost_total += (prompt_tokens / 1000.0) * price_in
        has_cost = True
    if completion_tokens and price_out:
        cost_total += (completion_tokens / 1000.0) * price_out
        has_cost = True
    return round(cost_total, 6) if has_cost else None


def _count_assistant_turns(path: Path) -> int:
    from alignmenter.utils.io import read_jsonl

    records = read_jsonl(path)
    return sum(1 for record in records if record.get("role") == "assistant" and record.get("text"))


def _relative_to_cwd(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


class _ProgressReporter:
    """Wrap Typer's progress bar to expose a simple callback."""

    def __init__(self, *, total: int, label: str) -> None:
        self.total = max(0, total)
        self.label = label
        self._manager: Optional[Any] = None
        self._bar: Optional[Any] = None

    def __enter__(self) -> Callable[[int], None]:
        if self.total > 0:
            self._manager = typer.progressbar(length=self.total, label=self.label)
            self._bar = self._manager.__enter__()
        return self.advance

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: D401 - Typer handles teardown
        if self._manager is not None:
            self._manager.__exit__(exc_type, exc, tb)
        self._manager = None
        self._bar = None

    def advance(self, step: int = 1) -> None:
        if self._bar is not None and step:
            self._bar.update(step)


@dataclass
class RunInputs:
    """Resolved configuration for `alignmenter run`."""

    model_identifier: str
    compare_identifier: Optional[str]
    dataset_path: Path
    persona_path: Path
    keywords_path: Path
    out_dir: Path
    run_id: str
    include_raw: bool
    embedding_identifier: Optional[str]
    judge_identifier: Optional[str]
    judge_budget: Optional[int]
    judge_cost: dict[str, float | int]
    classifier_identifier: str


def _prepare_run_inputs(
    *,
    settings: Any,
    config_options: dict[str, object],
    model: Optional[str],
    dataset: Optional[str],
    persona: Optional[str],
    keywords: Optional[str],
    out: Optional[str],
    compare: Optional[str],
    judge: Optional[str],
    judge_budget: Optional[int],
    embedding: Optional[str],
) -> tuple[RunInputs, RunConfig]:
    model_identifier = model or config_options.get("model") or settings.default_model
    try:
        parse_provider_model(model_identifier)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    dataset_candidate = dataset or config_options.get("dataset") or settings.default_dataset
    persona_candidate = persona or config_options.get("persona") or settings.default_persona
    keywords_candidate = keywords or config_options.get("keywords") or settings.default_keywords
    out_candidate = out or config_options.get("report_out_dir") or "reports/"

    dataset_path = _resolve_path(dataset_candidate)
    persona_path = _resolve_path(persona_candidate)
    keywords_path = _resolve_path(keywords_candidate)
    out_dir = Path(out_candidate)

    compare_identifier = compare if compare is not None else config_options.get("compare_model")
    judge_identifier = judge or config_options.get("judge_provider") or settings.judge_provider
    resolved_judge_budget = (
        judge_budget
        if judge_budget is not None
        else config_options.get("judge_budget", settings.judge_budget)
    )
    judge_cost = _build_judge_cost_config(config_options, settings)
    run_id = config_options.get("run_id", "alignmenter_run")
    include_raw = config_options.get("include_raw")
    embedding_identifier = (
        embedding or config_options.get("embedding") or settings.embedding_provider
    )
    classifier_identifier = (
        config_options.get("safety_classifier")
        or settings.safety_classifier
        or "auto"
    )

    persona_path = _sync_custom_gpt(model_identifier, persona_path)

    run_config = RunConfig(
        model=model_identifier,
        dataset_path=dataset_path,
        persona_path=persona_path,
        compare_model=compare_identifier,
        report_out_dir=out_dir,
        run_id=run_id,
        include_raw=bool(include_raw) if include_raw is not None else True,
    )

    inputs = RunInputs(
        model_identifier=model_identifier,
        compare_identifier=compare_identifier,
        dataset_path=dataset_path,
        persona_path=persona_path,
        keywords_path=keywords_path,
        out_dir=out_dir,
        run_id=run_id,
        include_raw=run_config.include_raw,
        embedding_identifier=embedding_identifier,
        judge_identifier=judge_identifier,
        judge_budget=resolved_judge_budget,
        judge_cost=judge_cost,
        classifier_identifier=classifier_identifier,
    )

    return inputs, run_config


def _lazy_assistant_turn_counter(dataset_path: Path) -> Callable[[], int]:
    cached: Optional[int] = None

    def _inner() -> int:
        nonlocal cached
        if cached is None:
            cached = _count_assistant_turns(dataset_path)
        return cached

    return _inner


def _maybe_warn_about_cost(inputs: RunInputs, turn_counter: Callable[[], int]) -> None:
    cost_estimate = inputs.judge_cost.get("cost_per_call_estimate")
    budget = inputs.judge_cost.get("budget_usd")
    if not inputs.judge_identifier or cost_estimate is None or budget is None:
        return

    try:
        estimate_value = float(cost_estimate)
        budget_value = float(budget)
    except (TypeError, ValueError):
        return

    turns = turn_counter()
    projected_cost = turns * estimate_value
    if projected_cost > budget_value:
        typer.secho(
            (
                f"Projected judge spend ${projected_cost:.2f} exceeds budget ${budget_value:.2f}."
                " Continue?"
            ),
            fg=typer.colors.YELLOW,
        )
        if not typer.confirm("Proceed with potential overage?", default=False):
            raise typer.Exit(code=1)
    else:
        typer.secho(
            f"Projected judge spend ${projected_cost:.2f} across {turns} calls.",
            fg=typer.colors.BLUE,
        )


def _initialise_providers(
    model_identifier: str,
    compare_identifier: Optional[str],
    regenerate: bool,
) -> tuple[bool, Optional[Any], Optional[Any]]:
    provider = None
    compare_provider = None

    if not regenerate:
        return False, provider, compare_provider

    try:
        provider = load_chat_provider(model_identifier)
    except Exception as exc:  # noqa: BLE001 - surface friendly guidance
        typer.secho(
            f"Unable to initialise provider '{model_identifier}': {exc}",
            fg=typer.colors.YELLOW,
        )
        typer.secho(
            "Falling back to recorded transcripts. Re-run with --generate after configuring credentials.",
            fg=typer.colors.YELLOW,
        )
        return False, None, None

    if compare_identifier:
        try:
            compare_provider = load_chat_provider(str(compare_identifier))
        except Exception as exc:  # noqa: BLE001 - surface friendly guidance
            typer.secho(
                f"Unable to initialise compare provider '{compare_identifier}': {exc}",
                fg=typer.colors.YELLOW,
            )
            typer.secho(
                "Falling back to recorded transcripts for both models.",
                fg=typer.colors.YELLOW,
            )
            return False, provider, None

    return True, provider, compare_provider


def _initialise_judge_provider(judge_identifier: Optional[str]):
    if not judge_identifier:
        return None
    try:
        return load_judge_provider(judge_identifier)
    except RuntimeError as exc:
        typer.secho(str(exc), fg=typer.colors.YELLOW)
        typer.secho(
            "Proceeding without the LLM judge. Set OPENAI_API_KEY or disable the judge in your config.",
            fg=typer.colors.YELLOW,
        )
        return None


def _build_scorers_for_run(
    inputs: RunInputs,
    *,
    safety_classifier: Any,
    judge_provider: Optional[Any],
) -> tuple[list[Any], Optional[list[Any]]]:
    scorer_kwargs = {"embedding": inputs.embedding_identifier}
    judge_callable = judge_provider.evaluate if judge_provider else None

    def _bundle() -> list[Any]:
        return [
            AuthenticityScorer(persona_path=inputs.persona_path, **scorer_kwargs),
            SafetyScorer(
                keyword_path=inputs.keywords_path,
                judge=judge_callable,
                judge_budget=inputs.judge_budget,
                cost_config=inputs.judge_cost,
                classifier=safety_classifier,
            ),
            StabilityScorer(**scorer_kwargs),
        ]

    scorers = _bundle()
    compare_scorers = _bundle() if inputs.compare_identifier else None
    return scorers, compare_scorers


def _build_progress_managers(
    inputs: RunInputs,
    regenerate: bool,
    turn_counter: Callable[[], int],
) -> tuple[_ProgressReporter, _ProgressReporter]:
    primary_total = turn_counter() if regenerate else 0
    compare_total = (
        turn_counter() if regenerate and inputs.compare_identifier else 0
    )
    primary = _ProgressReporter(
        total=primary_total,
        label=f"Generating transcripts ({inputs.model_identifier})",
    )
    compare = _ProgressReporter(
        total=compare_total,
        label=f"Generating transcripts (compare: {inputs.compare_identifier or 'secondary'})",
    )
    return primary, compare


def _default_gpt_persona_path(gpt_id: str) -> Path:
    slug = _slugify(gpt_id.replace("gpt://", ""))
    default_dir = Path("configs/persona/_gpt")
    return (Path.cwd() / default_dir / f"{slug}.yaml").resolve()


def _sync_custom_gpt(
    model_identifier: str,
    default_persona: Path,
    *,
    output_path: Optional[Path] = None,
    force: bool = False,
    silent: bool = True,
) -> Path:
    if not model_identifier.startswith("openai-gpt:"):
        return default_persona

    try:
        _, gpt_id = parse_provider_model(model_identifier)
    except ValueError:
        return default_persona

    settings = get_settings()
    if not settings.openai_api_key:
        if not silent:
            typer.secho(
                "Skipping Custom GPT sync: OPENAI_API_KEY is not configured.",
                fg=typer.colors.YELLOW,
            )
        return default_persona

    target_path = output_path or _default_gpt_persona_path(gpt_id)
    if target_path.exists() and not force:
        if not silent:
            typer.secho(f"Using existing synced persona: {target_path}", fg=typer.colors.BLUE)
        return target_path

    metadata, reason = _fetch_custom_gpt_metadata(gpt_id, settings.openai_api_key)
    if metadata:
        persona_doc = _persona_from_gpt_metadata(metadata)
        if not silent:
            typer.secho(f"Synced GPT persona -> {target_path}", fg=typer.colors.GREEN)
    else:
        description_doc, description_reason = _describe_gpt_via_conversation(
            gpt_id,
            settings.openai_api_key,
        )
        if description_doc:
            persona_doc = _persona_from_gpt_description(description_doc, gpt_id)
            if not silent:
                typer.secho(
                    f"Synced GPT persona via conversation -> {target_path}",
                    fg=typer.colors.GREEN,
                )
        else:
            if not silent and reason:
                typer.secho(reason, fg=typer.colors.YELLOW)
            if not silent and description_reason:
                typer.secho(description_reason, fg=typer.colors.YELLOW)
            persona_doc = _persona_stub_from_gpt(gpt_id)

    _ensure_parent(target_path)
    with target_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(persona_doc, handle, sort_keys=False)

    return target_path


def _fetch_custom_gpt_metadata(
    gpt_id: str, api_key: Optional[str]
) -> tuple[dict[str, Any], Optional[str]]:
    if not api_key:
        return {}, "OPENAI_API_KEY not configured; generating persona stub."
    try:
        provider = OpenAICustomGPTProvider(gpt_id)
    except RuntimeError as exc:
        return {}, str(exc)

    client = getattr(provider, "_client", None)
    gpts = getattr(client, "gpts", None)
    if gpts is None:
        data, reason = _fetch_custom_gpt_metadata_http(gpt_id, api_key)
        if data:
            return data, None
        return {}, reason or "Custom GPT API not available; update openai package or request API access."

    try:
        gpt = gpts.retrieve(gpt_id)
    except Exception as exc:  # pragma: no cover - network failure
        return {}, f"Failed to retrieve GPT metadata via SDK: {exc}"

    return _normalize_gpt_metadata(gpt_id, gpt), None


def _fetch_custom_gpt_metadata_http(
    gpt_id: str, api_key: str
) -> tuple[dict[str, Any], Optional[str]]:
    url = f"https://api.openai.com/v1/gpts/{gpt_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "OpenAI-Beta": "gpts=2024-11-14",
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException as exc:  # pragma: no cover - network failure
        return {}, f"Failed to retrieve GPT metadata via HTTP: {exc}"

    if response.status_code != 200:
        reason = (
            "Custom GPT API access is required (HTTP 404)."
            if response.status_code == 404
            else f"GPT metadata request returned {response.status_code}: {response.text[:120]}"
        )
        return {}, reason

    return _normalize_gpt_metadata(gpt_id, response.json()), None


def _persona_from_gpt_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    gpt_id = metadata.get("id", "custom_gpt")
    slug = _slugify(gpt_id.replace("gpt://", ""))
    instructions = metadata.get("instructions") or ""
    conversation_starters = metadata.get("conversation_starters") or []
    if not conversation_starters and instructions:
        conversation_starters = [line.strip() for line in instructions.splitlines() if line.strip()][:2]

    return {
        "id": f"{slug}_gpt",
        "display_name": metadata.get("name", slug.replace("_", " ").title()),
        "source": {"type": "openai_gpt", "id": gpt_id},
        "exemplars": conversation_starters,
        "lexicon": {"preferred": [], "avoid": []},
        "style_rules": {"instructions": instructions},
        "brand_notes": instructions,
    }


def _persona_stub_from_gpt(gpt_id: str) -> dict[str, Any]:
    slug = _slugify(gpt_id.replace("gpt://", ""))
    display_name = slug.replace("_", " ").title()
    return {
        "id": f"{slug}_gpt",
        "display_name": display_name,
        "source": {"type": "openai_gpt", "id": gpt_id},
        "exemplars": ["Describe the brand voice."],
        "lexicon": {"preferred": [], "avoid": []},
        "style_rules": {"instructions": ""},
        "brand_notes": "",
    }


def _persona_from_instructions(name: str, text: str) -> dict[str, Any]:
    slug = _slugify(name)
    exemplars = _extract_exemplars(text)
    lexicon_pref, lexicon_avoid = _extract_lexicon(text)
    style_rules = _extract_style_rules(text)
    safety = _extract_safety_rules(text)

    return {
        "id": f"{slug}_v1",
        "display_name": name,
        "source": {"type": "manual"},
        "exemplars": exemplars,
        "lexicon": {"preferred": lexicon_pref, "avoid": lexicon_avoid},
        "style_rules": style_rules,
        "safety_rules": safety,
        "brand_notes": text.strip(),
    }


def _extract_exemplars(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    exemplars = [s for s in sentences if 40 <= len(s) <= 200][:3]
    if not exemplars:
        exemplars = sentences[:2]
    return [s.strip() for s in exemplars if s.strip()]


def _extract_lexicon(text: str) -> tuple[list[str], list[str]]:
    stopwords = set(
        """
        a an the and or for with to of in on is are be this that it you your about
        from into through over under as at by we i their our ours yours its which
        """.split()
    )
    words = re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", text.lower())
    frequency: Counter[str] = Counter(w for w in words if w not in stopwords)
    preferred = [w for w, _ in frequency.most_common(12)]

    avoid: list[str] = []
    for match in re.finditer(r"(avoid|never|do not|don’t)[:\-]?\s*(.+)", text, flags=re.I):
        items = re.split(r"[;,/•\n]", match.group(2))
        avoid.extend([i.strip().lower() for i in items if 2 <= len(i.strip()) <= 24])
    avoid = list(dict.fromkeys(avoid))[:12]
    return preferred, avoid


def _extract_style_rules(text: str) -> dict[str, Any]:
    concise = bool(re.search(r"\b(concise|brief|succinct)\b", text, re.I))
    formal = bool(re.search(r"\b(formal|objective|professional)\b", text, re.I))
    emoji_mention = bool(re.search(r"\bemoji|emojis|emoticon\b", text, re.I))
    allow_emoji = bool(re.search(r"emoji.*(allow|use|ok)\b", text, re.I)) if emoji_mention else False

    return {
        "sentence_length": {"max_avg": 16 if concise else 20},
        "contractions": {"allowed": not formal},
        "emojis": {"allowed": allow_emoji},
    }


def _extract_safety_rules(text: str) -> dict[str, list[str]]:
    disallowed: list[str] = []
    for match in re.finditer(r"(disallow|prohibit|no|never)[:\-]?\s*(.+)", text, re.I):
        disallowed.extend(
            [
                item.strip().lower()
                for item in re.split(r"[;,/•\n]", match.group(2))
                if 2 <= len(item.strip()) <= 40
            ]
        )
    disallowed = list(dict.fromkeys(disallowed))[:12]
    return {"disallowed_topics": disallowed}


def _coerce_attr(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _normalize_gpt_metadata(gpt_id: str, payload: Any) -> dict[str, Any]:
    instructions = _coerce_attr(payload, "instructions") or ""
    name = _coerce_attr(payload, "name") or gpt_id.split("/")[-1]
    starters: list[str] = []
    for starter in _coerce_attr(payload, "conversation_starters") or []:
        text = starter
        if isinstance(starter, dict):
            text = starter.get("message") or starter.get("text") or starter.get("content")
            if isinstance(text, dict):
                text = text.get("content") or text.get("text")
        if text:
            starters.append(str(text))

    return {
        "id": gpt_id,
        "name": name,
        "instructions": instructions,
        "conversation_starters": starters,
    }


def _describe_gpt_via_conversation(
    gpt_id: str, api_key: Optional[str]
) -> tuple[dict[str, Any], Optional[str]]:
    if not api_key:
        return {}, "OPENAI_API_KEY not configured; cannot query GPT for self-description."

    if not gpt_id.startswith("gpt://"):
        return {}, (
            "Custom GPT runs require the `gpt://` model identifier (e.g. gpt://org/gpt-name). "
            "The raw g-… object ID cannot be used with the Responses API."
        )
    if not api_key:
        return {}, None

    try:
        provider = OpenAICustomGPTProvider(gpt_id)
    except RuntimeError as exc:
        return {}, str(exc)

    prompt = (
        "You are being evaluated for alignment. "
        "Summarize your own system instructions as JSON with keys: "
        "name (string), description (string), voice_samples (array of 2 short quotes), "
        "lexicon_preferred (array), lexicon_avoid (array), disallowed_topics (array). "
        "Return only JSON."  # keep it strict
    )

    try:
        response = provider.chat([
            {"role": "user", "content": prompt},
        ])
    except Exception as exc:  # pragma: no cover - network failure
        return {}, f"Failed to query GPT for self-description: {exc}"

    text = (response.text or "").strip()
    json_text = _extract_json_block(text)
    if not json_text:
        return {}, "GPT did not return JSON description; using stub persona."

    try:
        description = json.loads(json_text)
    except json.JSONDecodeError:
        return {}, "Unable to parse GPT self-description JSON."

    return description, None


def _persona_from_gpt_description(description: dict[str, Any], gpt_id: str) -> dict[str, Any]:
    slug = _slugify(gpt_id.replace("gpt://", ""))
    name = description.get("name") or slug.replace("_", " ").title()
    samples = description.get("voice_samples") or []
    if isinstance(samples, str):
        samples = [samples]

    preferred = description.get("lexicon_preferred") or []
    avoid = description.get("lexicon_avoid") or []
    disallowed = description.get("disallowed_topics") or []
    description_text = description.get("description") or ""

    return {
        "id": f"{slug}_gpt",
        "display_name": name,
        "source": {"type": "openai_gpt", "id": gpt_id},
        "exemplars": [s for s in samples if isinstance(s, str)][:3],
        "lexicon": {
            "preferred": [w for w in preferred if isinstance(w, str)],
            "avoid": [w for w in avoid if isinstance(w, str)],
        },
        "style_rules": {"instructions": description_text},
        "safety_rules": {
            "disallowed_topics": [t for t in disallowed if isinstance(t, str)],
        },
        "brand_notes": description_text,
    }


def _extract_json_block(text: str) -> Optional[str]:
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    block = text[start : end + 1]
    block = block.replace("```json", "").replace("```", "").strip()
    return block or None


def _print_run_summary(run_dir: Path) -> None:
    run_meta = _safe_read_json(run_dir / "run.json")
    if run_meta:
        turns = run_meta.get("turn_count")
        sessions = run_meta.get("session_count")
        if isinstance(turns, int) and isinstance(sessions, int):
            typer.echo(f"Loading dataset: {turns} turns across {sessions} sessions")

    results = _safe_read_json(run_dir / "results.json")
    if not results:
        return

    scorecards_raw = results.get("scorecards")
    scorecards = (
        [card for card in scorecards_raw if isinstance(card, dict)]
        if isinstance(scorecards_raw, list)
        else []
    )
    scorecard_index = {
        card.get("id"): card for card in scorecards if isinstance(card.get("id"), str)
    }

    scores = results.get("scores")
    primary_scores = (
        scores.get("primary")
        if isinstance(scores, dict) and isinstance(scores.get("primary"), dict)
        else {}
    )

    headlines = [
        ("authenticity", "Brand voice score"),
        ("safety", "Safety score"),
        ("stability", "Consistency score"),
    ]

    for scorer_id, label in headlines:
        value: Optional[float] = None
        card = scorecard_index.get(scorer_id)
        if card:
            primary_value = card.get("primary")
            if isinstance(primary_value, (int, float)):
                value = float(primary_value)
        if value is None and isinstance(primary_scores, dict):
            metrics = primary_scores.get(scorer_id)
            if isinstance(metrics, dict):
                for key in ("mean", "score", "stability"):
                    metric_value = metrics.get(key)
                    if isinstance(metric_value, (int, float)):
                        value = float(metric_value)
                        break
        if value is None:
            continue

        line = f"✓ {label}: {_format_score_value(value)}"
        if scorer_id == "authenticity" and isinstance(primary_scores, dict):
            metrics = primary_scores.get("authenticity")
            if isinstance(metrics, dict):
                low = metrics.get("ci95_low")
                high = metrics.get("ci95_high")
                if isinstance(low, (int, float)) and isinstance(high, (int, float)):
                    line += f" (range: {_format_score_value(low)}-{_format_score_value(high)})"

        typer.echo(line)


def _humanize_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _safe_read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _format_score_value(value: float) -> str:
    return f"{value:.2f}"


def _offer_report_open(run_dir: Path) -> None:
    report_html = run_dir / "index.html"
    if not report_html.exists():
        return
    if typer.confirm("Open the report in your browser now?", default=False):
        try:
            typer.launch(str(report_html))
        except Exception as exc:  # pragma: no cover
            typer.secho(f"Failed to launch browser automatically: {exc}", fg=typer.colors.YELLOW)
            typer.echo(f"Run manually: alignmenter report --path {_humanize_path(run_dir)}")


if __name__ == "__main__":
    app()
