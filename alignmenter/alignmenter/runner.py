"""Run orchestration pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from alignmenter.reports.html import HTMLReporter
from alignmenter.reports.json_out import JSONReporter
from alignmenter.utils.io import read_jsonl, write_json


@dataclass
class RunConfig:
    """Configuration for a single evaluation run."""

    model: str
    dataset_path: Path
    persona_path: Path
    run_id: str = "alignmenter_run"
    compare_model: Optional[str] = None
    report_out_dir: Path = Path("reports")
    include_raw: bool = True

    def __post_init__(self) -> None:
        self.dataset_path = Path(self.dataset_path)
        self.persona_path = Path(self.persona_path)
        self.report_out_dir = Path(self.report_out_dir)


@dataclass
class Session:
    """Grouped conversation session."""

    session_id: str
    turns: List[dict]


class Runner:
    """Coordinates provider calls, scoring, and reporting."""

    def __init__(
        self,
        config: RunConfig,
        scorers: Iterable,
        reporters: Optional[Iterable] = None,
    ) -> None:
        self.config = config
        self.scorers = list(scorers)
        self.reporters = list(reporters or [JSONReporter(), HTMLReporter()])

    def execute(self) -> Path:
        """Execute an evaluation run and return the artifact directory."""

        records = load_dataset(self.config.dataset_path)
        sessions = group_sessions(records)

        score_results = {}
        for scorer in self.scorers:
            score_results[scorer.id] = scorer.score(sessions)

        run_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        run_dir = prepare_run_directory(self.config.report_out_dir, run_at, self.config.run_id)

        run_summary = {
            "run_id": self.config.run_id,
            "model": self.config.model,
            "compare_model": self.config.compare_model,
            "dataset_path": str(self.config.dataset_path),
            "persona_path": str(self.config.persona_path),
            "run_at": run_at,
            "session_count": len(sessions),
            "turn_count": len(records),
        }

        write_json(run_dir / "run.json", run_summary)
        write_json(run_dir / "results.json", {"scores": score_results})

        aggregates = build_aggregates(score_results)
        write_json(run_dir / "aggregates.json", aggregates)

        for reporter in self.reporters:
            reporter.write(run_dir, run_summary, score_results, sessions)

        if self.config.include_raw:
            write_json(run_dir / "raw.json", {"sessions": [session.__dict__ for session in sessions]})

        return run_dir


def load_dataset(path: Path) -> list[dict]:
    """Load the dataset located at *path*."""

    return read_jsonl(path)


def group_sessions(records: Iterable[dict]) -> list[Session]:
    """Group flat dataset records into ordered sessions."""

    sessions: dict[str, list[dict]] = {}
    for record in records:
        session_id = record.get("session_id")
        if not session_id:
            raise ValueError("Dataset record missing 'session_id'.")
        sessions.setdefault(session_id, []).append(record)

    grouped: list[Session] = []
    for session_id, turns in sessions.items():
        ordered = sorted(turns, key=lambda item: item.get("turn_index", 0))
        grouped.append(Session(session_id=session_id, turns=ordered))

    grouped.sort(key=lambda session: session.session_id)
    return grouped


def prepare_run_directory(base_dir: Path, run_at: str, run_id: str) -> Path:
    """Create a timestamped run directory."""

    timestamp = run_at.replace(":", "-").replace("Z", "")
    run_dir = base_dir / f"{timestamp}_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def build_aggregates(score_results: dict) -> dict:
    """Produce lightweight aggregates for reports."""

    aggregates = {}
    for scorer_id, result in score_results.items():
        if isinstance(result, dict):
            aggregates[scorer_id] = {
                key: value
                for key, value in result.items()
                if isinstance(value, (int, float))
            }
        else:
            aggregates[scorer_id] = {"value": result}
    return {"aggregates": aggregates}
