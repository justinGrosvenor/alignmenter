"""Run a quick OpenAI-backed Alignmenter demo."""

from __future__ import annotations

import os
from pathlib import Path
from subprocess import CalledProcessError, run

DEFAULT_CONFIG = Path("configs/openai_demo.yaml")


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    env_file = project_root / ".env"

    if not os.getenv("OPENAI_API_KEY") and not _env_has_key(env_file, "OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY not found. Run `alignmenter init` or export the key before running the demo."
        )

    demo_config = project_root / DEFAULT_CONFIG
    if not demo_config.exists():
        _write_config(demo_config, project_root)

    try:
        run(["alignmenter", "run", "--config", str(demo_config.relative_to(project_root))], check=True)
    except CalledProcessError as exc:  # pragma: no cover - passthrough
        raise SystemExit(exc.returncode)


def _env_has_key(path: Path, key: str) -> bool:
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            return True
    return False


def _write_config(config_path: Path, project_root: Path) -> None:
    reports_dir = project_root / "reports"
    dataset = project_root / "datasets" / "demo_conversations.jsonl"
    persona = project_root / "configs" / "persona" / "default.yaml"
    keywords = project_root / "configs" / "safety_keywords.yaml"

    config = {
        "run_id": "openai_demo",
        "model": os.getenv("ALIGNMENTER_DEFAULT_MODEL", "openai:gpt-4o-mini"),
        "dataset": str(dataset.relative_to(project_root)),
        "persona": str(persona.relative_to(project_root)),
        "keywords": str(keywords.relative_to(project_root)),
        "embedding": os.getenv("ALIGNMENTER_EMBEDDING_PROVIDER", "hashed"),
        "scorers": {
            "safety": {
                "offline_classifier": "auto",
                "judge": {
                    "provider": os.getenv("ALIGNMENTER_JUDGE_PROVIDER", "openai:gpt-4o-mini"),
                    "budget": int(os.getenv("ALIGNMENTER_JUDGE_BUDGET", "10")),
                    "budget_usd": float(os.getenv("ALIGNMENTER_JUDGE_BUDGET_USD", "1.0")),
                },
            }
        },
        "report": {"out_dir": str(reports_dir.relative_to(project_root)), "include_raw": True},
    }

    import yaml

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)


if __name__ == "__main__":
    main()
