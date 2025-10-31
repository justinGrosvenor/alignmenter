"""Tests for the OpenAI provider adapter."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from alignmenter.providers.base import parse_provider_model
from alignmenter.providers.openai import OpenAIProvider


def test_parse_provider_model_valid() -> None:
    provider, model = parse_provider_model("openai:gpt-4o-mini")
    assert provider == "openai"
    assert model == "gpt-4o-mini"


def test_parse_provider_model_invalid() -> None:
    with pytest.raises(ValueError):
        parse_provider_model("gpt-4o-mini")


class DummyClient:
    def __init__(self, response):
        self._response = response

    class _Chat:
        def __init__(self, response):
            self._response = response

        class _Completions:
            def __init__(self, response):
                self._response = response

            def create(self, **_):
                return self._response

        @property
        def completions(self):
            return DummyClient._Chat._Completions(self._response)

    @property
    def chat(self):
        return DummyClient._Chat(self._response)


def test_openai_provider_chat() -> None:
    choice = SimpleNamespace(message=SimpleNamespace(content="Hello"))
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    response = SimpleNamespace(choices=[choice], usage=usage)
    provider = OpenAIProvider(model="gpt-4o-mini", client=DummyClient(response))

    result = provider.chat(messages=[{"role": "user", "content": "Hi"}])

    assert result.text == "Hello"
    assert result.usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
