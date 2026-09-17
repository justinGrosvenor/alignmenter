"""CLI for decomposed rubric grading (`alignmenter rubric-grade`).

Grades a captured dataset against its per-record ``metadata.rubrics`` — one narrow
judge call per criterion — with a cheap gateway model, budget-capped. With
``--compare-judge`` it runs an agreement check (cheap vs strong) instead, so the
cheap judge is proven before it is trusted. The judge model is any Vercel AI
Gateway ``provider/model`` string; auth is ``AI_GATEWAY_API_KEY`` (or ``OPENAI_API_KEY``).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from alignmenter.rubric_grade import grade_dataset, measure_agreement
from alignmenter.utils.io import read_jsonl, write_json

GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh/v1"


def _make_gateway_judge(model: str, base_url: str):
    """An OpenAIJudge whose OpenAI-compatible client points at the AI Gateway.

    The gateway routes by the ``provider/model`` string, so any gateway model
    works as a judge without a provider-specific SDK. Kept lazy so importing the
    CLI never requires the openai package.
    """
    from openai import OpenAI

    from alignmenter.providers.judges import OpenAIJudge

    api_key = os.environ.get("AI_GATEWAY_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise typer.BadParameter(
            "rubric-grade needs AI_GATEWAY_API_KEY (or OPENAI_API_KEY) for the judge model"
        )
    return OpenAIJudge(model=model, client=OpenAI(base_url=base_url, api_key=api_key))


def register_rubric_grade_command(app: typer.Typer) -> None:
    @app.command("rubric-grade")
    def rubric_grade_cmd(
        dataset: Path = typer.Argument(
            ...,
            exists=True,
            dir_okay=False,
            help="Captured dataset JSONL (turns + metadata.rubrics).",
        ),
        judge: str = typer.Option(
            ..., "--judge", help="Gateway judge model, e.g. anthropic/claude-haiku-4.5."
        ),
        compare_judge: str | None = typer.Option(
            None, "--compare-judge", help="Second model → agreement mode (cheap vs strong)."
        ),
        max_calls: int | None = typer.Option(
            None, "--max-calls", min=1, help="Cap total judge calls (budget)."
        ),
        base_url: str = typer.Option(GATEWAY_BASE_URL, "--base-url", help="AI Gateway base URL."),
        out: Path | None = typer.Option(None, "--out", help="Write the full report JSON here."),
    ):
        """Grade captured responses against per-record rubrics with a cheap decomposed judge.

        Grade mode (default):
            alignmenter rubric-grade captures.jsonl --judge anthropic/claude-haiku-4.5 --max-calls 200
        Agreement mode (prove the cheap judge against a strong one):
            alignmenter rubric-grade captures.jsonl --judge anthropic/claude-haiku-4.5 \\
                --compare-judge anthropic/claude-sonnet-5 --max-calls 200
        """
        records = read_jsonl(dataset)
        judge_a = _make_gateway_judge(judge, base_url)

        if compare_judge:
            judge_b = _make_gateway_judge(compare_judge, base_url)
            report = measure_agreement(records, judge_a, judge_b, max_calls=max_calls)
            payload = {
                "mode": "agreement",
                "judge_a": judge,
                "judge_b": compare_judge,
                **report.to_dict(),
            }
            agr = f"{report.agreement:.1%}" if report.agreement is not None else "n/a"
            kappa = f"{report.kappa:.3f}" if report.kappa is not None else "n/a"
            typer.echo(
                f"agreement: {report.agree}/{report.n} criteria = {agr} · Cohen's κ={kappa} "
                f"· calls {report.calls_a}+{report.calls_b}"
            )
        else:
            report = grade_dataset(records, judge_a, max_calls=max_calls)
            payload = {"mode": "grade", "judge": judge, **report.to_dict()}
            mean = f"{report.mean_score:.3f}" if report.mean_score is not None else "n/a"
            typer.echo(
                f"graded {len(report.graded_cases)}/{len(report.cases)} cases · mean score {mean} "
                f"· {report.calls} calls"
                + (f" · {report.budget_blocked} budget-blocked" if report.budget_blocked else "")
                + (f" · {report.invalid} invalid" if report.invalid else "")
            )

        if out is not None:
            write_json(out, payload)
            typer.echo(f"wrote report -> {out}")
        else:
            typer.echo(json.dumps(payload, indent=2))
