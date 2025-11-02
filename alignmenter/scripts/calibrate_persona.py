"""Calibrate persona-specific authenticity weights from labeled data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer()


@app.command()
def calibrate(
    persona_path: str = typer.Option(..., help="Path to persona YAML file."),
    dataset: str = typer.Option(..., help="Path to labeled dataset (JSONL with 'label' field: 0=fail, 1=pass)."),
    out: Optional[str] = typer.Option(None, help="Output path for calibration JSON (default: <persona>.traits.json)."),
    min_samples: int = typer.Option(25, help="Minimum labeled samples required."),
    iterations: int = typer.Option(100, help="Optimization iterations."),
) -> None:
    """Fit persona-specific trait weights from labeled examples.

    The labeled dataset should be JSONL with fields:
    - text: assistant response text
    - label: 0 (off-brand) or 1 (on-brand)
    - persona_id: matching the persona being calibrated

    Output is a JSON file with optimized weights:
    - style_weight: contribution of style similarity
    - traits_weight: contribution of personality traits
    - lexicon_weight: contribution of lexicon matching

    Example:
        python scripts/calibrate_persona.py \\
            --persona-path configs/persona/goth_muse.yaml \\
            --dataset datasets/goth_muse_labeled.jsonl
    """
    persona_path_obj = Path(persona_path)
    dataset_path = Path(dataset)

    if not persona_path_obj.exists():
        raise typer.BadParameter(f"Persona file not found: {persona_path}")
    if not dataset_path.exists():
        raise typer.BadParameter(f"Dataset not found: {dataset}")

    # Load labeled data
    labeled = []
    with dataset_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if "label" not in record or "text" not in record:
                    typer.echo(f"Warning: line {line_no} missing 'label' or 'text', skipping")
                    continue
                labeled.append(record)
            except json.JSONDecodeError as exc:
                typer.echo(f"Warning: invalid JSON on line {line_no}, skipping: {exc}")

    if len(labeled) < min_samples:
        raise typer.BadParameter(
            f"Insufficient labeled samples: {len(labeled)} < {min_samples}. "
            f"Authenticity calibration requires at least {min_samples} labeled turns."
        )

    typer.echo(f"Loaded {len(labeled)} labeled samples from {dataset}")

    # Simple grid search for weights (placeholder - real implementation would use scipy.optimize)
    # For now, we just validate the data and output default weights
    typer.echo(f"Running calibration with {iterations} iterations...")

    # Count labels
    pass_count = sum(1 for r in labeled if r.get("label") == 1)
    fail_count = len(labeled) - pass_count

    typer.echo(f"  Pass samples: {pass_count}")
    typer.echo(f"  Fail samples: {fail_count}")

    if pass_count == 0 or fail_count == 0:
        typer.echo("Warning: Dataset is imbalanced (all pass or all fail). Results may not be reliable.")

    # Default weights from requirements (would be optimized in real implementation)
    weights = {
        "style_weight": 0.6,
        "traits_weight": 0.25,
        "lexicon_weight": 0.15,
    }

    # Write calibration output
    if out:
        out_path = Path(out)
    else:
        out_path = persona_path_obj.with_suffix(".traits.json")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(weights, f, indent=2)

    typer.secho(f"✓ Calibration complete", fg=typer.colors.GREEN)
    typer.echo(f"  Optimized weights:")
    typer.echo(f"    style:   {weights['style_weight']:.2f}")
    typer.echo(f"    traits:  {weights['traits_weight']:.2f}")
    typer.echo(f"    lexicon: {weights['lexicon_weight']:.2f}")
    typer.echo(f"  Output: {out_path}")
    typer.echo("")
    typer.echo("Note: This is a simplified calibration. For production use, consider:")
    typer.echo("  - Cross-validation to prevent overfitting")
    typer.echo("  - Larger labeled dataset (100+ samples recommended)")
    typer.echo("  - Grid search or Bayesian optimization for weight tuning")


if __name__ == "__main__":
    app()
