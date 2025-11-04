"""Runner pipeline tests."""

from __future__ import annotations

import json
from pathlib import Path

from alignmenter.providers.base import ChatResponse
from alignmenter.runner import RunConfig, Runner
from alignmenter.scorers.authenticity import AuthenticityScorer
from alignmenter.scorers.safety import SafetyScorer
from alignmenter.scorers.stability import StabilityScorer
from alignmenter.utils.io import read_jsonl


class StubScorer:
    id = "stub"

    def score(self, sessions):
        return {"mean": 0.5, "count": len(sessions)}


def test_runner_execute_creates_reports(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    base = root / "alignmenter"
    config = RunConfig(
        model="openai:gpt-4o-mini",
        dataset_path=base / "datasets" / "demo_conversations.jsonl",
        persona_path=base / "configs" / "persona" / "default.yaml",
        run_id="test",
        report_out_dir=tmp_path,
    )

    runner = Runner(config=config, scorers=[StubScorer()])
    run_dir = runner.execute()

    assert run_dir.exists()
    report_json = run_dir / "report.json"
    html = run_dir / "index.html"
    run_meta = run_dir / "run.json"

    assert report_json.exists()
    assert html.exists()
    assert run_meta.exists()

    payload = json.loads(report_json.read_text())
    assert payload["scores"]["primary"]["stub"]["mean"] == 0.5
    transcripts_dir = run_dir / "transcripts"
    assert transcripts_dir.exists()
    assert any(transcripts_dir.iterdir())


def test_runner_execute_with_compare(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    base = root / "alignmenter"
    config = RunConfig(
        model="openai:gpt-4o-mini",
        dataset_path=base / "datasets" / "demo_conversations.jsonl",
        persona_path=base / "configs" / "persona" / "default.yaml",
        compare_model="openai:gpt-4o-mini",
        run_id="test",
        report_out_dir=tmp_path,
    )

    scorer_primary = StubScorer()
    scorer_compare = StubScorer()
    runner = Runner(config=config, scorers=[scorer_primary], compare_scorers=[scorer_compare])
    run_dir = runner.execute()

    payload = json.loads((run_dir / "results.json").read_text())
    assert "primary" in payload["scores"]
    assert "compare" in payload["scores"]
    assert "diff" in payload["scores"]
    assert "scorecards" in payload


def test_runner_with_real_scorers_produces_scorecards(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    base = root / "alignmenter"

    config = RunConfig(
        model="openai:gpt-4o-mini",
        dataset_path=base / "datasets" / "demo_conversations.jsonl",
        persona_path=base / "configs" / "persona" / "default.yaml",
        report_out_dir=tmp_path,
        run_id="test-real",
    )

    scorers = [
        AuthenticityScorer(persona_path=config.persona_path, embedding="hashed"),
        SafetyScorer(keyword_path=base / "configs" / "safety_keywords.yaml"),
        StabilityScorer(embedding="hashed"),
    ]

    runner = Runner(config=config, scorers=scorers)
    run_dir = runner.execute()

    results = json.loads((run_dir / "results.json").read_text())
    scorecards = results.get("scorecards", [])

    assert scorecards, "scorecards should be populated"
    assert any(card["id"] == "safety" for card in scorecards)


class StubProvider:
    name = "stub"

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        return ChatResponse(
            text=f"generated-{self.calls}",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

    def tokenizer(self):  # pragma: no cover - not used in tests
        return None


def test_runner_generates_transcripts_with_provider(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.jsonl"
    dataset_records = [
        {
            "session_id": "s1",
            "turn_index": 1,
            "role": "user",
            "text": "Hello",
            "tags": [],
            "persona_id": "default_v1",
        },
        {
            "session_id": "s1",
            "turn_index": 2,
            "role": "assistant",
            "text": "Original",
            "tags": [],
            "persona_id": "default_v1",
        },
    ]
    dataset_path.write_text("\n".join(json.dumps(record) for record in dataset_records) + "\n", encoding="utf-8")

    repo_root = Path(__file__).resolve().parents[1]
    persona_path = repo_root / "configs" / "persona" / "default.yaml"

    config = RunConfig(
        model="openai:gpt-4o-mini",
        dataset_path=dataset_path,
        persona_path=persona_path,
        report_out_dir=tmp_path,
        run_id="generated",
    )

    provider = StubProvider()
    runner = Runner(
        config=config,
        scorers=[StubScorer()],
        provider=provider,
        generate_transcripts=True,
    )

    run_dir = runner.execute()

    assert provider.calls == 1

    transcripts_dir = run_dir / "transcripts"
    transcript_files = list(transcripts_dir.glob("*.jsonl"))
    assert transcript_files, "expected transcript artifacts to be written"

    transcript_records = read_jsonl(transcript_files[0])
    assert transcript_records[1]["text"] == "generated-1"
    metadata = transcript_records[1].get("metadata", {})
    assert metadata.get("baseline_text") == "Original"
    assert metadata.get("generated_by") == "openai:gpt-4o-mini"

    run_meta = json.loads((run_dir / "run.json").read_text())
    assert run_meta["transcripts"]["primary"]["source"] == "generated"
    assert run_meta["usage"]["primary"]["total_tokens"] == 15
