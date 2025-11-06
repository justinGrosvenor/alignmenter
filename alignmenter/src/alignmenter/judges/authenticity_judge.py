"""LLM judge for authenticity evaluation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from alignmenter.providers.base import JudgeProvider
from alignmenter.utils import load_yaml
from .prompts import format_authenticity_prompt

LOGGER = logging.getLogger(__name__)


# Pricing per 1M tokens (input, output) in USD
# Prices as of January 2025
PRICING_TABLE = {
    # OpenAI models
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4-turbo-preview": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    # Anthropic models
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-5-sonnet-20240620": (3.00, 15.00),
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    "claude-3-opus-20240229": (15.00, 75.00),
    "claude-3-sonnet-20240229": (3.00, 15.00),
    "claude-3-haiku-20240307": (0.25, 1.25),
}


def extract_json_from_text(text: str) -> str:
    """Extract JSON string from text that may contain markdown blocks or prose.

    Handles:
    - Raw JSON: {"score": 8, ...}
    - Markdown code block: ```json\n{...}\n```
    - Prose-wrapped JSON: "Here's my analysis: {...}"

    Args:
        text: Raw text possibly containing JSON

    Returns:
        Extracted JSON string

    Raises:
        ValueError: If no JSON object found in text
    """
    text = text.strip()

    # First, try to extract from markdown code blocks
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        return text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        return text[start:end].strip()

    # If no code block, try to find JSON object
    json_start = text.find("{")
    if json_start == -1:
        raise ValueError("No JSON object found in response")

    # Return from first brace to end (will be validated by json.loads)
    return text[json_start:]


@dataclass
class JudgeAnalysis:
    """LLM judge analysis of a scenario."""

    session_id: str
    score: float  # 0-10 scale
    reasoning: str
    strengths: list[str]
    weaknesses: list[str]
    suggestion: Optional[str]
    context_appropriate: bool
    calibrated_score: Optional[float] = None  # For comparison
    cost: Optional[float] = None  # API cost for this call


@dataclass
class JudgeCostSummary:
    """Summary of LLM judge API costs."""

    total_cost: float
    calls_made: int
    cost_per_call: float
    average_cost: float


class AuthenticityJudge:
    """LLM judge for evaluating brand voice authenticity across conversations."""

    def __init__(
        self,
        persona_path: Path,
        judge_provider: JudgeProvider,
        cost_per_call: float = 0.003,
    ) -> None:
        """Initialize the authenticity judge.

        Args:
            persona_path: Path to persona YAML file
            judge_provider: LLM provider for judging (OpenAI, Anthropic, etc.)
            cost_per_call: Estimated cost per judge API call in USD
        """
        self.persona_path = persona_path
        self.judge_provider = judge_provider
        self.cost_per_call = cost_per_call

        # Load persona data
        persona = load_yaml(persona_path) or {}
        self.persona_id = persona.get("id", "unknown")
        self.persona_description = persona.get("description", "")

        # Extract voice/style configuration
        # Try both "voice" and "style_rules" keys for compatibility
        voice = persona.get("voice", {})
        style_rules = persona.get("style_rules", {})

        # Normalize tone to a list (can be string or list in YAML)
        tone = voice.get("tone") or style_rules.get("tone", [])
        if isinstance(tone, str):
            self.persona_tone = [tone]
        elif isinstance(tone, list):
            self.persona_tone = tone
        else:
            self.persona_tone = []

        self.persona_formality = (
            voice.get("formality") or style_rules.get("formality", "Not specified")
        )

        # Extract lexicon (can be at top level or under voice)
        lexicon = persona.get("lexicon", voice.get("lexicon", {}))
        self.preferred_words = lexicon.get("preferred", [])
        self.avoided_words = lexicon.get("avoid", lexicon.get("avoided", []))

        # Extract exemplars (can be "examples" or "exemplars")
        self.exemplars = persona.get("exemplars", persona.get("examples", []))

        # Track costs
        self.total_cost = 0.0
        self.calls_made = 0

    def evaluate_session(
        self,
        session_id: str,
        turns: list[dict],
        scenario_tag: Optional[str] = None,
        calibrated_score: Optional[float] = None,
    ) -> JudgeAnalysis:
        """Evaluate a full conversation session for brand voice authenticity.

        Args:
            session_id: Session identifier
            turns: List of conversation turns (dicts with 'role' and 'text')
            scenario_tag: Optional scenario tag for context
            calibrated_score: Optional calibrated authenticity score for comparison

        Returns:
            JudgeAnalysis with score, reasoning, and suggestions
        """
        # Format the prompt
        prompt = format_authenticity_prompt(
            persona_id=self.persona_id,
            persona_description=self.persona_description,
            persona_tone=self.persona_tone,
            persona_formality=self.persona_formality,
            preferred_words=self.preferred_words,
            avoided_words=self.avoided_words,
            exemplars=self.exemplars,
            scenario_tag=scenario_tag or "untagged",
            session_id=session_id,
            conversation_turns=turns,
        )

        # Call the judge
        try:
            response = self.judge_provider.evaluate(prompt)
            self.calls_made += 1

            # Extract cost from usage if available
            call_cost = self._calculate_cost(response.get("usage"))
            self.total_cost += call_cost

            # Parse the response
            analysis = self._parse_response(
                session_id=session_id,
                response_text=response.get("notes", ""),
                calibrated_score=calibrated_score,
                cost=call_cost,
            )

            return analysis

        except Exception as e:
            LOGGER.error(f"Judge evaluation failed for session {session_id}: {e}")
            # Return a default analysis on failure
            return JudgeAnalysis(
                session_id=session_id,
                score=5.0,  # Neutral score
                reasoning=f"Judge evaluation failed: {str(e)}",
                strengths=[],
                weaknesses=[],
                suggestion=None,
                context_appropriate=True,
                calibrated_score=calibrated_score,
                cost=0.0,
            )

    def _parse_response(
        self,
        session_id: str,
        response_text: str,
        calibrated_score: Optional[float],
        cost: float,
    ) -> JudgeAnalysis:
        """Parse the JSON response from the judge.

        Args:
            session_id: Session identifier
            response_text: Raw response text from judge
            calibrated_score: Optional calibrated score for comparison
            cost: API cost for this call

        Returns:
            Parsed JudgeAnalysis
        """
        try:
            # Extract JSON from response (handles markdown, prose, etc.)
            json_str = extract_json_from_text(response_text)

            # Parse JSON with fallback for incomplete objects
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                # Use JSONDecoder for partial JSON extraction
                decoder = json.JSONDecoder()
                data, _ = decoder.raw_decode(json_str)

            score = float(data.get("score", 5.0))
            reasoning = data.get("reasoning", "No reasoning provided")
            strengths = data.get("strengths", [])
            weaknesses = data.get("weaknesses", [])
            suggestion = data.get("suggestion")
            context_appropriate = data.get("context_appropriate", True)

            # Ensure lists are actually lists
            if not isinstance(strengths, list):
                strengths = [str(strengths)] if strengths else []
            if not isinstance(weaknesses, list):
                weaknesses = [str(weaknesses)] if weaknesses else []

            # Clamp score to 0-10 range
            score = max(0.0, min(10.0, score))

            return JudgeAnalysis(
                session_id=session_id,
                score=score,
                reasoning=reasoning,
                strengths=strengths,
                weaknesses=weaknesses,
                suggestion=suggestion if suggestion else None,
                context_appropriate=context_appropriate,
                calibrated_score=calibrated_score,
                cost=cost,
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            LOGGER.warning(f"Failed to parse judge response for {session_id}: {e}")
            LOGGER.debug(f"Raw response: {response_text[:200]}")

            # Fallback: return neutral analysis
            return JudgeAnalysis(
                session_id=session_id,
                score=5.0,
                reasoning=f"Failed to parse response: {response_text[:100]}",
                strengths=[],
                weaknesses=[],
                suggestion=None,
                context_appropriate=True,
                calibrated_score=calibrated_score,
                cost=cost,
            )

    def _calculate_cost(self, usage: Optional[dict]) -> float:
        """Calculate cost from usage data using provider-specific pricing.

        Args:
            usage: Usage dict with prompt_tokens, completion_tokens

        Returns:
            Actual or estimated cost in USD
        """
        if not usage:
            LOGGER.debug("No usage data - using flat estimate: $%.4f", self.cost_per_call)
            return self.cost_per_call

        # Get model name from provider
        model_name = getattr(self.judge_provider, "model", None)
        if not model_name:
            LOGGER.debug(
                "Provider has no model attribute - using flat estimate: $%.4f",
                self.cost_per_call,
            )
            return self.cost_per_call

        # Look up pricing
        pricing = PRICING_TABLE.get(model_name)
        if not pricing:
            LOGGER.warning(
                "No pricing data for model '%s' - using flat estimate: $%.4f",
                model_name,
                self.cost_per_call,
            )
            return self.cost_per_call

        # Calculate real cost from token counts
        input_price_per_million, output_price_per_million = pricing
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        cost = (
            (prompt_tokens / 1_000_000) * input_price_per_million
            + (completion_tokens / 1_000_000) * output_price_per_million
        )

        LOGGER.debug(
            "Cost for %s: %d input + %d output tokens = $%.4f",
            model_name,
            prompt_tokens,
            completion_tokens,
            cost,
        )

        return cost

    def get_cost_summary(self) -> JudgeCostSummary:
        """Get summary of judge costs.

        Returns:
            JudgeCostSummary with cost metrics
        """
        return JudgeCostSummary(
            total_cost=self.total_cost,
            calls_made=self.calls_made,
            cost_per_call=self.cost_per_call,
            average_cost=(
                self.total_cost / self.calls_made if self.calls_made > 0 else 0.0
            ),
        )
