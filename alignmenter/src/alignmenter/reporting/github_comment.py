"""Sticky GitHub pull-request comment over one saved decision; never executes a scorer.

Renders the same ``report`` structure the other durable reporters consume
(:mod:`alignmenter.reporting.durable`) into Markdown tuned for a PR comment: a
verdict badge, blocking issues first, a gate table, metrics (with baseline
deltas when a comparison is present), and collapsed breakdowns. The leading
marker lets a CI step find and update one sticky comment instead of appending.
"""

from __future__ import annotations

MARKER = "<!-- alignmenter:report -->"

_DECISION_BADGE = {"pass": "✅ Pass", "fail": "❌ Fail", "inconclusive": "⚠️ Inconclusive"}
_CHECK_ICON = {"pass": "✅", "fail": "❌", "inconclusive": "➖"}
_OPERATOR = {"at_least": "≥", "at_most": "≤"}


def _cell(value):
    """Escape a value for a single Markdown table cell."""
    if value is None:
        return "—"
    return (str(value).replace("\\", "\\\\").replace("|", "\\|")
            .replace("\n", " ").replace("<", "&lt;").replace(">", "&gt;"))


def _num(value, digits=3):
    if value is None:
        return "—"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{digits}f}".rstrip("0").rstrip(".") or "0"
    return str(value)


def _signed(value, digits=3):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return ("+" if value > 0 else "") + _num(value, digits)
    return _num(value, digits)


def _icon(decision):
    return _CHECK_ICON.get(decision, _cell(decision))


def _gate_detail(check):
    metric = check.get("metric")
    if metric is None:
        return _cell(check.get("reason", ""))
    operator = _OPERATOR.get(check.get("operator"), check.get("operator") or "")
    return f"`{_cell(metric)}` {operator} {_num(check.get('threshold'))} · got **{_num(check.get('value'))}**"


def _blocking_lines(report):
    lines = []
    for check in report["gate_report"].get("checks", []):
        # Skip the structural "evaluation"/"comparison" umbrella checks (no metric);
        # the ❌ badge and the violated cases below already convey those.
        if check["decision"] == "fail" and check.get("metric") is not None:
            lines.append(f"- **{_cell(check['id'])}** — {_gate_detail(check)}")
    inputs = {item["key"]: item for item in report.get("inputs", [])}
    violated = [(inputs.get(r["input_key"]), r) for r in report.get("results", [])
                if r.get("status") == "violated"]
    for item, result in violated[:5]:
        item = item or {}
        label = _cell(item.get("case_id") or item.get("session_id") or "case")
        lines.append(f"- case **{label}** / {_cell(item.get('criterion_id'))}: "
                     f"{_cell(result.get('reason') or 'violated')}")
    if len(violated) > 5:
        lines.append(f"- …and {len(violated) - 5} more violated case(s)")
    return lines


def _gate_table(report):
    checks = report["gate_report"].get("checks", [])
    if not checks:
        return []
    rows = ["| Gate | Result | Detail |", "| --- | :---: | --- |"]
    rows += [f"| {_cell(c['id'])} | {_icon(c['decision'])} | {_gate_detail(c)} |" for c in checks]
    return ["#### Gates", *rows, ""]


def _metrics_table(report):
    comparison = report.get("comparison")
    if comparison and comparison.get("metrics"):
        rows = ["| Metric | Baseline | Candidate | Δ | Note |",
                "| --- | ---: | ---: | ---: | :---: |"]
        for name, metric in comparison["metrics"].items():
            note = "⚠️ unavailable" if metric.get("unavailable") else ""
            rows.append(f"| `{_cell(name)}` | {_num(metric.get('baseline'))} | "
                        f"{_num(metric.get('candidate'))} | {_signed(metric.get('delta'))} | {note} |")
        return ["#### Metrics (vs baseline)", *rows, ""]
    metrics = report.get("metrics") or {}
    if not metrics:
        return []
    rows = ["| Metric | Value | Denominator |", "| --- | ---: | ---: |"]
    rows += [f"| `{_cell(name)}` | {_num(m.get('value'))} | {_num(m.get('denominator'))} |"
             for name, m in metrics.items()]
    return ["#### Metrics", *rows, ""]


def _details(summary, body):
    return [f"<details><summary>{_cell(summary)}</summary>", "", body, "", "</details>", ""]


def _breakdown(report):
    lines = []
    criteria = report.get("criteria") or {}
    if criteria:
        rows = ["| Criterion | met | violated | n/a | decision |",
                "| --- | ---: | ---: | ---: | :---: |"]
        for cid, summary in criteria.items():
            counts = summary.get("counts", {})
            rows.append(f"| `{_cell(cid)}` | {counts.get('met', 0)} | {counts.get('violated', 0)} | "
                        f"{counts.get('not_applicable', 0)} | {_icon(summary.get('decision'))} |")
        lines += _details("Per-criterion breakdown", "\n".join(rows))
    counts = report.get("counts") or {}
    if counts:
        lines += _details("Outcome counts", ", ".join(f"{k}: {v}" for k, v in counts.items()))
    return lines


def render_github_comment(report, *, title="Alignmenter"):
    """Return a sticky PR-comment Markdown body for one saved evaluation ``report``."""
    decision = report["gate_report"]["decision"]
    spec = report["spec"]
    header = (f"`{_cell(spec['id'])} @ {_cell(spec['revision'])}` · "
              f"qualification `{_cell(spec['qualification'])}` · "
              f"{report['judged']}/{report['applicable']} applicable criteria evaluated")
    if report.get("unavailable"):
        header += f" · {report['unavailable']} unavailable"
    lines = [MARKER, f"### {_DECISION_BADGE.get(decision, _cell(decision))} — {_cell(title)}", header, ""]
    blocking = _blocking_lines(report)
    if blocking:
        lines += ["#### ❌ Blocking", *blocking, ""]
    lines += _gate_table(report)
    lines += _metrics_table(report)
    lines += _breakdown(report)
    return "\n".join(lines).rstrip() + "\n"
