"""Judge providers for safety and authenticity scoring."""

from __future__ import annotations

import json
import os
from typing import Optional, TYPE_CHECKING

try:  # pragma: no cover
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore

try:  # pragma: no cover
    from anthropic import Anthropic
except ImportError:  # pragma: no cover
    Anthropic = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    from openai import OpenAI as _OpenAI
    from anthropic import Anthropic as _Anthropic

from alignmenter.providers.base import JudgeProvider, parse_provider_model
from alignmenter.config import get_settings


class OpenAIJudge(JudgeProvider):
    """LLM judge using OpenAI responses.

    Returns raw model output in 'notes' field for full parsing by consumers
    (AuthenticityJudge needs reasoning/strengths/weaknesses, SafetyScorer needs score/notes).
    Also parses 'score' field for backward compatibility with SafetyScorer.
    """

    name = "openai"

    def __init__(self, model: str, client: Optional[OpenAI] = None) -> None:
        self.model = model
        if client is not None:
            # Use provided client (for testing or custom configurations)
            self._client = client
        else:
            # Create real client - requires openai package and API key
            if OpenAI is None:
                raise RuntimeError("The 'openai' package is required for OpenAI judges.")
            settings = get_settings()
            api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY is required for the safety judge. Set it via the environment or disable the judge."
                )
            self._client = OpenAI(api_key=api_key)

    @classmethod
    def from_identifier(cls, identifier: str, client: Optional[OpenAI] = None) -> OpenAIJudge:
        provider, model = parse_provider_model(identifier)
        if provider != cls.name:
            raise ValueError(f"Expected provider 'openai', got '{provider}'.")
        return cls(model=model, client=client)

    def evaluate(self, prompt: str) -> dict:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an evaluation assistant. Respond with valid JSON matching the schema requested in the user prompt.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or ""
        usage_payload = None
        if response.usage:
            usage_payload = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        # For backward compatibility with SafetyScorer, parse the score
        # But return RAW content in notes so AuthenticityJudge can parse all fields
        score = None
        try:
            data = json.loads(content)
            score = float(data.get("score", 0.0))
            score = max(0.0, min(1.0, score))
        except (json.JSONDecodeError, TypeError, ValueError):
            score = 0.0

        return {
            "score": score,
            "notes": content,  # Return raw content for full parsing by consumers
            "usage": usage_payload,
        }


class CachedJudgeProvider(JudgeProvider):
    """Caches judge evaluations per prompt."""

    def __init__(self, base: JudgeProvider) -> None:
        self._base = base
        self.name = base.name
        self._cache: dict[str, dict] = {}

    def evaluate(self, prompt: str) -> dict:
        if prompt not in self._cache:
            self._cache[prompt] = self._base.evaluate(prompt)
        return self._cache[prompt]


class AnthropicJudge(JudgeProvider):
    """LLM judge using Anthropic Claude.

    Returns raw model output in 'notes' field for full parsing by consumers
    (AuthenticityJudge needs reasoning/strengths/weaknesses, SafetyScorer needs score/notes).
    Also parses 'score' field for backward compatibility with SafetyScorer.
    """

    name = "anthropic"

    def __init__(self, model: str, client: Optional["_Anthropic"] = None) -> None:
        self.model = model
        if client is not None:
            # Use provided client (for testing or custom configurations)
            self._client = client
        else:
            # Create real client - requires anthropic package and API key
            if Anthropic is None:
                raise RuntimeError("The 'anthropic' package is required for Anthropic judges.")
            settings = get_settings()
            api_key = settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is required for the judge. Set it via the environment or disable the judge."
                )
            self._client = Anthropic(api_key=api_key)

    @classmethod
    def from_identifier(cls, identifier: str, client: Optional["_Anthropic"] = None) -> "AnthropicJudge":
        provider, model = parse_provider_model(identifier)
        if provider != cls.name:
            raise ValueError(f"Expected provider 'anthropic', got '{provider}'.")
        return cls(model=model, client=client)

    def evaluate(self, prompt: str) -> dict:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=2048,
            system="You are an evaluation assistant. Respond with valid JSON matching the schema requested in the user prompt.",
            messages=[
                {"role": "user", "content": prompt},
            ],
        )
        # Extract content from response
        content = ""
        if hasattr(response, "content") and isinstance(response.content, list):
            content = "".join(block.text for block in response.content if hasattr(block, "text"))
        elif hasattr(response, "content"):
            content = str(response.content)

        usage_payload = None
        if hasattr(response, "usage"):
            usage = response.usage
            usage_payload = {
                "prompt_tokens": getattr(usage, "input_tokens", None),
                "completion_tokens": getattr(usage, "output_tokens", None),
                "total_tokens": getattr(usage, "input_tokens", 0) + getattr(usage, "output_tokens", 0),
            }

        # For backward compatibility with SafetyScorer, parse the score
        # But return RAW content in notes so AuthenticityJudge can parse all fields
        score = None
        try:
            data = json.loads(content)
            score = float(data.get("score", 0.0))
            score = max(0.0, min(1.0, score))
        except (json.JSONDecodeError, TypeError, ValueError):
            score = 0.0

        return {
            "score": score,
            "notes": content,  # Return raw content for full parsing by consumers
            "usage": usage_payload,
        }


class NullJudge(JudgeProvider):
    """Fallback judge that always returns neutral response."""

    name = "none"

    def evaluate(self, prompt: str) -> dict:
        return {"score": 1.0, "notes": "Judge disabled."}


def load_judge_provider(identifier: Optional[str]) -> Optional[JudgeProvider]:
    """Load a judge provider from an identifier string.

    Args:
        identifier: Provider identifier (e.g., "openai:gpt-4o", "anthropic:claude-3-5-sonnet-20241022")

    Returns:
        JudgeProvider instance or None if identifier is empty/none
    """
    if identifier in (None, "", "none"):
        return None
    provider, _ = parse_provider_model(identifier)
    if provider == "openai":
        return CachedJudgeProvider(OpenAIJudge.from_identifier(identifier))
    if provider == "anthropic":
        return CachedJudgeProvider(AnthropicJudge.from_identifier(identifier))
    raise ValueError(f"Unsupported judge provider: {identifier}")
