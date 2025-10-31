# Repository Guidelines

## Project Structure
- Core Python package, CLI, scorers, and providers live under `alignmenter/alignmenter/`.
- Configuration defaults, datasets, and persona packs reside in `alignmenter/configs/` and `alignmenter/datasets/`.
- Marketing site is a Next.js app in `marketing/`, with static export handled via `npm run export`.
- Tests are colocated under `alignmenter/tests/` and should mirror the package layout.
- CI workflows live in `.github/workflows/` (see `ci.yml`).

## Build, Test, and Development
- Create a virtual environment and install the toolkit in editable mode:
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  pip install -e alignmenter[dev]
  ```
- Run CLI from the repo root: `alignmenter run --model openai:gpt-4o-mini --dataset alignmenter/datasets/demo_conversations.jsonl`.
- Execute the test suite with `pytest` from the project root.
- Frontend:
  ```bash
  cd marketing
  npm install
  npm run dev
  ```
- Lint/format:
  - Python: `ruff check alignmenter` (formatting handled by Ruff settings in `pyproject.toml`).
  - Next.js: `npm run lint` inside `marketing/`.

## Coding Standards
- Python code follows Ruff/Black defaults: 4-space indent, snake_case for functions/variables, PascalCase for classes.
- Keep functions small and composable (“Unix-style”)—push heavy lifting into helpers that are easy to test.
- Prefer Pydantic models or dataclasses for structured data over loose dicts.
- CLI commands should validate inputs early and raise friendly Typer errors.
- JavaScript/TypeScript uses ESLint/Prettier defaults, camelCase for values, PascalCase for components, descriptive filenames.

## Testing Guidelines
- Tests assert behavior, not implementation details. Focus on verifying outputs and side effects.
- Place Python tests alongside the package namespace (`alignmenter/tests/…`) using `test_<feature>.py` naming.
- Use fixtures and helper factories to keep tests readable.
- Mock only external boundaries (network calls, file I/O) and leave core logic unmocked.
- Never skip failing tests to “get CI green.” Fix or remove tests that no longer apply.
- Mark slow/external tests with `@pytest.mark.integration`; keep unit tests fast and deterministic.
- For the marketing app, add Playwright or React Testing Library coverage as interactive components grow.

## Pull Requests & Commits
- Commits should be imperative and scoped (“Add OpenAI embedding provider”, “Fix dataset path resolution”).
- PR descriptions must summarize scope, list testing performed, link issues/tickets, and call out follow-up actions (e.g., “requires OPENAI_API_KEY secret in CI”).
- Ensure `pytest`, `ruff`, and marketing builds succeed locally before requesting review.
- Keep PRs focused; large refactors should be split across logical commits.

## Environment & Secrets
- Runtime configuration uses `alignmenter/config.py` (`pydantic-settings`). Use `.env` for local development and populate CI with `OPENAI_API_KEY`, `ALIGNMENTER_DEFAULT_MODEL`, etc.
- Do not hardcode secrets in code or tests. Rely on settings or fixtures to inject sensitive values.
- When adding new settings, expose sensible defaults and document required env vars in the PR.

## Performance & Safety Notes
- Authenticity/Stability scorers default to a deterministic hashed embedding. Switching to real embeddings (SentenceTransformers/OpenAI) can incur heavy downloads/API cost—cache results where possible.
- Guard external API usage with budgets/batch limits to avoid rate limiting; ensure tests mock these interactions.
- Maintain deterministic behavior by using the shared `stable_hash` helper instead of Python’s `hash()`.

These guidelines evolve with the project—if you spot gaps, update this document along with the code changes.
