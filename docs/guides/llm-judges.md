# LLM Judges

LLM judges provide qualitative analysis of your AI's brand voice alignment. They complement quantitative metrics with human-readable feedback.

## Overview

While Alignmenter's core metrics (authenticity, safety, stability) are fast and deterministic, LLM judges add:

- **Explanations**: Why did a session score high or low?
- **Nuance**: Catches subtleties that formulas might miss
- **Validation**: Confirms metric accuracy against human-like judgment

## When to Use Judges

✅ **Good use cases**:
- Validating metric calibration
- Diagnosing unexpected scores
- Getting qualitative feedback for stakeholders
- Research and experimentation

❌ **Avoid judges for**:
- Every test run (expensive and slow)
- Real-time monitoring (use metrics instead)
- Large-scale batch processing (cost prohibitive)

## Basic Usage

### Validate Metrics

Check if LLM judge agrees with your quantitative scores:

```bash
alignmenter calibrate validate --judge openai:gpt-4o --judge-sample 0.2
```

Output:
```
Analyzing 12 sessions (20% sample) with LLM judge...
✓ Judge agreement with metrics: 87.5%
→ "Tone matches brand guidelines well, but occasionally too formal in casual contexts"
Cost: $0.032 (12 judge calls)
```

### Diagnose Errors

Find sessions where judge disagrees with metrics:

```bash
alignmenter calibrate diagnose-errors --judge openai:gpt-4o
```

Shows sessions with large score discrepancies for manual review.

### Analyze Scenarios

Deep dive into specific test cases:

```bash
alignmenter calibrate analyze-scenarios --judge openai:gpt-4o --sessions session_001,session_002
```

## Cost Control

LLM judge calls can get expensive. Alignmenter provides multiple cost controls:

### 1. Sampling Strategies

Only analyze a subset of sessions:

```bash
# Random 20% sample
--judge-sample 0.2

# First N sessions
--judge-sample 10

# Stratified sampling (coming soon)
```

### 2. Budget Guardrails

Set maximum spend:

```bash
--judge-budget 1.00   # Stop at $1.00
--judge-budget 5.00   # Stop at $5.00
```

Alignmenter halts at 90% of budget to prevent overruns.

### 3. Cost Estimation

Preview costs before running:

```bash
alignmenter calibrate validate --judge gpt-4o --judge-sample 0.2 --dry-run
```

Shows:
```
Estimated cost: $0.032 (12 calls × $0.0027/call)
Would analyze 12/60 sessions
```

### 4. Smart Sampling

`on_failure` strategy only judges low-scoring sessions:

```bash
--judge-strategy on_failure --judge-threshold 0.7
```

Typically saves 90% of cost while catching issues.

## Supported Providers

### OpenAI

```bash
--judge openai:gpt-4o
--judge openai:gpt-4o-mini  # Cheaper option
```

**Pricing** (as of Nov 2025):
- gpt-4o: $2.50 / 1M input tokens, $10.00 / 1M output
- gpt-4o-mini: $0.15 / 1M input tokens, $0.60 / 1M output

### Anthropic

```bash
--judge anthropic:claude-3-5-sonnet-20241022
--judge anthropic:claude-3-5-haiku-20241022  # Cheaper
```

**Pricing**:
- Claude 3.5 Sonnet: $3.00 / 1M input, $15.00 / 1M output
- Claude 3.5 Haiku: $0.80 / 1M input, $4.00 / 1M output

## Judge Output Format

Judges return structured JSON:

```json
{
  "score": 8,
  "reasoning": "The response maintains a professional tone and uses preferred terminology. However, it could be slightly more conversational in casual contexts.",
  "strengths": [
    "Uses preferred lexicon ('baseline', 'signal')",
    "Professional and precise language",
    "Clear structure and logic"
  ],
  "weaknesses": [
    "Occasionally too formal for casual questions",
    "Could use more varied sentence structure"
  ],
  "suggestion": "Consider adjusting formality based on user's tone. Casual questions could receive friendlier responses."
}
```

This appears in HTML reports and JSON exports.

## Calibration Workflow

Recommended process for using judges:

### 1. Initial Run

Get baseline metrics without judges:

```bash
alignmenter run --model gpt-4o --config configs/brand.yaml
```

Review the quantitative scores first.

### 2. Validate Metrics

Check if metrics align with LLM judgment:

```bash
alignmenter calibrate validate --judge gpt-4o --judge-sample 0.2
```

Aim for **≥85% agreement rate**.

### 3. Diagnose Issues

If agreement is low, find problematic sessions:

```bash
alignmenter calibrate diagnose-errors --judge gpt-4o
```

Review these manually to understand discrepancies.

### 4. Adjust Persona

Based on judge feedback, refine your persona config:

```yaml
# Before
voice:
  tone: ["professional"]

# After (based on judge feedback)
voice:
  tone: ["professional", "approachable"]
```

### 5. Re-validate

Run validation again to confirm improvement:

```bash
alignmenter calibrate validate --judge gpt-4o --judge-sample 0.2
```

## Advanced: Custom Prompts

You can customize the judge prompt (advanced users):

```python
from alignmenter.judges import AuthenticityJudge

judge = AuthenticityJudge(
    persona_path="configs/persona/brand.yaml",
    judge_provider=judge_provider,
    custom_prompt="Evaluate if this response matches our brand voice..."
)
```

## Cost Optimization

### Recommended Strategies

**Development**:
```bash
# Use cheap mini model with small sample
--judge openai:gpt-4o-mini --judge-sample 0.1
```

**Pre-deployment validation**:
```bash
# Use full model with larger sample
--judge openai:gpt-4o --judge-sample 0.3
```

**Production monitoring**:
```bash
# Only judge failures
--judge openai:gpt-4o-mini --judge-strategy on_failure
```

### Typical Costs

For a 60-session dataset:

| Strategy | Sessions Judged | Cost (gpt-4o-mini) | Cost (gpt-4o) |
|----------|----------------|-------------------|---------------|
| Full (100%) | 60 | $0.10 | $0.60 |
| Sample 20% | 12 | $0.02 | $0.12 |
| On failure (10% fail) | 6 | $0.01 | $0.06 |

## Troubleshooting

### "Judge API key not found"

Set your API key:
```bash
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Judge calls are slow

- Use `gpt-4o-mini` instead of `gpt-4o`
- Reduce sample size
- Run in parallel (coming soon)

### High cost

- Use `--judge-budget` to set limits
- Try `on_failure` strategy
- Use mini/haiku models

### Low agreement rate

- Review diagnose-errors output
- Check if persona definition is clear
- Ensure reference examples are representative
- Consider adjusting metric weights

## Next Steps

- **[Calibration Guide](calibration.md)** - Full calibration workflow
- **[Persona Guide](persona.md)** - Improve persona definitions
- **[CLI Reference](../reference/cli.md)** - Full command options
