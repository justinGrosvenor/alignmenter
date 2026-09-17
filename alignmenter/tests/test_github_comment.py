"""GitHub PR-comment reporter and the --allow-inconclusive CI exit flag."""

from __future__ import annotations

from typer.testing import CliRunner

from alignmenter.cli import app
from alignmenter.execution.evaluation import evaluate_saved
from alignmenter.release_cli import _exit_code
from alignmenter.reporting.durable import export_evaluation
from alignmenter.reporting.github_comment import MARKER, render_github_comment
from alignmenter.schemas.evaluation import JudgeBudget

from .test_durable_evaluations import Judge, captured, spec


def make_report(*, decision="pass", checks=None, metrics=None, comparison=None,
                criteria=None, counts=None, inputs=None, results=None,
                judged=2, applicable=2, unavailable=0, qualification="reviewed"):
    return {
        "spec": {"id": "avercare", "revision": "v1", "qualification": qualification},
        "judged": judged, "applicable": applicable, "unavailable": unavailable,
        "metrics": metrics or {}, "comparison": comparison,
        "criteria": criteria or {}, "counts": counts or {},
        "inputs": inputs or [], "results": results or [],
        "gate_report": {"decision": decision, "checks": checks or [
            {"id": "evaluation", "decision": decision, "reason": "All required outcomes."}]},
    }


def test_pass_comment_has_marker_badge_and_header():
    body = render_github_comment(make_report(decision="pass"))
    assert body.splitlines()[0] == MARKER  # first line so a sticky-comment step can match it
    assert "✅ Pass" in body
    assert "`avercare @ v1`" in body and "2/2 applicable criteria" in body


def test_failing_gate_and_violated_case_surface_in_blocking_section():
    report = make_report(
        decision="fail",
        checks=[
            {"id": "evaluation", "decision": "fail", "reason": "A criterion was violated."},
            {"id": "dangerous_zero", "decision": "fail", "metric": "faithfulness.dangerous_answers",
             "operator": "at_most", "threshold": 0, "value": 2},
        ],
        inputs=[{"key": "k1", "case_id": "hydration-01", "criterion_id": "faithfulness"}],
        results=[{"input_key": "k1", "status": "violated", "reason": "Unsupported dosage claim."}],
    )
    body = render_github_comment(report)
    blocking = body.split("#### ❌ Blocking", 1)[1]
    assert "❌ Fail" in body
    assert "**dangerous_zero**" in blocking and "≤ 0" in blocking and "got **2**" in blocking
    assert "hydration-01" in blocking and "Unsupported dosage claim." in blocking


def test_inconclusive_badge_and_no_blocking_section():
    body = render_github_comment(make_report(decision="inconclusive", qualification="draft"))
    assert "⚠️ Inconclusive" in body
    assert "#### ❌ Blocking" not in body


def test_comparison_renders_baseline_delta_columns():
    report = make_report(
        decision="pass",
        comparison={"metrics": {
            "evaluation.met_rate": {"baseline": 0.8, "candidate": 0.9, "delta": 0.1, "unavailable": False},
            "grounding.citation_resolution": {"baseline": None, "candidate": None, "delta": None, "unavailable": True},
        }},
    )
    body = render_github_comment(report)
    assert "Metrics (vs baseline)" in body
    assert "+0.1" in body                     # signed delta
    assert "⚠️ unavailable" in body           # unavailable metric flagged, not dropped


def test_table_cells_are_escaped_and_do_not_break_the_marker():
    report = make_report(
        decision="fail",
        checks=[{"id": "evaluation", "decision": "fail", "reason": "pipe | and\nnewline <b>"}],
        inputs=[{"key": "k1", "case_id": "a|b", "criterion_id": "c"}],
        results=[{"input_key": "k1", "status": "violated", "reason": "x | y\nz"}],
    )
    body = render_github_comment(report)
    assert body.splitlines()[0] == MARKER
    # no raw pipe/newline leaks into a table cell that would break rendering
    assert "a\\|b" in body and "x \\| y z" in body
    assert "<b>" not in body


def test_exit_code_mapping_and_allow_inconclusive():
    assert _exit_code("pass") == 0
    assert _exit_code("fail") == 2
    assert _exit_code("inconclusive") == 3
    assert _exit_code("inconclusive", allow_inconclusive=True) == 0
    assert _exit_code("fail", allow_inconclusive=True) == 2  # a real failure still blocks


def test_export_writes_comment_alongside_other_artifacts(tmp_path):
    run_dir = captured(tmp_path)
    evaluate_saved(run_dir, spec(), Judge(), budget=JudgeBudget(max_calls=10))  # reviewed + met => pass
    out = tmp_path / "reports"
    export_evaluation(run_dir, out)
    for name in ("evaluation.json", "index.html", "junit.xml", "summary.md", "comment.md"):
        assert (out / name).exists(), name
    comment = (out / "comment.md").read_text()
    assert comment.startswith(MARKER) and "✅ Pass" in comment


def test_check_cli_allow_inconclusive_flips_exit_but_not_failure(tmp_path):
    run_dir = captured(tmp_path)
    evaluate_saved(run_dir, spec(qualification="draft"), Judge(), budget=JudgeBudget(max_calls=10))  # met, but draft => inconclusive
    default = CliRunner().invoke(app, ["check", str(run_dir), "--out", str(tmp_path / "r1")])
    assert default.exit_code == 3, default.output
    allowed = CliRunner().invoke(app, ["check", str(run_dir), "--out", str(tmp_path / "r2"), "--allow-inconclusive"])
    assert allowed.exit_code == 0, allowed.output
    assert (tmp_path / "r2" / "comment.md").exists()
