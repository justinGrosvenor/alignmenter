"""Optional strict provider schemas preserve raw replies and single-dispatch accounting."""
import json

import httpx
import pytest
from openai import APIStatusError, OpenAI

from alignmenter.providers.durable_judge import ChatCompletionJudge
from alignmenter.schemas.evaluation import JudgeRequest


def schema():
    return {"type": "object", "properties": {"reason": {"type": ["string", "null"]}},
            "required": ["reason"], "additionalProperties": False}


@pytest.mark.parametrize("mode", ["schema", "json", "text"])
def test_explicit_schema_and_legacy_modes_preserve_raw_response(mode):
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "test", "object": "chat.completion", "created": 0,
            "model": "fixture", "choices": [{"index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": '{"reason":null}'}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenAI(api_key="fixture-unused", base_url="http://fixture.invalid/v1", http_client=http_client)
        original = schema()
        judge = ChatCompletionJudge(client=client, model="fixture", revision="v1", json_mode=mode != "text",
                                    response_schema=original if mode == "schema" else None)
        digest = judge.contract.configuration_digest
        original["required"].clear()  # Caller mutation must not change a frozen judge's wire contract.
        reply = judge.evaluate(JudgeRequest(system="Grade.", prompt="Fixture."))
    assert len(calls) == 1 and reply.text == '{"reason":null}'
    assert reply.usage["total_tokens"] == 5 and judge.contract.configuration_digest == digest
    if mode == "schema":
        form = calls[0]["response_format"]
        assert form["type"] == "json_schema" and form["json_schema"]["strict"] is True
        assert form["json_schema"]["schema"]["required"] == ["reason"]
    elif mode == "json":
        assert calls[0]["response_format"] == {"type": "json_object"}
    else:
        assert "response_format" not in calls[0]


def test_schema_is_in_cache_identity_and_retries_stay_disabled():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(429, json={"error": {"message": "Fixture rate limit"}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenAI(api_key="fixture-unused", base_url="http://fixture.invalid/v1", http_client=http_client, max_retries=7)
        legacy = ChatCompletionJudge(client=client, model="fixture", revision="v1")
        strict = ChatCompletionJudge(client=client, model="fixture", revision="v1", response_schema=schema())
        assert legacy.contract.configuration_digest != strict.contract.configuration_digest
        with pytest.raises(APIStatusError):
            strict.evaluate(JudgeRequest(system="Grade.", prompt="Fixture."))
    assert len(calls) == 1 and strict.contract.max_dispatches_per_request == 1


@pytest.mark.parametrize("value", [[], {"type": "array"}, {"type": "object", "bad": float("nan")}])
def test_invalid_schema_rejected_before_dispatch(value):
    with httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail("No dispatch expected"))) as http_client:
        client = OpenAI(api_key="fixture-unused", base_url="http://fixture.invalid/v1", http_client=http_client)
        with pytest.raises((ValueError, TypeError)):
            ChatCompletionJudge(client=client, model="fixture", revision="v1", response_schema=value)
        with pytest.raises(ValueError, match="json_mode"):
            ChatCompletionJudge(client=client, model="fixture", revision="v1", json_mode=False, response_schema=schema())
