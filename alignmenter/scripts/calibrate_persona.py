"""Calibrate persona-specific authenticity weights from labeled data."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import typer

from alignmenter.scorers.authenticity import TOKEN_PATTERN
from alignmenter.utils import load_yaml

app = typer.Typer()


@dataclass
class Sample:
    text: str
    label: int


@app.command()
def calibrate(
    persona_path: str = typer.Option(..., help="Path to persona YAML file."),
    dataset: str = typer.Option(..., help="Path to labeled dataset (JSONL with 'label' field: 0=fail, 1=pass)."),
    out: Optional[str] = typer.Option(None, help="Output path for calibration JSON (default: <persona>.traits.json)."),
    min_samples: int = typer.Option(25, help="Minimum labeled samples required."),
    learning_rate: float = typer.Option(0.1, help="Learning rate for gradient descent."),
    epochs: int = typer.Option(300, help="Training epochs."),
    l2: float = typer.Option(0.0, help="L2 regularization strength."),
) -> None:
    """Fit persona-specific logistic regression weights from labeled examples.

    The labeled dataset should be JSONL with fields:
    - text: assistant response text
    - label: 0 (off-brand) or 1 (on-brand)
    - persona_id: matching the persona being calibrated

    Output JSON contains:
    - weights.style / weights.traits / weights.lexicon: scalar blend weights
    - trait_model.bias: logistic intercept
    - trait_model.token_weights: per-token coefficients
    - trait_model.phrase_weights: placeholder for phrase-level overrides (empty by default)
    """

    persona_path_obj = Path(persona_path)
    dataset_path = Path(dataset)

    if not persona_path_obj.exists():
        raise typer.BadParameter(f"Persona file not found: {persona_path}")
    if not dataset_path.exists():
        raise typer.BadParameter(f"Dataset not found: {dataset}")

    persona_id = _load_persona_id(persona_path_obj)
    typer.echo(f"Persona id: {persona_id}")

    if not isinstance(l2, (int, float)):
        l2 = float(getattr(l2, "default", 0.0))

    samples, skipped = _load_samples(dataset_path, expected_persona=persona_id)
    if skipped:
        typer.echo(f"Skipped {skipped} samples with mismatched persona_id")
    if len(samples) < min_samples:
        raise typer.BadParameter(
            f"Insufficient labeled samples: {len(samples)} < {min_samples}. "
            f"Authenticity calibration requires at least {min_samples} labeled turns."
        )

    typer.echo(f"Loaded {len(samples)} labeled samples from {dataset}")

    vocabulary = _build_vocabulary(samples)
    typer.echo(f"Feature vocabulary size: {len(vocabulary)} tokens")

    bias, weights = _train_logistic(samples, vocabulary, learning_rate, epochs, l2)

    weights_out = {
        "style": 0.6,
        "traits": 0.25,
        "lexicon": 0.15,
    }

    trait_model = {
        "bias": bias,
        "token_weights": {token: coeff for token, coeff in weights.items() if coeff != 0.0},
        "phrase_weights": {},
    }

    payload = {
        "weights": weights_out,
        "trait_model": trait_model,
    }

    out_path = Path(out) if out else persona_path_obj.with_suffix(".traits.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    typer.secho("✓ Calibration complete", fg=typer.colors.GREEN)
    typer.echo(f"Bias: {bias:.4f}")
    typer.echo(f"Non-zero coefficients: {len(trait_model['token_weights'])}")
    typer.echo(f"Output: {out_path}")


def _load_persona_id(persona_path: Path) -> str:
    persona = load_yaml(persona_path) or {}
    if isinstance(persona, dict) and persona.get("id"):
        return str(persona["id"])
    raise typer.BadParameter(f"Persona file {persona_path} is missing required 'id' field")


def _load_samples(path: Path, expected_persona: str) -> Tuple[list[Sample], int]:
    samples: list[Sample] = []
    skipped = 0
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                typer.echo(f"Warning: invalid JSON on line {line_no}, skipping: {exc}")
                continue
            label = record.get("label")
            text = record.get("text")
            persona_id = record.get("persona_id")
            if persona_id and persona_id != expected_persona:
                skipped += 1
                continue
            if label in (0, 1) and isinstance(text, str) and text and persona_id == expected_persona:
                samples.append(Sample(text=text, label=int(label)))
            else:
                typer.echo(f"Warning: line {line_no} missing label/text, skipping")
    if not samples:
        raise typer.BadParameter(
            f"No labeled samples matched persona_id '{expected_persona}'. "
            "Ensure the dataset includes persona-specific labels."
        )
    return samples, skipped


def _build_vocabulary(samples: list[Sample]) -> dict[str, int]:
    vocab: dict[str, int] = {}
    for sample in samples:
        for token in _tokenize(sample.text):
            if token not in vocab:
                vocab[token] = len(vocab)
    return vocab


def _train_logistic(
    samples: list[Sample],
    vocab: dict[str, int],
    learning_rate: float,
    epochs: int,
    l2: float,
) -> tuple[float, dict[str, float]]:
    bias = 0.0
    weights = {token: 0.0 for token in vocab}

    for epoch in range(epochs):
        total_loss = 0.0
        for sample in samples:
            features = _token_set(sample.text)
            logits = bias + sum(weights[token] for token in features if token in weights)
            pred = 1 / (1 + math.exp(-logits))
            error = pred - sample.label
            total_loss += abs(error)

            grad_bias = error
            bias -= learning_rate * grad_bias

            for token in features:
                if token not in weights:
                    continue
                grad = error + l2 * weights[token]
                weights[token] -= learning_rate * grad

        if epoch % 50 == 0:
            typer.echo(f"Epoch {epoch:03d} | mean abs error {total_loss / len(samples):.4f}")

    return bias, weights


def _tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]


def _token_set(text: str) -> set[str]:
    return set(_tokenize(text))


if __name__ == "__main__":
    app()
