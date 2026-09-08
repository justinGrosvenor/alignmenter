"""CLI entry points for saved review, comparisons, and release decisions."""

import json
from pathlib import Path
from uuid import UUID

import typer
import yaml

from alignmenter.execution.archive import export_archive, import_archive
from alignmenter.execution.comparison import compare_saved
from alignmenter.execution.review import (
    export_review,
    import_review,
    promote_regression,
    qualification_report,
)
from alignmenter.execution.suite import run_suite
from alignmenter.reporting.durable import export_evaluation
from alignmenter.schemas.gates import GatePolicy

EXIT_CODES = {"pass": 0, "fail": 2, "inconclusive": 3}


def register_release_commands(app):
    @app.command("archive-export")
    def archive_export(
        run_dir: Path = typer.Argument(..., exists=True, file_okay=False),
        out: Path = typer.Option(..., "--out"),
        force: bool = typer.Option(False, "--force"),
    ):
        """Export a verified SQLite snapshot with saved source evidence and reviews."""
        try:
            result = export_archive(run_dir, out, force=force)
        except Exception as exc:
            raise typer.BadParameter(str(exc)) from exc
        typer.echo(f"Archived run {result['run_id']} to {out}")

    @app.command("archive-import")
    def archive_import(
        archive: Path = typer.Argument(..., exists=True, dir_okay=False),
        out: Path = typer.Option(..., "--out"),
    ):
        """Import an inspection copy that cannot fork the original run's call budget."""
        try:
            manifest = import_archive(archive, out)
        except Exception as exc:
            raise typer.BadParameter(str(exc)) from exc
        typer.echo(f"Imported read-only run {manifest.id} to {out}")

    @app.command("init-suite")
    def init_suite(out: Path = typer.Option(..., "--out")):
        """Create a runnable, offline resource-constraint example with no model dependency."""
        from alignmenter.examples.resource_task import example_files
        from alignmenter.reporting.durable import write_artifacts

        try:
            records, suite = example_files()
            write_artifacts(out, {"dataset.jsonl": "".join(json.dumps(r) + "\n" for r in records),
                                  "suite.yaml": yaml.safe_dump(suite, sort_keys=False)})
        except Exception as exc:
            raise typer.BadParameter(str(exc)) from exc
        typer.echo(f"Created {out / 'suite.yaml'}; run with alignmenter run-suite {out / 'suite.yaml'}")

    @app.command("run-suite")
    def run_suite_command(
        suite: Path = typer.Argument(..., exists=True, dir_okay=False),
        out: Path = typer.Option(Path("reports"), "--out"),
        resume: Path | None = typer.Option(None, "--resume", exists=True, file_okay=False),
    ):
        """Capture, evaluate, compare, and write CI artifacts under a frozen suite config."""
        try:
            result = run_suite(suite, out_dir=out, resume=resume)
        except Exception as exc:
            raise typer.BadParameter(str(exc)) from exc
        typer.echo(json.dumps(result, indent=2))
        raise typer.Exit(EXIT_CODES[result["decision"]])

    @app.command("review-export")
    def review_export(
        run_dir: Path = typer.Argument(..., exists=True, file_okay=False),
        out: Path = typer.Option(..., "--out", help="JSONL tasks with editable annotation fields."),
        evaluation_id: UUID | None = typer.Option(None, "--evaluation-id"),
        force: bool = typer.Option(False, "--force"),
    ):
        """Export frozen evidence and blank review fields; original verdicts remain unchanged."""
        try:
            count = export_review(run_dir, out, evaluation_id=evaluation_id, force=force)
        except Exception as exc:
            raise typer.BadParameter(str(exc)) from exc
        typer.echo(f"Exported {count} review tasks to {out}")

    @app.command("review-import")
    def review_import(
        run_dir: Path = typer.Argument(..., exists=True, file_okay=False),
        annotations: Path = typer.Option(..., "--annotations", exists=True, dir_okay=False),
    ):
        """Append completed review annotations atomically; blank outcomes are left pending."""
        try:
            count = import_review(run_dir, annotations)
        except Exception as exc:
            raise typer.BadParameter(str(exc)) from exc
        typer.echo(f"Accepted {count} annotations; existing matching IDs were reused.")

    @app.command("qualify")
    def qualify(
        run_dir: Path = typer.Argument(..., exists=True, file_okay=False),
        evaluation_id: UUID | None = typer.Option(None, "--evaluation-id"),
    ):
        """Measure saved evaluator agreement with supplied human adjudications."""
        try:
            report = qualification_report(run_dir, evaluation_id)
        except Exception as exc:
            raise typer.BadParameter(str(exc)) from exc
        typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
        raise typer.Exit(EXIT_CODES[report["decision"]])

    @app.command("promote")
    def promote(
        run_dir: Path = typer.Argument(..., exists=True, file_okay=False),
        annotation_id: UUID = typer.Option(..., "--annotation-id"),
        out: Path = typer.Option(..., "--out"),
    ):
        """Promote an adjudicated case with separate expectations and preserved split lineage."""
        try:
            result = promote_regression(run_dir, annotation_id, out)
        except Exception as exc:
            raise typer.BadParameter(str(exc)) from exc
        typer.echo(f"Promoted {result['case_id']} to {out}")

    @app.command("check")
    def check(
        run_dir: Path = typer.Argument(..., exists=True, file_okay=False),
        out: Path = typer.Option(..., "--out", help="Write offline HTML, JSON, Markdown, and JUnit here."),
        policy: Path | None = typer.Option(None, "--policy", exists=True, dir_okay=False),
        evaluation_id: UUID | None = typer.Option(None, "--evaluation-id"),
        baseline: Path | None = typer.Option(None, "--baseline", exists=True, file_okay=False),
        baseline_id: UUID | None = typer.Option(None, "--baseline-id"),
        force: bool = typer.Option(False, "--force"),
    ):
        """Check saved results and export CI artifacts without invoking any provider."""
        try:
            configured = GatePolicy.model_validate(yaml.safe_load(policy.read_text())) if policy else None
            comparison = compare_saved(baseline, run_dir, baseline_id=baseline_id, candidate_id=evaluation_id) if baseline else None
            report = export_evaluation(run_dir, out, evaluation_id=evaluation_id, policy=configured, comparison=comparison, force=force)
        except Exception as exc:
            raise typer.BadParameter(str(exc)) from exc
        decision = report["gate_report"]["decision"]
        typer.echo(f"Decision: {decision}\nArtifacts: {out.resolve()}")
        raise typer.Exit(EXIT_CODES[decision])

    @app.command("compare")
    def compare(
        baseline: Path = typer.Argument(..., exists=True, file_okay=False),
        candidate: Path = typer.Argument(..., exists=True, file_okay=False),
        out: Path = typer.Option(..., "--out"),
        baseline_id: UUID | None = typer.Option(None, "--baseline-id"),
        candidate_id: UUID | None = typer.Option(None, "--candidate-id"),
        force: bool = typer.Option(False, "--force"),
    ):
        """Compare matched saved cases and write an offline review with CI artifacts."""
        try:
            comparison = compare_saved(baseline, candidate, baseline_id=baseline_id, candidate_id=candidate_id)
            report = export_evaluation(candidate, out, evaluation_id=candidate_id, comparison=comparison, force=force)
        except Exception as exc:
            raise typer.BadParameter(str(exc)) from exc
        decision = report["gate_report"]["decision"]
        typer.echo(f"Comparison: {decision}; regressions: {comparison['regressions']}\nArtifacts: {out.resolve()}")
        raise typer.Exit(EXIT_CODES[decision])
