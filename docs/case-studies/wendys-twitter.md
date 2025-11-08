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

Everything lives under `case-studies/wendys-twitter/demo/`, so there’s no need to copy files unless you want to edit them. If you do need a personalized copy, just `cp case-studies/wendys-twitter/demo/wendys_full.jsonl my_dataset.jsonl` and iterate from there.

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
```

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

The Wendy's case study proves that Alignmenter’s calibration tooling can master a playful, culturally aware persona without hand-tuned heuristics. Use it as a template for social media, marketing, or support personas that demand more than keyword checks.
