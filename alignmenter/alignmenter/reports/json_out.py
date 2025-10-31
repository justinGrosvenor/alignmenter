"""JSON artifact reporter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alignmenter.utils.io import write_json


class JSONReporter:
    """Write JSON artifacts summarizing a run."""

    def write(
        self,
        run_dir: Path,
        summary: dict[str, Any],
        scores: dict[str, Any],
        sessions: list,
        **extras: Any,
    ) -> Path:
        """Persist JSON outputs to *run_dir*."""

        payload = {
            "run": summary,
            "scores": scores,
        }
        scorecards = extras.get("scorecards")
        if scorecards:
            payload["scorecards"] = scorecards
        path = Path(run_dir) / "report.json"
        write_json(path, payload)
        return path
