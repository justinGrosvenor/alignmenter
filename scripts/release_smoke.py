"""Exercise the installed distribution, including a deliberate non-green CI result."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from xml.etree import ElementTree as ET

import yaml
from alignmenter.sdk import (
    evaluation_summary,
    export_archive,
    export_review,
    import_archive,
    import_review,
    qualification_report,
)

from alignmenter import __version__


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--core-only", action="store_true")
    options = parser.parse_args()
    root = options.out.resolve()
    root.mkdir(parents=True, exist_ok=True)
    assert __version__ == version("alignmenter") == "0.3.0"
    if options.core_only:
        assert importlib.util.find_spec("torch") is None
        assert importlib.util.find_spec("sklearn") is None
    executable = Path(sys.executable).parent / ("alignmenter.exe" if os.name == "nt" else "alignmenter")

    def cli(arguments, expected=0, env=None):
        result = subprocess.run([str(executable), *arguments], capture_output=True, text=True,
                                env={**os.environ, **(env or {})}, timeout=60, check=False)
        assert result.returncode == expected, result.stdout + result.stderr
        return result.stdout

    cli(["init-suite", "--out", str(root / "example")])
    suite = root / "example/suite.yaml"
    baseline = json.loads(cli(["run-suite", str(suite), "--out", str(root / "runs")]))
    configured = yaml.safe_load(suite.read_text())
    configured["baseline"] = baseline["run_dir"]
    configured["baseline_evaluation_id"] = baseline["evaluation_id"]
    configured["policy"]["regressions"] = [{"id": "no_regression", "metric": "resource_task.success", "max_regression": 0}]
    suite.write_text(yaml.safe_dump(configured))
    candidate = json.loads(cli(["run-suite", str(suite), "--out", str(root / "runs")], expected=2,
                               env={"ALIGNMENTER_DEMO_VARIANT": "bad"}))
    report = json.loads((Path(candidate["artifacts"]) / "evaluation.json").read_text())
    assert report["gate_report"]["decision"] == "fail" and report["comparison"]["regressions"] == 2
    assert int(ET.parse(Path(candidate["artifacts"]) / "junit.xml").getroot().attrib["failures"]) > 0
    assert report["budget"]["reserved_calls"] == 0 and report["budget"]["target"]["reserved_calls"] == 2
    cli(["check", candidate["run_dir"], "--out", str(root / "candidate-check")], expected=2)
    saved_check = json.loads((root / "candidate-check/evaluation.json").read_text())
    assert saved_check["gate_report"] == report["gate_report"]
    assert saved_check["comparison"] == report["comparison"]
    archive = root / "baseline.zip"
    export_archive(baseline["run_dir"], archive)
    import_archive(archive, root / "imported")
    assert evaluation_summary(root / "imported", details=True) == evaluation_summary(baseline["run_dir"], details=True)
    cli(["check", str(root / "imported"), "--out", str(root / "imported-review")])
    labels = root / "synthetic-review.jsonl"
    export_review(candidate["run_dir"], labels)
    rows = [json.loads(line) for line in labels.read_text().splitlines()]
    for row in rows:
        row["annotation"].update(reviewer="Automated release rehearsal", provenance="synthetic", role="adjudication",
                                  outcome="violated", rationale="The engineered bad variant requires unavailable resources.")
    labels.write_text("".join(json.dumps(row) + "\n" for row in rows))
    import_review(candidate["run_dir"], labels)
    qualification = qualification_report(candidate["run_dir"])
    assert qualification["references"] == 0 and qualification["decision"] == "inconclusive"
    result = {"version": __version__, "python": sys.version, "baseline": baseline, "candidate": candidate,
              "archive_roundtrip": True, "remote_judge_calls": 0, "synthetic_labels_remain_unqualified": True}
    (root / "rehearsal.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
