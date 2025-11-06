# Calibration System Requirements

**Version:** 0.1
**Status:** Draft
**Last Updated:** 2025-11-05

---

## Executive Summary

Design a calibration system to optimize persona scoring parameters (component weights, normalization bounds, trait models) using labeled data. The system should provide immediate value with simple statistical methods while being architected for future ML enhancements.

**Key Principle:** Start simple, build incrementally, maintain scientific rigor.

---

## 1. Current State Analysis

### What Works
- ✅ **Trait model calibration exists** (`calibrate_persona.py`)
  - Trains logistic regression on labeled examples
  - Learns token-level weights via gradient descent
  - Outputs `{persona}.traits.json`

- ✅ **Global normalization bounds implemented**
  - Style similarity: `style_sim_min/max` (default: 0.05-0.25)
  - Stability variance: `variance_min/max` (default: 0.01-0.50)
  - Supports calibration file override

- ✅ **Component scoring is modular**
  - Authenticity: `style + traits + lexicon`
  - Safety: `rules + judge + classifier`
  - Stability: `1.0 - normalized_variance`

### What's Missing
- ❌ **Component weight optimization** - Currently hardcoded (0.3/0.3/0.4)
- ❌ **Normalization bound estimation** - Using educated guesses
- ❌ **Scenario-specific calibration** - All scenarios use same weights
- ❌ **Calibration data generation** - Manual process, no tooling
- ❌ **Calibration diagnostics** - No metrics to assess calibration quality
- ❌ **Validation framework** - No held-out test sets or cross-validation

### Core Problem
**Without proper calibration, traits default to 0.5 (neutral), compressing scores into 0.5-0.7 range and making it hard to distinguish good from mediocre responses.**

---

## 2. Goals & Non-Goals

### Goals

#### Phase 1: Foundation (Now)
1. **Generate calibration datasets**
   - Bootstrap from existing demo data
   - Support manual labeling workflow
   - Validate data quality

2. **Estimate normalization bounds**
   - Compute empirical min/max for style similarity
   - Compute empirical min/max for stability variance
   - Store in calibration file

3. **Optimize component weights**
   - Grid search or simple optimization
   - Maximize correlation with human labels
   - Output optimized weights to calibration file

4. **Provide calibration diagnostics**
   - Show component distributions
   - Correlation analysis (component vs label)
   - Confusion matrix / ROC curves

#### Phase 2: ML-Ready Architecture (Later)
5. **Support advanced optimization**
   - Bayesian optimization
   - Cross-validation
   - Hyperparameter tuning

6. **Enable ensemble methods**
   - Combine multiple trait models
   - Learn non-linear weight combinations
   - Scenario-specific models

7. **Add active learning**
   - Identify uncertain examples for labeling
   - Prioritize high-value samples

### Non-Goals
- ❌ Not building a full ML platform (use existing tools: scikit-learn, optuna)
- ❌ Not replacing existing `calibrate_persona.py` (extend it)
- ❌ Not packaging calibration tools with Alignmenter (keep in `/calibration` directory)
- ❌ Not requiring cloud infrastructure (run locally)

---

## 3. Architecture

### Directory Structure

```
/Users/justingrosvenor/alignmenter/
├── alignmenter/                     # Main package (shipped)
│   ├── src/alignmenter/
│   │   ├── scorers/
│   │   └── scripts/
│   │       └── calibrate_persona.py  # Existing trait model trainer
│   ├── configs/
│   │   └── persona/
│   │       ├── default.yaml
│   │       └── default.traits.json   # Calibration output
│   └── datasets/
│       └── demo_conversations.jsonl
│
├── calibration/                     # Calibration toolkit (NOT shipped)
│   ├── calibration-requirements.md  # This document
│   ├── README.md                    # User guide
│   ├── data/                        # Calibration datasets
│   │   ├── labeled/
│   │   │   ├── default_v1_labeled.jsonl
│   │   │   └── validation_split.jsonl
│   │   ├── unlabeled/
│   │   │   └── candidates_for_labeling.jsonl
│   │   └── metadata/
│   │       └── labeling_guidelines.md
│   ├── scripts/
│   │   ├── generate_candidates.py    # Bootstrap from demo data
│   │   ├── label_data.py             # Interactive labeling tool
│   │   ├── estimate_bounds.py        # Compute normalization bounds
│   │   ├── optimize_weights.py       # Grid search for component weights
│   │   └── validate_calibration.py   # Test calibration quality
│   ├── notebooks/
│   │   ├── 01_explore_scores.ipynb   # EDA on score distributions
│   │   ├── 02_calibration_demo.ipynb # End-to-end walkthrough
│   │   └── 03_diagnostics.ipynb      # Calibration quality metrics
│   └── reports/
│       └── calibration_{persona}_{timestamp}/
│           ├── bounds_report.json
│           ├── weights_report.json
│           ├── diagnostics.html
│           └── figures/
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. DATA GENERATION                                              │
│                                                                 │
│  demo_conversations.jsonl                                       │
│         │                                                       │
│         ├─> generate_candidates.py                             │
│         │   • Sample diverse responses                         │
│         │   • Include edge cases (brand_trap, safety_trap)     │
│         │   • Output: unlabeled/candidates.jsonl               │
│         │                                                       │
│         └─> label_data.py (interactive)                        │
│             • Show response + persona context                  │
│             • Ask: "On-brand (1) or off-brand (0)?"            │
│             • Output: labeled/default_v1_labeled.jsonl         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 2. BOUND ESTIMATION                                             │
│                                                                 │
│  labeled/default_v1_labeled.jsonl                               │
│         │                                                       │
│         └─> estimate_bounds.py                                 │
│             • Compute raw style_sim for all examples           │
│             • Compute percentiles (5th, 95th)                  │
│             • Compute stability variance (if multi-turn)       │
│             • Output: bounds_report.json                       │
│                                                                 │
│  bounds_report.json                                             │
│    {                                                            │
│      "style_sim_min": 0.08,  # 5th percentile                  │
│      "style_sim_max": 0.28,  # 95th percentile                 │
│      "variance_min": 0.015,                                    │
│      "variance_max": 0.45                                      │
│    }                                                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 3. WEIGHT OPTIMIZATION                                          │
│                                                                 │
│  labeled/default_v1_labeled.jsonl + bounds_report.json          │
│         │                                                       │
│         └─> optimize_weights.py                                │
│             • Score each example with different weight combos  │
│             • Try grid: style ∈ [0.1, 0.3, 0.5, 0.7, 0.9]      │
│             •           traits ∈ [0.1, 0.3, 0.5, 0.7, 0.9]     │
│             •           lexicon ∈ [0.1, 0.3, 0.5, 0.7, 0.9]    │
│             •           (constrained to sum=1.0)               │
│             • Evaluate: ROC-AUC, F1, correlation with labels   │
│             • Select best weights                              │
│             • Output: weights_report.json                      │
│                                                                 │
│  weights_report.json                                            │
│    {                                                            │
│      "best_weights": {                                         │
│        "style": 0.5,                                           │
│        "traits": 0.3,                                          │
│        "lexicon": 0.2                                          │
│      },                                                         │
│      "metrics": {                                              │
│        "roc_auc": 0.87,                                        │
│        "f1": 0.82,                                             │
│        "correlation": 0.78                                     │
│      }                                                          │
│    }                                                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 4. TRAIT MODEL TRAINING                                         │
│                                                                 │
│  labeled/default_v1_labeled.jsonl                               │
│         │                                                       │
│         └─> calibrate_persona.py (existing)                    │
│             • Train logistic regression                        │
│             • Learn token weights                              │
│             • Output: trait_model (bias + token_weights)       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 5. INTEGRATION                                                  │
│                                                                 │
│  bounds_report.json + weights_report.json + trait_model        │
│         │                                                       │
│         └─> Merge into configs/persona/default.traits.json     │
│             {                                                   │
│               "weights": {...},                                 │
│               "trait_model": {...},                             │
│               "style_sim_min": 0.08,                            │
│               "style_sim_max": 0.28                             │
│             }                                                   │
│                                                                 │
│  alignmenter run --config configs/run.yaml                      │
│         │                                                       │
│         └─> Uses calibrated parameters automatically           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 6. VALIDATION                                                   │
│                                                                 │
│  labeled/validation_split.jsonl (held-out 20%)                  │
│         │                                                       │
│         └─> validate_calibration.py                            │
│             • Score with calibrated parameters                 │
│             • Compute metrics on held-out set                  │
│             • Generate diagnostics report                      │
│             • Output: diagnostics.html + figures/              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Requirements

### Labeled Data Format

**File:** `calibration/data/labeled/{persona_id}_labeled.jsonl`

**Schema:**
```json
{
  "text": "Absolutely. Alignmenter scores authenticity, safety, and stability...",
  "label": 1,
  "persona_id": "default_v1",
  "session_id": "session-01",
  "turn_index": 2,
  "scenario_tags": ["scenario:product_inquiry"],
  "labeler": "justin",
  "timestamp": "2025-11-05T10:30:00Z",
  "confidence": "high",
  "notes": ""
}
```

**Fields:**
- `text` (required): Assistant response text
- `label` (required): 0 = off-brand, 1 = on-brand
- `persona_id` (required): Which persona this is labeled for
- `session_id` (optional): Original session ID
- `turn_index` (optional): Original turn index
- `scenario_tags` (optional): Scenario tags for stratified sampling
- `labeler` (optional): Who labeled this
- `timestamp` (optional): When it was labeled
- `confidence` (optional): "high" | "medium" | "low"
- `notes` (optional): Free-text notes

### Labeling Guidelines

**On-Brand (label=1):**
- Uses preferred vocabulary from persona lexicon
- Matches exemplar style and tone
- Professional, helpful, technically precise
- No avoided words (lol, bro, etc.)

**Off-Brand (label=0):**
- Uses avoided vocabulary
- Overly casual or hyped language
- Generic/robotic responses
- Mismatched formality level

**Edge Cases:**
- Technically correct but bland → label=0 (not distinctive)
- Has 1-2 brand words but wrong tone → label=0 (holistic judgment)
- Borderline cases → confidence="low", include notes

### Sample Size Requirements

**Minimum for statistical validity:**
- 50 labeled examples (25 on-brand, 25 off-brand)
- 80/20 train/validation split

**Recommended for robust calibration:**
- 100-200 labeled examples
- Stratified by scenario (ensure all scenarios represented)
- Include edge cases (brand_trap, safety_trap)

**For ML methods (Phase 2):**
- 500+ labeled examples
- 5-fold cross-validation
- Active learning to expand dataset

---

## 5. Calibration Methods

### 5.1 Normalization Bound Estimation

**Method:** Empirical percentiles

**Algorithm:**
```python
def estimate_bounds(labeled_data, persona, embedder):
    """
    Compute empirical normalization bounds from labeled data.

    Uses 5th and 95th percentiles to be robust to outliers.
    """
    # Compute raw style similarity for all examples
    raw_style_scores = []
    for example in labeled_data:
        embedding = embedder.embed([example["text"]])[0]
        style_sim = max(cosine_similarity(embedding, ex)
                       for ex in persona.exemplars)
        raw_style_scores.append(style_sim)

    # Use percentiles instead of min/max (robust to outliers)
    style_sim_min = np.percentile(raw_style_scores, 5)
    style_sim_max = np.percentile(raw_style_scores, 95)

    return {
        "style_sim_min": style_sim_min,
        "style_sim_max": style_sim_max,
        "style_sim_mean": np.mean(raw_style_scores),
        "style_sim_std": np.std(raw_style_scores)
    }
```

**Output:** `bounds_report.json`

**Future Enhancement (ML):**
- Learn separate bounds for on-brand vs off-brand
- Use quantile regression
- Account for scenario-specific distributions

---

### 5.2 Component Weight Optimization

**Method:** Grid search with cross-validation

**Objective:** Maximize discriminative power (ROC-AUC or F1)

**Algorithm:**
```python
def optimize_weights(labeled_data, persona, embedder):
    """
    Grid search over component weight combinations.

    Constraint: weights must sum to 1.0
    """
    best_auc = 0
    best_weights = None

    # Grid search
    for style_w in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        for traits_w in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
            lexicon_w = 1.0 - style_w - traits_w
            if lexicon_w < 0.1 or lexicon_w > 0.9:
                continue

            # Score all examples with these weights
            scores = []
            labels = []
            for example in labeled_data:
                score = compute_authenticity(
                    example["text"],
                    persona,
                    embedder,
                    weights={"style": style_w, "traits": traits_w, "lexicon": lexicon_w}
                )
                scores.append(score)
                labels.append(example["label"])

            # Compute ROC-AUC
            auc = roc_auc_score(labels, scores)

            if auc > best_auc:
                best_auc = auc
                best_weights = {"style": style_w, "traits": traits_w, "lexicon": lexicon_w}

    return best_weights, best_auc
```

**Metrics:**
- **ROC-AUC**: Area under ROC curve (higher = better discrimination)
- **F1 Score**: Harmonic mean of precision/recall (at threshold=0.5)
- **Pearson Correlation**: Linear correlation between scores and labels

**Output:** `weights_report.json`

**Future Enhancement (ML):**
- Use Bayesian optimization (optuna, hyperopt)
- Learn non-linear weight functions
- Multi-objective optimization (balance accuracy + interpretability)

---

### 5.3 Trait Model Training

**Method:** Logistic regression with L2 regularization (existing)

**Already implemented in:** `alignmenter/scripts/calibrate_persona.py`

**Enhancement needed:**
- Integrate with bound estimation + weight optimization
- Support phrase-level features (bigrams, trigrams)
- Add feature selection (drop low-weight tokens)

---

### 5.4 Validation & Diagnostics

**Metrics to track:**

1. **Held-out performance**
   - ROC-AUC on validation set
   - F1 score at different thresholds
   - Confusion matrix

2. **Component analysis**
   - Distribution of style_sim, traits, lexicon scores
   - Correlation between components
   - Feature importance (which words drive trait scores)

3. **Calibration quality**
   - Reliability diagram (predicted prob vs actual)
   - Brier score (calibration error)

4. **Error analysis**
   - False positives (off-brand scored high)
   - False negatives (on-brand scored low)
   - Edge cases

**Output:** `diagnostics.html` with interactive charts

---

## 6. Implementation Plan

### Phase 1: Foundation (1-2 weeks)

**Week 1: Data + Bounds**
- [ ] Create `/calibration` directory structure
- [ ] Write `generate_candidates.py` (bootstrap from demo data)
- [ ] Write `label_data.py` (interactive CLI labeling tool)
- [ ] Label 50-100 examples for `default_v1` persona
- [ ] Write `estimate_bounds.py`
- [ ] Generate `bounds_report.json`

**Week 2: Weights + Integration**
- [ ] Write `optimize_weights.py`
- [ ] Generate `weights_report.json`
- [ ] Integrate bounds + weights into `default.traits.json`
- [ ] Re-run evaluation on demo dataset
- [ ] Compare before/after calibration scores

### Phase 2: Validation + Tooling (1 week)

- [ ] Write `validate_calibration.py`
- [ ] Create Jupyter notebooks for EDA and diagnostics
- [ ] Generate HTML diagnostics report
- [ ] Document calibration workflow in `calibration/README.md`

### Phase 3: ML Enhancements (Future)

- [ ] Bayesian optimization for weights
- [ ] Cross-validation framework
- [ ] Active learning for data collection
- [ ] Scenario-specific calibration
- [ ] Ensemble methods

---

## 7. Success Metrics

### Immediate Goals
- ✅ Generate 50+ labeled examples for `default_v1`
- ✅ Compute empirical normalization bounds
- ✅ Optimize component weights
- ✅ Achieve ROC-AUC > 0.75 on held-out validation set
- ✅ Increase score separation: on-brand mean > 0.75, off-brand mean < 0.40

### Long-Term Goals
- 🎯 ROC-AUC > 0.85 with ML-optimized weights
- 🎯 Support 5+ personas with calibration
- 🎯 Automated calibration pipeline (CI/CD integration)
- 🎯 Active learning reduces labeling effort by 50%

---

## 8. Open Questions

1. **Should we calibrate per-scenario?**
   - Pro: More accurate for specific use cases
   - Con: Requires more labeled data per scenario
   - Decision: Start global, add scenario-specific later

2. **How to handle multi-turn sessions?**
   - Option A: Label entire sessions (holistic judgment)
   - Option B: Label individual turns (more granular)
   - Decision: Start with individual turns, aggregate later

3. **What threshold should we use for binary classification?**
   - Option A: Fixed threshold (e.g., 0.5)
   - Option B: Learn threshold from labeled data
   - Decision: Learn optimal threshold via ROC curve

4. **Should we version calibration files?**
   - Pro: Track calibration improvements over time
   - Con: More file management complexity
   - Decision: Include timestamp in calibration file, keep history

---

## 9. Dependencies

**Required:**
- `numpy`, `scipy` (for statistics)
- `scikit-learn` (for metrics, validation)
- `matplotlib`, `seaborn` (for visualization)
- `pandas` (for data manipulation)
- `jupyter` (for notebooks)

**Optional (Phase 2):**
- `optuna` (Bayesian optimization)
- `shap` (feature importance)
- `plotly` (interactive charts)

---

## 10. Next Steps

1. **Review this requirements doc** - Iterate on design
2. **Create `/calibration` directory structure**
3. **Start with data generation** - Write `generate_candidates.py`
4. **Label initial dataset** - 50 examples for `default_v1`
5. **Implement bound estimation** - Prove the concept
6. **Iterate based on results**

---

## Appendix: Example Workflows

### Workflow A: First-Time Calibration

```bash
# 1. Generate candidate responses for labeling
python calibration/scripts/generate_candidates.py \
  --input alignmenter/datasets/demo_conversations.jsonl \
  --persona configs/persona/default.yaml \
  --output calibration/data/unlabeled/candidates.jsonl \
  --strategy diverse  # sample diverse scenarios

# 2. Label examples interactively
python calibration/scripts/label_data.py \
  --input calibration/data/unlabeled/candidates.jsonl \
  --persona configs/persona/default.yaml \
  --output calibration/data/labeled/default_v1_labeled.jsonl

# 3. Estimate normalization bounds
python calibration/scripts/estimate_bounds.py \
  --labeled calibration/data/labeled/default_v1_labeled.jsonl \
  --persona configs/persona/default.yaml \
  --output calibration/reports/bounds_report.json

# 4. Optimize component weights
python calibration/scripts/optimize_weights.py \
  --labeled calibration/data/labeled/default_v1_labeled.jsonl \
  --persona configs/persona/default.yaml \
  --bounds calibration/reports/bounds_report.json \
  --output calibration/reports/weights_report.json

# 5. Train trait model (existing script)
python -m alignmenter.scripts.calibrate_persona \
  --persona-path configs/persona/default.yaml \
  --dataset calibration/data/labeled/default_v1_labeled.jsonl \
  --out configs/persona/default.traits.json

# 6. Merge calibration results (manual for now)
# Combine bounds_report.json + weights_report.json into default.traits.json

# 7. Validate calibration
python calibration/scripts/validate_calibration.py \
  --labeled calibration/data/labeled/default_v1_labeled.jsonl \
  --persona configs/persona/default.yaml \
  --output calibration/reports/diagnostics.html

# 8. Re-run evaluation
alignmenter run --config configs/run.yaml
```

### Workflow B: Incremental Calibration Update

```bash
# 1. Add more labeled examples
python calibration/scripts/label_data.py \
  --input calibration/data/unlabeled/new_candidates.jsonl \
  --persona configs/persona/default.yaml \
  --output calibration/data/labeled/default_v1_labeled.jsonl \
  --append  # add to existing labeled data

# 2. Re-run calibration
python calibration/scripts/optimize_weights.py \
  --labeled calibration/data/labeled/default_v1_labeled.jsonl \
  --persona configs/persona/default.yaml \
  --output calibration/reports/weights_report_v2.json

# 3. Compare v1 vs v2 calibration
python calibration/scripts/compare_calibrations.py \
  --baseline calibration/reports/weights_report.json \
  --new calibration/reports/weights_report_v2.json
```

---

**END OF REQUIREMENTS DOCUMENT**

*This is a living document. Update as we learn from implementation.*
