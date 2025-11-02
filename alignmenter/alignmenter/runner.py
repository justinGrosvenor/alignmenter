"""Run orchestration pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

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
        compare_scorers: Optional[Iterable] = None,
        reporters: Optional[Iterable] = None,
    ) -> None:
        self.config = config
        self.scorers = list(scorers)
        self.compare_scorers = list(compare_scorers or [])
        self.reporters = list(reporters or [JSONReporter(), HTMLReporter()])

    def execute(self) -> Path:
        """Execute an evaluation run and return the artifact directory."""

        records = load_dataset(self.config.dataset_path)
        sessions = group_sessions(records)

        primary_scores = self._run_scorers(self.scorers, sessions)
        score_results = {"primary": primary_scores}

        compare_scores: dict = {}
        if self.compare_scorers and self.config.compare_model:
            compare_scores = self._run_scorers(self.compare_scorers, sessions)
            score_results["compare"] = compare_scores
            score_results["diff"] = compute_diffs(primary_scores, compare_scores)

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
        scorecards = build_scorecards(primary_scores, compare_scores, score_results.get("diff", {}))
        write_json(run_dir / "results.json", {"scores": score_results, "scorecards": scorecards})

        aggregates = build_aggregates(score_results)
        write_json(run_dir / "aggregates.json", aggregates)

        for reporter in self.reporters:
            reporter.write(run_dir, run_summary, score_results, sessions, scorecards=scorecards)

        if self.config.include_raw:
            write_json(run_dir / "raw.json", {"sessions": [session.__dict__ for session in sessions]})

        return run_dir

    def _run_scorers(self, scorers: Iterable, sessions: list[Session]) -> dict:
        results = {}
        for scorer in scorers:
            results[scorer.id] = scorer.score(sessions)
        return results


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


def compute_diffs(primary: dict, compare: dict) -> dict:
    """Compute numeric differences between primary and compare results."""

    diffs: dict = {}
    for scorer_id, primary_result in primary.items():
        compare_result = compare.get(scorer_id)
        if not isinstance(primary_result, dict) or not isinstance(compare_result, dict):
            continue
        diff_values = {}
        for key, value in primary_result.items():
            comp_value = compare_result.get(key)
            if isinstance(value, (int, float)) and isinstance(comp_value, (int, float)):
                diff_values[key] = round(value - comp_value, 3)
        if diff_values:
            diffs[scorer_id] = diff_values
    return diffs


def build_aggregates(score_results: dict) -> dict:
    """Produce lightweight aggregates for reports."""

    aggregates: dict[str, dict] = {}
    for scope in ("primary", "compare", "diff"):
        result_set = score_results.get(scope)
        if not isinstance(result_set, dict):
            continue
        scoped = {}
        for scorer_id, values in result_set.items():
            if isinstance(values, dict):
                scoped[scorer_id] = {
                    key: value
                    for key, value in values.items()
                    if isinstance(value, (int, float))
                }
        if scoped:
            aggregates[scope] = scoped
    return {"aggregates": aggregates}


def build_scorecards(primary: dict, compare: dict, diff: dict) -> list[dict]:
    """Create scorecard summaries for headline metrics."""

    config = {
        "authenticity": ("mean", "Authenticity Score"),
        "safety": ("violation_rate", "Safety Violation Rate"),
        "stability": ("stability", "Stability"),
    }

    scorecards: list[dict] = []
    for scorer_id, (metric_key, label) in config.items():
        primary_metrics = primary.get(scorer_id)
        primary_value = _extract_metric(primary_metrics, metric_key)
        if primary_value is None:
            continue

        card = {
            "id": scorer_id,
            "label": label,
            "metric": metric_key,
            "primary": primary_value,
        }

        compare_metrics = compare.get(scorer_id) if isinstance(compare, dict) else None
        if isinstance(compare_metrics, dict) and compare_metrics:
            compare_value = _extract_metric(compare_metrics, metric_key)
            if compare_value is not None:
                card["compare"] = compare_value

        diff_metrics = diff.get(scorer_id) if isinstance(diff, dict) else None
        if isinstance(diff_metrics, dict) and diff_metrics:
            diff_value = _extract_metric(diff_metrics, metric_key)
            if diff_value is not None:
                card["diff"] = diff_value

        scorecards.append(card)

    return scorecards


def _extract_metric(metrics: Optional[dict], key: str) -> Optional[float]:
    if isinstance(metrics, dict):
        value = metrics.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None
