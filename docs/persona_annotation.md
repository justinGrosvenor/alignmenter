# Persona Annotation

Calibration turns Alignmenter's authenticity scorer from a reasonable default into
a measurement tuned to *your* brand voice. It all starts with a small set of
human-labeled examples. This page explains the annotation workflow and how those
labels flow into calibration.

## The label format

Annotation is a binary judgment on individual assistant turns:

- **`1` = on-brand** – the response sounds like your persona
- **`0` = off-brand** – it does not

Labeled data is stored as JSONL, one record per turn. Each record needs at least:

```json
{"persona_id": "default_v1", "text": "Our baseline analysis shows a clear signal.", "label": 1}
```

The `persona_id` must match the `id` field of the persona YAML you are
calibrating; `calibrate-persona` skips rows whose `persona_id` does not match.
Interactive labeling also records `labeler`, `timestamp`, `confidence`
(`high`/`medium`/`low`), and free-text `notes`, but only `persona_id`, `text`, and
`label` are required for training.

Aim for at least **25 labeled turns** (the default `--min-samples`), balanced
between on-brand and off-brand examples. Calibration needs both classes present.

## Preparing candidates to label

You have two ways to assemble the turns you will label.

### Option A — `persona export` (for external annotation tools)

Export assistant turns from a dataset into a spreadsheet-friendly CSV, or into
Label Studio tasks:

```bash
# CSV for a spreadsheet / labeling tool
alignmenter persona export \
  --dataset datasets/prod.jsonl \
  --persona-id default_v1 \
  --out annotation_batch.csv

# Label Studio JSON tasks
alignmenter persona export \
  --dataset datasets/prod.jsonl \
  --format labelstudio \
  --out tasks.json
```

Add a `label` column/field (0 or 1) in your tool of choice, then convert the
results back to the JSONL format above.

### Option B — `calibrate generate` + `calibrate label` (built-in)

Sample a diverse set of candidate turns, then label them interactively in the
terminal:

```bash
# 1. Sample candidates from an existing dataset
alignmenter calibrate generate \
  --dataset datasets/prod.jsonl \
  --persona configs/persona/default.yaml \
  --output candidates.jsonl \
  --num-samples 50 --strategy diverse

# 2. Label them one-by-one (writes each label immediately)
alignmenter calibrate label \
  --input candidates.jsonl \
  --persona configs/persona/default.yaml \
  --output labeled.jsonl \
  --labeler jane
```

The labeler prompt shows the persona's exemplars and lexicon for context and
accepts `1` (on-brand), `0` (off-brand), `s` (skip), or `q` (quit). Use
`--append` to resume a labeling session without re-labeling turns you already
covered.

## Writing a review rubric

Consistent labels come from a shared definition of "on-brand." Before annotating,
write down for each persona:

- **Tone traits** to reward (e.g. measured, precise, warm) and their opposites.
- **Disallowed phrases / lexicon** — words the brand never uses (mirror the
  persona's `lexicon.avoid`).
- **Borderline guidance** — how to handle responses that are correct but flat, or
  on-topic but off-voice.

Keep the rubric next to the labeling tool so every annotator applies the same bar.

## From labels to a calibrated scorer

Once you have `labeled.jsonl`, the calibration pipeline consumes it in stages.
Diagnostics and weight tuning require the `[calibrate]` extra
(`pip install "alignmenter[calibrate]"`); fitting the trait model does not.

```bash
# 1. Estimate style-similarity normalization bounds   [calibrate]
alignmenter calibrate bounds \
  --labeled labeled.jsonl \
  --persona configs/persona/default.yaml \
  --output bounds.json

# 2. Grid-search the style/traits/lexicon blend weights  [calibrate]
alignmenter calibrate optimize \
  --labeled labeled.jsonl \
  --persona configs/persona/default.yaml \
  --bounds bounds.json \
  --output weights.json

# 3. Fit the persona trait model -> writes <persona>.traits.json
alignmenter calibrate-persona \
  --persona-path configs/persona/default.yaml \
  --dataset labeled.jsonl
```

What each stage produces:

- **`bounds`** derives `style_sim_min` / `style_sim_max` percentiles used to
  rescale raw embedding cosine similarity into a presentable band.
- **`optimize`** searches component weight combinations that sum to 1.0 and reports
  the blend that maximizes ROC-AUC against your labels.
- **`calibrate-persona`** trains a per-token/phrase-weight **logistic model** (the
  "traits" component) and writes `<persona>.traits.json` next to the persona YAML.
  The authenticity scorer loads this file automatically on the next run; without
  it, the scorer falls back to heuristic trait weights.

You can then confirm the result and inspect disagreements:

```bash
# Cross-validate and (optionally) sample an LLM judge   [calibrate]
alignmenter calibrate validate \
  --labeled labeled.jsonl \
  --persona configs/persona/default.yaml \
  --output diagnostics.json \
  --judge anthropic:claude-sonnet-5 --judge-sample 0.2

# Explain false positives / false negatives with a judge
alignmenter calibrate diagnose-errors \
  --labeled labeled.jsonl \
  --persona configs/persona/default.yaml \
  --output errors.json \
  --judge anthropic:claude-sonnet-5
```

## Related

- **[Calibration Guide](guides/calibration.md)** – end-to-end walkthrough
- **[Persona Guide](guides/persona.md)** – the persona YAML schema
- **[CLI Reference](reference/cli.md)** – every `calibrate` command
- **[Metrics Reference](reference/metrics.md)** – how the trait model scores
