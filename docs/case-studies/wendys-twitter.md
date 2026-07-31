# Wendy's Twitter Voice Case Study

This case study reproduces a full calibration workflow for Wendy's Twitter persona and shows, candidly, how far the deterministic authenticity scorer can and cannot be trusted after calibration. Follow the steps below to reproduce every artifact end to end. Read the caveats box before citing any number.

> **What the numbers actually say (leakage-free cross-validation, the credible ones)**
>
> Stratified 5-fold CV with the trait model **refit on each fold's training rows only** (`cross_validate.py` → `cross_validation_results.json`):
>
> **Cross-validated ROC-AUC: 0.949 ± 0.010** (per-fold 0.938 / 0.962 / 0.945 / 0.959 / 0.939; pooled out-of-fold 0.954; mean F1 @ 0.5 = 0.874).
>
> That is a genuine generalization estimate — a large, real gain over the uncalibrated baseline (ROC-AUC 0.733 / F1 0.594), and clearly short of the misleading "perfect" number below. This is the figure to cite.
>
> Corroborating same-author held-out scenario suites (72 turns, `holdout_evaluation_results.json`):
>
> | Holdout suite | n | ROC-AUC | Accuracy | Recall | F1 |
> | --- | --- | --- | --- | --- | --- |
> | Trend | 16 | 1.00 | 1.00 | 1.00 | 1.00 |
> | Crisis | 16 | 1.00 | 0.938 | 1.00 | 0.941 |
> | Mixed | 20 | 1.00 | 1.00 | 1.00 | 1.00 |
> | **Edge cases** | 20 | **0.86** | **0.75** | **0.50** | 0.667 |
>
> **The in-sample ROC-AUC 1.000 that older versions of this doc led with is train=test** (all 136 rows fit and scored together). It shows the classes are separable given the features — it is **not** a generalization estimate and should not be cited as performance.
>
> **Three caveats before you trust this:**
> - The calibrated trait model's top features are largely **function words** (`just`, `it`, `our`, `for`, `we're`, `you`). It partly keys on the register gap between deliberately-corporate off-brand examples and casual on-brand ones — a dataset-construction artifact, not proven brand-voice signal.
> - The holdout sets are **same-author synthetic data**, so even these out-of-sample numbers likely overstate performance on real production traffic.
> - For production decisions, use the **LLM-judge-blended authenticity path** (now the default when a judge is configured) and report **judge-vs-human agreement**, rather than relying on the deterministic classifier alone.
>
> Mechanism finding (not a performance claim): after calibration the scorer weights style + traits (0.5 / 0.4) far above lexicon (0.1).

---

## Assets in this Repository

> **Note**
> The Wendy's project ships only in the source repo. Install Alignmenter from this repository (not the PyPI wheel) so the `case-studies/` assets are available on disk.

All of the files referenced below live under [`case-studies/wendys-twitter/`](https://github.com/justinGrosvenor/alignmenter/tree/main/case-studies/wendys-twitter):

| File | Purpose |
| --- | --- |
| `wendys_dataset.jsonl` | 235-turn labeled dataset (10 scenarios, 64 on-brand / 72 off-brand) |
| `wendys_twitter.yaml` | Persona pack used for both baseline and calibrated runs |
| `wendys_twitter.traits.json` | Trained trait model (logistic regression weights) |
| `baseline_run.yaml` | Run config for the uncalibrated baseline |
| `baseline_diagnostics.json` | ROC, F1, and score separation for the baseline |
| `calibrated_diagnostics.json` | Post-calibration diagnostics (ROC-AUC 1.000 — in-sample/near-in-sample; see caveats box) |
| `holdout_evaluation_results.json` | Held-out scenario results (the credible, out-of-sample numbers) |
| `calibration_reports/` | Intermediate artifacts: bounds, weight grid search, confusion matrices |

> Tip: keep the case-study directory intact. All commands below reference these exact paths so you can copy‑paste without editing YAML.

---

## Step-by-Step Reproduction

### 1. Install Alignmenter

> This walkthrough requires the repo checkout (case-study assets are not included in the PyPI wheel).

```bash
git clone https://github.com/justinGrosvenor/alignmenter.git
cd alignmenter
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev,safety]
```

### 2. Prepare the Dataset (optional sanitization)

All of the data you need already ships in `case-studies/wendys-twitter/`:

| File | Purpose | Expected authenticity |
| --- | --- | --- |
| `demo/wendys_full.jsonl` | Mixed-quality set used for calibration (good + bad replies) | ≈0.40 before calibration |
| `demo/wendys_onbrand_strict.jsonl` | On-brand replies that just meet the “pass” threshold | ≈0.65 |
| `demo/wendys_generic_llm.jsonl` | Friendly but generic LLM voice (mid-grade) | ≈0.40 |
| `demo/wendys_offbrand.jsonl` | Explicitly off-brand corporate replies | ≈0.20 |
| `demo/wendys_holdout_service.jsonl` | 10 customer-service sessions (never used in calibration) | ≈0.45–0.55 |
| `demo/wendys_holdout_roast.jsonl` | 8 competitor-roast sessions for out-of-sample testing | ≈0.40–0.50 |
| `demo/wendys_holdout_product.jsonl` | 8 product-promo sessions (mixed quality) | ≈0.35–0.50 |
| `demo/wendys_holdout_community.jsonl` | 8 community-engagement sessions | ≈0.40–0.55 |
| `demo/wendys_holdout_trend.jsonl` | 2 trend-participation sessions (limited remaining data) | varies |
| `demo/wendys_holdout_crisis.jsonl` | 5 crisis-response sessions | ≈0.30–0.45 |

Everything lives under `case-studies/wendys-twitter/demo/`, so there’s no need to copy files unless you want to edit them. If you do need a personalized copy, just `cp case-studies/wendys-twitter/demo/wendys_full.jsonl my_dataset.jsonl` and iterate from there. The holdout files above were never used during calibration, so they’re safe for out-of-sample validation.

> **Why the extra `--embedding` flag?** The hashed fallback is great for offline demos, but its cosine range is narrow; authenticity style scores will hover near the floor even for perfect replies. For any calibration or artifact you plan to share, use a real embedding provider (the docs default to `sentence-transformer:all-MiniLM-L6-v2`) so style similarity has enough headroom.

### 3. Run the Baseline Evaluation

```bash
alignmenter run \
  --config case-studies/wendys-twitter/baseline_run.yaml \

```

This reproduces the `baseline_diagnostics.json` file (ROC-AUC ≈ 0.733). Open the HTML report under `reports/<timestamp>_baseline/` and note that the new scenario/persona analytics already highlight which flows are most off-brand.

### 4. Calibrate the Persona

Use the CLI `calibrate` namespace to replicate the calibration pipeline:

1. **Estimate style bounds**
```bash
alignmenter calibrate bounds \
  --labeled case-studies/wendys-twitter/wendys_dataset.jsonl \
  --persona case-studies/wendys-twitter/wendys_twitter.yaml \
  --embedding sentence-transformer:all-MiniLM-L6-v2 \
  --output case-studies/wendys-twitter/calibration_reports/bounds.json
```

2. **Optimize weights**
```bash
alignmenter calibrate optimize \
  --labeled case-studies/wendys-twitter/wendys_dataset.jsonl \
  --persona case-studies/wendys-twitter/wendys_twitter.yaml \
  --bounds case-studies/wendys-twitter/calibration_reports/bounds.json \
  --embedding sentence-transformer:all-MiniLM-L6-v2 \
  --output case-studies/wendys-twitter/calibration_reports/weights.json \
  --grid-step 0.1
```

3. **Validate + diagnose**
```bash
alignmenter calibrate validate \
  --labeled case-studies/wendys-twitter/wendys_dataset.jsonl \
  --persona case-studies/wendys-twitter/wendys_twitter.yaml \
  --embedding sentence-transformer:all-MiniLM-L6-v2 \
  --output case-studies/wendys-twitter/calibrated_diagnostics.json
```

4. **Store the trait model** (already included as `wendys_twitter.traits.json`, but you can regenerate by passing `--output wendys_twitter.traits.json` to the calibration commands above).

### 5. Re-run With Calibrated Traits

Update the persona pack to reference the `.traits.json` file (already wired in `case-studies/wendys-twitter/wendys_twitter.yaml`), then run:

```bash
# Pass: strict on-brand slice
alignmenter run \
  --model openai:gpt-4o-mini \
  --dataset case-studies/wendys-twitter/demo/wendys_onbrand_strict.jsonl \
  --persona case-studies/wendys-twitter/wendys_twitter.yaml \
  --embedding sentence-transformer:all-MiniLM-L6-v2 \
  --out reports/wendys_onbrand

# Mid: generic-but-friendly LLM voice
alignmenter run \
  --model openai:gpt-4o-mini \
  --dataset case-studies/wendys-twitter/demo/wendys_generic_llm.jsonl \
  --persona case-studies/wendys-twitter/wendys_twitter.yaml \
  --embedding sentence-transformer:all-MiniLM-L6-v2 \
  --out reports/wendys_generic

# Fail: explicitly off-brand corporate replies
alignmenter run \
  --model openai:gpt-4o-mini \
  --dataset case-studies/wendys-twitter/demo/wendys_offbrand.jsonl \
  --persona case-studies/wendys-twitter/wendys_twitter.yaml \
  --embedding sentence-transformer:all-MiniLM-L6-v2 \
  --out reports/wendys_offbrand

# Holdout suites (fresh sessions not seen during calibration)
alignmenter run \
  --model openai:gpt-4o-mini \
  --dataset case-studies/wendys-twitter/demo/wendys_holdout_service.jsonl \
  --persona case-studies/wendys-twitter/wendys_twitter.yaml \
  --embedding sentence-transformer:all-MiniLM-L6-v2 \
  --out reports/wendys_holdout_service

alignmenter run \
  --model openai:gpt-4o-mini \
  --dataset case-studies/wendys-twitter/demo/wendys_holdout_roast.jsonl \
  --persona case-studies/wendys-twitter/wendys_twitter.yaml \
  --embedding sentence-transformer:all-MiniLM-L6-v2 \
  --out reports/wendys_holdout_roast
```

Swap the dataset path for any of the other holdouts (`wendys_holdout_product.jsonl`, `wendys_holdout_community.jsonl`, `wendys_holdout_trend.jsonl`, `wendys_holdout_crisis.jsonl`) to benchmark additional scenario buckets.

Typical authenticity scores on a laptop (re-using recorded transcripts):

```
On-brand strict  -> Brand voice ≈ 0.65 (passes) 
Generic LLM voice -> Brand voice ≈ 0.40 (borderline, reads polite but off-voice)
Off-brand set     -> Brand voice ≈ 0.20 (clearly corporate / wrong persona)
```

These contrasts make it easy to show stakeholders what “good vs. mid vs. bad” looks like without invoking a provider. When you’re ready to evaluate your real assistant, point `--dataset` at your sanitized transcripts or add `--generate-transcripts` to regenerate turns via the configured provider.

The CLI summary now shows pass/fail status based on the thresholds declared in `baseline_run.yaml`, and the HTML report’s “Scenario Breakdown” + “Persona Breakdown” tables surface which flows still need work.

### 6. Inspect the Artifacts

- `reports/wendys_twitter_calibrated/index.html` – includes scenario/persona tables, threshold notes, and the 20 riskiest turns.
- `reports/.../analytics.json` – machine-readable breakdowns for CI dashboards.
- `calibrated_diagnostics.json` – validation metrics, confusion matrix, ROC curves.

---

## How to Adapt This for Your Brand

1. Duplicate the workflow with your own dataset + persona pack.
2. Swap out `wendys_dataset.jsonl` for your transcripts.
3. Use `alignmenter dataset sanitize` before labeling to avoid leaking PII.
4. Work through the **bounds → optimize → validate** pipeline.
5. Set thresholds in your run config (`scorers.authenticity.threshold_warn`, etc.) so CI exits non-zero when voice drift occurs.

The Wendy's case study shows Alignmenter’s calibration tooling can substantially improve out-of-sample separation for a playful, culturally aware persona without hand-tuned heuristics — while also being honest about where the deterministic scorer weakens (edge cases) and where its apparent strength comes from surface statistics rather than brand voice. Use it as a template for social media, marketing, or support personas, and pair the deterministic scorer with the LLM-judge-blended path before trusting it in production.
