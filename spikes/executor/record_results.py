"""Write reviewable measurements from a completed JUnit acceptance run."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import platform
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_install_measurement() -> dict:
    seen, pending = set(), ["inspect-ai"]
    while pending:
        name = canonicalize_name(pending.pop())
        if name in seen:
            continue
        seen.add(name)
        for raw in metadata.distribution(name).requires or []:
            dependency = Requirement(raw)
            if dependency.marker is None or dependency.marker.evaluate({"extra": ""}):
                pending.append(dependency.name)
    files = set()
    for name in seen:
        distribution = metadata.distribution(name)
        for entry in distribution.files or []:
            path = Path(distribution.locate_file(entry))
            if path.is_file():
                files.add(path.resolve())
    return {"distributions": len(seen), "recorded_file_bytes": sum(p.stat().st_size for p in files)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    xml = ET.parse(args.junit).getroot()
    results = []
    for case in xml.iter("testcase"):
        name = case.attrib["name"]
        status = "pass"
        if case.find("failure") is not None or case.find("error") is not None:
            status = "fail"
        elif case.find("skipped") is not None:
            status = "not_tested"
        contract = re.search(r"test_(E\d\d)_", name)
        results.append(
            {
                "test": name,
                "contract": contract[1] if contract else None,
                "status": status,
                "seconds": float(case.attrib.get("time", 0)),
            }
        )
    sources = sorted((root / "spikes").rglob("*.py"))
    suites = list(xml.iter("testsuite"))
    payload = {
        "schema_version": 1,
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Isolated local prototypes; not production or real-device acceptance",
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "inspect_ai": metadata.version("inspect-ai"),
        "inspect_install": inspect_install_measurement(),
        "pytest": metadata.version("pytest"),
        "repository_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "junit": {"path": str(args.junit), "sha256": sha(args.junit)},
        "environment_lock_sha256": sha(root / "spikes/executor/requirements.lock"),
        "source_sha256": {str(path.relative_to(root)): sha(path) for path in sources},
        "source_lines": {
            str(path.relative_to(root)): len(path.read_text().splitlines()) for path in sources
        },
        "tests": len(results),
        "passed": sum(r["status"] == "pass" for r in results),
        "failed": sum(r["status"] == "fail" for r in results),
        "not_tested": sum(r["status"] == "not_tested" for r in results),
        "suite_seconds": sum(float(s.attrib.get("time", 0)) for s in suites),
        "results": results,
    }
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: payload[key]
                for key in ("tests", "passed", "failed", "not_tested", "suite_seconds")
            }
        )
    )


if __name__ == "__main__":
    main()
