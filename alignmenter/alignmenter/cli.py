"""Command-line interface scaffold for Alignmenter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import typer

from alignmenter.config import get_settings
from alignmenter.providers.base import parse_provider_model
from alignmenter.providers.judges import load_judge_provider
from alignmenter.run_config import load_run_options
from alignmenter.runner import RunConfig, Runner
from alignmenter.scorers.authenticity import AuthenticityScorer
from alignmenter.scorers.safety import SafetyScorer
from alignmenter.scorers.stability import StabilityScorer
app = typer.Typer(help="Alignmenter — audit your model's alignment signals.")

persona_app = typer.Typer(help="Persona helper commands.")
dataset_app = typer.Typer(help="Dataset helper commands.")

app.add_typer(persona_app, name="persona")
app.add_typer(dataset_app, name="dataset")


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = PACKAGE_ROOT.name
CONFIGS_DIR = PACKAGE_ROOT / "configs"
PERSONA_DIR = CONFIGS_DIR / "persona"
DATASETS_DIR = PACKAGE_ROOT / "datasets"
SAFETY_KEYWORDS = CONFIGS_DIR / "safety_keywords.yaml"


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
        fallback = PACKAGE_ROOT / normalized
        if fallback.exists():
            return fallback
    raise typer.BadParameter(f"Path not found: {candidate}")


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
) -> None:
    """Execute an evaluation run."""

    settings = get_settings()
    config_options: dict[str, object] = {}
    if config:
        config_path = _resolve_path(config)
        config_options = load_run_options(config_path)

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
    judge_budget = (
        judge_budget
        if judge_budget is not None
        else config_options.get("judge_budget", settings.judge_budget)
    )
    judge_cost = _build_judge_cost_config(config_options, settings)
    run_id = config_options.get("run_id", "alignmenter_run")
    include_raw = config_options.get("include_raw")

    projected_cost = None
    if judge_identifier and judge_cost.get("budget_usd") and judge_cost.get("cost_per_call_estimate"):
        assistant_turns = _count_assistant_turns(dataset_path)
        projected_cost = assistant_turns * judge_cost["cost_per_call_estimate"]
        if projected_cost > judge_cost["budget_usd"]:
            typer.secho(
                (
                    f"Projected judge spend ${projected_cost:.2f} exceeds budget ${judge_cost['budget_usd']:.2f}."
                    " Continue?"
                ),
                fg=typer.colors.YELLOW,
            )
            if not typer.confirm("Proceed with potential overage?", default=False):
                raise typer.Exit(code=1)
        else:
            typer.secho(
                f"Projected judge spend ${projected_cost:.2f} across {assistant_turns} calls.",
                fg=typer.colors.BLUE,
            )

    config = RunConfig(
        model=model_identifier,
        dataset_path=dataset_path,
        persona_path=persona_path,
        compare_model=compare_identifier,
        report_out_dir=out_dir,
        run_id=run_id,
        include_raw=bool(include_raw) if include_raw is not None else True,
    )

    embedding_identifier = embedding or config_options.get("embedding") or settings.embedding_provider
    scorer_kwargs = {
        "embedding": embedding_identifier,
    }
    judge_provider = load_judge_provider(judge_identifier)

    scorers = [
        AuthenticityScorer(persona_path=persona_path, **scorer_kwargs),
        SafetyScorer(
            keyword_path=keywords_path,
            judge=judge_provider.evaluate if judge_provider else None,
            judge_budget=judge_budget,
            cost_config=judge_cost,
        ),
        StabilityScorer(**scorer_kwargs),
    ]

    compare_scorers = None
    if compare_identifier:
        compare_scorers = [
            AuthenticityScorer(persona_path=persona_path, **scorer_kwargs),
            SafetyScorer(
                keyword_path=keywords_path,
                judge=judge_provider.evaluate if judge_provider else None,
                judge_budget=judge_budget,
                cost_config=judge_cost,
            ),
            StabilityScorer(**scorer_kwargs),
        ]

    runner = Runner(config=config, scorers=scorers, compare_scorers=compare_scorers)

    try:
        run_dir = runner.execute()
    except Exception as exc:  # noqa: BLE001 - present friendly message
        typer.secho(f"Run failed: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    typer.secho(f"Run complete. Artifacts written to {run_dir}", fg=typer.colors.GREEN)


@app.command()
def demo(
    model: str = typer.Option("openai:gpt-4o-mini", help="Demo model to evaluate."),
    out: str = typer.Option("reports/demo", help="Directory for demo artifacts."),
) -> None:
    """Convenience wrapper around run for demo datasets."""
    typer.secho("Running demo evaluation...")
    ctx = typer.get_current_context()
    ctx.invoke(
        run,
        model=model,
        dataset=str(DATASETS_DIR / "demo_conversations.jsonl"),
        persona=str(PERSONA_DIR / "default.yaml"),
        out=out,
        keywords=str(SAFETY_KEYWORDS),
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
    target = out or PERSONA_DIR / f"{slug}.yaml"
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


if __name__ == "__main__":
    app()
