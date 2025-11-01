# Alignmenter Monorepo

This workspace houses the Alignmenter evaluation toolkit and the public marketing site.

## Projects

- `alignmenter/` — Python package + CLI scaffold for running authenticity, safety, and stability audits.
- `marketing/` — Next.js + Tailwind marketing site that introduces the product and links to demos/docs.

## Getting Started

### CLI Toolkit (`alignmenter/`)

```bash
cd alignmenter
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env  # configure API keys/defaults
alignmenter --help

# Useful helpers
alignmenter persona scaffold --name "Brand Voice"
alignmenter persona export --dataset datasets/demo_conversations.jsonl --format labelstudio --out annotation_tasks.json
alignmenter dataset lint datasets/demo_conversations.jsonl --strict
alignmenter run --judge openai:gpt-4o-mini --judge-budget 5
alignmenter run --config alignmenter/configs/demo_config.yaml
```

Environment variables are loaded from `.env` (see `.env.example`). Common overrides:

- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` – enable LLM providers for chat, embeddings, judges.
- `ALIGNMENTER_EMBEDDING_PROVIDER` – e.g., `sentence-transformer:all-MiniLM-L6-v2`.
- `ALIGNMENTER_JUDGE_PROVIDER` / `ALIGNMENTER_JUDGE_BUDGET` – configure safety LLM moderation.
- `ALIGNMENTER_DEFAULT_MODEL`, `ALIGNMENTER_DEFAULT_DATASET`, etc. – change CLI defaults without flags.

### Marketing Site (`marketing/`)

```bash
cd marketing
npm install
npm run dev
```

Deploy the marketing app with Vercel/Netlify or any Node host. Build with `npm run build` before deploying.

Refer to `docs/alignmenter_requirements.md` for the canonical product specification spanning both experiences.
