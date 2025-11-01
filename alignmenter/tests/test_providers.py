"""Tests for provider caching wrappers."""

from alignmenter.providers.embeddings import CachedEmbeddingProvider
from alignmenter.providers.judges import CachedJudgeProvider


class DummyEmbedder:
    name = "dummy"

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts):
        self.calls += len(texts)
        return [[float(len(text))] for text in texts]


class DummyJudge:
    name = "dummy"

    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, prompt: str) -> dict:
        self.calls += 1
        return {"score": 0.5, "notes": prompt}


def test_cached_embedding_provider_reuses_vectors():
    base = DummyEmbedder()
    provider = CachedEmbeddingProvider(base)

    provider.embed(["alpha", "beta"])
    assert base.calls == 2

    provider.embed(["alpha", "beta", "gamma"])
    # only "gamma" should trigger a new embed
    assert base.calls == 3


def test_cached_judge_provider_reuses_evaluations():
    base = DummyJudge()
    provider = CachedJudgeProvider(base)

    provider.evaluate("prompt")
    provider.evaluate("prompt")
    assert base.calls == 1

    provider.evaluate("other")
    assert base.calls == 2
