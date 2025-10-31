"""Token helpers."""

from __future__ import annotations

import hashlib


def estimate_tokens(text: str) -> int:
    raise NotImplementedError("Token estimation not implemented.")


def stable_hash(token: str, buckets: int = 512) -> int:
    digest = hashlib.blake2s(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % buckets
