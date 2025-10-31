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
alignmenter --help

# Useful helpers
alignmenter persona scaffold --name "Brand Voice"
alignmenter persona export --dataset datasets/demo_conversations.jsonl --format labelstudio --out annotation_tasks.json
alignmenter dataset lint datasets/demo_conversations.jsonl --strict
```

### Marketing Site (`marketing/`)

```bash
cd marketing
npm install
npm run dev
```

Deploy the marketing app with Vercel/Netlify or any Node host. Build with `npm run build` before deploying.

Refer to `docs/alignmenter_requirements.md` for the canonical product specification spanning both experiences.
