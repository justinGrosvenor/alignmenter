"""Honest cross-validation for the Wendy's persona authenticity scorer.

The published `calibrated_diagnostics.json` scores the validation split with a
trait model that was fit on the *full* dataset (including the validation rows),
so its ROC-AUC 1.000 reflects in-sample fit, not generalization. This script
does a clean stratified k-fold cross-validation: for every fold the trait model
is refit on the training rows only, and the held-out rows are scored with that
fold-specific model. Style-similarity and lexicon components come from the
persona definition (not trained on labels), so only the trait model needs
refitting to remove leakage.

ROC-AUC is rank-based and the score's min/max rescaling is monotonic, so the
normalization bounds do not affect AUC and are left at their calibrated values.

Requires the [ml] and [calibrate] extras:  pip install "alignmenter[all]"
Run from this directory:  python cross_validate.py
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold

from alignmenter.scorers.authenticity import AuthenticityScorer
from alignmenter.scripts.calibrate_persona import (
    Sample,
    _build_vocabulary,
    _train_logistic,
)

HERE = Path(__file__).resolve().parent
PERSONA = HERE / "wendys_twitter.yaml"
DATASET = HERE / "wendys_dataset.jsonl"
TRAITS = HERE / "wendys_twitter.traits.json"
PERSONA_ID = "wendys_twitter"
EMBEDDING = "sentence-transformer:all-MiniLM-L6-v2"
N_SPLITS = 5
SEED = 42


def load_labeled() -> list[dict]:
    rows = []
    with DATASET.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("label") in (0, 1) and row.get("persona_id") == PERSONA_ID and row.get("text"):
                rows.append(row)
    return rows


def fold_traits(train_rows: list[dict]) -> dict:
    """Refit the trait model on the training rows only (no leakage)."""
    samples = [Sample(text=r["text"], label=int(r["label"])) for r in train_rows]
    vocab = _build_vocabulary(samples)
    # Quiet the training echo used by the CLI variant.
    import alignmenter.scripts.calibrate_persona as cp

    cp.typer.echo = lambda *a, **k: None  # type: ignore[assignment]
    bias, weights = _train_logistic(samples, vocab, learning_rate=0.1, epochs=250, l2=0.0)

    base = json.loads(TRAITS.read_text())
    return {
        "weights": base["weights"],
        "style_sim_min": base.get("style_sim_min"),
        "style_sim_max": base.get("style_sim_max"),
        "trait_model": {
            "bias": bias,
            "token_weights": {t: c for t, c in weights.items() if c != 0.0},
            "phrase_weights": {},
        },
    }


def score_rows(persona_dir: Path, rows: list[dict]) -> list[float]:
    scorer = AuthenticityScorer(persona_dir / PERSONA.name, embedding=EMBEDDING)
    scores = []
    for row in rows:
        session = [{"session_id": "cv", "turns": [{"role": "assistant", "text": row["text"]}]}]
        scores.append(scorer.score(session)["mean"])
    return scores


def main() -> None:
    rows = load_labeled()
    labels = np.array([r["label"] for r in rows])
    print(f"Loaded {len(rows)} labeled rows ({labels.sum()} on-brand / {(labels == 0).sum()} off-brand)")

    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    fold_aucs, fold_f1s = [], []
    oof_scores = np.zeros(len(rows))
    oof_labels = labels.copy()

    for i, (train_idx, test_idx) in enumerate(skf.split(rows, labels), start=1):
        train_rows = [rows[j] for j in train_idx]
        test_rows = [rows[j] for j in test_idx]
        traits = fold_traits(train_rows)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            shutil.copy(PERSONA, tmp_dir / PERSONA.name)
            (tmp_dir / PERSONA.with_suffix(".traits.json").name).write_text(json.dumps(traits))
            test_scores = score_rows(tmp_dir, test_rows)

        y_true = labels[test_idx]
        oof_scores[test_idx] = test_scores
        auc = roc_auc_score(y_true, test_scores)
        preds = [1 if s >= 0.5 else 0 for s in test_scores]
        f1 = f1_score(y_true, preds)
        fold_aucs.append(auc)
        fold_f1s.append(f1)
        print(f"  fold {i}: n={len(test_rows):2d}  ROC-AUC={auc:.3f}  F1@0.5={f1:.3f}")

    pooled_auc = roc_auc_score(oof_labels, oof_scores)
    result = {
        "method": f"stratified {N_SPLITS}-fold CV, trait model refit per fold",
        "n": len(rows),
        "n_positive": int(labels.sum()),
        "embedding": EMBEDDING,
        "per_fold_roc_auc": [round(a, 3) for a in fold_aucs],
        "per_fold_f1": [round(f, 3) for f in fold_f1s],
        "mean_roc_auc": round(float(np.mean(fold_aucs)), 3),
        "std_roc_auc": round(float(np.std(fold_aucs)), 3),
        "mean_f1": round(float(np.mean(fold_f1s)), 3),
        "pooled_out_of_fold_roc_auc": round(float(pooled_auc), 3),
        "seed": SEED,
    }
    out = HERE / "cross_validation_results.json"
    out.write_text(json.dumps(result, indent=2))
    print(
        f"\nCV ROC-AUC: {result['mean_roc_auc']} ± {result['std_roc_auc']}  "
        f"| pooled OOF ROC-AUC: {result['pooled_out_of_fold_roc_auc']}  "
        f"| mean F1@0.5: {result['mean_f1']}"
    )
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
