"""HealthBench (OpenAI, MIT) → Alignmenter turn records.

HealthBench rows are physician-authored health conversations paired with rubric
criteria but NO reference answer — grading is rubric-based, not exact-match. So
each row becomes a *prompt session* (the conversation up to the turn the model
must answer); capture fills the assistant turn, and the physician rubrics ride in
the final user turn's ``metadata`` for a later rubric evaluator. Deterministic
safety checks (refusal / escalation / non-diagnostic scope) still score the
captured response for free.

Row shape (``oss_eval.jsonl``)::

    {"prompt": [{"role": "user", "content": "..."}, ...],
     "rubrics": [{"criterion": "...", "points": 5, "tags": [...]}, ...],
     "example_tags": ["theme:emergency_referrals", ...],
     "prompt_id": "abc123"}

The corpus is MIT-licensed but the user fetches it themselves — this adapter only
maps rows already read from a local file.
"""

from __future__ import annotations

import hashlib

_ROLES = {"user", "assistant"}


def _stable_id(prompt: list) -> str:
    """Deterministic id for rows without a prompt_id (content-addressed)."""
    raw = "\n".join(f"{m.get('role')}:{m.get('content')}" for m in prompt if isinstance(m, dict))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _theme_tags(example_tags) -> list[str]:
    """HealthBench axis tags (``theme:...``, ``physician_agreed_category:...``)
    pass through unchanged; a bare tag gets a ``theme:`` prefix so stratified
    sampling always has an axis to balance on."""
    tags: list[str] = []
    for t in example_tags or []:
        if isinstance(t, str) and t.strip():
            tags.append(t if ":" in t else f"theme:{t}")
    return tags


def healthbench_to_records(row: dict) -> list[dict]:
    """Map one HealthBench row to a list of turn records (empty list = skip)."""
    prompt = row.get("prompt")
    if not isinstance(prompt, list) or not prompt:
        return []

    msgs: list[tuple[str, str]] = []
    for m in prompt:
        if not isinstance(m, dict):
            return []
        role = m.get("role")
        content = m.get("content")
        if role not in _ROLES or not isinstance(content, str) or not content.strip():
            return []
        msgs.append((role, content))

    # The model answers the last turn; if it isn't a user turn there's nothing
    # to capture against, so skip the row rather than emit an ungradeable session.
    if msgs[-1][0] != "user":
        return []

    pid = row.get("prompt_id") or _stable_id(prompt)
    session_id = f"healthbench:{pid}"
    base_tags = ["source:healthbench", "group:healthbench", *_theme_tags(row.get("example_tags"))]

    records: list[dict] = []
    for i, (role, content) in enumerate(msgs):
        records.append(
            {
                "session_id": session_id,
                "turn_index": i + 1,
                "role": role,
                "text": content,
                "tags": list(base_tags),
                "persona_id": "reference",
            }
        )

    rubrics = [r for r in (row.get("rubrics") or []) if isinstance(r, dict)]
    records[-1]["metadata"] = {
        "benchmark": "healthbench",
        "prompt_id": pid,
        "example_tags": [t for t in (row.get("example_tags") or []) if isinstance(t, str)],
        "rubrics": rubrics,
    }
    return records
