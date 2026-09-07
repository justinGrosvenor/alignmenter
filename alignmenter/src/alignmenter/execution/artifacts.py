"""Derived capture exports shared by fresh and resumed runs."""

from alignmenter.schemas.execution import Stream
from alignmenter.storage.runs import RunStore
from alignmenter.utils.io import write_jsonl


def model_slug(identifier: str | None) -> str:
    if not identifier:
        return "model"
    slug = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in identifier)
    return slug.strip("_") or "model"


def transcript_filename(model: str, stream: Stream, primary_model: str) -> str:
    slug = model_slug(model)
    prefix = "compare_" if stream == "compare" and slug == model_slug(primary_model) else ""
    return f"{prefix}{slug}.jsonl"


def export_capture(store: RunStore) -> None:
    targets = store.manifest().targets
    primary = next(t.model for t in targets if t.stream == "primary")
    for target in targets:
        path = store.run_dir / "transcripts" / transcript_filename(target.model, target.stream, primary)
        write_jsonl(path, store.transcripts(target.stream))
