"""HTML report generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>Alignmenter Report - {run_id}</title>
    <link rel=\"icon\" type=\"image/png\" href=\"favicon.png\">
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 32px; }}
      h1, h2 {{ color: #22d3ee; }}
      section {{ margin-bottom: 32px; }}
      table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
      th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #1e293b; }}
      th {{ background: #1e293b; }}
      .meta {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
      .meta div {{ background: #1e293b; padding: 12px; border-radius: 8px; }}
      .report-card {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 16px; padding: 0; box-shadow: 0 20px 60px rgba(14,74,104,0.4); border: 1px solid #334155; max-width: 1200px; margin: 0 auto; }}
      .report-card-header {{ background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 32px 40px; border-radius: 16px 16px 0 0; border-bottom: 2px solid #22d3ee; }}
      .report-card-header-content {{ display: flex; align-items: center; gap: 20px; margin-bottom: 20px; }}
      .report-logo {{ height: 48px; width: auto; }}
      .report-card-title {{ margin: 0; font-size: 2rem; font-weight: 800; letter-spacing: -0.02em; color: #22d3ee; }}
      .report-info-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-top: 20px; }}
      .report-info-item {{ background: rgba(34, 211, 238, 0.05); padding: 12px 16px; border-radius: 8px; border: 1px solid rgba(34, 211, 238, 0.1); }}
      .report-info-label {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8; margin-bottom: 4px; font-weight: 600; }}
      .report-info-value {{ font-size: 1rem; font-weight: 700; color: #e2e8f0; }}
      .report-card-body {{ padding: 40px; }}
      .overall-grade {{ text-align: center; margin-bottom: 32px; padding: 24px; background: rgba(34, 211, 238, 0.05); border-radius: 12px; border: 2px solid rgba(34, 211, 238, 0.2); }}
      .overall-grade-label {{ font-size: 0.9rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 8px; }}
      .overall-grade-value {{ font-size: 4rem; font-weight: 800; line-height: 1; }}
      .overall-grade-value.pass {{ color: #4ade80; }}
      .overall-grade-value.warn {{ color: #fbbf24; }}
      .overall-grade-value.fail {{ color: #f87171; }}
      .overall-grade-desc {{ font-size: 0.9rem; color: #94a3b8; margin-top: 8px; }}
      .grade-table {{ width: 100%; border-collapse: separate; border-spacing: 0 8px; }}
      .grade-table thead th {{ padding: 12px 16px; text-align: left; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8; font-weight: 600; border-bottom: 2px solid #334155; }}
      .grade-table thead th:nth-child(2), .grade-table thead th:nth-child(3), .grade-table thead th:nth-child(4) {{ text-align: center; }}
      .grade-table tbody tr {{ background: #1e293b; }}
      .grade-table tbody td {{ padding: 20px 16px; border-top: 1px solid #334155; border-bottom: 1px solid #334155; }}
      .grade-table tbody td:first-child {{ border-left: 1px solid #334155; border-radius: 8px 0 0 8px; }}
      .grade-table tbody td:last-child {{ border-right: 1px solid #334155; border-radius: 0 8px 8px 0; }}
      .metric-name {{ font-weight: 600; color: #e2e8f0; font-size: 1.1rem; }}
      .grade-cell {{ text-align: center; }}
      .grade-badge {{ display: inline-flex; align-items: center; gap: 8px; padding: 8px 16px; border-radius: 8px; font-weight: 700; font-size: 1.1rem; }}
      .grade-badge.pass {{ background: rgba(74, 222, 128, 0.15); color: #4ade80; border: 2px solid rgba(74, 222, 128, 0.3); }}
      .grade-badge.warn {{ background: rgba(251, 191, 36, 0.15); color: #fbbf24; border: 2px solid rgba(251, 191, 36, 0.3); }}
      .grade-badge.fail {{ background: rgba(248, 113, 113, 0.15); color: #f87171; border: 2px solid rgba(248, 113, 113, 0.3); }}
      .grade-letter {{ font-size: 1.3rem; font-weight: 800; }}
      .grade-score {{ font-size: 0.95rem; opacity: 0.9; }}
      .compare-cell {{ text-align: center; color: #94a3b8; font-size: 0.95rem; }}
      .delta-cell {{ text-align: center; font-size: 1rem; font-weight: 700; }}
      .delta-cell.positive {{ color: #4ade80; }}
      .delta-cell.negative {{ color: #f87171; }}
      .delta-cell.neutral {{ color: #64748b; }}
      .turn-table td {{ vertical-align: top; }}
      .muted {{ color: #94a3b8; font-size: 0.85rem; }}
      code {{ background: rgba(15,23,42,0.6); padding: 2px 6px; border-radius: 4px; font-size: 0.85rem; }}
      .score-pass {{ background: rgba(74, 222, 128, 0.1); color: #4ade80; font-weight: 600; }}
      .score-warn {{ background: rgba(251, 191, 36, 0.1); color: #fbbf24; font-weight: 600; }}
      .score-fail {{ background: rgba(248, 113, 113, 0.1); color: #f87171; font-weight: 600; }}
      .calibration-section {{ background: #1e293b; padding: 16px; border-radius: 8px; margin-top: 16px; }}
      .calibration-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 12px; margin-top: 12px; }}
      .calibration-item {{ background: #0f172a; padding: 12px; border-radius: 6px; }}
      .calibration-item strong {{ color: #22d3ee; display: block; margin-bottom: 4px; }}
      .reproducibility-section {{ background: #1e293b; padding: 16px; border-radius: 8px; }}
      .reproducibility-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 12px; margin-top: 12px; }}
      .reproducibility-grid > div {{ overflow-wrap: break-word; word-break: break-all; }}
      .export-buttons {{ margin-top: 8px; }}
      .export-btn {{ background: #1e293b; color: #22d3ee; border: 1px solid #22d3ee; padding: 6px 12px; border-radius: 6px; cursor: pointer; text-decoration: none; display: inline-block; margin-right: 8px; font-size: 0.85rem; }}
      .export-btn:hover {{ background: #22d3ee; color: #0f172a; }}
      .chart-container {{ margin-top: 16px; background: #1e293b; padding: 16px; border-radius: 8px; }}
      canvas {{ max-width: 100%; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script>
      function downloadJSON(data, filename) {{
        const blob = new Blob([JSON.stringify(data, null, 2)], {{ type: 'application/json' }});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
      }}

      function downloadCSV(data, filename) {{
        const rows = [];
        if (data.length > 0) {{
          rows.push(Object.keys(data[0]).join(','));
          data.forEach(row => {{
            rows.push(Object.values(row).join(','));
          }});
        }}
        const csv = rows.join('\\n');
        const blob = new Blob([csv], {{ type: 'text/csv' }});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
      }}
    </script>
  </head>
  <body>
    {scorecard_block}
    {calibration_section}
    <section>
      <h2>Scores</h2>
      <div class="export-buttons">
        <button class="export-btn" onclick="downloadJSON(window.scoresData, 'scores.json')">Download JSON</button>
        <button class="export-btn" onclick="downloadCSV(window.scoresDataCSV, 'scores.csv')">Download CSV</button>
      </div>
      {score_tables}
      {charts_section}
    </section>
    {reproducibility_section}
    <section>
      <h2>Turn-Level Explorer</h2>
      {turn_preview}
    </section>
    <script>
      window.scoresData = {scores_json};
      window.scoresDataCSV = {scores_csv_json};
    </script>
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
        scorecards = extras.get("scorecards", [])

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
                primary_val = _format_metric(primary_metrics.get(key), metric_key=key)
                compare_val = _format_metric(compare_metrics.get(key), metric_key=key) if has_compare else ""
                delta_val = _format_metric(diff_metrics.get(key), metric_key=key, apply_color=False) if has_compare else ""
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
        calibration_section = _render_calibration_section(primary)
        reproducibility_section = _render_reproducibility_section(summary)
        charts_section = _render_charts(primary)
        scorecard_block = _render_scorecards(scorecards, summary)

        # Prepare data for export
        import json
        scores_json = json.dumps(scores)
        scores_csv_data = _prepare_csv_data(primary)
        scores_csv_json = json.dumps(scores_csv_data)

        html = HTML_TEMPLATE.format(
            run_id=summary.get("run_id", "alignmenter_run"),
            scorecard_block=scorecard_block,
            score_tables="".join(score_blocks) or "<p>No scores computed.</p>",
            turn_preview=turn_preview,
            calibration_section=calibration_section,
            reproducibility_section=reproducibility_section,
            charts_section=charts_section,
            scores_json=scores_json,
            scores_csv_json=scores_csv_json,
        )

        path = Path(run_dir) / "index.html"
        path.write_text(html, encoding="utf-8")

        # Copy logo and favicon to report directory
        import shutil
        assets_dir = Path(__file__).parent.parent.parent.parent.parent / "assets"

        # Copy logo
        logo_source = assets_dir / "alignmenter-transparent.png"
        if logo_source.exists():
            logo_dest = Path(run_dir) / "logo.png"
            shutil.copy2(logo_source, logo_dest)

        # Copy favicon (use the transparent icon version)
        favicon_source = assets_dir / "alignmenter-transparent.png"
        if favicon_source.exists():
            favicon_dest = Path(run_dir) / "favicon.png"
            shutil.copy2(favicon_source, favicon_dest)

        return path


def _format_metric(value: Any, metric_key: str = "", apply_color: bool = True) -> str:
    if value is None:
        return "—"

    formatted = ""
    if isinstance(value, float):
        formatted = f"{value:.3f}"
    elif isinstance(value, list):
        formatted = ", ".join(str(item) for item in value)
    else:
        formatted = str(value)

    # Apply color coding for score metrics
    if apply_color and isinstance(value, (int, float)) and metric_key in ("mean", "score", "stability", "rule_score", "fused_judge"):
        css_class = _get_score_class(value)
        return f'<span class="{css_class}">{formatted}</span>'

    return formatted


def _get_score_class(score: float) -> str:
    """Get CSS class based on score threshold."""
    if score >= 0.8:
        return "score-pass"
    elif score >= 0.6:
        return "score-warn"
    else:
        return "score-fail"


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


def _render_scorecards(scorecards: list[dict], summary: dict[str, Any]) -> str:
    if not scorecards:
        return ""

    has_compare = any(card.get("compare") is not None for card in scorecards)

    # Calculate overall grade
    scores = [card.get("primary") for card in scorecards if isinstance(card.get("primary"), (int, float))]
    overall_score = sum(scores) / len(scores) if scores else 0
    overall_class = _get_grade_class(overall_score)
    overall_letter = _get_grade_letter(overall_score)

    # Build run info
    model = summary.get("model", "Unknown")
    run_at = summary.get("run_at", "Unknown")
    session_count = summary.get("session_count", 0)
    turn_count = summary.get("turn_count", 0)
    run_id = summary.get("run_id", "alignmenter_run")

    run_info = f"""
    <div class="report-info-grid">
        <div class="report-info-item">
            <div class="report-info-label">Model</div>
            <div class="report-info-value">{model}</div>
        </div>
        <div class="report-info-item">
            <div class="report-info-label">Run ID</div>
            <div class="report-info-value">{run_id}</div>
        </div>
        <div class="report-info-item">
            <div class="report-info-label">Timestamp</div>
            <div class="report-info-value">{run_at}</div>
        </div>
        <div class="report-info-item">
            <div class="report-info-label">Dataset</div>
            <div class="report-info-value">{session_count} sessions · {turn_count} turns</div>
        </div>
    </div>
    """

    # Build overall grade section
    grade_desc = {
        "A": "Excellent performance across all metrics",
        "B": "Good performance with room for improvement",
        "C": "Needs attention in one or more areas"
    }.get(overall_letter, "")

    overall_grade_html = f"""
    <div class="overall-grade">
        <div class="overall-grade-label">Overall Grade</div>
        <div class="overall-grade-value {overall_class}">{overall_letter}</div>
        <div class="overall-grade-desc">{grade_desc}</div>
    </div>
    """

    # Build table
    table_header = '<thead><tr>'
    table_header += '<th>Metric</th>'
    table_header += '<th>Grade</th>'
    if has_compare:
        table_header += '<th>Compare</th>'
        table_header += '<th>Change</th>'
    table_header += '</tr></thead>'

    # Build rows
    rows = []
    for card in scorecards:
        primary_val = card.get("primary")
        compare_val = card.get("compare")
        diff_val = card.get("diff")

        # Determine grade class
        grade_class = _get_grade_class(primary_val)
        letter = _get_grade_letter(primary_val)

        row = '<tr>'
        row += f'<td><span class="metric-name">{card.get("label", card.get("id", "Metric").title())}</span></td>'
        row += f'<td class="grade-cell"><div class="grade-badge {grade_class}">'
        row += f'<span class="grade-letter">{letter}</span>'
        row += f'<span class="grade-score">{_format_scorecard_value(primary_val)}</span>'
        row += '</div></td>'

        if has_compare:
            if compare_val is not None:
                compare_letter = _get_grade_letter(compare_val)
                row += f'<td class="compare-cell">{compare_letter} {_format_scorecard_value(compare_val)}</td>'
            else:
                row += '<td class="compare-cell">—</td>'

            if diff_val is not None and isinstance(diff_val, (int, float)):
                delta_class = "positive" if diff_val >= 0 else "negative"
                delta_sign = "+" if diff_val >= 0 else ""
                row += f'<td class="delta-cell {delta_class}">{delta_sign}{_format_scorecard_value(diff_val)}</td>'
            else:
                row += '<td class="delta-cell neutral">—</td>'

        row += '</tr>'
        rows.append(row)

    return f"""
    <section>
        <div class="report-card">
            <div class="report-card-header">
                <div class="report-card-header-content">
                    <img src="logo.png" alt="Alignmenter" class="report-logo" onerror="this.style.display='none'">
                    <h1 class="report-card-title">Alignmenter Report Card</h1>
                </div>
                {run_info}
            </div>
            <div class="report-card-body">
                {overall_grade_html}
                <table class="grade-table">
                    {table_header}
                    <tbody>
                        {''.join(rows)}
                    </tbody>
                </table>
            </div>
        </div>
    </section>
    """


def _get_grade_class(score: Any) -> str:
    """Get CSS class for grade styling."""
    if not isinstance(score, (int, float)):
        return ""
    if score >= 0.8:
        return "pass"
    elif score >= 0.6:
        return "warn"
    else:
        return "fail"


def _get_grade_letter(score: Any) -> str:
    """Get letter grade for score."""
    if not isinstance(score, (int, float)):
        return "—"
    if score >= 0.8:
        return "A"
    elif score >= 0.6:
        return "B"
    else:
        return "C"


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


def _render_calibration_section(scores: dict[str, Any]) -> str:
    """Render calibration statistics (bootstrap CI, judge agreement, etc.)."""
    items = []

    # Authenticity calibration
    authenticity = scores.get("authenticity", {})
    if isinstance(authenticity, dict):
        ci_low = authenticity.get("ci95_low")
        ci_high = authenticity.get("ci95_high")
        if ci_low is not None and ci_high is not None:
            items.append(f"""
                <div class="calibration-item">
                    <strong>Authenticity 95% CI</strong>
                    <span>[{ci_low:.3f}, {ci_high:.3f}]</span>
                </div>
            """)

    # Safety judge agreement
    safety = scores.get("safety", {})
    if isinstance(safety, dict):
        judge_var = safety.get("judge_variance")
        if judge_var is not None:
            agreement = 1.0 - min(1.0, judge_var / 0.25)  # Normalize variance to agreement
            items.append(f"""
                <div class="calibration-item">
                    <strong>Judge Agreement</strong>
                    <span>{agreement:.3f}</span>
                    <div class="muted">Variance: {judge_var:.4f}</div>
                </div>
            """)

        # Judge cost tracking
        judge_cost = safety.get("judge_cost_spent")
        judge_budget = safety.get("judge_cost_budget")
        if judge_cost is not None:
            budget_display = f" / ${judge_budget:.2f}" if judge_budget else ""
            items.append(f"""
                <div class="calibration-item">
                    <strong>Judge Cost</strong>
                    <span>${judge_cost:.4f}{budget_display}</span>
                </div>
            """)

    # Stability calibration
    stability = scores.get("stability", {})
    if isinstance(stability, dict):
        norm_var = stability.get("normalized_variance")
        if norm_var is not None:
            items.append(f"""
                <div class="calibration-item">
                    <strong>Stability Variance</strong>
                    <span>{norm_var:.4f}</span>
                    <div class="muted">Lower is more consistent</div>
                </div>
            """)

    if not items:
        return ""

    return f"""
    <section>
        <h2>Calibration & Diagnostics</h2>
        <div class="calibration-section">
            <div class="calibration-grid">
                {''.join(items)}
            </div>
        </div>
    </section>
    """


def _render_reproducibility_section(summary: dict[str, Any]) -> str:
    """Render reproducibility information (config, versions, seed)."""
    import sys
    import platform

    items = []

    # Run configuration
    model = summary.get("model")
    if model:
        items.append(f"<div><strong>Model</strong><br />{model}</div>")

    compare_model = summary.get("compare_model")
    if compare_model:
        items.append(f"<div><strong>Compare Model</strong><br />{compare_model}</div>")

    # Dataset
    dataset_path = summary.get("dataset_path")
    if dataset_path:
        items.append(f"<div><strong>Dataset</strong><br /><code>{dataset_path}</code></div>")

    persona_path = summary.get("persona_path")
    if persona_path:
        items.append(f"<div><strong>Persona</strong><br /><code>{persona_path}</code></div>")

    # Environment
    items.append(f"<div><strong>Python Version</strong><br />{sys.version.split()[0]}</div>")
    items.append(f"<div><strong>Platform</strong><br />{platform.system()} {platform.machine()}</div>")

    # Run timestamp
    run_at = summary.get("run_at")
    if run_at:
        items.append(f"<div><strong>Run At</strong><br />{run_at}</div>")

    return f"""
    <section>
        <h2>Reproducibility</h2>
        <div class="reproducibility-section">
            <div class="reproducibility-grid">
                {''.join(items)}
            </div>
        </div>
    </section>
    """


def _render_charts(scores: dict[str, Any]) -> str:
    """Render score visualizations using Chart.js."""
    # Collect main metrics
    metric_labels = []
    metric_values = []

    for scorer_id in ("authenticity", "safety", "stability"):
        scorer_data = scores.get(scorer_id, {})
        if isinstance(scorer_data, dict):
            if scorer_id == "authenticity":
                value = scorer_data.get("mean")
                if value is not None:
                    metric_labels.append("Authenticity")
                    metric_values.append(value)
            elif scorer_id == "safety":
                value = scorer_data.get("score")
                if value is not None:
                    metric_labels.append("Safety")
                    metric_values.append(value)
            elif scorer_id == "stability":
                value = scorer_data.get("stability")
                if value is not None:
                    metric_labels.append("Stability")
                    metric_values.append(value)

    if not metric_labels:
        return ""

    chart_data = {
        "labels": metric_labels,
        "values": metric_values,
    }

    import json
    chart_json = json.dumps(chart_data)

    return f"""
    <div class="chart-container">
        <h3>Score Overview</h3>
        <canvas id="scoreChart" width="400" height="200"></canvas>
        <script>
            const chartData = {chart_json};
            const ctx = document.getElementById('scoreChart').getContext('2d');
            new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: chartData.labels,
                    datasets: [{{
                        label: 'Score',
                        data: chartData.values,
                        backgroundColor: [
                            'rgba(34, 211, 238, 0.6)',
                            'rgba(74, 222, 128, 0.6)',
                            'rgba(251, 191, 36, 0.6)',
                        ],
                        borderColor: [
                            'rgba(34, 211, 238, 1)',
                            'rgba(74, 222, 128, 1)',
                            'rgba(251, 191, 36, 1)',
                        ],
                        borderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            max: 1.0,
                            ticks: {{
                                color: '#e2e8f0'
                            }},
                            grid: {{
                                color: 'rgba(226, 232, 240, 0.1)'
                            }}
                        }},
                        x: {{
                            ticks: {{
                                color: '#e2e8f0'
                            }},
                            grid: {{
                                color: 'rgba(226, 232, 240, 0.1)'
                            }}
                        }}
                    }},
                    plugins: {{
                        legend: {{
                            display: false
                        }}
                    }}
                }}
            }});
        </script>
    </div>
    """


def _prepare_csv_data(scores: dict[str, Any]) -> list[dict]:
    """Prepare scores data for CSV export."""
    rows = []
    for scorer_id, metrics in scores.items():
        if isinstance(metrics, dict):
            row = {"scorer": scorer_id}
            row.update(metrics)
            rows.append(row)
    return rows
