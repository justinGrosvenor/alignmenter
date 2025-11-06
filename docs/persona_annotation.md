# Persona Annotation Workflow Guide

This guide covers the process of annotating conversation data for persona calibration in Alignmenter.

## Overview

Persona annotation involves labeling assistant responses as **on-brand** (1) or **off-brand** (0) to train persona-specific authenticity weights. Well-annotated data enables Alignmenter to learn what "authentic" means for your specific brand voice.

## Why Annotate?

Alignmenter's authenticity scorer uses three components:

1. **Style similarity** (embeddings) - automatic
2. **Traits** (logistic model) - **requires annotation**
3. **Lexicon** (preferred/avoided words) - manual configuration

Annotation trains the trait model to recognize subtle patterns that distinguish on-brand from off-brand responses.

## Minimum Requirements

- **25+ labeled samples** minimum (50-100 recommended)
- **Balanced labels**: aim for 40-60% positive examples
- **Diverse content**: cover different topics, conversation styles, edge cases
- **Single persona**: all annotations must be for the same persona

## Annotation Format

Create a JSONL file with one record per line:

```jsonl
{"text": "Our approach emphasizes precision and evidence-based analysis.", "label": 1, "persona_id": "alignmenter"}
{"text": "lol that's super hyped bro!", "label": 0, "persona_id": "alignmenter"}
{"text": "This aligns with our baseline methodology.", "label": 1, "persona_id": "alignmenter"}
```

### Required Fields

- **`text`**: The assistant's response text (string)
- **`label`**: Binary label (0 = off-brand, 1 = on-brand)
- **`persona_id`**: Matches the `id` field in your persona YAML

### Optional Fields

- **`session_id`**: Track which conversation this came from
- **`turn_index`**: Position in the conversation
- **`annotator`**: Who labeled this (useful for inter-annotator agreement)
- **`notes`**: Why this was labeled a certain way

## Workflow

### 1. Generate Candidate Responses

Start with real or synthetic conversation data:

```bash
# Bootstrap a test dataset with traps
alignmenter bootstrap-dataset \
  --out data/candidates.jsonl \
  --sessions 20 \
  --safety-trap-ratio 0.2 \
  --brand-trap-ratio 0.3
```

Or use production logs (sanitized first):

```bash
# Remove PII from production data
alignmenter sanitize-dataset \
  --input prod_logs.jsonl \
  --out data/candidates_clean.jsonl
```

### 2. Annotate Responses

Review each assistant response and label it:

**Label = 1 (on-brand)** when the response:
- Matches your brand's tone and style
- Uses preferred vocabulary/phrasing
- Demonstrates desired personality traits
- Aligns with your communication guidelines

**Label = 0 (off-brand)** when the response:
- Violates brand voice guidelines
- Uses avoided words or casual slang
- Exhibits wrong personality traits
- Misses the mark on formality/tone

**Annotation Tips:**

- **Be consistent**: Define clear criteria before starting
- **Consider context**: Some casual language may be appropriate depending on the conversation
- **Focus on voice**: Don't penalize for factual errors (that's a different metric)
- **Document edge cases**: Add notes for borderline examples
- **Review in batches**: Annotate 10-20 at a time, then take a break

### 3. Quality Checks

Before calibration, validate your annotations:

```python
# Check label balance
import json
from collections import Counter

with open('annotations.jsonl') as f:
    labels = [json.loads(line)['label'] for line in f]

print(Counter(labels))
# Should be roughly balanced: Counter({1: 42, 0: 38})

# Check persona_id consistency
with open('annotations.jsonl') as f:
    personas = set(json.loads(line)['persona_id'] for line in f)

assert len(personas) == 1, f"Mixed personas: {personas}"
```

### 4. Run Calibration

Train the trait model from your annotations:

```bash
alignmenter calibrate-persona \
  --persona-path configs/persona/mybot.yaml \
  --dataset annotations.jsonl \
  --out configs/persona/mybot.traits.json \
  --epochs 300 \
  --learning-rate 0.1
```

**Output:**
- `mybot.traits.json` contains learned weights
- Automatically loaded when evaluating with `mybot.yaml`

### 5. Validate Results

Test the calibrated model:

```bash
# Run evaluation with calibrated weights
alignmenter run \
  --model openai:gpt-4 \
  --dataset test_conversations.jsonl \
  --persona configs/persona/mybot.yaml
```

Review the authenticity scores and bootstrap confidence intervals to ensure the model generalizes well.

## Advanced Techniques

### Multi-Annotator Agreement

Track inter-annotator reliability:

```jsonl
{"text": "...", "label": 1, "persona_id": "bot", "annotator": "alice"}
{"text": "...", "label": 1, "persona_id": "bot", "annotator": "bob"}
{"text": "...", "label": 0, "persona_id": "bot", "annotator": "alice"}
```

Calculate Cohen's kappa or percentage agreement before finalizing.

### Active Learning

Focus annotation effort on uncertain examples:

1. Train initial model on small seed set (25-50 examples)
2. Score unlabeled candidates
3. Annotate examples where `0.4 < score < 0.6` (most uncertain)
4. Retrain and repeat

### Adversarial Examples

Deliberately include challenging cases:

- **Edge of acceptable**: Phrases that barely pass/fail
- **Context-dependent**: Same words, different appropriateness
- **Subtle violations**: Minor tone shifts
- **False positives**: Looks off-brand but isn't

## Common Pitfalls

❌ **Too few samples**: 10-15 annotations won't generalize
✅ Use at least 25, preferably 50-100

❌ **Imbalanced labels**: 90% positive, 10% negative
✅ Aim for 40-60% positive rate

❌ **Single annotator bias**: One person's interpretation
✅ Use 2-3 annotators for important personas

❌ **Annotating blindly**: No clear criteria
✅ Write down decision rules before starting

❌ **Overfitting to training data**: Model memorizes examples
✅ Hold out 20% for validation

## Example Workflow

Here's a complete end-to-end example:

```bash
# 1. Generate synthetic conversations with brand traps
alignmenter bootstrap-dataset \
  --out data/raw_candidates.jsonl \
  --sessions 30 \
  --brand-trap-ratio 0.3

# 2. Manually annotate (edit the file, add label and persona_id fields)
# Use your text editor to add labels to each turn

# 3. Validate annotations
python -c "
import json
from collections import Counter

data = [json.loads(line) for line in open('data/annotated.jsonl')]
labels = [d['label'] for d in data]
personas = set(d['persona_id'] for d in data)

print(f'Total: {len(data)}')
print(f'Balance: {Counter(labels)}')
print(f'Personas: {personas}')
assert len(data) >= 25, 'Need at least 25 samples'
assert len(personas) == 1, 'Mixed personas detected'
"

# 4. Train the model
alignmenter calibrate-persona \
  --persona-path configs/persona/mybot.yaml \
  --dataset data/annotated.jsonl \
  --min-samples 25 \
  --epochs 300

# 5. Evaluate
alignmenter run \
  --model openai:gpt-4 \
  --dataset test/holdout.jsonl \
  --persona configs/persona/mybot.yaml

# Check the authenticity CI range in the report
alignmenter report --last
```

## Annotation Guidelines Template

Use this template when onboarding annotators:

```markdown
# [Your Brand] Voice Annotation Guidelines

## On-Brand (label = 1)

✅ Professional but approachable
✅ Uses "signal", "baseline", "alignment"
✅ Evidence-driven, specific
✅ Calm, measured tone

Example:
> "Our baseline analysis shows a 15% improvement in alignment metrics."

## Off-Brand (label = 0)

❌ Overly casual or slang-heavy
❌ Uses "lol", "bro", "hype", "totally"
❌ Emotional or reactive
❌ Vague handwaving

Example:
> "Bro this is totally hype!! lol the vibes are immaculate 🔥"

## Edge Cases

- Technical jargon: ✅ (encouraged)
- Light humor: ✅ (if professional)
- Emoji: ❌ (avoid)
- Contractions: ✅ (natural, not casual)
```

## Resources

- **Calibration script**: `scripts/calibrate_persona.py`
- **Bootstrap tool**: `scripts/bootstrap_dataset.py`
- **Sanitization**: `scripts/sanitize_dataset.py`
- **Example persona**: `configs/persona/default.yaml`

## Next Steps

Once you've calibrated your persona:

1. **Validate**: Test on held-out data
2. **Monitor**: Track authenticity scores over time
3. **Iterate**: Re-calibrate as your brand voice evolves
4. **Document**: Keep annotation guidelines up to date

For questions or issues, see the [main README](https://github.com/justinGrosvenor/alignmenter/blob/main/README.md) or file an issue on GitHub.
