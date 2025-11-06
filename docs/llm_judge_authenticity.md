# LLM Judge for Authenticity: Design Document

**Status:** Proposed
**Created:** 2025-11-05
**Author:** Alignmenter Team

---

## Executive Summary

Add an **optional LLM judge for authenticity evaluation** focused on **diagnostics and explainability** rather than scoring. The judge evaluates **full scenarios/sessions** (not individual turns) to provide contextual analysis of brand voice alignment.

**Key Principle:** The judge is a **diagnostic tool**, not a replacement for the existing scoring system. It helps teams understand *why* responses are off-brand and validates calibration quality.

---

## Problem Statement

Current authenticity scoring works well after calibration (ROC-AUC 1.000 in Wendy's case study), but has limitations:

1. **No explanations**: Scores are numeric without rationale
2. **Calibration validation**: Hard to know if calibration is working correctly
3. **Error analysis**: False positives/negatives lack context
4. **New personas**: Uncalibrated personas have poor baseline performance
5. **Edge cases**: Unusual scenarios may confuse pattern-matching

LLM judges can provide:
- ✅ Human-readable explanations
- ✅ Contextual understanding (not just pattern matching)
- ✅ Suggestions for improvement
- ✅ Validation of calibration quality

But they're:
- ❌ Expensive (API costs)
- ❌ Slow (latency)
- ❌ Non-deterministic

---

## Design Principles

### 1. Scenario-Based Evaluation

**Judge full scenarios/sessions, not individual turns.**

**Rationale:**
- Brand voice is contextual (crisis response vs casual banter)
- Tone consistency across a conversation matters
- Judge needs full context to evaluate appropriately

**Example:**
```
❌ Turn-by-turn (bad):
Turn 4: "that's rough" → Judge: 6/10
Turn 5: "DM us" → Judge: 8/10

✅ Scenario-level (good):
Session wendys-044 (6 turns, scenario:crisis_response):
User complains about 45-minute wait + wrong order
Wendy's responds with appropriate seriousness while maintaining voice
Judge: 9/10 - Handled crisis professionally without losing brand personality
```

### 2. Diagnostics Over Scoring

**Primary use case is explainability, not score fusion.**

**Rationale:**
- Calibrated scoring already achieves near-perfect accuracy
- Judge's value is in explaining *why* something is off-brand
- Helps teams improve personas and calibration

**Anti-Pattern:**
```python
# ❌ Don't do this (blend scores)
authenticity_score = 0.7 * base_score + 0.3 * judge_score
```

**Preferred Pattern:**
```python
# ✅ Do this (diagnostic analysis)
if base_score < 0.4 or base_score > 0.8:
    # Judge edge cases for explanation
    judge_analysis = llm_judge_scenario(session, persona)
    report["diagnostic_notes"][session_id] = judge_analysis
```

### 3. Sample-Based Analysis

**Judge a representative sample of scenarios, not all data.**

**Rationale:**
- Cost: Judging 100% of scenarios is expensive
- Diminishing returns: 10-20% sample reveals most issues
- Speed: Allows faster iteration

**Sampling Strategies:**
1. **Random sample**: 10-20% of all scenarios
2. **Stratified sample**: Equal representation per scenario tag
3. **Error-focused**: Only false positives/negatives from calibration
4. **Threshold-based**: Only ambiguous scores (0.4-0.6 range)

### 4. Optional, Off by Default

**Feature must be opt-in to avoid surprising users with costs.**

**Default behavior:**
```bash
# No judge, fast and free
alignmenter run --config myconfig.yaml
```

**Explicit opt-in:**
```bash
# Judge 20% of scenarios
alignmenter run --config myconfig.yaml --judge-authenticity-sample 0.2
```

---

## Use Cases

### Use Case 1: Calibration Validation

**Problem:** How do I know if my calibration is working correctly?

**Solution:** Judge a stratified sample and compare with calibrated scores.

```bash
# After calibration, validate quality
alignmenter calibrate validate \
  --labeled wendys_labeled.jsonl \
  --persona wendys_twitter.yaml \
  --judge-sample 0.2 \
  --output diagnostics.json
```

**Output:**
```json
{
  "validation_metrics": {
    "roc_auc": 0.95,
    "f1": 0.88
  },
  "judge_analysis": {
    "sessions_judged": 20,
    "agreement_rate": 0.85,
    "disagreements": [
      {
        "session_id": "wendys-043",
        "calibrated_score": 0.72,
        "judge_score": 0.4,
        "judge_reasoning": "Response uses 'oof, that's rough bestie' for a serious employee complaint. Too casual for the severity of the issue.",
        "recommendation": "Update calibration to penalize casualness in crisis scenarios"
      }
    ]
  }
}
```

### Use Case 2: Error Analysis

**Problem:** Why did calibration misclassify these scenarios?

**Solution:** Judge only false positives/negatives for explanations.

```bash
# Analyze calibration errors
alignmenter calibrate diagnose-errors \
  --labeled wendys_labeled.jsonl \
  --persona wendys_twitter.yaml \
  --output error_analysis.json
```

**Output:**
```json
{
  "false_positives": [
    {
      "session_id": "wendys-075",
      "text": "We appreciate your creativity, however we only accept...",
      "calibrated_score": 0.61,
      "true_label": 0,
      "judge_reasoning": "Uses formal corporate language ('we appreciate', 'however') and policy speak. Completely off-brand for Wendy's playful voice.",
      "pattern": "Lexicon score too high due to 'appreciate' being neutral, not penalized enough"
    }
  ],
  "false_negatives": [
    {
      "session_id": "wendys-051",
      "text": "that's rough - which location? we need to let them know their speaker is busted",
      "calibrated_score": 0.48,
      "true_label": 1,
      "judge_reasoning": "Perfect Wendy's voice - casual ('busted'), helpful, no corporate speak. On-brand.",
      "pattern": "Style similarity penalized due to lack of brand keywords, but tone is perfect"
    }
  ],
  "recommendations": [
    "Reduce lexicon weight from 0.1 to 0.05",
    "Add 'busted', 'rough' to positive trait vocabulary",
    "Increase style weight for casual helpful responses"
  ]
}
```

### Use Case 3: New Persona Baseline

**Problem:** I just created a new persona with no calibration data. How does it perform?

**Solution:** Judge a sample to get qualitative baseline before calibration.

```bash
# Before calibration, get diagnostic baseline
alignmenter run \
  --model openai:gpt-4o-mini \
  --dataset mydata.jsonl \
  --persona newbot.yaml \
  --judge-authenticity-sample 0.15 \
  --output baseline_with_diagnostics.json
```

**Output:**
```json
{
  "authenticity_score": 0.54,
  "judge_analysis": {
    "sessions_judged": 15,
    "common_issues": [
      {
        "issue": "Too formal",
        "frequency": 8,
        "examples": ["We apologize for the inconvenience", "Thank you for your patience"]
      },
      {
        "issue": "Missing brand keywords",
        "frequency": 6,
        "examples": ["No mention of 'precision', 'signal', or 'baseline'"]
      }
    ],
    "next_steps": [
      "Add more casual exemplars to persona",
      "Expand avoided vocabulary (apologize, regrettably, etc.)",
      "Calibrate with 50-100 labeled examples"
    ]
  }
}
```

### Use Case 4: Automatic Failure Diagnosis

**Problem:** A scenario fails authenticity checks in production. Why did it fail?

**Solution:** Automatically invoke judge when authenticity score falls below threshold.

```bash
# Auto-judge failures during evaluation
alignmenter run \
  --model openai:gpt-4o-mini \
  --dataset production_logs.jsonl \
  --persona mybot.yaml \
  --judge-on-failure \
  --auth-failure-threshold 0.6
```

**Config:**
```yaml
authenticity:
  judge:
    enabled: true
    trigger: "on_failure"  # Only judge when score < threshold
    failure_threshold: 0.6
    provider: "anthropic:claude-3-5-sonnet-20241022"
    budget: 100
```

**Output:**
```json
{
  "session_id": "prod-2847",
  "authenticity_score": 0.43,
  "status": "FAILED",
  "judge_analysis": {
    "triggered": true,
    "reason": "Score 0.43 below threshold 0.6",
    "score": 3,
    "reasoning": "Response uses corporate apology language ('We sincerely apologize', 'valued customer') which is explicitly avoided in persona. Tone is overly formal and lacks the playful brand personality.",
    "specific_issues": [
      "Uses 'sincerely apologize' (avoided vocabulary)",
      "Uses 'valued customer' (generic brand speak)",
      "Missing casual tone markers (no contractions, no brand slang)",
      "Could be any brand - no distinctive voice"
    ],
    "suggestion": "Rewrite: 'oof, that's not how it's supposed to go. slide into our DMs and we'll make it right 👀'",
    "cost": 0.003
  }
}
```

**Benefits:**
- ✅ **Targeted spending**: Only judge failures, not all scenarios
- ✅ **Immediate diagnostics**: Get explanation when it matters most
- ✅ **Production monitoring**: Catch voice drift in real deployments
- ✅ **Cost-effective**: Typical failure rate 5-10% = 90-95% cost savings vs judging all

**Cost analysis:**
```
100 scenarios, 10% failure rate:
- Without judge: Score all 100, no explanations
- With failure judge: Score all 100 + judge 10 failures = $0.03 extra
- With full judge: Judge all 100 = $0.30

Failure-triggered = 90% cheaper than full judging!
```

### Use Case 5: Scenario-Specific Performance

**Problem:** Are certain scenario types performing worse?

**Solution:** Judge stratified sample across all scenario tags.

```bash
# Analyze performance by scenario
alignmenter analyze-scenarios \
  --dataset wendys_dataset.jsonl \
  --persona wendys_twitter.yaml \
  --judge-per-scenario 3 \
  --output scenario_analysis.json
```

**Output:**
```json
{
  "scenario_performance": {
    "customer_service": {
      "avg_score": 0.82,
      "sessions_judged": 3,
      "judge_notes": "Strong performance. Balances helpfulness with sass."
    },
    "crisis_response": {
      "avg_score": 0.71,
      "sessions_judged": 3,
      "judge_notes": "Mixed. Some responses too casual for serious issues (food safety). Needs context-aware calibration."
    },
    "trend_participation": {
      "avg_score": 0.91,
      "sessions_judged": 3,
      "judge_notes": "Excellent meme fluency. Nails Gen Z voice."
    }
  },
  "recommendations": [
    "Add scenario-specific calibration for crisis_response",
    "Consider separate trait models for serious vs playful contexts"
  ]
}
```

---

## Technical Design

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                 AuthenticityScorer                      │
│  (Existing: embeddings + traits + lexicon)             │
└─────────────────────────────────────────────────────────┘
                         │
                         │ scores
                         ▼
┌─────────────────────────────────────────────────────────┐
│           AuthenticityJudge (NEW)                       │
│  - Evaluates full scenarios                             │
│  - Provides explanations                                │
│  - Diagnostic analysis                                  │
└─────────────────────────────────────────────────────────┘
                         │
                         │ analysis
                         ▼
┌─────────────────────────────────────────────────────────┐
│              DiagnosticReporter                         │
│  - Merges scores + judge analysis                       │
│  - Highlights disagreements                             │
│  - Suggests improvements                                │
└─────────────────────────────────────────────────────────┘
```

### Scenario Selection

**Sample selection algorithm:**

```python
def select_scenarios_for_judge(
    sessions: list[Session],
    sample_rate: float = 0.2,
    strategy: str = "stratified",
    failure_threshold: float = 0.6
) -> list[Session]:
    """
    Select representative scenarios for LLM judge analysis.

    Strategies:
    - random: Random sample across all sessions
    - stratified: Equal representation per scenario tag
    - errors: Only sessions with ambiguous scores (0.4-0.6)
    - extremes: High confidence cases (verify calibration)
    - on_failure: Only sessions below failure_threshold (most cost-effective)
    """
    if strategy == "random":
        k = int(len(sessions) * sample_rate)
        return random.sample(sessions, k)

    elif strategy == "stratified":
        # Group by scenario tag
        by_scenario = defaultdict(list)
        for session in sessions:
            tag = session.tags[0] if session.tags else "untagged"
            by_scenario[tag].append(session)

        # Sample equally from each scenario
        samples = []
        per_scenario = max(1, int(sample_rate * len(sessions) / len(by_scenario)))
        for scenario_sessions in by_scenario.values():
            samples.extend(random.sample(
                scenario_sessions,
                min(per_scenario, len(scenario_sessions))
            ))
        return samples

    elif strategy == "errors":
        # Only ambiguous scores
        return [s for s in sessions if 0.4 <= s.authenticity_score <= 0.6]

    elif strategy == "extremes":
        # High/low scores to verify calibration
        return [s for s in sessions if s.authenticity_score < 0.3 or s.authenticity_score > 0.8]

    elif strategy == "on_failure":
        # Only failed scenarios (below threshold)
        return [s for s in sessions if s.authenticity_score < failure_threshold]
```

### Judge Prompt

**Scenario-level evaluation prompt:**

```python
AUTHENTICITY_JUDGE_SCENARIO_PROMPT = """
You are evaluating whether an AI assistant maintains a consistent brand voice across a conversation.

# Brand Voice Definition

**ID:** {persona_id}
**Description:** {persona_description}

**Tone:** {persona_tone}
**Formality:** {persona_formality}

**Preferred Vocabulary:**
{preferred_words}

**Avoided Vocabulary:**
{avoided_words}

**On-Brand Examples:**
{exemplars}

# Conversation to Evaluate

**Scenario:** {scenario_tag}
**Session ID:** {session_id}

{conversation_turns}

# Evaluation Task

Rate the assistant's overall brand voice consistency in this conversation on a scale of 0-10:

**0-3: Completely off-brand**
- Wrong tone (too formal/casual for brand)
- Heavy use of avoided vocabulary
- Misses brand personality entirely

**4-6: Generic/Neutral**
- Not wrong, but not distinctive
- Could be any brand
- Lacks personality or flair

**7-9: On-brand**
- Matches tone and formality level
- Uses preferred vocabulary appropriately
- Captures brand personality

**10: Perfect embodiment**
- Exemplary brand voice
- Could be used as training example
- Distinctive and consistent

# Response Format

Provide your analysis in JSON format:

```json
{{
  "score": <0-10>,
  "reasoning": "<1-2 sentences explaining the score>",
  "strengths": ["<specific on-brand elements>"],
  "weaknesses": ["<specific off-brand elements>"],
  "suggestion": "<how to improve if score < 7, or 'None' if perfect>",
  "context_appropriate": <true/false, whether response fits scenario context>
}}
```

Be specific. Quote actual phrases from the conversation in your analysis.
"""
```

### Response Schema

```python
@dataclass
class JudgeAnalysis:
    """LLM judge analysis of a scenario."""
    session_id: str
    score: float  # 0-10 scale
    reasoning: str
    strengths: list[str]
    weaknesses: list[str]
    suggestion: Optional[str]
    context_appropriate: bool
    calibrated_score: float  # For comparison
    agreement: bool  # True if judge and calibration agree on on/off-brand
```

### CLI Interface

**New commands:**

```bash
# 1. Validate calibration with judge sample
alignmenter calibrate validate \
  --labeled data.jsonl \
  --persona mybot.yaml \
  --judge-sample 0.2 \
  --judge-strategy stratified \
  --output diagnostics.json

# 2. Diagnose calibration errors
alignmenter calibrate diagnose-errors \
  --labeled data.jsonl \
  --persona mybot.yaml \
  --output error_analysis.json

# 3. Analyze scenario performance
alignmenter analyze-scenarios \
  --dataset data.jsonl \
  --persona mybot.yaml \
  --judge-per-scenario 3 \
  --output scenario_analysis.json

# 4. Run evaluation with diagnostic judging
alignmenter run \
  --config run.yaml \
  --judge-authenticity-sample 0.15 \
  --judge-strategy errors  # Only judge ambiguous cases

# 5. Auto-judge failures only (most cost-effective)
alignmenter run \
  --config run.yaml \
  --judge-on-failure \
  --auth-failure-threshold 0.6
```

**Config file options:**

```yaml
# configs/run_with_judge.yaml
authenticity:
  judge:
    enabled: true
    provider: "anthropic:claude-3-5-sonnet-20241022"
    sample_rate: 0.2
    strategy: "stratified"  # random | stratified | errors | extremes | on_failure
    budget: 50  # Max API calls
    include_in_report: true  # Add judge analysis to HTML report

# Alternative: Failure-triggered mode
# authenticity:
#   judge:
#     enabled: true
#     trigger: "on_failure"
#     failure_threshold: 0.6  # Judge if score < 0.6
#     provider: "anthropic:claude-3-5-sonnet-20241022"
#     budget: 100
```

### Cost Estimation

**Pricing assumptions:**
- Claude 3.5 Sonnet: ~$0.003 per scenario (input + output)
- GPT-4o-mini: ~$0.001 per scenario

**Example costs:**

| Dataset Size | Sample Rate | Strategy | Scenarios Judged | Cost (Claude) | Cost (GPT-4o-mini) |
|--------------|-------------|----------|------------------|---------------|-------------------|
| 100 scenarios | 20% | Stratified | 20 | $0.06 | $0.02 |
| 500 scenarios | 10% | Random | 50 | $0.15 | $0.05 |
| 1000 scenarios | 5% | Errors only | ~50 | $0.15 | $0.05 |
| 100 scenarios | N/A | **On failure (10% fail)** | **10** | **$0.03** | **$0.01** |
| 1000 scenarios | N/A | **On failure (8% fail)** | **80** | **$0.24** | **$0.08** |
| 100 scenarios | 100% | All (diagnostic run) | 100 | $0.30 | $0.10 |

**On-failure strategy is most cost-effective for production monitoring:**
- Only pays for failures (typically 5-15% of scenarios)
- Provides immediate diagnostics when needed
- Scales well: 1000 scenarios × 10% failure = $0.03 vs $0.30 for full judging

**Budget guardrails:**

```python
if judge_config.enabled:
    estimated_cost = num_scenarios * sample_rate * COST_PER_SCENARIO
    if estimated_cost > judge_config.budget:
        logger.warning(
            f"Estimated judge cost ${estimated_cost:.2f} exceeds budget ${judge_config.budget:.2f}. "
            f"Reducing sample rate to {judge_config.budget / (num_scenarios * COST_PER_SCENARIO):.2%}"
        )
```

---

## Implementation Plan

### Phase 1: Core Judge Implementation ✅ COMPLETE

**Deliverables:**
- ✅ Create `AuthenticityJudge` class
- ✅ Scenario-level prompt template
- ✅ Response parsing (JSON output)
- ✅ Cost tracking per judge call
- ✅ OpenAI and Anthropic judge providers
- ✅ Scenario sampling strategies (6 strategies)
- ✅ Comprehensive test coverage (23 tests)

**Files:**
- ✅ `src/alignmenter/judges/__init__.py` (new)
- ✅ `src/alignmenter/judges/authenticity_judge.py` (new)
- ✅ `src/alignmenter/judges/prompts.py` (new)
- ✅ `src/alignmenter/calibration/sampling.py` (new)
- ✅ `src/alignmenter/providers/judges.py` (updated - added AnthropicJudge, fixed OpenAI)
- ✅ `tests/test_authenticity_judge.py` (new - 9 tests)
- ✅ `tests/test_sampling.py` (new - 14 tests)

### Phase 2: Sampling Logic ✅ COMPLETE

**Deliverables:**
- ✅ Scenario selection algorithms (random, stratified, errors, extremes, on_failure)
- ✅ Cost estimation function
- ✅ CLI flags for sample rate and strategy
- ✅ Budget guardrails

**Files:**
- ✅ `src/alignmenter/calibration/sampling.py` (new - includes all 6 strategies + cost estimation)
- ✅ `src/alignmenter/cli.py` (updated in Phase 3)

### Phase 3: Diagnostic Commands ✅ COMPLETE

**Deliverables:**
- ✅ `calibrate validate --judge-sample` - Added judge support to existing validate command
- ✅ `calibrate diagnose-errors` - New command for error analysis with LLM judge
- ✅ `analyze-scenarios` - New command for scenario performance analysis
- ✅ Budget guardrails and sampling integration

**Files:**
- ✅ `src/alignmenter/cli.py` (updated - added judge parameters and 2 new commands)
- ✅ `src/alignmenter/calibration/validate.py` (updated - added _run_judge_analysis helper)
- ✅ `src/alignmenter/calibration/diagnose.py` (new)
- ✅ `src/alignmenter/calibration/analyze.py` (new)

### Phase 4: Reporting Integration ✅ COMPLETE

**Deliverables:**
- ✅ HTML report section for judge analysis with collapsible UI
- ✅ JSON export of judge results
- ✅ Agreement metrics (judge vs calibration)
- ✅ Cost tracking and visualization
- ✅ Disagreements table with reasoning

**Files:**
- ✅ `src/alignmenter/reporting/html.py` (updated - added `_render_judge_analysis_section`)
- ✅ `src/alignmenter/reporting/json_out.py` (updated - exports judge_analysis)

**Features Added:**
- Collapsible "LLM Judge Analysis" section in HTML reports
- Summary stats: sessions judged, agreement rate, total cost
- Judge configuration details (provider, strategy, sample rate)
- Disagreements table showing calibrated vs judge scores with reasoning
- Color-coded agreement rate (green ≥85%, yellow ≥70%, red <70%)
- Full judge data exported to report.json for programmatic access

### Phase 5: Documentation & Testing ✅ COMPLETE

**Deliverables:**
- ✅ Design document with use cases and examples
- ✅ Cost estimation tables and comparisons
- ✅ Unit tests for judge + sampling (23 tests)
- ✅ Integration tests with mock providers (4 tests)
- ✅ CLI command documentation
- ⏳ User guide and tutorials (in design doc)
- ⏳ Example workflows (in design doc)

**Files:**
- ✅ `docs/llm_judge_authenticity.md` (this doc - comprehensive design)
- ✅ `tests/test_authenticity_judge.py` (new - 9 tests)
- ✅ `tests/test_sampling.py` (new - 14 tests)
- ✅ `tests/test_judge_providers.py` (new - 4 tests)

**Test Coverage:**
- AuthenticityJudge initialization and configuration
- Session evaluation and score parsing
- JSON and markdown response handling
- Error handling and fallbacks
- Cost tracking and budget management
- All 6 sampling strategies
- Judge provider compatibility (OpenAI & Anthropic)
- Backward compatibility with SafetyScorer

---

## Configuration Examples

### Example 1: Validation After Calibration

```yaml
# validate_with_judge.yaml
authenticity:
  judge:
    enabled: true
    provider: "anthropic:claude-3-5-sonnet-20241022"
    sample_rate: 0.2
    strategy: "stratified"
    budget: 100
```

```bash
alignmenter calibrate validate \
  --labeled wendys_labeled.jsonl \
  --persona wendys_twitter.yaml \
  --config validate_with_judge.yaml
```

### Example 2: Error Diagnosis Only

```yaml
# diagnose_errors.yaml
authenticity:
  judge:
    enabled: true
    provider: "openai:gpt-4o-mini"  # Cheaper for diagnostics
    strategy: "errors"  # Only ambiguous scores
    budget: 50
```

```bash
alignmenter calibrate diagnose-errors \
  --labeled wendys_labeled.jsonl \
  --persona wendys_twitter.yaml \
  --config diagnose_errors.yaml
```

### Example 3: Scenario Performance Analysis

```yaml
# scenario_analysis.yaml
authenticity:
  judge:
    enabled: true
    provider: "anthropic:claude-3-5-sonnet-20241022"
    sample_per_scenario: 3  # 3 sessions per scenario tag
    budget: 200
```

```bash
alignmenter analyze-scenarios \
  --dataset wendys_dataset.jsonl \
  --persona wendys_twitter.yaml \
  --config scenario_analysis.yaml
```

---

## Success Metrics

**How do we measure success of this feature?**

1. **Adoption rate**: 20%+ of calibration runs use judge validation
2. **Diagnostic value**: Users report actionable insights from judge analysis
3. **Cost control**: Average cost per run < $0.50
4. **Accuracy**: Judge agreement with calibrated scores > 85%
5. **Explainability**: Judge reasoning helps users improve personas

---

## Open Questions

1. **Should we support multiple judges (ensemble)?**
   - Pro: Reduces variance, higher confidence
   - Con: 2-3x cost
   - Decision: Not in MVP, revisit if single judge is unreliable

2. **Should judge outputs be cached?**
   - Pro: Re-running same dataset is free
   - Con: Cache invalidation complexity
   - Decision: Yes, cache by (session_id + persona_id + judge_provider)

3. **Should we support local judge models?**
   - Pro: No API costs
   - Con: Quality may be lower, requires GPU
   - Decision: Not in MVP, but design with abstraction for future

4. **What if judge disagrees strongly with calibration?**
   - Flag for manual review
   - Generate detailed comparison report
   - Recommend recalibration

---

## Alternatives Considered

### Alternative 1: Turn-by-Turn Judging

**Rejected because:**
- Loses conversational context
- Much higher cost (3-6x more API calls)
- Tone appropriateness is context-dependent

### Alternative 2: Judge as Primary Scorer

**Rejected because:**
- Too slow for production (1-2s per scenario)
- Too expensive at scale
- Non-deterministic (harder to track regressions)
- Calibrated scoring already works great

### Alternative 3: Hybrid Scoring (Blend Judge + Calibration)

**Rejected because:**
- Adds complexity without clear benefit
- Calibrated system already achieves ROC-AUC 1.000
- Judge's value is explainability, not better scores

---

## Future Enhancements

**Not in MVP, but could be added later:**

1. **Multi-judge ensemble**: Run 2-3 judges and average
2. **Fine-tuned local judge**: Train lightweight model for persona-specific judging
3. **Active learning**: Judge suggests which scenarios to label next
4. **Calibration auto-tuning**: Judge analysis automatically adjusts weights
5. **Comparative analysis**: Judge multiple model outputs side-by-side
6. **Temporal drift detection**: Judge scores over time to detect voice degradation

---

## References

- **Safety Judge Design**: See `src/alignmenter/scorers/safety.py` for existing judge pattern
- **Calibration System**: See `calibration/README.md` for context
- **Wendy's Case Study**: See `case-studies/wendys-twitter/RESULTS.md` for calibration performance

---

**Next Steps:**
1. Review this document with team
2. Get approval on cost/scope tradeoffs
3. Begin Phase 1 implementation (core judge)
4. Test on Wendy's dataset to validate approach
