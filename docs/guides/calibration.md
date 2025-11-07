# Calibration Toolkit

The calibration toolkit optimizes persona scoring parameters (component weights, normalization bounds, trait models) using labeled data to improve scoring accuracy.

## Why Calibrate?

Without calibration, authenticity scores are compressed in the 0.5-0.7 range because:
- **Traits default to 0.5** (neutral) without training data
- **Normalization bounds are guesses** (may not match your embedding model)
- **Component weights are hardcoded** (may not be optimal for your persona)

With proper calibration, you get:
- **Better score separation**: on-brand > 0.75, off-brand < 0.40
- **Higher accuracy**: ROC-AUC > 0.75 (ideally > 0.85)
- **Persona-specific tuning**: weights tailored to your brand voice

## Quick Start

### 1. Generate Candidates for Labeling

Bootstrap unlabeled candidates from your existing dataset:

```bash
alignmenter calibrate generate \
  --dataset alignmenter/datasets/demo_conversations.jsonl \
  --persona alignmenter/configs/persona/default.yaml \
  --output calibration_data/unlabeled/candidates.jsonl \
  --num-samples 50 \
  --strategy diverse
```

**Strategies:**
- `diverse`: Sample across all scenario tags (recommended)
- `edge_cases`: Prioritize brand_trap, safety_trap
- `random`: Random sampling

### 2. Label the Data

Interactively label responses as on-brand (1) or off-brand (0):

```bash
alignmenter calibrate label \
  --input calibration_data/unlabeled/candidates.jsonl \
  --persona alignmenter/configs/persona/default.yaml \
  --output calibration_data/labeled/default_v1_labeled.jsonl \
  --labeler your_name
```

**Interactive Prompts:**
- Shows persona exemplars and lexicon for context
- Asks: "1 = On-brand, 0 = Off-brand, s = Skip, q = Quit"
- Optionally records confidence (high/medium/low) and notes
- Saves progress after each label (safe to interrupt)

**Labeling Guidelines:**
- **On-brand (1)**: Uses preferred vocabulary, matches exemplar style/tone
- **Off-brand (0)**: Uses avoided words, wrong tone, generic/bland
- **Borderline**: Mark confidence="low" and add notes

**Minimum:** 50 examples (25 on-brand, 25 off-brand)
**Recommended:** 100-200 examples for robust calibration

### 3. Estimate Normalization Bounds

Compute empirical min/max for style similarity:

```bash
alignmenter calibrate bounds \
  --labeled calibration_data/labeled/default_v1_labeled.jsonl \
  --persona alignmenter/configs/persona/default.yaml \
  --output calibration_data/reports/bounds_report.json
```

**Output:**
```json
{
  "style_sim_min": 0.08,
  "style_sim_max": 0.28,
  "style_sim_mean": 0.18,
  "on_brand_style": {"mean": 0.22, ...},
  "off_brand_style": {"mean": 0.14, ...}
}
```

### 4. Optimize Component Weights

Grid search to find best weights (style, traits, lexicon):

```bash
alignmenter calibrate optimize \
  --labeled calibration_data/labeled/default_v1_labeled.jsonl \
  --persona alignmenter/configs/persona/default.yaml \
  --bounds calibration_data/reports/bounds_report.json \
  --output calibration_data/reports/weights_report.json \
  --grid-step 0.1
```

**Output:**
```json
{
  "best_weights": {
    "style": 0.5,
    "traits": 0.3,
    "lexicon": 0.2
  },
  "metrics": {
    "roc_auc": 0.87,
    "f1": 0.82,
    "correlation": 0.78
  },
  "confusion_matrix": {...}
}
```

**Grid step:** 0.1 evaluates ~66 combinations (faster), 0.05 evaluates ~231 (more thorough)

### 5. Train Trait Model

Use existing script to train logistic regression on token features:

```bash
python -m alignmenter.scripts.calibrate_persona \
  --persona-path alignmenter/configs/persona/default.yaml \
  --dataset calibration_data/labeled/default_v1_labeled.jsonl \
  --out alignmenter/configs/persona/default.traits.json
```

### 6. Merge Calibration Results

Manually merge bounds + weights into the trait model file:

```bash
# Edit alignmenter/configs/persona/default.traits.json
{
  "weights": {
    "style": 0.5,
    "traits": 0.3,
    "lexicon": 0.2
  },
  "trait_model": {
    "bias": -0.123,
    "token_weights": {...},
    "phrase_weights": {}
  },
  "style_sim_min": 0.08,
  "style_sim_max": 0.28
}
```

**TODO:** Automate this merge step

### 7. Validate Calibration

Test calibration quality on held-out validation set:

```bash
alignmenter calibrate validate \
  --labeled calibration_data/labeled/default_v1_labeled.jsonl \
  --persona alignmenter/configs/persona/default.yaml \
  --output calibration_data/reports/diagnostics.json \
  --train-split 0.8
```

**Output:**
```json
{
  "validation_metrics": {
    "roc_auc": 0.85,
    "f1": 0.80,
    "optimal_threshold": 0.52
  },
  "score_distributions": {
    "on_brand": {"mean": 0.78, "std": 0.12},
    "off_brand": {"mean": 0.32, "std": 0.15}
  },
  "error_analysis": {
    "false_positives": [...],
    "false_negatives": [...]
  }
}
```

### 8. Re-run Evaluation

Use the calibrated persona:

```bash
alignmenter run --config alignmenter/configs/run.yaml
```

The scorer will automatically load `default.traits.json` if it exists.

---

## Directory Structure

```
calibration_data/
├── unlabeled/
│   └── candidates.jsonl          # Generated candidates for labeling
├── labeled/
│   └── default_v1_labeled.jsonl  # Your labeled data
└── reports/
    ├── bounds_report.json        # Normalization bounds
    ├── weights_report.json       # Optimized component weights
    └── diagnostics.json          # Validation metrics
```

**Note:** `calibration_data/` is gitignored to protect proprietary labeled data

---

## CLI Reference

### `alignmenter calibrate generate`

Generate candidate responses for labeling.

**Options:**
- `--dataset PATH`: Input JSONL dataset (required)
- `--persona PATH`: Persona YAML (required)
- `--output PATH`: Output unlabeled candidates (required)
- `--num-samples INT`: Number of candidates (default: 50)
- `--strategy STR`: diverse | random | edge_cases (default: diverse)
- `--seed INT`: Random seed (default: 42)

### `alignmenter calibrate label`

Interactively label responses.

**Options:**
- `--input PATH`: Unlabeled candidates JSONL (required)
- `--persona PATH`: Persona YAML (required)
- `--output PATH`: Output labeled JSONL (required)
- `--append`: Append to existing labeled data
- `--labeler STR`: Name of person labeling

### `alignmenter calibrate bounds`

Estimate normalization bounds from labeled data.

**Options:**
- `--labeled PATH`: Labeled JSONL (required)
- `--persona PATH`: Persona YAML (required)
- `--output PATH`: Output bounds report JSON (required)
- `--embedding STR`: Embedding provider
- `--percentile-low FLOAT`: Lower percentile (default: 5.0)
- `--percentile-high FLOAT`: Upper percentile (default: 95.0)

### `alignmenter calibrate optimize`

Optimize component weights via grid search.

**Options:**
- `--labeled PATH`: Labeled JSONL (required)
- `--persona PATH`: Persona YAML (required)
- `--output PATH`: Output weights report JSON (required)
- `--bounds PATH`: Bounds report JSON (optional but recommended)
- `--embedding STR`: Embedding provider
- `--grid-step FLOAT`: Grid step size (default: 0.1)

### `alignmenter calibrate validate`

Validate calibration quality.

**Options:**
- `--labeled PATH`: Labeled JSONL (required)
- `--persona PATH`: Persona YAML with .traits.json (required)
- `--output PATH`: Output diagnostics JSON (required)
- `--embedding STR`: Embedding provider
- `--train-split FLOAT`: Train fraction (default: 0.8)
- `--seed INT`: Random seed (default: 42)

---

## Best Practices

### Data Collection

1. **Stratify by scenario**: Ensure all scenario tags are represented
2. **Include edge cases**: brand_trap and safety_trap are valuable
3. **Balance classes**: Aim for 50/50 on-brand vs off-brand
4. **Quality over quantity**: 50 high-quality labels > 200 rushed ones

### Labeling

1. **Be consistent**: Use exemplars as your north star
2. **Trust your judgment**: If it feels off-brand, it probably is
3. **Mark uncertainty**: Use confidence="low" for borderline cases
4. **Take breaks**: Labeling fatigue leads to inconsistency

### Calibration

1. **Start simple**: Get 50 labels, calibrate, evaluate
2. **Iterate**: Add more labels in areas of confusion
3. **Validate regularly**: Use held-out validation set
4. **Version control**: Keep dated snapshots of calibration files

### Deployment

1. **Test before production**: Run on full dataset, inspect score distributions
2. **Monitor drift**: Re-calibrate if persona evolves
3. **Document changes**: Note what changed between calibration versions

---

## Troubleshooting

### "ROC-AUC is low (< 0.7)"

**Causes:**
- Too few labeled examples
- Inconsistent labeling
- Persona lexicon doesn't match actual brand voice

**Solutions:**
- Add more labeled data (aim for 100+)
- Re-label with stricter guidelines
- Update persona exemplars and lexicon

### "Scores still compressed after calibration"

**Causes:**
- Trait model not trained (still using heuristic)
- Bounds are wrong (check bounds_report.json)

**Solutions:**
- Run `calibrate_persona.py` to train trait model
- Verify bounds match your embedding model's actual range

### "False positives (off-brand scored high)"

**Causes:**
- Lexicon weight too high
- Missing avoided words in persona

**Solutions:**
- Reduce lexicon weight, increase style/traits
- Add more avoided words to persona YAML

### "False negatives (on-brand scored low)"

**Causes:**
- Style weight too high, bounds too narrow
- Not enough exemplars

**Solutions:**
- Widen normalization bounds (lower percentile_low, raise percentile_high)
- Add more diverse exemplars to persona

---

## Advanced Topics

### Scenario-Specific Calibration

To calibrate per-scenario (future):

```bash
# Filter labeled data by scenario tag
jq -c 'select(.scenario_tags | contains(["scenario:support"]))' \
  calibration_data/labeled/default_v1_labeled.jsonl \
  > calibration_data/labeled/support_only.jsonl

# Calibrate for support scenario
alignmenter calibrate optimize \
  --labeled calibration_data/labeled/support_only.jsonl \
  --persona alignmenter/configs/persona/default.yaml \
  --output calibration_data/reports/weights_support.json
```

### Active Learning

Identify uncertain examples for labeling (future):

```python
# Score unlabeled pool with current calibration
# Select examples where score is close to threshold (e.g., 0.45-0.55)
# Prioritize these for manual labeling
```

### Bayesian Optimization

For finer-grained weight search (future):

```python
import optuna

def objective(trial):
    style_w = trial.suggest_float("style", 0.0, 1.0)
    traits_w = trial.suggest_float("traits", 0.0, 1.0 - style_w)
    lexicon_w = 1.0 - style_w - traits_w
    # ... evaluate ROC-AUC with these weights
    return auc

study = optuna.create_study(direction="maximize")
study.optimize(objective, n_trials=100)
```

---

## Calibration File Format

**`{persona}.traits.json`**

```json
{
  "weights": {
    "style": 0.5,
    "traits": 0.3,
    "lexicon": 0.2
  },
  "trait_model": {
    "bias": -0.123,
    "token_weights": {
      "absolutely": 1.2,
      "configure": 0.8,
      "lol": -2.5,
      "bro": -2.0
    },
    "phrase_weights": {
      "let me know": 0.5
    }
  },
  "style_sim_min": 0.08,
  "style_sim_max": 0.28
}
```

**Fields:**
- `weights`: Component weights (must sum to 1.0)
- `trait_model.bias`: Logistic regression bias term
- `trait_model.token_weights`: Per-token coefficients
- `trait_model.phrase_weights`: Per-phrase coefficients (optional)
- `style_sim_min/max`: Normalization bounds for style similarity

---

## Contributing

Ideas for improving the calibration toolkit:

- [ ] Automate merge of bounds + weights into .traits.json
- [ ] Add `alignmenter calibrate all` to run full pipeline
- [ ] Generate HTML diagnostics report with charts
- [ ] Support cross-validation (k-fold)
- [ ] Add active learning recommendations
- [ ] Bayesian optimization integration
- [ ] Scenario-specific calibration helpers

See `docs/calibration_requirements.md` for full design docs.
