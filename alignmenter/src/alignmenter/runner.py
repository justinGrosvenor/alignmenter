"""Run orchestration pipeline."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from uuid import uuid4

from alignmenter.execution.artifacts import export_capture, model_slug, transcript_filename
from alignmenter.execution.leases import coordinator_lease
from alignmenter.execution.legacy import capture_transcripts
from alignmenter.providers.base import ChatProvider
from alignmenter.providers.callable import recovery_contract
from alignmenter.reporting.html import HTMLReporter
from alignmenter.reporting.json_out import JSONReporter
from alignmenter.schemas.execution import (
    ExecutionStatus,
    FailureInfo,
    PlannedTurn,
    RunManifest,
    RunPhase,
    Stream,
    TargetSnapshot,
    content_digest,
)
from alignmenter.storage.runs import DATABASE_NAME, DATABASE_VERSION, RunStore
from alignmenter.utils.io import read_jsonl, write_json, write_jsonl

logger = logging.getLogger(__name__)


@dataclass
class RunConfig:
    """Configuration for a single evaluation run."""

    model: str
    dataset_path: Path
    persona_path: Path
    run_id: str = "alignmenter_run"
    compare_model: str | None = None
    report_out_dir: Path = Path("reports")
    include_raw: bool = True
    max_target_calls: int | None = None

    def __post_init__(self) -> None:
        self.dataset_path = Path(self.dataset_path)
        self.persona_path = Path(self.persona_path)
        self.report_out_dir = Path(self.report_out_dir)


@dataclass
class Session:
    """Grouped conversation session."""

    session_id: str
    turns: list[dict]
    persona_ids: set[str]
    scenario_tags: set[str]


class Runner:
    """Coordinates provider calls, scoring, and reporting."""

    def __init__(
        self,
        config: RunConfig,
        scorers: Iterable,
        compare_scorers: Iterable | None = None,
        reporters: Iterable | None = None,
        *,
        provider: ChatProvider | None = None,
        compare_provider: ChatProvider | None = None,
        generate_transcripts: bool = True,
        compare_generate: bool | None = None,
        progress_callback: Callable[[int], None] | None = None,
        compare_progress_callback: Callable[[int], None] | None = None,
        thresholds: dict[str, dict[str, float]] | None = None,
        suite_snapshot: dict | None = None,
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
        self.thresholds = thresholds or {}
        self.suite_snapshot = suite_snapshot
        self.latest_results: dict[str, Any] | None = None
        self.threshold_results: dict[str, dict[str, Any]] = {}
        self.analytics: dict[str, Any] = {}
        self.run_dir: Path | None = None

    def capture(self) -> Path:
        """Capture inputs and answers without invoking scorers or reporters."""
        return self.execute(capture_only=True)

    def execute(self, *, capture_only: bool = False) -> Path:
        """Execute a fresh run; committed captures survive later failures."""

        self.run_dir = None
        self.latest_results = None
        self.threshold_results = {}
        self.analytics = {}
        records = load_dataset(self.config.dataset_path)
        manifest, plan, persona = self._plan_run(records)
        run_at = manifest.created_at.isoformat().replace("+00:00", "Z")
        run_dir = prepare_run_directory(self.config.report_out_dir, run_at, self.config.run_id)
        self.run_dir = run_dir
        with coordinator_lease(run_dir):
            store = RunStore.create(run_dir, manifest, plan, dataset=records, persona=persona)
            return self._execute_created(store, run_at, capture_only=capture_only)

    def _execute_created(self, store: RunStore, run_at: str, *, capture_only: bool) -> Path:
        run_dir, manifest = store.run_dir, store.manifest()
        try:
            write_json(run_dir / "manifest.json", manifest.model_dump(mode="json"))
            write_json(run_dir / "run.json", {
                "run_id": self.config.run_id, "model": self.config.model,
                "compare_model": self.config.compare_model, "run_at": run_at,
                "dataset_path": str(self.config.dataset_path),
                "persona_path": str(self.config.persona_path),
                "storage": {"schema_version": DATABASE_VERSION, "path": DATABASE_NAME, "run_uuid": str(manifest.id)},
            })
            result = self._execute_pipeline(run_dir, run_at, store, capture_only=capture_only)
            store.set_run_state(status=ExecutionStatus.CAPTURED if capture_only else ExecutionStatus.SUCCEEDED)
            return result
        except BaseException as exc:
            self.latest_results = None
            try:
                interrupted = isinstance(exc, (KeyboardInterrupt, SystemExit))
                store.set_run_state(
                    status=ExecutionStatus.INTERRUPTED if interrupted else ExecutionStatus.FAILED,
                    failure=FailureInfo(kind="interrupted" if interrupted else "pipeline_error",
                                        exception_type=type(exc).__name__),
                )
                self._export_captured_transcripts(store)
            except Exception:
                logger.error("Could not finalize run artifacts; committed database records remain authoritative")
            raise

    def _plan_run(self, records: list[dict]) -> tuple[RunManifest, list[PlannedTurn], bytes | None]:
        grouped = _group_records(records)
        ordered = [turn for turns in grouped.values() for turn in turns]
        targets = [TargetSnapshot(
            stream="primary", model=self.config.model,
            mode="generate" if self.generate_transcripts else "recorded",
            adapter=_adapter_name(self.provider) if self.generate_transcripts else None,
            recovery=recovery_contract(self.provider) if self.generate_transcripts else None,
        )]
        if self.compare_scorers:
            targets.append(TargetSnapshot(
                stream="compare", model=self.config.compare_model or "compare",
                mode="generate" if self.compare_generate else "recorded",
                adapter=_adapter_name(self.compare_provider) if self.compare_generate else None,
                recovery=recovery_contract(self.compare_provider) if self.compare_generate else None,
            ))
        plan = [PlannedTurn(
            stream=target.stream, ordinal=ordinal, session_id=record["session_id"],
            role=(record.get("role") or "user").strip().lower(),
            generate=target.mode == "generate" and (record.get("role") or "user").strip().lower() == "assistant",
            record=record,
        ) for target in targets for ordinal, record in enumerate(ordered)]
        persona = self.config.persona_path.read_bytes() if self.config.persona_path.is_file() else None
        try:
            package_version = version("alignmenter")
        except PackageNotFoundError:
            package_version = "unknown"
        manifest = RunManifest(
            label=self.config.run_id, dataset_path=str(self.config.dataset_path),
            dataset_digest=content_digest(records), persona_path=str(self.config.persona_path),
            plan_digest=content_digest([t.model_dump(mode="json") for t in sorted(plan, key=lambda t: (t.stream, t.ordinal))]),
            persona_digest=hashlib.sha256(persona).hexdigest() if persona is not None else None,
            targets=tuple(targets), scorer_ids={"primary": [s.id for s in self.scorers],
                                               "compare": [s.id for s in self.compare_scorers]},
            thresholds=self.thresholds, include_raw=self.config.include_raw, package_version=package_version,
            max_target_calls=self.config.max_target_calls, suite=self.suite_snapshot,
        )
        return manifest, plan, persona

    def _export_captured_transcripts(self, store: RunStore) -> None:
        export_capture(store)

    def _transcript_filename(self, stream: Stream) -> str:
        model = self.config.model if stream == "primary" else self.config.compare_model or "compare"
        return transcript_filename(model, stream, self.config.model)

    def _execute_pipeline(
        self, run_dir: Path, run_at: str, store: RunStore, *, capture_only: bool = False
    ) -> Path:

        primary_records, primary_usage = self._prepare_transcripts(
            store=store, stream="primary",
            provider=self.provider if self.generate_transcripts else None,
            model_identifier=self.config.model,
            progress_callback=self.progress_callback,
        )
        primary_sessions = group_sessions(primary_records)

        compare_records: list[dict[str, Any]] | None = None
        compare_usage: dict[str, int] = {}
        compare_sessions: list[Session] | None = None

        if self.compare_scorers:
            compare_records, compare_usage = self._prepare_transcripts(
                store=store, stream="compare",
                provider=self.compare_provider if self.compare_generate else None,
                model_identifier=self.config.compare_model,
                progress_callback=self.compare_progress_callback,
            )
            compare_sessions = group_sessions(compare_records)

        self._export_captured_transcripts(store)
        if capture_only:
            return run_dir
        store.set_run_state(phase=RunPhase.SCORING)
        primary_scores = self._run_scorers(self.scorers, primary_sessions)
        score_results: dict[str, Any] = {"primary": primary_scores}

        threshold_eval = self._evaluate_thresholds(primary_scores)
        if threshold_eval:
            score_results["thresholds"] = threshold_eval
            self.threshold_results = threshold_eval

        compare_scores: dict[str, Any] = {}
        if self.compare_scorers and compare_sessions is not None:
            compare_scores = self._run_scorers(self.compare_scorers, compare_sessions)
            score_results["compare"] = compare_scores
            score_results["diff"] = compute_diffs(primary_scores, compare_scores)

        analytics = self._build_breakdowns(primary_sessions, self.scorers)
        if analytics:
            score_results["analytics"] = analytics
            self.analytics = analytics

        store.set_run_state(phase=RunPhase.REPORTING)

        transcript_info: dict[str, dict[str, str]] = {}
        transcripts_dir = run_dir / "transcripts"
        transcripts_dir.mkdir(parents=True, exist_ok=True)

        primary_transcript_path = transcripts_dir / self._transcript_filename("primary")
        write_jsonl(primary_transcript_path, primary_records)
        transcript_info["primary"] = {
            "model": self.config.model,
            "path": str(primary_transcript_path.relative_to(run_dir)),
            "source": "generated" if self.generate_transcripts else "dataset",
        }

        if compare_records is not None:
            compare_model = self.config.compare_model or "compare"
            compare_transcript_path = transcripts_dir / self._transcript_filename("compare")
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
            "storage": {"schema_version": DATABASE_VERSION, "path": DATABASE_NAME,
                        "run_uuid": str(store.manifest().id)},
        }

        if threshold_eval:
            run_summary["thresholds"] = threshold_eval

        usage_summary: dict[str, dict[str, int]] = {}
        if primary_usage:
            usage_summary["primary"] = {"model": self.config.model, **primary_usage}
        if compare_usage:
            usage_summary["compare"] = {"model": self.config.compare_model, **compare_usage}
        if usage_summary:
            run_summary["usage"] = usage_summary

        write_json(run_dir / "run.json", run_summary)
        scorecards = build_scorecards(
            primary_scores,
            compare_scores,
            score_results.get("diff", {}),
            thresholds=threshold_eval,
        )
        results_payload = {"scores": score_results, "scorecards": scorecards}
        write_json(run_dir / "results.json", results_payload)

        if analytics:
            write_json(run_dir / "analytics.json", analytics)

        aggregates = build_aggregates(score_results)
        write_json(run_dir / "aggregates.json", aggregates)

        for reporter in self.reporters:
            reporter.write(
                run_dir,
                run_summary,
                score_results,
                primary_sessions,
                scorecards=scorecards,
                analytics=analytics,
            )

        if self.config.include_raw:
            write_json(
                run_dir / "raw.json",
                {"sessions": [_serialize_session(session) for session in primary_sessions]},
            )

        self.latest_results = score_results
        return run_dir

    def _run_scorers(self, scorers: Iterable, sessions: list[Session]) -> dict:
        results = {}
        for scorer in scorers:
            results[scorer.id] = scorer.score(sessions)
        return results

    def _evaluate_thresholds(self, primary_scores: dict) -> dict[str, dict[str, Any]]:
        if not self.thresholds:
            return {}

        evaluations: dict[str, dict[str, Any]] = {}
        for scorer_id, config in self.thresholds.items():
            metric_info = THRESHOLD_METRICS.get(scorer_id)
            if not metric_info:
                continue

            metric_key, higher_is_better = metric_info
            # "dangerous" is a gate on the faithfulness scorer's count, not a scorer of its own.
            metrics = primary_scores.get("faithfulness" if scorer_id == "dangerous" else scorer_id)
            value = _extract_metric(metrics, metric_key)
            if value is None:
                continue

            # `or` would drop a legitimate threshold of 0 (e.g. dangerous.fail: 0).
            warn_threshold = _safe_float(_first_present(config.get("warn"), config.get("threshold_warn")))
            fail_threshold = _safe_float(_first_present(config.get("fail"), config.get("threshold_fail")))

            status = "pass"
            if fail_threshold is not None:
                if higher_is_better and value < fail_threshold:
                    status = "fail"
                elif not higher_is_better and value > fail_threshold:
                    status = "fail"
            if status != "fail" and warn_threshold is not None:
                if higher_is_better and value < warn_threshold:
                    status = "warn"
                elif not higher_is_better and value > warn_threshold:
                    status = "warn"

            evaluations[scorer_id] = {
                "metric": metric_key,
                "value": round(value, 3),
                "warn": warn_threshold,
                "fail": fail_threshold,
                "status": status,
            }

        return evaluations

    def _build_breakdowns(
        self, sessions: list[Session], scorers: Iterable
    ) -> dict[str, Any]:
        breakdowns: dict[str, Any] = {"scenarios": {}, "personas": {}}

        scenario_groups: dict[str, list[Session]] = {}
        persona_groups: dict[str, list[Session]] = {}

        for session in sessions:
            for scenario in session.scenario_tags:
                scenario_groups.setdefault(scenario, []).append(session)
            for persona in session.persona_ids:
                persona_groups.setdefault(persona, []).append(session)

        def summarize(group: list[Session]) -> dict[str, Any]:
            if not group:
                return {}
            subset = list(group)
            scores = self._run_scorers(scorers, subset)
            return {
                "sessions": len(subset),
                "turns": sum(len(session.turns) for session in subset),
                "scores": scores,
            }

        for scenario, group in sorted(scenario_groups.items()):
            breakdowns["scenarios"][scenario] = summarize(group)

        for persona, group in sorted(persona_groups.items()):
            breakdowns["personas"][persona] = summarize(group)

        return breakdowns

    def _prepare_transcripts(
        self,
        *,
        store: RunStore,
        stream: Stream,
        provider: ChatProvider | None,
        model_identifier: str | None,
        progress_callback: Callable[[int], None] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        output = capture_transcripts(store, stream, provider, model_identifier or "provider", progress_callback)
        usage = _UsageAccumulator()
        if provider is not None:
            for observation in store.observations():
                if observation.stream == stream and observation.origin == "generated" and observation.usage is not None:
                    usage.add(observation.usage)
        return output, usage.as_dict()


def load_dataset(path: Path) -> list[dict]:
    """Load the dataset located at *path*."""

    return read_jsonl(path)


def group_sessions(records: Iterable[dict]) -> list[Session]:
    """Group flat dataset records into ordered sessions."""

    sessions: dict[str, list[dict]] = {}
    persona_map: dict[str, set[str]] = {}
    scenario_map: dict[str, set[str]] = {}

    for record in records:
        session_id = record.get("session_id")
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("Dataset record missing 'session_id'.")
        session_id = session_id.strip()
        sessions.setdefault(session_id, []).append(record)

        persona_id = record.get("persona_id")
        if isinstance(persona_id, str) and persona_id.strip():
            persona_map.setdefault(session_id, set()).add(persona_id.strip())

        tags = record.get("tags") or []
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag.startswith("scenario:"):
                    scenario_map.setdefault(session_id, set()).add(tag)

    grouped: list[Session] = []
    for session_id, turns in sessions.items():
        ordered = sorted(turns, key=lambda item: item.get("turn_index", 0))
        grouped.append(
            Session(
                session_id=session_id,
                turns=ordered,
                persona_ids=persona_map.get(session_id, set()),
                scenario_tags=scenario_map.get(session_id, set()),
            )
        )

    grouped.sort(key=lambda session: session.session_id)
    return grouped


def prepare_run_directory(base_dir: Path, run_at: str, run_id: str) -> Path:
    """Create a timestamped run directory."""

    timestamp = run_at.replace(":", "-").replace("Z", "")
    base_dir = Path(base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{timestamp}_{_slugify_model(run_id)}"
    run_dir = base_dir / stem
    while True:
        try:
            run_dir.mkdir(exist_ok=False)
            return run_dir
        except FileExistsError:
            run_dir = base_dir / f"{stem}_{uuid4().hex}"


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


def build_scorecards(
    primary: dict,
    compare: dict,
    diff: dict,
    *,
    thresholds: dict[str, dict[str, Any]] | None = None,
) -> list[dict]:
    """Create scorecard summaries for headline metrics."""

    config = {
        "authenticity": ("mean", "Authenticity Score"),
        "safety": ("score", "Safety Score"),
        "stability": ("stability", "Stability"),
        "grounding": ("score", "Grounding"),
        "faithfulness": ("score", "Faithfulness"),
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

        if thresholds and scorer_id in thresholds:
            card["status"] = thresholds[scorer_id].get("status")
            card["warn"] = thresholds[scorer_id].get("warn")
            card["fail"] = thresholds[scorer_id].get("fail")
        scorecards.append(card)

    return scorecards


def _extract_metric(metrics: dict | None, key: str) -> float | None:
    if isinstance(metrics, dict):
        value = metrics.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _serialize_session(session: Session) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "turns": session.turns,
        "persona_ids": sorted(session.persona_ids),
        "scenario_tags": sorted(session.scenario_tags),
    }


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _group_records(records: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    seen: set[tuple[str, int]] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Dataset records must be JSON objects")
        session_id = record.get("session_id")
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("Dataset record missing 'session_id'.")
        if not isinstance(record.get("role") or "user", str):
            raise ValueError("Dataset role must be a string")
        if "turn_index" in record:
            index = record["turn_index"]
            if type(index) is not int or index < 0:
                raise ValueError("Dataset turn_index must be a nonnegative integer")
            if (session_id, index) in seen:
                raise ValueError(f"Duplicate turn_index in session {session_id!r}")
            seen.add((session_id, index))
        grouped.setdefault(session_id, []).append(record)

    for turns in grouped.values():
        turns.sort(key=lambda item: item.get("turn_index", 0))

    return {session_id: grouped[session_id] for session_id in sorted(grouped)}


def _adapter_name(provider: ChatProvider | None) -> str | None:
    if provider is None:
        return None
    return f"{type(provider).__module__}.{type(provider).__qualname__}"


def _slugify_model(identifier: str | None) -> str:
    return model_slug(identifier)


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
THRESHOLD_METRICS: dict[str, tuple[str, bool]] = {
    "authenticity": ("mean", True),
    "safety": ("score", True),
    "stability": ("stability", True),
    "grounding": ("score", True),
    "faithfulness": ("score", True),
    # A count, not a rate: the product gate is "zero answers that could hurt someone".
    "dangerous": ("dangerous", False),
}
