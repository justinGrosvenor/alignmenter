"""Resolve visible passages without silently repairing or compacting retrieval evidence."""

from alignmenter.schemas.scoring import EvidenceBundle, Passage

ALIASES = ("excerpts", "passages", "documents", "sources", "context")


def evidence_bundle(answer, context, history):
    if not isinstance(context, dict):
        return None
    collection = next((context[k] for k in ALIASES if k in context), None)
    if not isinstance(collection, list):
        return None
    passages = []
    for index, item in enumerate(collection, 1):
        provider_id = None
        if isinstance(item, str):
            body = item
        elif isinstance(item, dict):
            body = next((item[k] for k in ("text", "content", "body") if k in item), None)
            raw_id = item.get("id")
            provider_id = str(raw_id) if isinstance(raw_id, (str, int)) and not isinstance(raw_id, bool) else None
        else:
            return None
        if not isinstance(body, str) or not body.strip():
            return None
        passages.append(Passage(source_id=f"passage:{index}", text=body, provider_id=provider_id))
    question = next((t for t in reversed(history) if t["role"] == "user"), None)
    if question is None:
        return None
    return EvidenceBundle(answer=answer, question=question["content"],
                          question_source_id=question["source_id"], passages=passages)


def supporting_sources(data: EvidenceBundle) -> dict[str, str]:
    # Earlier assistant assertions are not independent evidence for new claims.
    return {data.question_source_id: data.question, **{p.source_id: p.text for p in data.passages}}
