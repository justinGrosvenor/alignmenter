"""Portable, offline reports over one saved decision; never executes a scorer."""

from __future__ import annotations

import html
import json
import os
import re
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

from alignmenter.execution.evaluation import evaluation_summary
from alignmenter.execution.gates import gate_report


def _escape(value):
    return html.escape(str(value), quote=True)


def _pretty(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)


def _question(item):
    if item["data"] is not None:
        return item["data"]["question"]
    payload = item.get("payload")
    if payload is None and item["request"] is not None:
        payload = json.loads(item["request"]["prompt"])
    history = (payload or {}).get("conversation", [])
    return next((t["content"] for t in reversed(history) if t["role"] == "user"), "Question unavailable in this evaluation input.")


def _table(headers, rows):
    return "<table><thead><tr>" + "".join(f"<th>{_escape(h)}</th>" for h in headers) + "</tr></thead><tbody>" + "".join(
        "<tr>" + "".join(f"<td>{_escape(c)}</td>" for c in row) + "</tr>" for row in rows) + "</tbody></table>"


def _result_html(result):
    if result is None:
        return "<p>Pending: no result has been committed.</p>"
    value = result["verdict"] or result["assessment"] or {}
    verdict = value.get("verdict", value)
    reasoning = verdict.get("rationale") or verdict.get("reasoning") or result["reason"]
    output = f"<p>{_escape(reasoning)}</p>" if reasoning else ""
    if "claims" in verdict:
        output += _table(["Claim", "Support", "Evidence"], [(c["text"], c["status"], "\n".join(f'{e["source_id"]}: {e["quote"]}' for e in c["evidence"])) for c in verdict["claims"]])
        output += _table(["Correctness / 10", "Answers question", "Abstained", "Abstention appropriate", "Dangerous"],
                         [(verdict[k] for k in ("correctness", "answers_question", "abstained", "abstention_appropriate", "dangerous"))])
        if verdict.get("danger_reason"):
            output += f"<p>Danger: {_escape(verdict['danger_reason'])}</p>"
    if "quantities" in value:
        output += _table(["Quantity", "Traceability", "Evidence"], [(q["quote"], q["status"], q["evidence"]["quote"] if q["evidence"] else "Unavailable") for q in value["quantities"]])
        output += _table(["Citation", "Resolved source"], [(c["quote"], c["source_id"] or "Unresolved") for c in value["citations"]])
    if "evidence" in verdict:
        output += _table(["Source", "Exact quote"], [(e["source_id"], e["quote"]) for e in verdict["evidence"]])
    return output


def render_html(report):
    decision = report["gate_report"]["decision"]
    results = {r["input_key"]: r for r in report["results"]}
    body = f"<h1>Alignmenter evaluation: {_escape(decision)}</h1><p>Spec: {_escape(report['spec']['id'])} / {_escape(report['spec']['revision'])} · Qualification: {_escape(report['spec']['qualification'])}</p>"
    body += f"<p>Evaluated: {report['judged']} / {report['applicable']} applicable criteria. Unavailable: {report['unavailable']}.</p>"
    budget = report["budget"]
    body += f"<p>Judge reservations: {budget['reserved_calls']}. Target reservations: {budget['target']['reserved_calls']}. Target cost: unavailable.</p>"
    body += _table(["Gate", "Decision"], [(c["id"], c["decision"]) for c in report["gate_report"]["checks"]])
    body += "<h2>Saved metrics</h2>" + _table(["Metric", "Value", "Unit", "Denominator"],
                                            [(name, m["value"] if m["value"] is not None else "Unavailable", m["unit"], m["denominator"]) for name, m in report["metrics"].items()])
    if report.get("comparison") is not None:
        comparison = report["comparison"]
        body += f"<h2>Baseline comparison: {_escape(comparison['decision'])}</h2>"
        body += _table(["Metric", "Baseline", "Candidate", "Delta", "Paired", "Unavailable"],
                       [(name, m["baseline"], m["candidate"], m["delta"], m["paired"], m["unavailable"]) for name, m in comparison["metrics"].items()])
        for pair in comparison["details"]:
            body += f"<details><summary>{_escape(pair['case_id'])} · {_escape(pair['criterion_id'])}: baseline / candidate</summary>"
            body += _table(["Baseline answer", "Candidate answer"], [(pair["baseline_input"]["sources"].get("answer", "Unavailable"), pair["candidate_input"]["sources"].get("answer", "Unavailable"))]) + "</details>"
        if comparison["added"] or comparison["removed"] or comparison["mismatched"]:
            body += "<p>Unpaired or changed cases prevent a complete release comparison.</p>"
    body += "<h2>Case evidence</h2>"
    for item in report["inputs"]:
        result = results.get(item["key"])
        status = result["status"] if result else "pending"
        body += f"<article><h3>{_escape(item['case_id'] or item['session_id'])} · {_escape(item['criterion_id'])}: {_escape(status)}</h3>"
        body += f"<h4>Question</h4><pre>{_escape(_question(item))}</pre><h4>Answer</h4><pre>{_escape(item['sources'].get('answer', 'No captured answer available.'))}</pre>"
        body += _result_html(result)
        reviewed = next((r for r in report.get("review", {}).get("details", []) if r["input_key"] == item["key"]), None)
        if reviewed is not None:
            body += f"<p>Human review: {_escape(reviewed['review_state'])}; reference: {_escape(reviewed['reference'] or 'Unavailable')}. Original machine outcome: {_escape(status)}.</p>"
        for source_id, source in item["sources"].items():
            if source_id != "answer":
                body += f"<details><summary>Source: {_escape(source_id)}</summary><pre>{_escape(source)}</pre></details>"
        body += "</article>"
    return "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'><meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'\"><title>Alignmenter evaluation</title><style>body{max-width:1100px;margin:2rem auto;padding:0 1rem;font:16px/1.5 system-ui;color:#18202a;background:#f7f8fa}table{border-collapse:collapse;width:100%;margin:1rem 0}th,td{border:1px solid #bcc6d0;padding:.5rem;text-align:left;vertical-align:top;white-space:pre-wrap;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere}article{background:white;border:1px solid #cbd2da;padding:1rem;margin:1rem 0}summary{cursor:pointer}h1,h2,h3{line-height:1.2}</style><body>" + body + "</body></html>"


def _xml_text(value):
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "�", str(value))


def render_junit(report):
    suite = ET.Element("testsuite", name="alignmenter", tests=str(len(report["inputs"]) + 1))
    results = {r["input_key"]: r for r in report["results"]}
    for item in report["inputs"]:
        result = results.get(item["key"])
        status = result["status"] if result else "pending"
        case = ET.SubElement(suite, "testcase", name=_xml_text(f"{item['case_id'] or item['session_id']} / {item['criterion_id']}"), classname="alignmenter.criteria")
        if status == "not_applicable":
            ET.SubElement(case, "skipped", message="Explicitly not applicable")
        elif status != "met":
            failure = ET.SubElement(case, "failure" if status == "violated" else "error", message=status)
            failure.text = _xml_text((result or {}).get("reason") or status)
    decision = report["gate_report"]["decision"]
    policy = ET.SubElement(suite, "testcase", name="release policy", classname="alignmenter.gates")
    if decision != "pass":
        ET.SubElement(policy, "failure" if decision == "fail" else "error", message=decision).text = _xml_text(_pretty(report["gate_report"]))
    for name in ("failure", "error", "skipped"):
        suite.set({"failure": "failures", "error": "errors", "skipped": "skipped"}[name], str(len(suite.findall(f"testcase/{name}"))))
    return ET.tostring(suite, encoding="unicode", xml_declaration=True)


def render_markdown(report):
    def clean(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("<", "&lt;").replace(">", "&gt;")
    rows = [f"Alignmenter decision: **{report['gate_report']['decision']}**", "",
            f"Evaluated {report['judged']}/{report['applicable']} applicable criteria; {report['unavailable']} unavailable.", "",
            "| Gate | Decision |", "| --- | --- |"]
    rows.extend(f"| {clean(c['id'])} | {c['decision']} |" for c in report["gate_report"]["checks"])
    return "\n".join(rows) + "\n"


def write_artifacts(out_dir, artifacts, *, force=False):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not force and any((out_dir / name).exists() for name in artifacts):
        raise ValueError("Report artifacts already exist; use force to replace them")
    for name, value in artifacts.items():
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=out_dir, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.replace(temporary, out_dir / name)
        finally:
            temporary.unlink(missing_ok=True)


def export_evaluation(run_dir, out_dir, *, evaluation_id=None, policy=None, comparison=None, force=False):
    from alignmenter.execution.comparison import compare_saved
    from alignmenter.execution.review import qualification_report
    from alignmenter.schemas.gates import GatePolicy
    from alignmenter.storage.runs import RunStore

    report = evaluation_summary(run_dir, evaluation_id, details=True)
    if policy is None:
        suite = RunStore(run_dir).manifest().suite
        if suite is not None:
            config = suite["configuration"]
            policy = GatePolicy.model_validate(config["policy"])
            if comparison is None and config.get("baseline") is not None:
                comparison = compare_saved(config["baseline"], run_dir,
                                           baseline_id=config.get("baseline_evaluation_id"),
                                           candidate_id=report["evaluation_id"])
    report["gate_report"] = gate_report(report, policy, comparison=comparison)
    report["comparison"] = comparison
    report["review"] = qualification_report(run_dir, report["evaluation_id"])
    write_artifacts(out_dir, {"evaluation.json": _pretty(report) + "\n", "index.html": render_html(report),
                              "junit.xml": render_junit(report), "summary.md": render_markdown(report)}, force=force)
    return report
