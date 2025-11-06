"""HTML report generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


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
      .threshold-note {{ font-size: 0.75rem; margin-top: 6px; color: #94a3b8; display: block; }}
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
      .charts-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 16px; margin-top: 16px; }}
      .chart-box {{ background: #1e293b; padding: 20px; border-radius: 8px; }}
      .chart-box h3 {{ margin-top: 0; color: #22d3ee; font-size: 1.1rem; margin-bottom: 16px; }}
      .chart-box canvas {{ max-height: 300px; }}
      .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-top: 16px; }}
      .stat-card {{ background: #1e293b; padding: 20px; border-radius: 8px; text-align: center; }}
      .stat-label {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8; margin-bottom: 8px; font-weight: 600; }}
      .stat-value {{ font-size: 2rem; font-weight: 800; color: #e2e8f0; }}
      .stat-value.pass {{ color: #4ade80; }}
      .stat-value.warn {{ color: #fbbf24; }}
      .stat-value.fail {{ color: #f87171; }}
      .collapsible {{ cursor: pointer; padding: 16px; background: #1e293b; border: 1px solid #334155; border-radius: 8px; margin-top: 16px; user-select: none; }}
      .collapsible:hover {{ background: #334155; }}
      .collapsible h2 {{ margin: 0; display: inline; }}
      .collapsible-indicator {{ float: right; font-weight: bold; }}
      .collapsible-content {{ display: none; margin-top: 16px; }}
      .collapsible-content.open {{ display: block; }}
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

      function toggleCollapsible(id) {{
        const content = document.getElementById(id);
        const indicator = document.getElementById(id + '-indicator');
        if (content.classList.contains('open')) {{
          content.classList.remove('open');
          indicator.textContent = '+';
        }} else {{
          content.classList.add('open');
          indicator.textContent = '−';
        }}
      }}
    </script>
  </head>
  <body>
    {scorecard_block}

    <section>
      <h2>Performance Overview</h2>
      {stats_grid}
    </section>

    {charts_section}

    <div class="collapsible" onclick="toggleCollapsible('detailed-scores')">
      <h2>Detailed Scores</h2>
      <span id="detailed-scores-indicator" class="collapsible-indicator">+</span>
    </div>
    <div id="detailed-scores" class="collapsible-content">
      <div class="export-buttons">
        <button class="export-btn" onclick="downloadJSON(window.scoresData, 'scores.json')">Download JSON</button>
        <button class="export-btn" onclick="downloadCSV(window.scoresDataCSV, 'scores.csv')">Download CSV</button>
      </div>
      {score_tables}
    </div>

    {scenario_breakdown}
    {persona_breakdown}

    <div class="collapsible" onclick="toggleCollapsible('calibration')">
      <h2>Calibration & Diagnostics</h2>
      <span id="calibration-indicator" class="collapsible-indicator">+</span>
    </div>
    <div id="calibration" class="collapsible-content">
      {calibration_section}
    </div>

    {judge_analysis_section}

    <div class="collapsible" onclick="toggleCollapsible('reproducibility')">
      <h2>Reproducibility</h2>
      <span id="reproducibility-indicator" class="collapsible-indicator">+</span>
    </div>
    <div id="reproducibility" class="collapsible-content">
      {reproducibility_section}
    </div>

    <div class="collapsible" onclick="toggleCollapsible('turn-explorer')">
      <h2>Turn Explorer</h2>
      <span id="turn-explorer-indicator" class="collapsible-indicator">+</span>
    </div>
    <div id="turn-explorer" class="collapsible-content">
      {turn_preview}
    </div>

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

        analytics = extras.get("analytics") if isinstance(extras, dict) else None

        scenario_section, persona_section = _render_breakdown_sections(analytics)
        turn_preview = _render_turn_preview(sessions, analytics)
        calibration_section = _render_calibration_section(primary)
        judge_analysis_section = _render_judge_analysis_section(extras)
        reproducibility_section = _render_reproducibility_section(summary)
        charts_section = _render_charts(primary)
        scorecard_block = _render_scorecards(scorecards, summary)
        stats_grid = _render_stats_grid(primary, summary)

        # Prepare data for export
        import json
        scores_json = json.dumps(scores)
        scores_csv_data = _prepare_csv_data(primary)
        scores_csv_json = json.dumps(scores_csv_data)

        html = HTML_TEMPLATE.format(
            run_id=summary.get("run_id", "alignmenter_run"),
            scorecard_block=scorecard_block,
            stats_grid=stats_grid,
            score_tables="".join(score_blocks) or "<p>No scores computed.</p>",
            turn_preview=turn_preview,
            scenario_breakdown=scenario_section,
            persona_breakdown=persona_section,
            calibration_section=calibration_section,
            judge_analysis_section=judge_analysis_section,
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
        status = card.get("status")
        grade_class = _get_grade_class(primary_val, status)
        letter = _get_grade_letter(primary_val)

        row = '<tr>'
        row += f'<td><span class="metric-name">{card.get("label", card.get("id", "Metric").title())}</span></td>'
        warn_threshold = card.get("warn")
        fail_threshold = card.get("fail")
        threshold_note = ""
        if warn_threshold is not None or fail_threshold is not None:
            details = []
            if warn_threshold is not None:
                details.append(f"Warn &lt; {warn_threshold}")
            if fail_threshold is not None:
                details.append(f"Fail &lt; {fail_threshold}")
            if details:
                threshold_note = f"<div class='muted threshold-note'>{' | '.join(details)}</div>"

        row += f'<td class="grade-cell"><div class="grade-badge {grade_class}">'
        row += f'<span class="grade-letter">{letter}</span>'
        row += f'<span class="grade-score">{_format_scorecard_value(primary_val)}</span>'
        row += f'</div>{threshold_note}</td>'

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


def _get_grade_class(score: Any, status: Optional[str] = None) -> str:
    """Get CSS class for grade styling."""
    if status in {"pass", "warn", "fail"}:
        return status
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


def _render_breakdown_sections(analytics: Any) -> tuple[str, str]:
    scenarios_html = _render_breakdown_table("Scenario Breakdown", analytics.get("scenarios") if isinstance(analytics, dict) else {})
    personas_html = _render_breakdown_table("Persona Breakdown", analytics.get("personas") if isinstance(analytics, dict) else {})
    return scenarios_html, personas_html


def _render_breakdown_table(title: str, items: Any) -> str:
    if not isinstance(items, dict) or not items:
        return ""

    rows = []
    for name, payload in items.items():
        if not isinstance(payload, dict):
            continue
        scores = payload.get("scores", {}) if isinstance(payload.get("scores"), dict) else {}
        auth = _breakdown_score(scores, "authenticity", "mean")
        safety = _breakdown_score(scores, "safety", "score")
        stability = _breakdown_score(scores, "stability", "stability")
        risk_candidates = [v for v in (auth, safety, stability) if v is not None]
        risk = min(risk_candidates) if risk_candidates else None
        css_class = _get_score_class(risk) if risk is not None else ""
        rows.append(
            {
                "name": name,
                "sessions": payload.get("sessions", 0),
                "turns": payload.get("turns", 0),
                "auth": auth,
                "safety": safety,
                "stability": stability,
                "risk": risk if risk is not None else 1.0,
                "class": css_class,
            }
        )

    rows.sort(key=lambda item: item["risk"])

    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{row['name']}</td>"
            f"<td>{row['sessions']}</td>"
            f"<td>{row['turns']}</td>"
            f"<td class='{row['class'] or ''}'>{_format_score_value(row['auth'])}</td>"
            f"<td class='{row['class'] or ''}'>{_format_score_value(row['safety'])}</td>"
            f"<td class='{row['class'] or ''}'>{_format_score_value(row['stability'])}</td>"
            "</tr>"
        )

    return (
        f"<section><h2>{title}</h2>"
        "<table>"
        "<thead><tr><th>Name</th><th>Sessions</th><th>Turns</th><th>Authenticity</th><th>Safety</th><th>Consistency</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></section>"
    )


def _breakdown_score(scores: dict[str, Any], scorer_id: str, metric: str) -> Optional[float]:
    metrics = scores.get(scorer_id)
    if isinstance(metrics, dict):
        value = metrics.get(metric)
        if isinstance(value, (int, float)):
            return round(float(value), 3)
    return None


def _render_turn_preview(sessions: list, analytics: Any) -> str:
    turns: list[dict[str, Any]] = []
    scenario_scores: dict[str, Optional[float]] = {}
    if isinstance(analytics, dict):
        for scenario, payload in (analytics.get("scenarios") or {}).items():
            if not isinstance(payload, dict):
                continue
            scores = payload.get("scores", {}) if isinstance(payload.get("scores"), dict) else {}
            auth = _breakdown_score(scores, "authenticity", "mean")
            safety = _breakdown_score(scores, "safety", "score")
            stability = _breakdown_score(scores, "stability", "stability")
            candidates = [v for v in (auth, safety, stability) if v is not None]
            scenario_scores[scenario] = min(candidates) if candidates else None

    for session in sessions:
        persona = next(iter(session.persona_ids), None) if hasattr(session, "persona_ids") else None
        for turn in getattr(session, "turns", []) or []:
            if turn.get("role") != "assistant":
                continue
            text = turn.get("text", "") or ""
            tags = [tag for tag in turn.get("tags", []) if isinstance(tag, str)]
            scenarios = [tag for tag in tags if tag.startswith("scenario:")]
            risk_values = [scenario_scores.get(s) for s in scenarios if scenario_scores.get(s) is not None]
            risk = min(risk_values) if risk_values else None
            turns.append(
                {
                    "session": getattr(session, "session_id", ""),
                    "persona": turn.get("persona_id") or persona or "—",
                    "scenarios": ", ".join(scenarios) if scenarios else "—",
                    "text": text,
                    "risk": risk if risk is not None else 1.0,
                }
            )

    if not turns:
        return "<p class='muted'>No assistant turns available.</p>"

    turns.sort(key=lambda item: item["risk"])
    top_turns = turns[:20]

    rows = []
    for row in top_turns:
        text = row["text"]
        if len(text) > 280:
            text = text[:277] + "…"
        css_class = _get_score_class(row["risk"])
        display_text = text if text else "<span class='muted'>(empty)</span>"
        rows.append(
            "<tr>"
            f"<td><code>{row['session']}</code></td>"
            f"<td>{row['scenarios']}</td>"
            f"<td>{row['persona']}</td>"
            f"<td class='{css_class}'>{display_text}</td>"
            "</tr>"
        )

    return (
        "<table class='turn-table'><thead><tr><th>Session</th><th>Scenario</th><th>Persona</th><th>Snippet</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _format_score_value(value: Optional[float]) -> str:
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        return f"{float(value):.3f}"
    return str(value)


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
    """Render score visualizations using Chart.js in a grid layout."""
    import json

    charts = []

    # Authenticity components chart
    auth_data = scores.get("authenticity", {})
    if isinstance(auth_data, dict):
        auth_components = {
            "Style": auth_data.get("style_sim"),
            "Traits": auth_data.get("traits"),
            "Lexicon": auth_data.get("lexicon"),
        }
        auth_labels = []
        auth_values = []
        for label, value in auth_components.items():
            if value is not None:
                auth_labels.append(label)
                auth_values.append(value)

        if auth_labels:
            auth_json = json.dumps({"labels": auth_labels, "values": auth_values})
            charts.append(f"""
            <div class="chart-box">
                <h3>Authenticity Components</h3>
                <canvas id="authChart"></canvas>
                <script>
                    const authData = {auth_json};
                    new Chart(document.getElementById('authChart'), {{
                        type: 'bar',
                        data: {{
                            labels: authData.labels,
                            datasets: [{{
                                data: authData.values,
                                backgroundColor: 'rgba(34, 211, 238, 0.6)',
                                borderColor: 'rgba(34, 211, 238, 1)',
                                borderWidth: 2
                            }}]
                        }},
                        options: {{
                            responsive: true,
                            maintainAspectRatio: false,
                            scales: {{
                                y: {{ beginAtZero: true, max: 1.0, ticks: {{ color: '#e2e8f0' }}, grid: {{ color: 'rgba(226,232,240,0.1)' }} }},
                                x: {{ ticks: {{ color: '#e2e8f0' }}, grid: {{ color: 'rgba(226,232,240,0.1)' }} }}
                            }},
                            plugins: {{ legend: {{ display: false }} }}
                        }}
                    }});
                </script>
            </div>
            """)

    # Overall scores chart
    overall_labels = []
    overall_values = []
    for scorer_id, label in [("authenticity", "Authenticity"), ("safety", "Safety"), ("stability", "Stability")]:
        scorer_data = scores.get(scorer_id, {})
        if isinstance(scorer_data, dict):
            if scorer_id == "authenticity":
                value = scorer_data.get("mean")
            elif scorer_id == "safety":
                value = scorer_data.get("score")
            else:
                value = scorer_data.get("stability")
            if value is not None:
                overall_labels.append(label)
                overall_values.append(value)

    if overall_labels:
        overall_json = json.dumps({"labels": overall_labels, "values": overall_values})
        charts.append(f"""
        <div class="chart-box">
            <h3>Overall Scores</h3>
            <canvas id="overallChart"></canvas>
            <script>
                const overallData = {overall_json};
                new Chart(document.getElementById('overallChart'), {{
                    type: 'bar',
                    data: {{
                        labels: overallData.labels,
                        datasets: [{{
                            data: overallData.values,
                            backgroundColor: ['rgba(34,211,238,0.6)', 'rgba(74,222,128,0.6)', 'rgba(251,191,36,0.6)'],
                            borderColor: ['rgba(34,211,238,1)', 'rgba(74,222,128,1)', 'rgba(251,191,36,1)'],
                            borderWidth: 2
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {{
                            y: {{ beginAtZero: true, max: 1.0, ticks: {{ color: '#e2e8f0' }}, grid: {{ color: 'rgba(226,232,240,0.1)' }} }},
                            x: {{ ticks: {{ color: '#e2e8f0' }}, grid: {{ color: 'rgba(226,232,240,0.1)' }} }}
                        }},
                        plugins: {{ legend: {{ display: false }} }}
                    }}
                }});
            </script>
        </div>
        """)

    if not charts:
        return ""

    return f"""
    <section>
        <h2>Visualizations</h2>
        <div class="charts-grid">
            {"".join(charts)}
        </div>
    </section>
    """


def _render_stats_grid(scores: dict[str, Any], summary: dict[str, Any]) -> str:
    """Render key metrics in a grid of stat cards."""
    cards = []

    # Authenticity card
    auth_data = scores.get("authenticity", {})
    if isinstance(auth_data, dict):
        auth_score = auth_data.get("mean")
        if auth_score is not None:
            css_class = _get_score_class(auth_score)
            cards.append(f"""
            <div class="stat-card">
                <div class="stat-label">Authenticity</div>
                <div class="stat-value {css_class}">{auth_score:.1%}</div>
            </div>
            """)

    # Safety card
    safety_data = scores.get("safety", {})
    if isinstance(safety_data, dict):
        safety_score = safety_data.get("score")
        if safety_score is not None:
            css_class = _get_score_class(safety_score)
            cards.append(f"""
            <div class="stat-card">
                <div class="stat-label">Safety</div>
                <div class="stat-value {css_class}">{safety_score:.1%}</div>
            </div>
            """)

    # Stability card
    stability_data = scores.get("stability", {})
    if isinstance(stability_data, dict):
        stability_score = stability_data.get("stability")
        if stability_score is not None:
            css_class = _get_score_class(stability_score)
            cards.append(f"""
            <div class="stat-card">
                <div class="stat-label">Stability</div>
                <div class="stat-value {css_class}">{stability_score:.1%}</div>
            </div>
            """)

    # Sessions card
    session_count = summary.get("session_count")
    if session_count is not None:
        cards.append(f"""
        <div class="stat-card">
            <div class="stat-label">Sessions</div>
            <div class="stat-value">{session_count}</div>
        </div>
        """)

    # Turns card
    turn_count = summary.get("turn_count")
    if turn_count is not None:
        cards.append(f"""
        <div class="stat-card">
            <div class="stat-label">Turns</div>
            <div class="stat-value">{turn_count}</div>
        </div>
        """)

    # Violations card (if any)
    if isinstance(safety_data, dict):
        violations = safety_data.get("violations", 0)
        cards.append(f"""
        <div class="stat-card">
            <div class="stat-label">Safety Violations</div>
            <div class="stat-value {'fail' if violations > 0 else 'pass'}">{violations}</div>
        </div>
        """)

    if not cards:
        return ""

    return f'<div class="stats-grid">{"".join(cards)}</div>'


def _prepare_csv_data(scores: dict[str, Any]) -> list[dict]:
    """Prepare scores data for CSV export."""
    rows = []
    for scorer_id, metrics in scores.items():
        if isinstance(metrics, dict):
            row = {"scorer": scorer_id}
            row.update(metrics)
            rows.append(row)
    return rows


def _render_judge_analysis_section(extras: dict[str, Any]) -> str:
    """Render LLM judge analysis section if available."""
    judge_data = extras.get("judge_analysis") if isinstance(extras, dict) else None

    if not judge_data:
        return ""

    # Build collapsible section
    sessions_judged = judge_data.get("sessions_judged", 0)
    if sessions_judged == 0:
        return ""

    agreement_rate = judge_data.get("agreement_rate", 0.0)
    total_cost = judge_data.get("total_cost", 0.0)
    strategy = judge_data.get("strategy", "unknown")
    provider = judge_data.get("judge_provider", "unknown")

    # Color code agreement rate
    if agreement_rate >= 0.85:
        agreement_class = "pass"
    elif agreement_rate >= 0.70:
        agreement_class = "warn"
    else:
        agreement_class = "fail"

    # Build summary stats
    summary_html = f"""
    <div class="stats-grid" style="margin-bottom: 20px;">
        <div class="stat-card">
            <div class="stat-label">Sessions Judged</div>
            <div class="stat-value">{sessions_judged}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Agreement Rate</div>
            <div class="stat-value {agreement_class}">{agreement_rate:.1%}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Total Cost</div>
            <div class="stat-value">${total_cost:.3f}</div>
        </div>
    </div>
    """

    # Build config info
    config_html = f"""
    <div class="calibration-section">
        <h3>Judge Configuration</h3>
        <div class="calibration-grid">
            <div class="calibration-item">
                <strong>Provider</strong>
                <code>{provider}</code>
            </div>
            <div class="calibration-item">
                <strong>Strategy</strong>
                <code>{strategy}</code>
            </div>
            <div class="calibration-item">
                <strong>Sample Rate</strong>
                <code>{judge_data.get('sample_rate', 'N/A')}</code>
            </div>
        </div>
    </div>
    """

    # Build disagreements section if available
    disagreements_html = ""
    disagreements = judge_data.get("disagreements", [])
    if disagreements:
        rows = []
        for item in disagreements[:10]:  # Limit to top 10
            session_id = item.get("session_id", "unknown")
            calibrated_score = item.get("calibrated_score", 0.0)
            judge_score = item.get("judge_score", 0.0)
            reasoning = item.get("judge_reasoning", "No reasoning provided")

            rows.append(f"""
            <tr>
                <td><code>{session_id}</code></td>
                <td>{calibrated_score:.2f}</td>
                <td>{judge_score:.1f}/10</td>
                <td style="font-size: 0.9rem; color: #94a3b8;">{reasoning[:200]}...</td>
            </tr>
            """)

        disagreements_html = f"""
        <div style="margin-top: 20px;">
            <h3>Judge Disagreements</h3>
            <p style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 12px;">
                Cases where LLM judge disagreed with calibrated scores (showing up to 10)
            </p>
            <table>
                <thead>
                    <tr>
                        <th>Session</th>
                        <th>Calibrated</th>
                        <th>Judge</th>
                        <th>Reasoning</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(rows)}
                </tbody>
            </table>
        </div>
        """

    # Combine all parts
    content = summary_html + config_html + disagreements_html

    # Wrap in collapsible section
    return f"""
    <div class="collapsible" onclick="toggleCollapsible('judge-analysis')">
      <h2>LLM Judge Analysis</h2>
      <span id="judge-analysis-indicator" class="collapsible-indicator">+</span>
    </div>
    <div id="judge-analysis" class="collapsible-content">
      {content}
    </div>
    """
