"""Run orchestration pipeline."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from alignmenter.providers.base import ChatProvider
from alignmenter.reporting.html import HTMLReporter
from alignmenter.reporting.json_out import JSONReporter
from alignmenter.utils.io import read_jsonl, write_json, write_jsonl


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
        *,
        provider: Optional[ChatProvider] = None,
        compare_provider: Optional[ChatProvider] = None,
        generate_transcripts: bool = True,
        compare_generate: Optional[bool] = None,
        progress_callback: Optional[Callable[[int], None]] = None,
        compare_progress_callback: Optional[Callable[[int], None]] = None,
    ) -> None:
        self.config = config
        self.scorers = list(scorers)
        self.compare_scorers = list(compare_scorers or [])
        self.reporters = list(reporters or [JSONReporter(), HTMLReporter()])
        self.provider = provider
        self.compare_provider = compare_provider
        self.generate_transcripts = bool(generate_transcripts and provider is not None)
        if compare_generate is None:
            compare_generate = generate_transcripts
        self.compare_generate = bool(compare_generate and compare_provider is not None)
        self.progress_callback = progress_callback if self.generate_transcripts else None
        self.compare_progress_callback = (
            compare_progress_callback if self.compare_generate else None
        )

    def execute(self) -> Path:
        """Execute an evaluation run and return the artifact directory."""

        records = load_dataset(self.config.dataset_path)

        primary_records, primary_usage = self._prepare_transcripts(
            records,
            provider=self.provider if self.generate_transcripts else None,
            model_identifier=self.config.model,
            progress_callback=self.progress_callback,
        )
        primary_sessions = group_sessions(primary_records)

        compare_records: Optional[list[dict[str, Any]]] = None
        compare_usage: dict[str, int] = {}
        compare_sessions: Optional[list[Session]] = None

        if self.compare_scorers:
            compare_records, compare_usage = self._prepare_transcripts(
                records,
                provider=self.compare_provider if self.compare_generate else None,
                model_identifier=self.config.compare_model,
                progress_callback=self.compare_progress_callback,
            )
            compare_sessions = group_sessions(compare_records)

        primary_scores = self._run_scorers(self.scorers, primary_sessions)
        score_results: dict[str, Any] = {"primary": primary_scores}

        compare_scores: dict[str, Any] = {}
        if self.compare_scorers and compare_sessions is not None:
            compare_scores = self._run_scorers(self.compare_scorers, compare_sessions)
            score_results["compare"] = compare_scores
            score_results["diff"] = compute_diffs(primary_scores, compare_scores)

        run_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        run_dir = prepare_run_directory(self.config.report_out_dir, run_at, self.config.run_id)

        transcript_info: dict[str, dict[str, str]] = {}
        transcripts_dir = run_dir / "transcripts"
        transcripts_dir.mkdir(parents=True, exist_ok=True)

        primary_transcript_path = transcripts_dir / f"{_slugify_model(self.config.model)}.jsonl"
        write_jsonl(primary_transcript_path, primary_records)
        transcript_info["primary"] = {
            "model": self.config.model,
            "path": str(primary_transcript_path.relative_to(run_dir)),
            "source": "generated" if self.generate_transcripts else "dataset",
        }

        if compare_records is not None:
            compare_model = self.config.compare_model or "compare"
            compare_transcript_path = transcripts_dir / f"{_slugify_model(compare_model)}.jsonl"
            write_jsonl(compare_transcript_path, compare_records)
            transcript_info["compare"] = {
                "model": compare_model,
                "path": str(compare_transcript_path.relative_to(run_dir)),
                "source": "generated" if self.compare_generate else "dataset",
            }

        run_summary = {
            "run_id": self.config.run_id,
            "model": self.config.model,
            "compare_model": self.config.compare_model,
            "dataset_path": str(self.config.dataset_path),
            "persona_path": str(self.config.persona_path),
            "run_at": run_at,
            "session_count": len(primary_sessions),
            "turn_count": len(primary_records),
            "transcripts": transcript_info,
        }

        usage_summary: dict[str, dict[str, int]] = {}
        if primary_usage:
            usage_summary["primary"] = {"model": self.config.model, **primary_usage}
        if compare_usage:
            usage_summary["compare"] = {"model": self.config.compare_model, **compare_usage}
        if usage_summary:
            run_summary["usage"] = usage_summary

        write_json(run_dir / "run.json", run_summary)
        scorecards = build_scorecards(primary_scores, compare_scores, score_results.get("diff", {}))
        write_json(run_dir / "results.json", {"scores": score_results, "scorecards": scorecards})

        aggregates = build_aggregates(score_results)
        write_json(run_dir / "aggregates.json", aggregates)

        for reporter in self.reporters:
            reporter.write(run_dir, run_summary, score_results, primary_sessions, scorecards=scorecards)

        if self.config.include_raw:
            write_json(
                run_dir / "raw.json",
                {"sessions": [session.__dict__ for session in primary_sessions]},
            )

        return run_dir

    def _run_scorers(self, scorers: Iterable, sessions: list[Session]) -> dict:
        results = {}
        for scorer in scorers:
            results[scorer.id] = scorer.score(sessions)
        return results

    def _prepare_transcripts(
        self,
        records: Iterable[dict[str, Any]],
        *,
        provider: Optional[ChatProvider],
        model_identifier: Optional[str],
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> Tuple[List[dict[str, Any]], dict[str, int]]:
        grouped = _group_records(records)
        output: List[dict[str, Any]] = []
        usage = _UsageAccumulator()

        for session_id in grouped:
            conversation: List[dict[str, str]] = []
            for turn in grouped[session_id]:
                record = copy.deepcopy(turn)
                role = (record.get("role") or "user").strip().lower()

                if role == "assistant" and provider is not None:
                    baseline = record.get("text")
                    if baseline:
                        metadata = _ensure_metadata(record)
                        metadata.setdefault("baseline_text", baseline)

                    response = provider.chat([dict(msg) for msg in conversation])
                    generated_text = (response.text or "").strip()
                    record["text"] = generated_text

                    metadata = _ensure_metadata(record)
                    metadata["generated_by"] = model_identifier or getattr(provider, "name", "provider")
                    if response.usage:
                        metadata["usage"] = response.usage
                        usage.add(response.usage)

                    conversation.append({"role": "assistant", "content": generated_text})
                    if progress_callback:
                        progress_callback(1)
                else:
                    conversation.append({"role": role or "user", "content": record.get("text", "")})

                output.append(record)

        return output, usage.as_dict()


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
        "safety": ("score", "Safety Score"),
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


def _group_records(records: Iterable[dict[str, Any]]) -> Dict[str, List[dict[str, Any]]]:
    grouped: Dict[str, List[dict[str, Any]]] = {}
    for record in records:
        session_id = record.get("session_id")
        if not session_id:
            raise ValueError("Dataset record missing 'session_id'.")
        grouped.setdefault(session_id, []).append(record)

    for turns in grouped.values():
        turns.sort(key=lambda item: item.get("turn_index", 0))

    return {session_id: grouped[session_id] for session_id in sorted(grouped)}


def _ensure_metadata(record: dict[str, Any]) -> dict[str, Any]:
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        record["metadata"] = metadata
    return metadata


def _slugify_model(identifier: Optional[str]) -> str:
    if not identifier:
        return "model"
    slug = [ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in identifier]
    collapsed = "".join(slug).strip("_")
    return collapsed or "model"


class _UsageAccumulator:
    """Track token usage totals for provider calls."""

    def __init__(self) -> None:
        self.prompt = 0
        self.completion = 0
        self.total = 0

    def add(self, usage: dict[str, Any]) -> None:
        self.prompt += _safe_int(usage.get("prompt_tokens"))
        self.completion += _safe_int(usage.get("completion_tokens"))
        self.total += _safe_int(usage.get("total_tokens"))

    def as_dict(self) -> dict[str, int]:
        return {
            key: value
            for key, value in {
                "prompt_tokens": self.prompt,
                "completion_tokens": self.completion,
                "total_tokens": self.total,
            }.items()
            if value
        }


def _safe_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value))
    except (ValueError, TypeError):
        return 0
