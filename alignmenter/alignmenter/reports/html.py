"""HTML report generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>Alignmenter Report - {run_id}</title>
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 32px; }}
      h1, h2 {{ color: #22d3ee; }}
      section {{ margin-bottom: 32px; }}
      table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
      th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #1e293b; }}
      th {{ background: #1e293b; }}
      .meta {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
      .meta div {{ background: #1e293b; padding: 12px; border-radius: 8px; }}
      .scorecards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }}
      .scorecard {{ background: #1e293b; border-radius: 12px; padding: 16px; box-shadow: 0 10px 25px rgba(14,74,104,0.25); }}
      .scorecard h3 {{ margin: 0 0 8px 0; font-size: 1rem; color: #f8fafc; }}
      .scorecard .value {{ font-size: 2rem; font-weight: 600; color: #38bdf8; }}
      .scorecard .compare {{ font-size: 0.9rem; color: #cbd5f5; margin-top: 4px; }}
      .scorecard .delta {{ font-size: 0.9rem; margin-top: 8px; }}
      .scorecard .delta.positive {{ color: #4ade80; }}
      .scorecard .delta.negative {{ color: #f87171; }}
      .turn-table td {{ vertical-align: top; }}
      .muted {{ color: #94a3b8; font-size: 0.85rem; }}
      code {{ background: rgba(15,23,42,0.6); padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; }}
    </style>
  </head>
  <body>
    <h1>Alignmenter Report</h1>
    <section>
      <h2>Run Summary</h2>
      <div class=\"meta\">
        {meta_rows}
      </div>
    </section>
    {scorecard_block}
    <section>
      <h2>Scores</h2>
      {score_tables}
    </section>
    <section>
      <h2>Turn-Level Explorer</h2>
      {turn_preview}
    </section>
    <section>
      <h2>Dataset</h2>
      <p>{session_count} sessions · {turn_count} turns</p>
    </section>
  </body>
</html>
"""


class HTMLReporter:
    """Generate a minimal HTML report."""

    def write(
        self,
        run_dir: Path,
        summary: dict[str, Any],
        scores: dict[str, Any],
        sessions: list,
        **extras: Any,
    ) -> Path:
        meta_rows = "".join(
            f"<div><strong>{key.replace('_', ' ').title()}</strong><br />{value}</div>"
            for key, value in summary.items()
            if value is not None
        )

        scorecards = extras.get("scorecards", [])
        scorecard_block = _render_scorecards(scorecards)

        primary = scores.get("primary", {}) if isinstance(scores, dict) else {}
        compare = scores.get("compare", {}) if isinstance(scores, dict) else {}
        diff = scores.get("diff", {}) if isinstance(scores, dict) else {}

        score_blocks = []
        scorer_ids = sorted({*primary.keys(), *compare.keys()}) or list(scores.keys())

        for scorer_id in scorer_ids:
            primary_metrics = primary.get(scorer_id, {}) if isinstance(primary, dict) else {}
            compare_metrics = compare.get(scorer_id, {}) if isinstance(compare, dict) else {}
            diff_metrics = diff.get(scorer_id, {}) if isinstance(diff, dict) else {}

            metric_keys = sorted({*primary_metrics.keys(), *compare_metrics.keys(), *diff_metrics.keys()}) or ["value"]

            if not isinstance(primary_metrics, dict) and scorer_id in primary:
                primary_metrics = {"value": primary[scorer_id]}
            if not isinstance(compare_metrics, dict) and scorer_id in compare:
                compare_metrics = {"value": compare[scorer_id]}
            if not isinstance(diff_metrics, dict) and scorer_id in diff:
                diff_metrics = {"value": diff[scorer_id]}

            has_compare = bool(compare_metrics)
            header = "<th>Metric</th><th>Primary</th>"
            if has_compare:
                header += "<th>Compare</th><th>Δ</th>"

            row_html = []
            for key in metric_keys:
                primary_val = _format_metric(primary_metrics.get(key))
                compare_val = _format_metric(compare_metrics.get(key)) if has_compare else ""
                delta_val = _format_metric(diff_metrics.get(key)) if has_compare else ""
                if has_compare:
                    row_html.append(
                        f"<tr><td>{key}</td><td>{primary_val}</td><td>{compare_val}</td><td>{delta_val}</td></tr>"
                    )
                else:
                    row_html.append(f"<tr><td>{key}</td><td>{primary_val}</td></tr>")

            table = (
                f"<h3>{scorer_id.title()}</h3>"
                f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(row_html)}</tbody></table>"
            )
            if scorer_id == "safety":
                safety_details = _render_judge_details(primary_metrics)
                if safety_details:
                    table += safety_details
            score_blocks.append(table)

        turn_preview = _render_turn_preview(sessions)

        html = HTML_TEMPLATE.format(
            run_id=summary.get("run_id", "alignmenter_run"),
            meta_rows=meta_rows,
            scorecard_block=scorecard_block,
            score_tables="".join(score_blocks) or "<p>No scores computed.</p>",
            session_count=summary.get("session_count", 0),
            turn_count=summary.get("turn_count", 0),
            turn_preview=turn_preview,
        )

        path = Path(run_dir) / "index.html"
        path.write_text(html, encoding="utf-8")
        return path


def _format_metric(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _render_judge_details(metrics: dict[str, Any]) -> str:
    if not isinstance(metrics, dict):
        return ""
    calls = metrics.get("judge_calls")
    budget = metrics.get("judge_budget")
    mean_score = metrics.get("judge_mean")
    notes = metrics.get("judge_notes") or []

    if calls is None and not notes and mean_score is None:
        return ""

    lines = []
    if calls is not None:
        info = f"Judge calls: {calls}"
        if budget:
            info += f" / budget {budget}"
        lines.append(info)
    if mean_score is not None:
        lines.append(f"Average judge score: {mean_score:.3f}")
    if notes:
        notes_html = "".join(f"<li>{note}</li>" for note in notes)
        lines.append(f"<ul>{notes_html}</ul>")

    body = "<br />".join(item for item in lines if not item.startswith("<ul>"))
    list_html = "".join(item for item in lines if item.startswith("<ul>"))
    return f"<div class='muted'>{body}{list_html}</div>"


def _render_scorecards(scorecards: list[dict]) -> str:
    if not scorecards:
        return ""
    cards_html = []
    for card in scorecards:
        primary_val = _format_scorecard_value(card.get("primary"))
        compare_val = card.get("compare")
        diff_val = card.get("diff")
        compare_html = ""
        if compare_val is not None:
            compare_html = f"<div class=\"compare\">Compare: {_format_scorecard_value(compare_val)}</div>"
        delta_class = "delta"
        delta_html = ""
        if isinstance(diff_val, (int, float)):
            delta_class += " positive" if diff_val >= 0 else " negative"
            delta_html = f"<div class=\"{delta_class}\">Δ {_format_scorecard_value(diff_val)}</div>"
        cards_html.append(
            """
            <div class="scorecard">
              <h3>{label}</h3>
              <div class="value">{primary}</div>
              {compare}
              {delta}
            </div>
            """.format(
                label=card.get("label", card.get("id", "Metric").title()),
                primary=primary_val,
                compare=compare_html,
                delta=delta_html,
            )
        )
    return f"<section><h2>Headline Scores</h2><div class=\"scorecards\">{''.join(cards_html)}</div></section>"


def _format_scorecard_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, int):
        return str(value)
    return str(value)


def _render_turn_preview(sessions: list) -> str:
    rows = []
    for session in sessions[:3]:
        turns = getattr(session, "turns", None)
        if turns is None and hasattr(session, "get"):
            turns = session.get("turns", [])
        if turns is None:
            turns = []
        for turn in turns[:4]:
            text = turn.get("text", "")
            if len(text) > 160:
                text = text[:157] + "…"
            if hasattr(session, "session_id"):
                session_id = getattr(session, "session_id")
            elif hasattr(session, "get"):
                session_id = session.get("session_id", "")
            else:
                session_id = ""
            rows.append(
                """
                <tr>
                  <td><code>{session_id}</code></td>
                  <td>{role}</td>
                  <td>{text}</td>
                </tr>
                """.format(
                    session_id=session_id,
                    role=turn.get("role", ""),
                    text=text or "<span class='muted'>(empty)</span>",
                )
            )
    if not rows:
        return "<p class='muted'>No turn data available.</p>"
    return (
        "<table class='turn-table'><thead><tr><th>Session</th><th>Role</th><th>Text</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )
