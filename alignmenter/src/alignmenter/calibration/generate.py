"""Generate candidate responses for labeling from existing datasets."""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Optional

from alignmenter.utils import load_yaml


def generate_candidates(
    dataset_path: Path,
    persona_path: Path,
    output_path: Path,
    *,
    num_samples: int = 50,
    strategy: str = "diverse",
    seed: int = 42,
) -> dict:
    """
    Generate candidate responses for labeling from an existing dataset.

    Args:
        dataset_path: Path to input JSONL dataset
        persona_path: Path to persona YAML
        output_path: Path to output unlabeled candidates
        num_samples: Number of candidates to generate
        strategy: Sampling strategy ("diverse", "random", "edge_cases")
        seed: Random seed for reproducibility

    Returns:
        Statistics about generated candidates
    """
    random.seed(seed)

    # Load persona to get persona_id
    persona = load_yaml(persona_path) or {}
    persona_id = persona.get("id", persona_path.stem)

    # Read dataset
    records = []
    with open(dataset_path, "r") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    # Filter for assistant responses
    assistant_turns = [
        r for r in records
        if r.get("role") == "assistant" and r.get("text")
    ]

    if not assistant_turns:
        raise ValueError(f"No assistant turns found in {dataset_path}")

    # Apply sampling strategy
    if strategy == "diverse":
        candidates = _sample_diverse(assistant_turns, num_samples)
    elif strategy == "edge_cases":
        candidates = _sample_edge_cases(assistant_turns, num_samples, persona)
    else:  # random
        candidates = random.sample(assistant_turns, min(num_samples, len(assistant_turns)))

    # Convert to unlabeled format
    unlabeled = []
    for turn in candidates:
        unlabeled.append({
            "text": turn["text"],
            "label": None,  # To be filled by labeler
            "persona_id": persona_id,
            "session_id": turn.get("session_id"),
            "turn_index": turn.get("turn_index"),
            "scenario_tags": turn.get("tags", []),
            "labeler": None,
            "timestamp": None,
            "confidence": None,
            "notes": "",
        })

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for item in unlabeled:
            f.write(json.dumps(item) + "\n")

    # Compute statistics
    scenario_counts = defaultdict(int)
    for item in unlabeled:
        for tag in item.get("scenario_tags", []):
            if tag.startswith("scenario:"):
                scenario_counts[tag] += 1

    return {
        "total_candidates": len(unlabeled),
        "strategy": strategy,
        "scenario_distribution": dict(scenario_counts),
        "output_path": str(output_path),
    }


def _sample_diverse(turns: list[dict], num_samples: int) -> list[dict]:
    """
    Sample diverse responses across scenarios.

    Ensures representation from different scenario tags.
    """
    # Group by scenario tags
    by_scenario = defaultdict(list)
    for turn in turns:
        tags = turn.get("tags", [])
        scenario_tags = [t for t in tags if t.startswith("scenario:")]
        if scenario_tags:
            # Use first scenario tag as primary
            by_scenario[scenario_tags[0]].append(turn)
        else:
            by_scenario["untagged"].append(turn)

    # Sample proportionally from each scenario
    scenarios = list(by_scenario.keys())
    if not scenarios:
        return random.sample(turns, min(num_samples, len(turns)))

    samples_per_scenario = max(1, num_samples // len(scenarios))
    candidates = []

    for scenario, scenario_turns in by_scenario.items():
        n = min(samples_per_scenario, len(scenario_turns))
        candidates.extend(random.sample(scenario_turns, n))

    # If we haven't reached num_samples, add more randomly
    if len(candidates) < num_samples:
        remaining = [t for t in turns if t not in candidates]
        additional = min(num_samples - len(candidates), len(remaining))
        candidates.extend(random.sample(remaining, additional))

    return candidates[:num_samples]


def _sample_edge_cases(turns: list[dict], num_samples: int, persona: dict) -> list[dict]:
    """
    Prioritize edge cases: brand_trap, safety_trap, etc.

    These are likely to be off-brand and useful for calibration.
    """
    edge_case_tags = ["scenario:brand_trap", "scenario:safety_trap"]

    # Prioritize edge cases
    edge_cases = []
    normal_cases = []

    for turn in turns:
        tags = turn.get("tags", [])
        if any(tag in edge_case_tags for tag in tags):
            edge_cases.append(turn)
        else:
            normal_cases.append(turn)

    # Take all edge cases, then fill with normal cases
    candidates = edge_cases[:]
    if len(candidates) < num_samples:
        additional = min(num_samples - len(candidates), len(normal_cases))
        candidates.extend(random.sample(normal_cases, additional))

    return candidates[:num_samples]


def main():
    """CLI entry point for generate_candidates."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate candidate responses for labeling"
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="Path to input JSONL dataset",
    )
    parser.add_argument(
        "--persona",
        type=Path,
        required=True,
        help="Path to persona YAML",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to output unlabeled candidates",
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=50,
        help="Number of candidates to generate (default: 50)",
    )
    parser.add_argument(
        "--strategy",
        choices=["diverse", "random", "edge_cases"],
        default="diverse",
        help="Sampling strategy (default: diverse)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )

    args = parser.parse_args()

    result = generate_candidates(
        dataset_path=args.dataset,
        persona_path=args.persona,
        output_path=args.output,
        num_samples=args.num_samples,
        strategy=args.strategy,
        seed=args.seed,
    )

    print(f"✓ Generated {result['total_candidates']} candidates")
    print(f"  Strategy: {result['strategy']}")
    print(f"  Output: {result['output_path']}")
    print(f"\nScenario distribution:")
    for scenario, count in sorted(result['scenario_distribution'].items()):
        print(f"  {scenario}: {count}")


if __name__ == "__main__":
    main()
