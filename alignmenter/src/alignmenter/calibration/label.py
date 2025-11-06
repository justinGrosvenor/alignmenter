"""Interactive labeling tool for calibration data."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from alignmenter.utils import load_yaml


def label_data(
    input_path: Path,
    persona_path: Path,
    output_path: Path,
    *,
    append: bool = False,
    labeler: Optional[str] = None,
) -> dict:
    """
    Interactively label responses as on-brand (1) or off-brand (0).

    Args:
        input_path: Path to unlabeled candidates JSONL
        persona_path: Path to persona YAML (for context)
        output_path: Path to output labeled JSONL
        append: If True, append to existing labeled data
        labeler: Name of person labeling (optional)

    Returns:
        Statistics about labeling session
    """
    # Load persona for context
    persona = load_yaml(persona_path) or {}
    persona_id = persona.get("id", persona_path.stem)
    display_name = persona.get("display_name", persona_id)

    # Load candidates
    candidates = []
    with open(input_path, "r") as f:
        for line in f:
            if line.strip():
                candidates.append(json.loads(line))

    if not candidates:
        print("No candidates found in input file.")
        return {"labeled": 0, "skipped": 0}

    # Load existing labeled data if appending
    existing_texts = set()
    if append and output_path.exists():
        with open(output_path, "r") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    existing_texts.add(item.get("text", ""))

    # Filter out already-labeled
    to_label = [c for c in candidates if c.get("text") not in existing_texts]

    if not to_label:
        print(f"All candidates already labeled (found {len(existing_texts)} existing labels)")
        return {"labeled": 0, "skipped": len(candidates)}

    print("=" * 80)
    print(f"PERSONA: {display_name} ({persona_id})")
    print("=" * 80)
    print()
    _print_persona_context(persona)
    print()
    print("=" * 80)
    print(f"Ready to label {len(to_label)} responses")
    print("=" * 80)
    print()

    # Open output file in append mode
    mode = "a" if append else "w"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stats = {"labeled": 0, "skipped": 0, "on_brand": 0, "off_brand": 0}

    with open(output_path, mode) as f:
        for i, candidate in enumerate(to_label):
            print(f"\n[{i + 1}/{len(to_label)}]")
            print("-" * 80)
            print(f"TEXT: {candidate['text']}")
            print()

            # Show scenario tags if available
            tags = candidate.get("scenario_tags", [])
            if tags:
                print(f"TAGS: {', '.join(tags)}")
                print()

            # Get label
            label, confidence, notes = _prompt_label()

            if label is None:
                print("⊘ Skipped")
                stats["skipped"] += 1
                continue

            # Update candidate with label
            candidate["label"] = label
            candidate["labeler"] = labeler
            candidate["timestamp"] = datetime.now(timezone.utc).isoformat()
            candidate["confidence"] = confidence
            candidate["notes"] = notes

            # Write to file immediately (don't lose progress)
            f.write(json.dumps(candidate) + "\n")
            f.flush()

            stats["labeled"] += 1
            if label == 1:
                stats["on_brand"] += 1
                print("✓ Labeled: ON-BRAND")
            else:
                stats["off_brand"] += 1
                print("✓ Labeled: OFF-BRAND")

    print()
    print("=" * 80)
    print("LABELING SESSION COMPLETE")
    print("=" * 80)
    print(f"Labeled: {stats['labeled']}")
    print(f"  On-brand: {stats['on_brand']}")
    print(f"  Off-brand: {stats['off_brand']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"Output: {output_path}")

    return stats


def _print_persona_context(persona: dict):
    """Print persona context to help labeler."""
    print("PERSONA CONTEXT:")
    print()

    # Show exemplars
    exemplars = persona.get("exemplars", [])
    if exemplars:
        print("  Exemplars (on-brand examples):")
        for ex in exemplars[:3]:  # Show first 3
            print(f"    • {ex}")
        if len(exemplars) > 3:
            print(f"    ... and {len(exemplars) - 3} more")
        print()

    # Show lexicon
    lexicon = persona.get("lexicon", {})
    if lexicon:
        preferred = lexicon.get("preferred", [])
        avoided = lexicon.get("avoid", [])

        if preferred:
            print(f"  Preferred words: {', '.join(preferred[:10])}")
            if len(preferred) > 10:
                print(f"    ... and {len(preferred) - 10} more")
        if avoided:
            print(f"  Avoid words: {', '.join(avoided[:10])}")
            if len(avoided) > 10:
                print(f"    ... and {len(avoided) - 10} more")


def _prompt_label() -> tuple[Optional[int], Optional[str], str]:
    """
    Prompt user for label, confidence, and notes.

    Returns:
        (label, confidence, notes) or (None, None, "") if skipped
    """
    print("Label this response:")
    print("  1 = On-brand")
    print("  0 = Off-brand")
    print("  s = Skip")
    print("  q = Quit")

    while True:
        response = input("\nYour choice [1/0/s/q]: ").strip().lower()

        if response == "q":
            print("\nQuitting...")
            sys.exit(0)

        if response == "s":
            return None, None, ""

        if response in ["1", "0"]:
            label = int(response)

            # Ask for confidence
            conf_input = input("Confidence [h/m/l] (default: high): ").strip().lower()
            if conf_input == "m":
                confidence = "medium"
            elif conf_input == "l":
                confidence = "low"
            else:
                confidence = "high"

            # Ask for notes
            notes = input("Notes (optional): ").strip()

            return label, confidence, notes

        print("Invalid input. Please enter 1, 0, s, or q.")


def main():
    """CLI entry point for label_data."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Interactively label responses for calibration"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to unlabeled candidates JSONL",
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
        help="Path to output labeled JSONL",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing labeled data",
    )
    parser.add_argument(
        "--labeler",
        type=str,
        help="Name of person labeling",
    )

    args = parser.parse_args()

    label_data(
        input_path=args.input,
        persona_path=args.persona,
        output_path=args.output,
        append=args.append,
        labeler=args.labeler,
    )


if __name__ == "__main__":
    main()
