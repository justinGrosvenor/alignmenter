"""Command-line interface scaffold for Alignmenter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from alignmenter.config import get_settings
from alignmenter.providers.base import parse_provider_model
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
    fallback = PACKAGE_ROOT / path
    if fallback.exists():
        return fallback
    raise typer.BadParameter(f"Path not found: {candidate}")


@app.command()
def run(
    model: Optional[str] = typer.Option(None, help="Primary model identifier (provider:model-id)."),
    dataset: Optional[str] = typer.Option(None, help="Path to conversation dataset."),
    persona: Optional[str] = typer.Option(None, help="Persona pack to evaluate against."),
    compare: Optional[str] = typer.Option(
        None, help="Optional secondary model identifier for diff runs."
    ),
    out: Optional[str] = typer.Option(None, help="Output directory for run artifacts."),
    keywords: Optional[str] = typer.Option(None, help="Safety keyword configuration file."),
    embedding: Optional[str] = typer.Option(None, help="Embedding provider identifier (e.g. 'sentence-transformer:all-MiniLM-L6-v2')."),
) -> None:
    """Execute an evaluation run."""

    settings = get_settings()
    model_identifier = model or settings.default_model

    try:
        parse_provider_model(model_identifier)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    dataset_path = _resolve_path(dataset or settings.default_dataset)
    persona_path = _resolve_path(persona or settings.default_persona)
    keywords_path = _resolve_path(keywords or settings.default_keywords)
    out_dir = Path(out or "reports/")

    config = RunConfig(
        model=model_identifier,
        dataset_path=dataset_path,
        persona_path=persona_path,
        compare_model=compare,
        report_out_dir=out_dir,
    )

    scorers = [
        AuthenticityScorer(persona_path=persona_path, embedding=embedding or settings.embedding_provider),
        SafetyScorer(keyword_path=keywords_path),
        StabilityScorer(embedding=embedding or settings.embedding_provider),
    ]

    compare_scorers = None
    if compare:
        compare_scorers = [
            AuthenticityScorer(persona_path=persona_path, embedding=embedding or settings.embedding_provider),
            SafetyScorer(keyword_path=keywords_path),
            StabilityScorer(embedding=embedding or settings.embedding_provider),
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


if __name__ == "__main__":
    app()
