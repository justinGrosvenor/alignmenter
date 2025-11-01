"""Tests for provider caching wrappers and loaders."""

from unittest.mock import Mock

import pytest

from alignmenter.providers.embeddings import CachedEmbeddingProvider, load_embedding_provider
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


def test_load_embedding_provider_hashed_fallback() -> None:
    provider = load_embedding_provider(None)
    vectors = provider.embed(["foo", "foo"])
    assert vectors[0] == vectors[1]


def test_load_embedding_provider_sentence_transformer(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy_model = Mock()
    dummy_model.encode.side_effect = lambda texts, convert_to_numpy=False: [[float(len(t))] for t in texts]
    monkeypatch.setattr("alignmenter.providers.embeddings.SentenceTransformer", lambda name: dummy_model)

    provider = load_embedding_provider("sentence-transformer:dummy-model")
    vectors = provider.embed(["foo", "foo"])

    assert vectors[0] == [3.0]
    provider.embed(["foo"])
    # second embed uses cached value, so underlying model should not run again
    assert dummy_model.encode.call_count == 1
