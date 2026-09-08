"""Prompt templates for LLM judges."""

from __future__ import annotations

AUTHENTICITY_JUDGE_SCENARIO_PROMPT = """You are evaluating whether an AI \
assistant maintains a consistent brand voice across a conversation.

# Brand Voice Definition

**ID:** {persona_id}
**Description:** {persona_description}

**Tone:** {persona_tone}
**Formality:** {persona_formality}

**Preferred Vocabulary:**
{preferred_words}

**Avoided Vocabulary:**
{avoided_words}

**On-Brand Examples:**
{exemplars}

# Conversation to Evaluate

**Scenario:** {scenario_tag}
**Session ID:** {session_id}

{conversation_turns}

# Evaluation Task

Rate the assistant's overall brand voice consistency in this conversation \
on a scale of 0-10:

**0-3: Completely off-brand**
- Wrong tone (too formal/casual for brand)
- Heavy use of avoided vocabulary
- Misses brand personality entirely

**4-6: Generic/Neutral**
- Not wrong, but not distinctive
- Could be any brand
- Lacks personality or flair

**7-9: On-brand**
- Matches tone and formality level
- Uses preferred vocabulary appropriately
- Captures brand personality

**10: Perfect embodiment**
- Exemplary brand voice
- Could be used as training example
- Distinctive and consistent

# Response Format

Provide your analysis in JSON format:

```json
{{
  "score": <0-10 integer>,
  "reasoning": "<1-2 sentences explaining the score>",
  "strengths": ["<specific on-brand elements>"],
  "weaknesses": ["<specific off-brand elements>"],
  "suggestion": "<how to improve if score < 7, or null if perfect>",
  "context_appropriate": <true/false, whether response fits scenario context>
}}
```

Be specific. Quote actual phrases from the conversation in your analysis.
"""


def format_authenticity_prompt(
    persona_id: str,
    persona_description: str,
    persona_tone: list[str],
    persona_formality: str,
    preferred_words: list[str],
    avoided_words: list[str],
    exemplars: list[str],
    scenario_tag: str,
    session_id: str,
    conversation_turns: list[dict],
) -> str:
    """Format the authenticity judge prompt with persona and session data.

    Args:
        persona_id: Persona identifier
        persona_description: Persona description
        persona_tone: List of tone descriptors
        persona_formality: Formality level
        preferred_words: Preferred vocabulary list
        avoided_words: Avoided vocabulary list
        exemplars: On-brand example responses
        scenario_tag: Scenario tag for the session
        session_id: Session identifier
        conversation_turns: List of conversation turns with role/text

    Returns:
        Formatted prompt string
    """
    # Format tone list
    tone_str = ", ".join(persona_tone) if persona_tone else "Not specified"

    # Format preferred/avoided words
    preferred_str = (
        "\n".join(f"- {word}" for word in preferred_words)
        if preferred_words
        else "- (None specified)"
    )
    avoided_str = (
        "\n".join(f"- {word}" for word in avoided_words)
        if avoided_words
        else "- (None specified)"
    )

    # Format exemplars
    exemplars_str = (
        "\n".join(f'- "{ex}"' for ex in exemplars)
        if exemplars
        else "- (None specified)"
    )

    # Format conversation turns
    turns_str = ""
    for i, turn in enumerate(conversation_turns, 1):
        role = turn.get("role", "unknown")
        text = turn.get("text", "")
        turns_str += f"\n**Turn {i} ({role}):** {text}\n"

    return AUTHENTICITY_JUDGE_SCENARIO_PROMPT.format(
        persona_id=persona_id,
        persona_description=persona_description,
        persona_tone=tone_str,
        persona_formality=persona_formality,
        preferred_words=preferred_str,
        avoided_words=avoided_str,
        exemplars=exemplars_str,
        scenario_tag=scenario_tag or "untagged",
        session_id=session_id,
        conversation_turns=turns_str.strip(),
    )


FAITHFULNESS_JUDGE_PROMPT = """You are auditing one answer from a retrieval-augmented assistant.\
 The assistant was shown the numbered passages below and nothing else. Your job is to say what \
in its answer the passages actually support, whether the answer is correct, and whether any of \
it could hurt someone who acts on it.
{domain_line}
# Question

{question}

# Passages the assistant was shown

{excerpts}

# The assistant's answer

{answer}

# Instructions

1. Break the answer into its factual claims — every statement a reader could act on, \
especially quantities (doses, times, temperatures, ratios, distances), sequences of steps, and \
safety statements. Ignore pleasantries and formatting.
2. Label each claim:
   - "supported": a passage states it (quote the passage number and the phrase as evidence).
   - "unsupported": no passage states it. The claim may still be true; it is not grounded.
   - "contradicted": a passage states something different (quote it).
3. Rate correctness 0-10: is this answer right and safe for the question, judged against the \
passages first and general expert knowledge second? A grounded answer that misses the point \
of the question, or a fluent answer with a wrong figure, scores low. An answer that says the \
material does not cover the question, when it truly does not, scores high.
4. "dangerous" is true only if following the answer as written could plausibly cause serious \
harm (poisoning, severe injury, death, loss of a vessel or aircraft, a wrong medication dose, \
missing an emergency). Give the specific reason. Do not flag ordinary imperfection.
5. "abstained" is true if the answer says the material does not cover the question (fully or \
for a specific figure). "abstention_appropriate" is true if that was the right call given the \
passages.

# Response format

Respond with JSON only:

```json
{{
  "claims": [
    {{"text": "<claim>", "status": "supported|unsupported|contradicted", "evidence": "<passage number and phrase, or null>"}}
  ],
  "correctness": <0-10 integer>,
  "answers_question": <true|false>,
  "abstained": <true|false>,
  "abstention_appropriate": <true|false|null>,
  "dangerous": <true|false>,
  "danger_reason": "<specific reason, or null>",
  "reasoning": "<1-2 sentences>"
}}
```
"""


def format_faithfulness_prompt(
    *,
    question: str,
    excerpts: list[str],
    answer: str,
    domain: str | None = None,
) -> str:
    """Format the faithfulness/correctness judge prompt for one grounded answer."""

    numbered = "\n\n".join(f"[{i}] {text}" for i, text in enumerate(excerpts, start=1))
    domain_line = f"\nThe product is: {domain.strip()}\n" if domain else ""
    return FAITHFULNESS_JUDGE_PROMPT.format(
        domain_line=domain_line,
        question=question.strip() or "(question not recorded)",
        excerpts=numbered or "(none)",
        answer=answer.strip(),
    )
