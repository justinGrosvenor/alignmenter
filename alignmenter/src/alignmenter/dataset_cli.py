"""Dataset-management commands: stats, validate, dedupe, merge, split, manifest.

Registered onto the existing `dataset` sub-app (alongside lint/sanitize/bootstrap)
via register_dataset_commands(dataset_app). Builds on the shared primitives
(content_digest, read/write_jsonl) and schemas/dataset.py.
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import typer

from alignmenter.schemas.dataset import (
    ProvenanceEntry,
    build_manifest,
    dataset_digest,
    validate_records,
)
from alignmenter.schemas.execution import content_digest
from alignmenter.utils.io import read_jsonl, write_json, write_jsonl


def _group_key(record: dict, by: str) -> str:
    """Grouping key for split — keeps a case + its variants on the same side."""
    if not isinstance(record, dict):
        return ""  # non-dict rows group together (like the other commands, don't crash)
    metadata = record.get("metadata") or {}
    session = record.get("session_id") or ""
    if by == "split_group":
        return str(metadata.get("split_group") or session)
    if by == "group":
        for tag in record.get("tags") or []:
            if isinstance(tag, str) and tag.startswith("group:"):
                return tag
        return session
    if by == "persona":
        return str(record.get("persona_id") or session)
    return session


def register_dataset_commands(dataset_app: typer.Typer) -> None:
    @dataset_app.command("stats")
    def stats(
        path: Path = typer.Argument(..., exists=True, dir_okay=False),
        as_json: bool = typer.Option(False, "--json", help="Emit the coverage report as JSON."),
    ):
        """Coverage report — record/session counts, role balance, tag + persona histograms."""
        records = read_jsonl(path)
        manifest = build_manifest(records, id=path.stem, revision="stats")
        roles = Counter(r.get("role") for r in records if isinstance(r, dict))
        with_context = sum(
            1 for r in records
            if isinstance(r, dict) and isinstance(r.get("metadata"), dict) and "context" in r["metadata"]
        )
        if as_json:
            typer.echo(json.dumps({
                "records": manifest.record_count, "sessions": manifest.session_count,
                "roles": {k: v for k, v in roles.items()}, "with_context": with_context,
                "tags": manifest.tags, "personas": manifest.personas,
                "content_digest": manifest.content_digest,
            }, indent=2))
            return
        typer.echo(f"records {manifest.record_count} · sessions {manifest.session_count} · turns-with-context {with_context}")
        typer.echo("roles: " + ", ".join(f"{k}={v}" for k, v in sorted(roles.items(), key=lambda kv: str(kv[0]))))
        if manifest.tags:
            typer.echo("tags:  " + ", ".join(f"{k}={v}" for k, v in sorted(manifest.tags.items())))
        if manifest.personas:
            typer.echo("personas: " + ", ".join(f"{k}={v}" for k, v in sorted(manifest.personas.items())))
        typer.echo(f"content_digest: {manifest.content_digest[:12]}…")

    @dataset_app.command("validate")
    def validate(
        path: Path = typer.Argument(..., exists=True, dir_okay=False),
        strict: bool = typer.Option(False, "--strict", help="Require turn_index+tags+persona_id and an assistant turn per session."),
    ):
        """Schema validator — lenient by default, --strict adds turn_index+tags+persona_id + an assistant turn per session.

        Complements `dataset lint`, which additionally checks turn-index contiguity,
        scenario-tag coverage, and persona-file existence.
        """
        records = read_jsonl(path)
        errors = validate_records(records, strict=strict)
        for error in errors:
            typer.echo(error, err=True)
        typer.echo(f"{len(records)} records, {len(errors)} error(s)")
        raise typer.Exit(1 if errors else 0)

    @dataset_app.command("dedupe")
    def dedupe(
        path: Path = typer.Argument(..., exists=True, dir_okay=False),
        out: Path | None = typer.Option(None, "--out", help="Output path (default: <stem>.dedup.jsonl)."),
        in_place: bool = typer.Option(False, "--in-place"),
    ):
        """Drop content-identical duplicate records (order preserved)."""
        records = read_jsonl(path)
        seen: set[str] = set()
        kept = []
        for record in records:
            digest = content_digest(record)
            if digest in seen:
                continue
            seen.add(digest)
            kept.append(record)
        destination = path if in_place else (out or path.with_name(f"{path.stem}.dedup.jsonl"))
        write_jsonl(destination, kept)
        typer.echo(f"removed {len(records) - len(kept)} duplicate(s); wrote {len(kept)} -> {destination}")

    @dataset_app.command("merge")
    def merge(
        paths: list[Path] = typer.Argument(..., exists=True, dir_okay=False),
        out: Path = typer.Option(..., "--out"),
        dedupe: bool = typer.Option(False, "--dedupe", help="Drop content-identical records after merging."),
        namespace_sessions: bool = typer.Option(False, "--namespace-sessions", help="Prefix session_id with the source file stem to avoid collisions."),
    ):
        """Concatenate datasets into one (optionally dedupe / namespace session ids)."""
        merged: list[dict] = []
        for source in paths:
            records = read_jsonl(source)
            if namespace_sessions:
                for record in records:
                    if isinstance(record, dict) and record.get("session_id"):
                        record["session_id"] = f"{source.stem}:{record['session_id']}"
            merged.extend(records)
        if dedupe:
            seen: set[str] = set()
            deduped = []
            for record in merged:
                digest = content_digest(record)
                if digest in seen:
                    continue
                seen.add(digest)
                deduped.append(record)
            merged = deduped
        write_jsonl(out, merged)
        typer.echo(f"merged {len(paths)} file(s) -> {len(merged)} records -> {out}")

    @dataset_app.command("split")
    def split(
        path: Path = typer.Argument(..., exists=True, dir_okay=False),
        out: Path = typer.Option(..., "--out", help="Output directory for train.jsonl + holdout.jsonl."),
        holdout: float = typer.Option(0.2, "--holdout", min=0.0, max=1.0, help="Target holdout fraction of records."),
        by: str = typer.Option("split_group", "--by", help="Grouping unit kept together: split_group | group | session | persona."),
        seed: int = typer.Option(42, "--seed"),
    ):
        """Group-aware train/holdout split — a case and its variants never straddle the boundary."""
        if by not in {"split_group", "group", "session", "persona"}:
            raise typer.BadParameter("--by must be split_group, group, session, or persona")
        records = read_jsonl(path)
        groups: dict[str, list[dict]] = defaultdict(list)
        for record in records:
            groups[_group_key(record, by)].append(record)
        names = sorted(groups)
        random.Random(seed).shuffle(names)
        target = holdout * len(records)
        held: set[str] = set()
        accumulated = 0
        for name in names:
            if accumulated >= target:
                break
            held.add(name)
            accumulated += len(groups[name])
        train = [r for r in records if _group_key(r, by) not in held]
        holdout_records = [r for r in records if _group_key(r, by) in held]
        write_jsonl(Path(out) / "train.jsonl", train)
        write_jsonl(Path(out) / "holdout.jsonl", holdout_records)
        typer.echo(
            f"train {len(train)} · holdout {len(holdout_records)} "
            f"({len(held)}/{len(names)} '{by}' groups) -> {out}"
        )

    @dataset_app.command("manifest")
    def manifest(
        path: Path = typer.Argument(..., exists=True, dir_okay=False),
        out: Path | None = typer.Option(None, "--out", help="Write the manifest JSON here (default: stdout)."),
        identifier: str | None = typer.Option(None, "--id", help="Dataset id (default: file stem)."),
        revision: str = typer.Option("v1", "--revision"),
        verify: Path | None = typer.Option(None, "--verify", help="Verify the data still matches this manifest's content_digest."),
    ):
        """Build (or --verify) a content-addressed dataset manifest with provenance."""
        records = read_jsonl(path)
        if verify is not None:
            try:
                expected = json.loads(Path(verify).read_text()).get("content_digest")
            except (json.JSONDecodeError, OSError) as exc:
                raise typer.BadParameter(f"Could not read manifest {verify}: {exc}") from exc
            actual = dataset_digest(records)
            match = expected == actual
            typer.echo(f"{'OK' if match else 'MISMATCH'}: manifest {str(expected)[:12]} vs data {actual[:12]}")
            raise typer.Exit(0 if match else 2)
        built = build_manifest(
            records,
            id=identifier or path.stem,
            revision=revision,
            provenance=(ProvenanceEntry(kind="authored", ref=str(path), count=len(records), digest=dataset_digest(records)),),
        )
        payload = built.model_dump(mode="json")
        if out is not None:
            write_json(out, payload)
            typer.echo(f"wrote manifest -> {out}")
        else:
            typer.echo(json.dumps(payload, indent=2))
