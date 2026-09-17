"""Dataset manifest + canonical record validation for dataset management.

Datasets are flat JSONL of turn records (see datasets/README.md). `validate_records`
is a schema validator: lenient by default (matching what capture requires —
session_id + role + text, unique turn_index per session), `strict=True` adds
turn_index + tags + persona_id and an assistant turn per session. It complements
`dataset lint`, which additionally checks turn-index contiguity, scenario-tag
coverage, and persona-file existence. `DatasetManifest` gives a dataset a
content-addressed identity + provenance so a curated set can be versioned and its
lineage tracked.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from pydantic import AwareDatetime, Field

from alignmenter.schemas.evaluation import NonBlank
from alignmenter.schemas.execution import (
    Digest,
    NonNegativeInt,
    VersionedRecord,
    content_digest,
    utc_now,
)

ROLES = {"user", "assistant"}


def dataset_digest(records) -> str:
    """Order-independent content hash of a dataset (same records, any order → same digest).

    content_digest sorts dict keys but preserves list order, so hashing the record
    list directly would change when rows are merely reordered. Hashing the sorted
    per-record digests gives a stable content identity for versioning/verification.

    Note: this is distinct from RunManifest.dataset_digest (runner.py), which is the
    order-SENSITIVE content_digest(records) used for run reproducibility — don't
    compare the two.
    """
    return content_digest(sorted(content_digest(r) for r in records))


class ProvenanceEntry(VersionedRecord):
    kind: NonBlank  # authored | bootstrap | import | merge | dedupe | split | promote
    ref: str = ""  # source path / url / description
    count: NonNegativeInt = 0
    digest: str | None = None


class DatasetManifest(VersionedRecord):
    id: NonBlank
    revision: NonBlank
    content_digest: Digest
    record_count: NonNegativeInt
    session_count: NonNegativeInt
    created_at: AwareDatetime = Field(default_factory=utc_now)
    tags: dict[str, int] = Field(default_factory=dict)
    personas: dict[str, int] = Field(default_factory=dict)
    provenance: tuple[ProvenanceEntry, ...] = ()


def build_manifest(records, *, id: str, revision: str, provenance=()) -> DatasetManifest:
    """Content-address a record list into a DatasetManifest (order-independent digest)."""
    dicts = [r for r in records if isinstance(r, dict)]
    sessions = {r.get("session_id") for r in dicts if r.get("session_id")}
    tags = Counter(t for r in dicts for t in (r.get("tags") or []) if isinstance(t, str))
    personas = Counter(r["persona_id"] for r in dicts if isinstance(r.get("persona_id"), str))
    return DatasetManifest(
        id=id,
        revision=revision,
        content_digest=dataset_digest(records),
        record_count=len(records),
        session_count=len(sessions),
        tags=dict(tags),
        personas=dict(personas),
        provenance=tuple(provenance),
    )


def validate_records(records, *, strict: bool = False) -> list[str]:
    """Return a list of human-readable schema errors (empty == valid).

    Default rules match ingest (session_id + role + text; turn_index optional but,
    when present, a non-negative int unique within its session). ``strict`` adds the
    lint contract: turn_index + tags + persona_id required, and every session must
    have an assistant turn.
    """
    errors: list[str] = []
    seen_turns: dict[str, set[int]] = defaultdict(set)
    session_roles: dict[str, set] = defaultdict(set)

    for i, r in enumerate(records):
        loc = f"record {i}"
        if not isinstance(r, dict):
            errors.append(f"{loc}: not a JSON object")
            continue
        sid = r.get("session_id")
        if not isinstance(sid, str) or not sid.strip():
            errors.append(f"{loc}: missing or blank session_id")
        role = r.get("role")
        if role not in ROLES:
            errors.append(f"{loc}: role must be one of {sorted(ROLES)} (got {role!r})")
        if not isinstance(r.get("text"), str):
            errors.append(f"{loc}: text must be a string")

        ti = r.get("turn_index")
        if ti is not None:
            if isinstance(ti, bool) or not isinstance(ti, int) or ti < 0:
                errors.append(f"{loc}: turn_index must be a non-negative int")
            elif isinstance(sid, str):
                if ti in seen_turns[sid]:
                    errors.append(f"{loc}: duplicate turn_index {ti} in session {sid!r}")
                seen_turns[sid].add(ti)

        tags = r.get("tags")
        if tags is not None and not (isinstance(tags, list) and all(isinstance(t, str) for t in tags)):
            errors.append(f"{loc}: tags must be a list of strings")
        md = r.get("metadata")
        if md is not None and not isinstance(md, dict):
            errors.append(f"{loc}: metadata must be an object")

        if isinstance(sid, str) and role in ROLES:
            session_roles[sid].add(role)

        if strict:
            if ti is None:
                errors.append(f"{loc}: turn_index is required in --strict mode")
            if not isinstance(tags, list):
                errors.append(f"{loc}: tags is required in --strict mode")
            if not isinstance(r.get("persona_id"), str):
                errors.append(f"{loc}: persona_id is required in --strict mode")

    if strict:
        for sid, roles in session_roles.items():
            if "assistant" not in roles:
                errors.append(f"session {sid!r}: has no assistant turn (--strict)")
    return errors
