# Alignmenter: Requirements Document

## 0. Brand & Identity

**Product Name:** Alignmenter
**Domain:** [alignmenter.com](https://alignmenter.com)

**Taglines**
- "Alignmenter: measure what your model stands for."
- "The open-source alignment linter for AI."
- "Quantify tone, trust, and truth."
- "Alignmenter: audits your AI's authenticity."

**Brand Essence**
Alignmenter is an open-source evaluation suite for AI systems. It brings the rigor of software linting to AI alignment, quantifying how models behave, communicate, and remain authentic over time.

**Voice and Tone**
Professional yet transparent. Write with clarity, accountability, and evidence; avoid hype. The brand speaks as a peer to engineers and researchers, not as marketing copy.

**Visual Direction**
Minimal geometric aesthetics with converging lines forming an **A** shape to symbolize alignment. Neutral palette (grays/whites) with a bright signal-green or electric-blue accent conveying precision and trust.

## 1. Purpose
Alignmenter is an open, portable evaluation suite for chatbots and LLM apps. It measures authenticity, safety, and stability so teams can quickly audit model behavior and compare versions. The first release must demo value with a single command and produce a shareable report.

## 2. Goals
- **Fast demo**: `alignmenter demo` (or `make demo`) runs on a small dataset against a chosen model endpoint and outputs an HTML report.
- **Portable**: Works with OpenAI, Anthropic, and local vLLM backends.
- **Opinionated metrics**: Authenticity (persona alignment), Safety, Stability (drift).
- **Reproducibility**: Deterministic dataset, config-driven runs, artifacts saved to disk.
- **Extensible**: Plug-in adapters for models, metrics, datasets, and reporters.

## 3. Non-Goals
- Hosting or serving models
- Full security certification
- Recreating production observability platforms
- Covering every eval task: focus on the 3 core metrics first

## 4. Primary Users
Applied ML engineers, product/brand owners, and researchers who need transparent, reproducible behavior audits.

## 5. Success Metrics
- Demo runs to completion in under 5 minutes on laptop
- Works on at least two providers
- All three core metrics render with version diff view
- 100% of runs produce self-contained `reports/<timestamp>/` artifacts
- Config-only changes cover common scenarios (no code edits)

## 6. Core Scenarios and Acceptance Criteria

### S1: Single Model Audit
- **Given** API key and model name
- **When** `alignmenter run --model openai:gpt-4o-mini`
- **Then** tool executes 10 short conversations, scores Authenticity, Safety, Stability, and writes `reports/<ts>/index.html`

### S2: Version Comparison
- **When** `alignmenter run --model openai:gpt-4o-mini --compare anthropic:claude-3-5`
- **Then** produces side-by-side aggregates and CSV deltas

### S3: Custom Persona Pack
- **When** `alignmenter run --persona configs/persona/goth_muse.yaml`
- **Then** Authenticity uses exemplars and lexicon from that pack

### S4: Local Model
- **When** `alignmenter run --model local:http://localhost:8000/v1/chat/completions`
- **Then** executes locally and logs latency/tokens/cost

## 7. System Overview

CLI -> Runner -> Provider Adapter -> Scorers -> Aggregator -> Reporters

- **Providers:** OpenAI, Anthropic, Local (OpenAI-compatible)
- **Scorers:** Authenticity, Safety, Stability
- **Reporters:** JSON + HTML
- **Datasets:** Small conversation packs

## 8. Data and Config

### 8.1 Conversation Schema (Parquet or JSONL)
```json
{
  "session_id": "s1",
  "turn_index": 1,
  "role": "assistant",
  "text": "response text",
  "tags": ["scenario:test"],
  "persona_id": "goth_muse"
}
```

### 8.2 Persona Pack (YAML)
```yaml
id: goth_muse_v1
display_name: Goth Muse
exemplars:
  - "soft-voiced, dry humor, a little spooky, never saccharine"
  - "keep it brief; prefer concrete words to abstractions"
lexicon:
  preferred: ["sardonic", "velvet", "low-light", "quiet", "ritual"]
  avoid: ["awesome!!!", "super excited", "lol"]
style_rules:
  sentence_length: {max_avg: 16}
  contractions: {allowed: true}
  emojis: {allowed: false}
safety_rules:
  disallowed_topics: ["self-harm instructions", "hate"]
  brand_notes: "elegant, no camp"
```

- **Starter template**: ship `configs/persona/default.yaml` as a neutral voice for teams without a brand pack. A `alignmenter persona scaffold --name "Acme"` helper populates display name, exemplar scaffold, and lexicon prompts.
- **Generation guidance**: optionally call `openai:gpt-4o-mini` with a company brief to request exemplars; the command saves drafts to `configs/persona/generated/` for review before activation. Use `alignmenter persona export --format labelstudio` when preparing batches for Label Studio review.

### 8.3 Run Config (YAML)
```yaml
run_id: demo_gpt4o_vs_claude
dataset: datasets/demo_conversations.jsonl
providers:
  primary: openai:gpt-4o-mini
  compare: anthropic:claude-3-5
persona_pack: configs/persona/goth_muse.yaml
scorers:
  authenticity:
    embedding_model: intfloat/e5-small-v2
    threshold_warn: 0.72
  safety:
    keyword_lists: configs/safety_keywords.yaml
    judge:
      enabled: true
      provider: openai:gpt-4o-mini
      budget_usd: 0.05
      price_per_1k_input: 0.015
      price_per_1k_output: 0.06
      estimated_tokens_per_call: 900
      max_parallel: 4
  stability:
    window: 3
    variance_warn: 0.12
report:
  out_dir: reports/
  include_raw: true
```

### 8.4 Dataset Hygiene
- Default demo set is synthetic. When importing live transcripts, require contributors to run `scripts/sanitize_dataset.py` to remove PII, replace identifiers with hashed placeholders, and tag consent status in `tags`.
- Maintain a `datasets/README.md` outlining provenance, licensing, and anonymization steps for each pack.
- Provide `alignmenter dataset lint --path <file>` to validate schema, persona coverage, and safety traps before a run. Add `--strict` when teams need sequential turn checks, role coverage per session, and explicit `scenario:*` tag enforcement.

## 9. Metric Definitions

### 9.1 Authenticity Score
Formula:
`Auth = 0.6 * style_sim + 0.25 * traits + 0.15 * lexicon`

- **style_sim**: cosine similarity between response embedding and persona exemplars using `intfloat/e5-small-v2`.
- **traits**: fine-tuned logistic regression on labelled persona statements. Traits are calibrated per persona; `scripts/calibrate_persona.py` fits coefficients against a small QA set and exports JSON weights.
- **lexicon**: normalized count difference of preferred vs avoided phrases; uses stemming and case-folding.
- **Calibration**: Every persona pack includes at least 25 labelled turns (pass/fail). Authenticity CI bands derived from bootstrap resampling with fixed seed.
- **Sourcing guidance**: Recommended workflow—start with internal brand guidelines, draft 10 exemplar prompts per persona, collect 30-40 human-reviewed responses (pass/fail labels). Provide a `docs/persona_annotation.md` template describing tone traits, disallowed phrases, and review rubric. Offer `alignmenter persona export --format csv` to prep annotation batches for tools like Label Studio.

### 9.2 Safety Score
`Safety = min(1 - violation_rate, judge_score)`
- Combines rule-based heuristics with optional LLM judge ratings. Judge prompts stored in `configs/judges/safety_prompt.txt` and versioned.
- Offline fallback enables a `distilled_safety_roberta` classifier when budgets or connectivity restrict LLM judging.
- Open-source fallback model sourced from Hugging Face (e.g., "ProtectAI/distilled-safety-roberta"); installer verifies license compatibility and pins model hash. Document tokenizer/model cache location so security teams can review before adoption.
- Agreement target >= 0.8 Cohen's kappa across judge ensemble; mismatches flagged in report calibration section.

### 9.3 Stability (Drift) Score
- Within-session drift: 1 minus normalized variance of response embeddings across turns.
- Across-run drift: cosine difference between responses from two model versions.

### 9.4 Cost and Latency
- Logged per turn if available from provider, else estimated.

### 9.5 Judge Cost Model
- Estimated judge cost per run = `num_calls * ((prompt_tokens/1000) * price_per_1k_input + (completion_tokens/1000) * price_per_1k_output)`.
- CLI prints projected spend before execution based on `estimated_tokens_per_call` and dataset size; users confirm when projected cost exceeds `judge.budget_usd`.
- Budget guardrails halt judging once 90% of `judge.budget_usd` is consumed; remaining turns fall back to rule-based scores with warning badges in report.

## 10. Interfaces

### CLI
```bash
alignmenter run --model openai:gpt-4o-mini --dataset datasets/demo.jsonl --persona configs/persona/goth_muse.yaml --out reports/
alignmenter run --model openai:gpt-4o-mini --compare anthropic:claude-3-5
alignmenter report --last
alignmenter persona scaffold --name "Acme Voice"
alignmenter persona export --dataset datasets/demo_conversations.jsonl --out annotation.csv
alignmenter dataset lint datasets/demo_conversations.jsonl
```

### Provider Interface
```python
class ChatProvider(Protocol):
    name: str
    def chat(self, messages: list[dict], **kwargs) -> dict: ...
    def tokenizer(self) -> Optional[Tokenizer]: ...
```

### Scorer Interface
```python
class Scorer(Protocol):
    id: str
    def score(self, sessions: list[Session]) -> ScoreBundle: ...
```

## 11. Artifact Layout

```
reports/<timestamp>/
  run.json
  results.json
  aggregates.json
  index.html
  raw/
```

## 12. Result Schema (Excerpt)
```json
{
  "run_id": "demo_001",
  "model": "openai:gpt-4o-mini",
  "compare_model": "anthropic:claude-3-5",
  "aggregates": {
    "authenticity": {"mean": 0.83, "ci95": [0.79, 0.87]},
    "safety": {"mean": 0.95},
    "stability": {"mean": 0.88}
  }
}
```

## 13. Demo Dataset
10 sessions with 6 turns each, including brand, tone, and safety traps.

- Synthetic transcripts derived from original prompts in `datasets/demo_conversations.jsonl`. No third-party data included.
- Import checklist: confirm consent, strip user-identifiable tokens, and record provenance in dataset metadata block.
- Provide `scripts/bootstrap_dataset.py` to create balanced samples and inject optional adversarial safety turns.

## 14. Report Specification

**Sections:**
1. Overview
2. Headline Scores
3. Version Comparison
4. Turn-Level Explorer
5. Cost and Latency
6. Calibration
7. Reproducibility

Each chart independent and exportable. Color-coded pass/warn/fail bands.

## 15. Integrations
- OpenAI / Anthropic SDKs
- Local OpenAI-compatible endpoints
- Future: LangSmith, Arize Phoenix adapters

## 16. Security & Privacy
- Never upload user data by default
- Redact API keys
- Optional PII scrub for logs
- `.env` support for keys

## 17. Licensing
- Code: Apache 2.0
- Datasets: CC-BY 4.0
- Persona packs: open contribution with attribution

## 18. Performance Targets
- Demo runtime under 5 minutes on laptop
- Memory under 1 GB
- Retry on network failure
- Graceful budget handling for judges

## 19. Testing
- Unit tests for scorers
- Provider mocks for CI
- Snapshot tests for HTML reports
- `make test` runs all

## 20. Risks and Mitigations

### Technical Risks
- **Judge variance:** Average multiple calls with fixed seed. Note that achieving Cohen's kappa >= 0.8 across judge ensemble may be optimistic; budget time for tuning prompts and establishing realistic agreement thresholds.
- **Embedding bias:** Allow alternate models, provide calibration script.
- **Metric validity:** Publish metric cards and ablations. The Authenticity formula weights (0.6 * style_sim + 0.25 * traits + 0.15 * lexicon) require empirical validation against human brand judgments before hardcoding.

### Adoption Risks
- **Differentiation from existing tools:** Many eval frameworks exist (OpenAI Evals, HELM, BIG-bench). Authenticity is novel but narrow. Validate early that target users will invest setup effort (persona packs, 25+ labeled turns per persona) for this metric.
- **Competitive positioning:** Maintain a comparison matrix in `docs/competitive_landscape.md` contrasting Alignmenter against OpenAI Evals, LangSmith, Phoenix. Highlight unique persona authenticity scoring and budget-aware judge flows. Update quarterly as incumbents ship similar features.
- **User champion identification:** ML engineers prefer familiar frameworks; brand/product teams may lack embedding/calibration expertise. Identify which persona will champion adoption within target organizations and tailor onboarding accordingly.
- **LLM-as-judge concerns:** Using models to evaluate safety introduces its own biases and error modes. Document judge limitations transparently and provide strong rule-based fallbacks.
- **Scope clarity:** Stability metrics currently assume text-only conversations without tool calls or multimodal payloads. Explicitly label tool-call/multimodal auditing as post-M3 roadmap to avoid mismatched expectations during pilots.

## 21. Milestones

| Milestone | Deliverables |
|------------|--------------|
| **M0** | CLI + demo dataset + Authenticity v1 + HTML report v0 |
| **M1** | Safety + Stability metrics, JSON output |
| **M2** | Multi-provider support, version diff view |
| **M3** | Persona calibration notebook, docs, CI green badge |

## 22. Repo Layout

```
alignmenter/
  alignmenter/
    cli.py
    runner.py
    providers/
      openai.py
      anthropic.py
      local.py
    scorers/
      authenticity.py
      safety.py
      stability.py
    reports/
      html.py
      json_out.py
    utils/
      io.py
      tokens.py
  configs/
    persona/goth_muse.yaml
    safety_keywords.yaml
    demo_config.yaml
  datasets/
    demo_conversations.jsonl
  scripts/
    calibrate_persona.py
  tests/
  Makefile
  pyproject.toml
  README.md
  LICENSE
marketing/
  app/
  components/
  public/
  package.json
```

## 23. Makefile Targets

```
make venv
make quickstart
make demo
make test
make report-last
```

## 24. Roadmap After Launch
- RAG grounding adapter
- Public leaderboard publishing
- More persona packs and metrics
- LangSmith/Phoenix trace plugins
- Optional telemetry for metric tuning
