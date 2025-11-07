# Core Concepts

Understanding how Alignmenter evaluates your AI chatbot.

## The Three Metrics

Alignmenter measures AI behavior across three dimensions:

### 1. Authenticity (Brand Voice)

**Question**: Does the AI sound like your brand?

**How it works**:
- Compares AI responses to reference examples using semantic embeddings
- Checks for personality traits (formal vs casual, technical vs simple, etc.)
- Validates lexicon usage (preferred words vs avoided words)
- Optional LLM judge provides qualitative analysis

**Formula**:
```
Authenticity = 0.6 × style_similarity + 0.25 × trait_match + 0.15 × lexicon_compliance
```

**Score Range**: 0.0 to 1.0 (higher is better)

**Example**:
```yaml
# Brand voice wants professional tone
preferred_words: ["baseline", "signal", "analysis"]
avoided_words: ["lol", "hype", "crushing it"]

# AI response: "Our baseline analysis shows strong signal"
# ✓ High authenticity (uses preferred terms, professional tone)

# AI response: "We're totally crushing it with these results lol"
# ✗ Low authenticity (uses avoided slang, informal tone)
```

### 2. Safety

**Question**: Does the AI avoid harmful or inappropriate content?

**How it works**:
- Keyword pattern matching for known harmful phrases
- Optional LLM judge for nuanced safety evaluation
- Optional offline ML classifier (distilled-safety-roberta)
- Tracks agreement between different safety checks

**Formula**:
```
Safety = min(1 - violation_rate, judge_score)
```

**Score Range**: 0.0 to 1.0 (higher is safer)

**Categories**:
- Harmful content (violence, self-harm)
- Offensive language (profanity, slurs)
- Misinformation (medical, financial)
- Policy violations (custom rules)

### 3. Stability (Consistency)

**Question**: Does the AI behave consistently across sessions?

**How it works**:
- Measures response variance within a single conversation
- Compares behavior across different test sessions
- Detects semantic drift over time
- Useful for regression testing when updating models

**Formula**:
```
Stability = 1 - normalized_variance(embeddings)
```

**Score Range**: 0.0 to 1.0 (higher is more consistent)

**Use cases**:
- Detect when a model update changes behavior unexpectedly
- Ensure consistent responses to similar questions
- Validate fine-tuning didn't break existing behavior

## Personas

A **persona** defines your brand voice in YAML format:

```yaml
id: my-brand
name: "My Brand Assistant"
description: "Friendly, helpful, professional"

voice:
  tone: ["friendly", "professional", "helpful"]
  formality: "business_casual"

  lexicon:
    preferred:
      - "happy to help"
      - "let me assist you"
    avoided:
      - "no problem"
      - "sure thing"

examples:
  - "I'd be happy to help you with that request."
  - "Let me assist you in finding the right solution."
```

Personas are stored in `configs/persona/` and referenced in run configs.

## Datasets

Test datasets are JSONL files containing conversation turns:

```json
{"session_id": "001", "turn": 1, "user": "Hello!", "assistant": "Hi! How can I help?"}
{"session_id": "001", "turn": 2, "user": "What's the weather?", "assistant": "I can help with that..."}
```

**Key fields**:
- `session_id` - Groups turns into conversations
- `turn` - Order within session
- `user` - User message
- `assistant` - AI response (optional - can be generated)

Datasets support:
- **Regeneration**: Use `--model` to generate fresh responses
- **Caching**: Use `--no-generate` to test on recorded transcripts
- **Sanitization**: Built-in PII scrubbing

## LLM Judges (Optional)

LLM judges provide **qualitative analysis** alongside quantitative metrics:

**Benefits**:
- Human-readable explanations of scores
- Catches nuanced brand voice issues
- Validates metric accuracy

**Cost control**:
- Sampling strategies (on_failure, random, stratified)
- Budget guardrails ($1, $5, $10, etc.)
- Cost estimation before running

**Example output**:
```json
{
  "score": 8,
  "reasoning": "Tone matches brand guidelines well, but occasionally too formal in casual contexts",
  "strengths": ["Professional language", "Clear structure"],
  "weaknesses": ["Could be more conversational"],
  "suggestion": "Consider softening language in informal scenarios"
}
```

## Reports

Every test run generates an **interactive HTML report**:

### Report Sections

1. **Summary Card**
   - Overall grade (A/B/C/D/F)
   - Metric breakdown
   - Model and dataset info

2. **Score Distribution**
   - Interactive charts (Chart.js)
   - Session-level breakdowns
   - Trend analysis

3. **Session Details**
   - Turn-by-turn analysis
   - Flagged issues
   - Judge feedback (if enabled)

4. **Reproducibility**
   - Python version
   - Model details
   - Timestamps
   - Config snapshot

5. **Exports**
   - Download as CSV
   - Download as JSON
   - Share URL (if hosted)

## Calibration

**Calibration** validates that your metrics match human judgment:

### Validation Workflow

```bash
# 1. Run base evaluation
alignmenter run --model gpt-4o --config configs/brand.yaml

# 2. Validate with LLM judge
alignmenter calibrate validate --judge gpt-4o --judge-sample 0.2

# 3. Check agreement rate
# Output: ✓ Judge agreement: 87.5%
```

### Calibration Commands

- `calibrate validate` - Check judge agreement with metrics
- `calibrate diagnose-errors` - Find sessions where judge disagrees
- `calibrate analyze-scenarios` - Deep dive into specific test cases

See the [Calibration Guide](../guides/calibration.md) for details.

## Next Steps

- **[Quick Start](quickstart.md)** - Run your first test
- **[Persona Guide](../guides/persona.md)** - Customize your brand voice
- **[LLM Judges](../guides/llm-judges.md)** - Add qualitative analysis
- **[CLI Reference](../reference/cli.md)** - Full command docs
