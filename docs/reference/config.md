# Configuration Reference

Complete reference for Alignmenter configuration files.

## Run Configuration

Run configs (`.yaml`) specify evaluation parameters.

### Full Example

```yaml
# configs/brand.yaml
model: "openai:gpt-4o"
persona: "configs/persona/brand.yaml"
dataset: "datasets/test_conversations.jsonl"

evaluation:
  # Score thresholds (fail if below)
  min_authenticity: 0.80
  min_safety: 0.95
  min_stability: 0.85

  # Metric weights (for overall score)
  authenticity_weight: 0.5
  safety_weight: 0.3
  stability_weight: 0.2

generation:
  # Only if --no-generate not specified
  temperature: 0.7
  max_tokens: 500
  top_p: 1.0

safety:
  # Keyword patterns to check
  violation_patterns:
    - "hate_speech"
    - "violence"
    - "self_harm"

  # Offline classifier (if installed)
  use_offline_classifier: false

judge:
  # Optional LLM judge
  enabled: false
  provider: "openai:gpt-4o-mini"
  sample_rate: 0.2
  budget: 1.00
  strategy: "random"  # random, on_failure, stratified

output:
  dir: "reports/"
  format: "html"  # html, json, csv
  include_json: true
  include_csv: true
  open_browser: true

reproducibility:
  seed: 42
  cache_responses: true
```

---

## Persona Configuration

Personas define your brand voice.

### Full Example

```yaml
# configs/persona/brand.yaml
id: brand-assistant
name: "Brand Assistant"
version: "1.0.0"
description: "Professional, helpful, evidence-driven support bot"

voice:
  tone:
    - professional
    - helpful
    - precise
    - friendly

  formality: business_casual  # formal, business_casual, casual

  verbosity: balanced  # concise, balanced, detailed

  lexicon:
    preferred:
      - "I'd be happy to"
      - "let me assist you"
      - "based on our analysis"
      - "the data indicates"

    avoided:
      - "no problem"
      - "sure thing"
      - "absolutely"
      - "lol"
      - "hype"

examples:
  - "I'd be happy to help you with that request. Let me look into the details."
  - "Based on our analysis, the baseline performance shows a 15% improvement."
  - "The data indicates strong signal across all test cases."
  - "Let me assist you in finding the right solution for your needs."

traits:
  uses_evidence: true
  cites_sources: true
  asks_clarifying_questions: true
  maintains_context: true

guidelines:
  - "Always acknowledge the user's request before responding"
  - "Use data and examples to support claims"
  - "Avoid slang and overly casual language"
  - "Be precise but approachable"

anti_patterns:
  - "Don't use exclamation marks excessively"
  - "Avoid saying 'I think' or 'I feel'"
  - "Don't make unsupported claims"
```

### Persona Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier |
| `name` | string | Display name |
| `version` | string | Version number (for tracking changes) |
| `description` | string | Brief summary |
| `voice.tone` | list | Personality traits |
| `voice.formality` | enum | formal, business_casual, casual |
| `voice.verbosity` | enum | concise, balanced, detailed |
| `voice.lexicon.preferred` | list | Words to use |
| `voice.lexicon.avoided` | list | Words to avoid |
| `examples` | list | Reference responses |
| `traits` | dict | Boolean trait flags |
| `guidelines` | list | Behavioral rules |
| `anti_patterns` | list | What not to do |

---

## Dataset Format

Datasets are JSONL (one JSON object per line).

### Basic Format

```jsonl
{"session_id": "001", "turn": 1, "user": "Hello!", "assistant": "Hi! How can I help you today?"}
{"session_id": "001", "turn": 2, "user": "Tell me about your product", "assistant": "Our product is..."}
{"session_id": "002", "turn": 1, "user": "What's the weather?", "assistant": "I can help with that..."}
```

### Required Fields

- `session_id` (string) - Groups turns into conversations
- `turn` (int) - Order within session
- `user` (string) - User message

### Optional Fields

- `assistant` (string) - AI response (if cached, otherwise generated)
- `metadata` (object) - Custom fields
- `timestamp` (string) - ISO 8601 timestamp

### Extended Format

```json
{
  "session_id": "prod_001",
  "turn": 1,
  "user": "What's your refund policy?",
  "assistant": "Our refund policy allows returns within 30 days...",
  "metadata": {
    "user_id": "user_12345",
    "timestamp": "2025-11-06T14:32:00Z",
    "channel": "web_chat"
  }
}
```

### Special Cases

**Re-generation mode**: Omit `assistant` to generate fresh responses:
```jsonl
{"session_id": "001", "turn": 1, "user": "Hello!"}
```

**ChatGPT export**: Use `alignmenter dataset convert`:
```bash
alignmenter dataset convert chatgpt_export.json dataset.jsonl --from-format chatgpt
```

---

## Environment Variables

### API Keys

```bash
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Cache

```bash
export ALIGNMENTER_CACHE_DIR="~/.alignmenter/cache"
```

Default: `~/.cache/alignmenter/` on Linux/Mac, `%LOCALAPPDATA%\alignmenter\` on Windows.

### Logging

```bash
export ALIGNMENTER_LOG_LEVEL="DEBUG"  # DEBUG, INFO, WARNING, ERROR
```

### Models

```bash
export ALIGNMENTER_DEFAULT_MODEL="openai:gpt-4o"
```

---

## Model Identifiers

### OpenAI

```
openai:gpt-4o
openai:gpt-4o-mini
openai:gpt-4-turbo
openai-gpt:custom-model-id  # Custom GPTs / fine-tunes
```

### Anthropic

```
anthropic:claude-3-5-sonnet-20241022
anthropic:claude-3-5-haiku-20241022
anthropic:claude-3-opus-20240229
```

### Local

```
local:vllm:localhost:8000/v1/completions
local:ollama:llama2
```

---

## Next Steps

- **[CLI Reference](cli.md)** - Command-line options
- **[Metrics Reference](metrics.md)** - Scoring formulas
- **[Persona Guide](../guides/persona.md)** - Creating personas
