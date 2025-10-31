# Persona Annotation Guide (Draft)

Use this template when gathering labeled examples for Authenticity calibration:

| Field | Description |
| --- | --- |
| Persona ID | Matches `configs/persona/<name>.yaml` |
| Turn Text | Assistant response evaluated |
| Pass/Fail | 1 if on-voice, 0 if off-voice |
| Notes | Rationale, references to lexicon/style rules |

## Suggested Workflow
1. Draft 10 exemplar prompts covering greetings, troubleshooting, sensitive topics.
2. Collect 30-40 assistant responses per persona.
3. Have two reviewers label pass/fail; log disagreements for calibration.
4. Use `alignmenter persona export --format csv` for spreadsheets or `--format labelstudio` to create ready-to-import JSON tasks for Label Studio.

Keep brand guidelines attached to the annotation packet so reviewers share a consistent rubric.
