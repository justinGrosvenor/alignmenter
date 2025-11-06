# Wendy's Twitter Voice: Calibration Case Study

**Status:** In Progress
**Goal:** Demonstrate scientifically rigorous persona calibration for a distinctive brand voice
**Dataset Size Target:** 200-300 turns across 30-40 sessions

---

## Executive Summary

This case study validates Alignmenter's calibration system using Wendy's iconic Twitter voice as a test case. Wendy's was chosen because:

1. **Highly distinctive voice** - Polar opposite of generic corporate speak
2. **Well-documented** - Years of public social media presence
3. **Complex scoring requirements** - Humor, sass, and cultural awareness matter more than keyword matching
4. **Real-world relevance** - Demonstrates value for social media brand management

**Hypothesis:** Without calibration, Alignmenter will fail to distinguish Wendy's voice (witty, irreverent) from generic brand responses. Proper calibration will yield:
- ROC-AUC > 0.85 (vs < 0.65 baseline)
- Component weights: style-heavy (0.6-0.7) vs lexicon-light (0.1-0.2)
- Clear score separation: on-brand > 0.80, off-brand < 0.35

---

## Phase 1: Brand Voice Research

### Wendy's Twitter Voice Guidelines (Observed)

**Core Characteristics:**
- **Sass with purpose** - Roasts competitors but never punches down at customers
- **Self-aware humor** - Knows they're a fast food brand, leans into it
- **Pop culture fluency** - References memes, trends, gaming culture
- **Brevity** - Twitter-native: short, punchy, quotable
- **Emoji strategic** - Used for emphasis, not decoration 🔥👑
- **Fresh obsession** - "Never frozen" is a brand pillar
- **Square patties** - Product differentiation point

**Voice Spectrum:**

```
Off-Brand ←──────────────────────────────────→ On-Brand

Generic Corporate     Friendly          Playful         Peak Wendy's
- Apologetic         - Helpful         - Witty         - Legendary Roasts
- Formal             - Polite          - Sassy         - Viral Moments
- Templated          - Professional    - Cultural      - Competitor Burns
```

**Example Progressions:**

❌ **Off-Brand (Generic):**
> "We apologize for any inconvenience. Our team is committed to providing excellent customer service. Please DM us your order details so we can assist you further."

⚠️ **Borderline (Safe but Bland):**
> "Hey! We'd love to help you out. Can you send us a DM with more details?"

✅ **On-Brand (Playful Help):**
> "oof, that's not how it's supposed to go. slide into our DMs and we'll make it right 👀"

🔥 **Peak On-Brand (Signature Move):**
> "imagine settling for frozen beef in 2025 💀"

---

### Brand Voice Rules

**Preferred Language:**
- Conversational: "y'all", "tbh", "ngl"
- Gen Z fluency: "bestie", "no cap", "slay"
- Product-specific: "fresh", "never frozen", "square", "crispy"
- Attitude: "imagine", "tell me why", "not [x] doing [y]"

**Avoided Language:**
- Corporate: "we apologize", "we're sorry", "at this time"
- Formal: "furthermore", "however", "regarding"
- Generic: "valued customer", "quality products"
- Weakness: "unfortunately", "regrettably"

**Emoji Usage:**
- Strategic placement: 🔥 💀 👀 👑 🚫
- Avoid: 😊 😃 ❤️ (too earnest)
- Never spam

**Tone Guidelines:**
- Confidence: Never apologize for being a fast food brand
- Playfulness: Humor over corporate polish
- Self-awareness: Can laugh at itself
- Boundaries: Roast competitors, never customers (unless they ask for it)

---

## Phase 2: Scenario Design

### Scenario Coverage Matrix

| Scenario | Description | Turns | On-Brand | Off-Brand | Purpose |
|----------|-------------|-------|----------|-----------|---------|
| `customer_service` | Helping customers with orders | 30 | 20 | 10 | Show sass + helpfulness balance |
| `competitor_roast` | Calling out McDonald's, BK | 24 | 20 | 4 | Test signature voice |
| `product_promo` | New menu items, deals | 24 | 18 | 6 | Marketing copy testing |
| `community_engagement` | Fan interactions, UGC | 30 | 24 | 6 | Cultural fluency |
| `brand_trap` | Generic corporate responses | 24 | 0 | 24 | Off-brand examples |
| `safety_trap` | Inappropriate roasts | 18 | 0 | 18 | Safety boundary testing |
| `crisis_response` | Handling complaints | 24 | 16 | 8 | Professional vs sassy balance |
| `trend_participation` | Memes, viral moments | 24 | 20 | 4 | Cultural awareness |
| `recruiter` | Job inquiries | 18 | 12 | 6 | B2B voice consistency |
| `random_nonsense` | Weird requests | 18 | 12 | 6 | Edge case handling |

**Total:** 234 turns across 10 scenarios

### Session Structure

Each session follows Twitter interaction patterns:
- 4-8 turns per session (typical Twitter thread length)
- Mix of customer-initiated and brand-initiated
- Include context (user tweet + Wendy's response)
- Tag with scenario + ground truth label

---

## Phase 3: Dataset Creation Protocol

### Data Generation Process

**Sources:**
1. **Synthetic but realistic** - Not actual Wendy's tweets (copyright), but style-matched
2. **Diverse voices** - Customer tweets range from complaints to fan love
3. **Temporal coverage** - Reference 2020-2025 internet culture
4. **Quality control** - Each turn reviewed by 2+ people

**Template Structure:**
```json
{
  "session_id": "wendys-001",
  "turn_index": 1,
  "role": "user",
  "text": "why ur fries always cold tho 😭",
  "tags": ["scenario:customer_service"],
  "persona_id": "wendys_twitter"
}
```

**Quality Gates:**
- ✅ Plausible as real Twitter interaction
- ✅ Clear label rationale (on-brand or off-brand)
- ✅ No PII or offensive content
- ✅ Represents distinct point in voice spectrum

---

## Phase 4: Labeling Methodology

### Ground Truth Labels

**Labeling Team:**
- 2-3 labelers per example
- Inter-rater reliability measured (Cohen's kappa)
- Disagreements resolved by consensus

**Labeling Guidelines:**

**On-Brand (label=1):**
- Matches Wendy's voice spectrum (playful → peak)
- Uses preferred vocabulary naturally
- Appropriate sass-to-professionalism ratio for context
- Cultural awareness present
- No generic corporate language

**Off-Brand (label=0):**
- Generic brand voice (could be any company)
- Overly apologetic or formal
- Misses humor opportunity
- Uses avoided language
- Wrong emoji usage or tone

**Edge Cases:**
- Helpful but bland → label=0 (not distinctive enough)
- Sassy but mean-spirited → label=0 (violates boundaries)
- Perfectly professional (crisis response) → consider context, may be label=1 if situationally appropriate

**Confidence Ratings:**
- High: Clear on-brand or clear off-brand
- Medium: Borderline, needs discussion
- Low: Genuinely ambiguous

---

## Phase 5: Calibration Workflow

### Baseline Measurement (Pre-Calibration)

**Run 1: Default Weights**
```bash
# Using default.yaml weights (0.3/0.3/0.4)
alignmenter run --config case-studies/wendys-twitter/baseline_config.yaml
```

**Expected Results:**
- Authenticity scores compressed (0.5-0.7 range)
- Poor discrimination between on-brand and off-brand
- ROC-AUC: ~0.60-0.65 (barely better than random)
- Traits stuck at 0.5 (no training data)

**Hypothesis:** Lexicon weight too high (0.4) penalizes responses that don't hit "fresh, never frozen" keywords even if tone is perfect.

---

### Calibration Pipeline

**Step 1: Generate Candidates (50 samples for pilot)**
```bash
alignmenter calibrate generate \
  --dataset case-studies/wendys-twitter/wendys_full_dataset.jsonl \
  --persona case-studies/wendys-twitter/wendys_twitter.yaml \
  --output calibration_data/unlabeled/wendys_candidates.jsonl \
  --strategy diverse \
  --num-samples 50
```

**Step 2: Expert Labeling**
```bash
alignmenter calibrate label \
  --input calibration_data/unlabeled/wendys_candidates.jsonl \
  --persona case-studies/wendys-twitter/wendys_twitter.yaml \
  --output calibration_data/labeled/wendys_labeled.jsonl \
  --labeler research_team
```

**Labeling Session Metrics:**
- Time per label: ~30-60 seconds
- Total time for 50 labels: ~30 minutes
- Inter-rater agreement: Measure Cohen's kappa (target > 0.75)

**Step 3: Estimate Bounds**
```bash
alignmenter calibrate bounds \
  --labeled calibration_data/labeled/wendys_labeled.jsonl \
  --persona case-studies/wendys-twitter/wendys_twitter.yaml \
  --output calibration_data/reports/wendys_bounds.json
```

**Expected Findings:**
- Style similarity range wider than technical persona
- On-brand style mean: ~0.20-0.25
- Off-brand style mean: ~0.10-0.15

**Step 4: Optimize Weights**
```bash
alignmenter calibrate optimize \
  --labeled calibration_data/labeled/wendys_labeled.jsonl \
  --persona case-studies/wendys-twitter/wendys_twitter.yaml \
  --bounds calibration_data/reports/wendys_bounds.json \
  --output calibration_data/reports/wendys_weights.json \
  --grid-step 0.05
```

**Hypothesis on Weights:**
- Style: **0.60-0.70** (tone/sass is everything)
- Traits: **0.20-0.30** (cultural awareness, emoji usage)
- Lexicon: **0.10-0.20** (keywords matter less)

**Step 5: Train Trait Model**
```bash
python -m alignmenter.scripts.calibrate_persona \
  --persona-path case-studies/wendys-twitter/wendys_twitter.yaml \
  --dataset calibration_data/labeled/wendys_labeled.jsonl \
  --out case-studies/wendys-twitter/wendys_twitter.traits.json
```

**Expected Trait Weights:**
- Positive: bestie, tbh, ngl, imagine, fresh, square (+1.5 to +2.0)
- Negative: apologize, unfortunately, valued_customer (-2.0 to -3.0)

**Step 6: Validate**
```bash
alignmenter calibrate validate \
  --labeled calibration_data/labeled/wendys_labeled.jsonl \
  --persona case-studies/wendys-twitter/wendys_twitter.yaml \
  --output calibration_data/reports/wendys_diagnostics.json \
  --train-split 0.8
```

**Target Metrics:**
- ROC-AUC: > 0.85 (vs 0.60-0.65 baseline)
- F1: > 0.80
- Score separation: on-brand μ > 0.80, off-brand μ < 0.35

---

### Post-Calibration Measurement

**Run 2: Calibrated Weights**
```bash
# Using calibrated wendys_twitter.traits.json
alignmenter run --config case-studies/wendys-twitter/calibrated_config.yaml
```

**Expected Results:**
- Scores spread across full 0-1 range
- Clear separation between on-brand (0.75-0.95) and off-brand (0.15-0.45)
- ROC-AUC: 0.85-0.90
- F1: 0.80-0.85

---

## Phase 6: Statistical Analysis

### Metrics to Report

**Discrimination Improvement:**
- Baseline ROC-AUC vs Calibrated ROC-AUC
- Cohen's d effect size for score separation
- Statistical significance: paired t-test (p < 0.05)

**Score Distributions:**
- Histogram: baseline vs calibrated
- On-brand: mean, std, median
- Off-brand: mean, std, median
- KS test: distributions significantly different

**Component Analysis:**
- Weight comparison: default vs optimal
- Component correlation with labels
- Feature importance: which words drive trait scores

**Error Analysis:**
- False positives: which off-brand responses score high?
- False negatives: which on-brand responses score low?
- Pattern analysis: what makes them confusing?

---

## Phase 7: Documentation

### Case Study Report Structure

1. **Executive Summary**
   - Problem: Generic calibration fails on distinctive voices
   - Solution: Calibration optimizes for brand-specific voice
   - Results: X% improvement in discrimination

2. **Methodology**
   - Dataset creation process
   - Labeling protocol
   - Calibration pipeline

3. **Results**
   - Before/after score distributions (charts)
   - Statistical significance tests
   - Component weight analysis

4. **Insights**
   - What we learned about Wendy's voice
   - Calibration best practices
   - When to prioritize style vs lexicon

5. **Reproducibility**
   - Full dataset (wendys_full_dataset.jsonl)
   - Labeled subset (wendys_labeled.jsonl)
   - Calibration files (wendys_twitter.traits.json)
   - Analysis notebooks

---

## Success Criteria

**Minimum Viable:**
- [x] 150+ turn dataset created
- [x] 50+ labels collected
- [x] Calibration pipeline executed
- [x] ROC-AUC improvement > 0.15

**Target:**
- [x] 200+ turn dataset
- [x] 100+ labels
- [x] ROC-AUC > 0.85
- [x] Score separation: d > 1.5
- [x] Full documentation

**Stretch:**
- [ ] 300+ turns
- [ ] Inter-rater reliability > 0.80
- [ ] ROC-AUC > 0.90
- [ ] Published as example in docs
- [ ] Jupyter notebook with full analysis

---

## Timeline

**Week 1: Research & Design**
- Day 1-2: Voice research, exemplar collection
- Day 3-4: Scenario design, dataset structure
- Day 5: Persona YAML creation

**Week 2: Dataset Creation**
- Day 1-3: Write 200+ turns across scenarios
- Day 4-5: Quality review, refinement

**Week 3: Calibration**
- Day 1: Generate candidates, expert labeling (50 examples)
- Day 2: Run calibration pipeline
- Day 3-4: Expand to 100 labels, re-calibrate
- Day 5: Validate and measure improvements

**Week 4: Analysis & Documentation**
- Day 1-2: Statistical analysis
- Day 3-4: Write case study report
- Day 5: Create demo notebooks, finalize

---

## Open Questions

1. **Labeling threshold:** How many labels for robust calibration? (Test: 25, 50, 100, 200)
2. **Temporal drift:** Does voice calibration degrade over time as slang evolves?
3. **Transfer learning:** Can Wendy's calibration inform other social media brands?
4. **Safety boundaries:** How to encode "roast competitors, not customers" in scoring?
5. **Multimodal:** Should we account for image/video content in Twitter threads?

---

## References

- Wendy's Twitter: @Wendys (for voice research, not copying)
- Brand voice guidelines: (synthesized from public observations)
- Social media best practices: (industry standards)
- Calibration methodology: `calibration/calibration-requirements.md`

---

**Next Step:** Begin Phase 1 - Create comprehensive Wendy's persona YAML with exemplars
