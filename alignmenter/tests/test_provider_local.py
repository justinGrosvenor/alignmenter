"""Tests for the local OpenAI-compatible provider."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from alignmenter.providers.local import LocalProvider


def test_local_provider_from_identifier() -> None:
    provider = LocalProvider.from_identifier("local:http://localhost:8000/v1/chat/completions|llama-3")
    assert provider.endpoint == "http://localhost:8000/v1/chat/completions"
    assert provider.default_model == "llama-3"


def test_local_provider_requires_model() -> None:
    provider = LocalProvider(endpoint="http://localhost:8000/v1/chat/completions")
    with pytest.raises(ValueError):
        provider.chat([{"role": "user", "content": "hi"}])


def test_local_provider_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_post(url, json, headers, timeout):  # pragma: no cover - simple stub
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout

        fake_response = Mock()
        fake_response.raise_for_status.return_value = None
        fake_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "Hello world"},
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        return fake_response

    monkeypatch.setattr("alignmenter.providers.local.requests.post", fake_post)

    provider = LocalProvider(endpoint="http://localhost:8000/v1/chat/completions", model="llama-3")
    response = provider.chat([{"role": "user", "content": "hi"}], temperature=0.0)

    assert captured["url"] == "http://localhost:8000/v1/chat/completions"
    assert captured["json"]["model"] == "llama-3"
    assert captured["json"]["messages"][0]["content"] == "hi"
    assert captured["json"]["temperature"] == 0.0
    assert response.text == "Hello world"
    assert response.usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
