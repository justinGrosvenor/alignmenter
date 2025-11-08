# Wendy's Twitter Voice Case Study

This case study reproduces a full calibration workflow for Wendy's Twitter persona, showing how Alignmenter can learn a highly distinctive voice and ship a trustworthy scorecard. Follow the steps below to recreate the published ROC-AUC 1.000 result and inspect every artifact end to end.

> **Highlights**
>
> | Metric | Baseline | Calibrated |
> | --- | --- | --- |
> | ROC-AUC | 0.733 | **1.000** |
> | F1 Score | 0.594 | **1.000** |
> | On-brand mean | 0.468 | **0.599** |
> | Off-brand mean | 0.323 | **0.169** |
>
> - Distinctive voice is driven by style + traits (0.5 / 0.4 weights); lexicon contributes only 0.1.
> - Scenario analytics isolate the riskiest flows (competitor roasts + crisis response).
> - Persona breakdown proves the calibrated scorer separates on/off brand turns within each session.

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
| `calibrated_diagnostics.json` | Final validation report (ROC-AUC 1.000) |
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
pip install -e .[dev]
```

### 2. Prepare the Dataset (optional sanitization)

```bash
cp case-studies/wendys-twitter/wendys_dataset.jsonl datasets/wendys_twitter.jsonl
alignmenter dataset sanitize datasets/wendys_twitter.jsonl --dry-run
```

The dry run prints the number of PII hits and shows how placeholders will be inserted. Drop `--dry-run` to write a cleaned copy alongside the original.

### 3. Run the Baseline Evaluation

```bash
alignmenter run \
  --config case-studies/wendys-twitter/baseline_run.yaml \
  --no-generate
```

This reproduces the `baseline_diagnostics.json` file (ROC-AUC ≈ 0.733). Open the HTML report under `reports/<timestamp>_baseline/` and note that the new scenario/persona analytics already highlight which flows are most off-brand.

### 4. Calibrate the Persona

Use the CLI `calibrate` namespace to replicate the calibration pipeline:

1. **Estimate style bounds**
   ```bash
   alignmenter calibrate bounds \
     --labeled case-studies/wendys-twitter/wendys_dataset.jsonl \
     --persona case-studies/wendys-twitter/wendys_twitter.yaml \
     --output case-studies/wendys-twitter/calibration_reports/bounds.json
   ```

2. **Optimize weights**
   ```bash
   alignmenter calibrate optimize \
     --labeled case-studies/wendys-twitter/wendys_dataset.jsonl \
     --persona case-studies/wendys-twitter/wendys_twitter.yaml \
     --bounds case-studies/wendys-twitter/calibration_reports/bounds.json \
     --output case-studies/wendys-twitter/calibration_reports/weights.json \
     --grid-step 0.1
   ```

3. **Validate + diagnose**
   ```bash
   alignmenter calibrate validate \
     --labeled case-studies/wendys-twitter/wendys_dataset.jsonl \
     --persona case-studies/wendys-twitter/wendys_twitter.yaml \
     --output case-studies/wendys-twitter/calibrated_diagnostics.json
   ```

4. **Store the trait model** (already included as `wendys_twitter.traits.json`, but you can regenerate by passing `--output wendys_twitter.traits.json` to the calibration commands above).

### 5. Re-run With Calibrated Traits

Update the persona pack to reference the `.traits.json` file (already wired in `case-studies/wendys-twitter/wendys_twitter.yaml`), then run:

```bash
alignmenter run \
  --model openai:gpt-4o-mini \
  --dataset datasets/wendys_twitter.jsonl \
  --persona case-studies/wendys-twitter/wendys_twitter.yaml \
  --no-generate \
  --out reports/wendys_twitter_calibrated
```

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

The Wendy's case study proves that Alignmenter’s calibration tooling can master a playful, culturally aware persona without hand-tuned heuristics. Use it as a template for social media, marketing, or support personas that demand more than keyword checks.
