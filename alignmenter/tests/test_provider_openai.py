"""Tests for the OpenAI provider adapter."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from alignmenter.providers.base import parse_provider_model
from alignmenter.providers.openai import OpenAIProvider, OpenAICustomGPTProvider


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


class DummyResponsesClient:
    def __init__(self, response):
        self._response = response
        self.kwargs = None

    def create(self, **kwargs):  # pragma: no cover - trivial
        self.kwargs = kwargs
        return self._response


class DummyGPTClient:
    def __init__(self, response):
        self.responses = DummyResponsesClient(response)


def test_openai_custom_gpt_provider_chat() -> None:
    response = SimpleNamespace(
        output_text=None,
        output=[{"content": [{"text": "Hello from GPT"}]}],
        usage={"prompt_tokens": 42, "completion_tokens": 8, "total_tokens": 50},
    )
    client = DummyGPTClient(response)
    provider = OpenAICustomGPTProvider.from_model_identifier(
        "openai-gpt:gpt://brand-voice-chef",
        client=client,
    )

    result = provider.chat([{"role": "user", "content": "Hi"}])

    assert client.responses.kwargs["model"] == "gpt://brand-voice-chef"
    assert result.text == "Hello from GPT"
    assert result.usage == {"prompt_tokens": 42, "completion_tokens": 8, "total_tokens": 50}
