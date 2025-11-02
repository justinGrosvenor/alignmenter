"""Token helpers."""

from __future__ import annotations

import hashlib
from functools import lru_cache

try:  # pragma: no cover - optional dependency
    import tiktoken
except ImportError:  # pragma: no cover
    tiktoken = None  # type: ignore


def estimate_tokens(text: str, encoding: str = "cl100k_base") -> int:
    """Estimate token count for *text* using tiktoken when available."""

    if not text:
        return 0

    encoder = _get_encoder(encoding)
    if encoder is None and encoding != "gpt-3.5-turbo":
        encoder = _get_encoder("gpt-3.5-turbo")

    if encoder is not None:
        try:
            return len(encoder.encode(text))
        except Exception:  # pragma: no cover - defensive fallback
            pass

    # Lightweight fallback: rough approximation by whitespace tokens
    return max(1, len(text.split()))


@lru_cache(maxsize=4)
def _get_encoder(name: str):
    if tiktoken is None:
        return None
    try:
        return tiktoken.get_encoding(name)
    except Exception:  # pragma: no cover - invalid encoding name
        return None


def stable_hash(token: str, buckets: int = 512) -> int:
    digest = hashlib.blake2s(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % buckets
