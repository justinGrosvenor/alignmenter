# Alignmenter

Alignmenter is the evaluation stack for teams that care about brand voice and AI safety in the same breath. Ship AI copilots and chat experiences that feel on-brand, stay safe, and remain stable over time.

- **Authenticity** – quantify how closely an AI response matches your approved persona packs.
- **Safety** – blend keyword guards, optional LLM judges, and budget tracking to keep conversations on the rails.
- **Stability** – track drift across sessions with deterministic embeddings and variance-based scoring.

---

## Open Source Model

Alignmenter is built as **open core**:

- The CLI, scorers, report generators, persona packs, and dataset tooling in `alignmenter/` ship under Apache-2.0. Use them locally, customize them, or run them in your own CI.
- The hosted dashboard, collaboration features, audit trails, and billing live in a separate private repo. Cloud access is how we monetize, while the open tooling earns trust and community contributions.

If you want to run Alignmenter in production today, start with the CLI and get in touch for hosted features.

---

## Repository Guide

- `alignmenter/` – Python package and Typer-based CLI. Includes providers, scorers, reporters, and the run pipeline.
- `docs/` – Canonical requirements, product notes, and research supporting the roadmap.

Refer to `docs/alignmenter_requirements.md` for the full product spec.

---

## Quickstart

### CLI (Python 3.11+)

```bash
cd alignmenter
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
alignmenter init  # collect API keys, judge budgets, and create a starter config
alignmenter --help

# useful commands
alignmenter persona scaffold --name "Brand Voice"
alignmenter persona export \
  --dataset datasets/demo_conversations.jsonl \
  --format labelstudio \
  --out annotation_tasks.json
alignmenter import gpt \
  --name "AlignmenterGPT" \
  --instructions gpt_instructions.txt \
  --out alignmenter/configs/persona/alignmentergpt.yaml
alignmenter dataset lint datasets/demo_conversations.jsonl --strict
alignmenter run --model openai-gpt:brand-voice --config alignmenter/configs/init_run.yaml
alignmenter run --config alignmenter/configs/demo_config.yaml
# Sync Custom GPT metadata via API access (see notes below)
alignmenter persona sync-gpt gpt://brand/voice --out alignmenter/configs/persona/_gpt/brand.yaml
```

### First Run (2 minutes)

1. `alignmenter init` – answers a short wizard that captures API keys (with the option to skip writing them to disk), surfaces curated chat-model/embedding choices, sets judge budgets, and writes `alignmenter/configs/run.yaml`.
2. `alignmenter run --config alignmenter/configs/run.yaml` – executes the authenticity/safety/stability pipeline using your settings.
3. (Optional) `alignmenter import gpt --instructions gpt_instructions.txt --out configs/persona/your_gpt.yaml` – paste your GPT Builder instructions into a text file and Alignmenter will create a persona pack from it. If your OpenAI workspace has Custom GPT API access, `alignmenter persona sync-gpt gpt://your-gpt-id` still works and skips the copy/paste step.
4. (Optional) `python -m alignmenter.scripts.run_openai_demo` – kicks off a one-off OpenAI-backed run using the config generated during `init`.

Environment configuration is handled via `.env` + [pydantic-settings](alignmenter/src/alignmenter/config.py). Alignmenter always prefers real environment variables (e.g. `export OPENAI_API_KEY=...`); during `alignmenter init` you can opt in to saving secrets to `alignmenter/.env` for convenience. Notable variables:

- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` – enable hosted chat/judge providers.
- `ALIGNMENTER_EMBEDDING_PROVIDER` – e.g. `sentence-transformer:all-MiniLM-L6-v2`.
- `ALIGNMENTER_JUDGE_PROVIDER`, `ALIGNMENTER_JUDGE_BUDGET` – default LLM judge and per-run dollar cap.
- `ALIGNMENTER_DEFAULT_MODEL`, `ALIGNMENTER_DEFAULT_DATASET` – CLI fallback values when flags are omitted.

Run tests with `pytest` from the `alignmenter/` directory (virtualenv required).

### Custom GPT Importer Notes

- The `alignmenter import gpt` command expects a plaintext export of your GPT’s "Instructions" (and optional knowledge bullets). Alignmenter extracts exemplars, lexicon hints, and safety rules automatically, creating a persona pack you can edit by hand.
- OpenAI’s Custom GPT metadata API is currently gated. When API access is unavailable, `alignmenter persona sync-gpt gpt://...` will fall back to the importer workflow and prompt you to supply the instructions file instead of failing silently.
- Once a persona pack exists, reference it in `configs/run.yaml` or via `--persona` to score authenticity against that GPT’s voice.

## Contributing

We welcome issues and pull requests! Start with the public CLI code:

1. Fork and branch off `main`.
2. Keep functions small and composable—Unix-style pipelines are encouraged.
3. Run `ruff` + `pytest` before opening a PR.

For larger roadmap ideas, open a discussion first so we can align on scope.

---

## License

The CLI and supporting libraries are licensed under [Apache License 2.0](LICENSE). Hosted and proprietary cloud components are not part of this repo.
