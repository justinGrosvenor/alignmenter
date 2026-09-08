"""Tests for the deterministic grounding scorer."""

from __future__ import annotations

from alignmenter.runner import RunConfig, Runner, build_scorecards
from alignmenter.scorers.grounding import GroundingScorer, extract_quantities


def _session(answer: str, excerpts: list, question: str = "How long do I boil water?") -> dict:
    return {
        "session_id": "s1",
        "turns": [
            {"role": "user", "text": question},
            {
                "role": "assistant",
                "text": answer,
                "metadata": {"context": {"question": question, "excerpts": excerpts}},
            },
        ],
    }


def test_extract_quantities_normalises_units_and_values() -> None:
    pairs = extract_quantities("Boil for 1.0 minute, add 2 drops per litre, cool to 70 °C.")
    assert ("1", "min") in pairs
    assert ("2", "drop") in pairs
    assert ("70", "deg") in pairs


def test_extract_quantities_ignores_list_numbers_and_citations() -> None:
    pairs = extract_quantities("1. Boil the water [2].\n2. Wait 3 minutes [1, 3].")
    assert pairs == [("3", "min")]


def test_grounded_answer_scores_one() -> None:
    excerpts = [{"title": "Water", "text": "Bring water to a rolling boil for 1 minute."}]
    result = GroundingScorer().score([_session("Boil it for 1 minute [1].", excerpts)])
    assert result["score"] == 1.0
    assert result["quantities_checked"] == 1
    assert result["citation_validity"] == 1.0
    assert result["violations"] == []


def test_invented_and_contradicted_are_split() -> None:
    excerpts = ["Boil for 1 minute. Use 2 drops of bleach per litre."]
    # 5 minutes contradicts a figure the passages gave in that unit; 40 grams is invented.
    answer = "Boil for 5 minutes and add 2 drops per litre, then stir in 40 grams of salt."
    result = GroundingScorer().score([_session(answer, excerpts)])
    assert result["quantities_checked"] == 3
    assert result["quantities_supported"] == 1
    assert result["contradicted"] == 1
    assert result["invented"] == 1
    violation = result["violations"][0]
    assert violation["question"] == "How long do I boil water?"
    assert "5 min" in violation["contradicted"]
    assert "40 g" in violation["invented"]


def test_citation_past_excerpt_list_is_invalid() -> None:
    result = GroundingScorer().score([_session("Boil for 1 minute [4].", ["Boil for 1 minute."])])
    assert result["citations"] == 1
    assert result["invalid_citations"] == 1
    assert result["citation_validity"] == 0.0


def test_plain_string_and_alternate_context_keys_are_read() -> None:
    session = {
        "session_id": "s2",
        "turns": [
            {"role": "user", "text": "Dose?"},
            {
                "role": "assistant",
                "text": "Take 500 mg.",
                "metadata": {"context": {"passages": ["The usual dose is 500 mg."]}},
            },
        ],
    }
    result = GroundingScorer().score([session])
    assert result["score"] == 1.0


def test_turns_without_context_are_ignored() -> None:
    session = {
        "session_id": "s3",
        "turns": [{"role": "user", "text": "hi"}, {"role": "assistant", "text": "Wait 10 minutes."}],
    }
    result = GroundingScorer().score([session])
    assert result["turns"] == 0
    assert result["score"] == 1.0


def test_scorecard_and_threshold_wiring(tmp_path) -> None:
    root = __import__("pathlib").Path(__file__).resolve().parents[2] / "alignmenter"
    config = RunConfig(
        model="openai:gpt-4o-mini",
        dataset_path=root / "datasets" / "demo_conversations.jsonl",
        persona_path=root / "configs" / "persona" / "default.yaml",
        run_id="grounded",
        report_out_dir=tmp_path,
    )

    class FixedGrounding:
        id = "grounding"

        def score(self, sessions):
            return {"score": 0.6, "violations": []}

    runner = Runner(config=config, scorers=[FixedGrounding()], thresholds={"grounding": {"fail": 0.8}})
    runner.execute()
    assert runner.threshold_results["grounding"]["status"] == "fail"
    cards = build_scorecards({"grounding": {"score": 0.6}}, {}, {})
    assert cards and cards[0]["label"] == "Grounding" and cards[0]["primary"] == 0.6
