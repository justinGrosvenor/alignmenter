"""Dataset importers: adapt public eval corpora into Alignmenter turn records.

Each importer is a pure ``row -> list[record]`` mapper registered by name.
``import_corpus`` owns the shared concerns — session-level sampling (optionally
stratified so a small sample keeps topic coverage), deterministic ordering, and a
counts report — so an adapter only has to describe the mapping.

Importers never download: the corpora are fetched and licensed by the user, then
this maps rows already read from a local JSONL. New corpora (K-QA, MedSafetyBench)
add a module + one ``IMPORTERS`` entry.
"""

from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Callable, Iterable

from alignmenter.importers.healthbench import healthbench_to_records

Mapper = Callable[[dict], list[dict]]

# name -> (row mapper, default stratification tag-prefix)
IMPORTERS: dict[str, tuple[Mapper, str]] = {
    "healthbench": (healthbench_to_records, "theme:"),
}


def available() -> list[str]:
    return sorted(IMPORTERS)


def get_importer(name: str) -> tuple[Mapper, str]:
    """Return (mapper, default_stratify_prefix); raises KeyError if unknown."""
    return IMPORTERS[name]


def _session_of(records: list[dict]) -> str:
    return records[0].get("session_id", "") if records else ""


def _stratum_of(records: list[dict], prefix: str) -> str:
    for r in records:
        for tag in r.get("tags") or []:
            if isinstance(tag, str) and tag.startswith(prefix):
                return tag
    return "(none)"


def _stratified_sample(
    sessions: list[list[dict]], sample: int, prefix: str, rng: random.Random
) -> list[list[dict]]:
    """Round-robin across strata (shuffled within each) for even coverage."""
    buckets: dict[str, list[list[dict]]] = defaultdict(list)
    for s in sessions:
        buckets[_stratum_of(s, prefix)].append(s)
    for b in buckets.values():
        rng.shuffle(b)
    keys = sorted(buckets)
    picked: list[list[dict]] = []
    i = 0
    while len(picked) < sample and any(buckets[k] for k in keys):
        key = keys[i % len(keys)]
        if buckets[key]:
            picked.append(buckets[key].pop())
        i += 1
    return picked


def import_corpus(
    rows: Iterable[dict],
    mapper: Mapper,
    *,
    sample: int | None = None,
    seed: int = 42,
    stratify_prefix: str | None = None,
) -> tuple[list[dict], dict]:
    """Map ``rows`` to turn records, optionally down-sampling whole sessions.

    Returns ``(records, report)``. Output is ordered by session_id so the content
    digest is stable regardless of input order. ``report`` carries input/skip/
    session counts and the per-stratum breakdown of what was kept.
    """
    sessions: list[list[dict]] = []
    total = 0
    skipped = 0
    for row in rows:
        total += 1
        recs = mapper(row) if isinstance(row, dict) else []
        if recs:
            sessions.append(recs)
        else:
            skipped += 1

    report: dict = {"input_rows": total, "skipped": skipped, "sessions_in": len(sessions)}

    if sample is not None and sample < len(sessions):
        rng = random.Random(seed)
        if stratify_prefix:
            sessions = _stratified_sample(sessions, sample, stratify_prefix, rng)
        else:
            rng.shuffle(sessions)
            sessions = sessions[:sample]

    sessions.sort(key=_session_of)
    records = [r for s in sessions for r in s]

    strata: dict[str, int] = defaultdict(int)
    axis = stratify_prefix or "theme:"
    for s in sessions:
        strata[_stratum_of(s, axis)] += 1
    report["sessions_out"] = len(sessions)
    report["records_out"] = len(records)
    report["strata"] = dict(sorted(strata.items()))
    return records, report
