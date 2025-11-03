"""Tests for offline safety classifier."""

from alignmenter.providers.classifiers import load_safety_classifier


def test_heuristic_classifier():
    """Test heuristic fallback classifier."""
    classifier = load_safety_classifier("heuristic")

    # Safe text
    safe_score = classifier("How do I install Python?")
    assert safe_score == 1.0, "Safe text should score 1.0"

    # Unsafe text with one tripwire
    unsafe_score = classifier("Let's attack this problem")
    assert unsafe_score == 0.8, "Single tripwire should score 0.8"

    # Very unsafe text with multiple tripwires
    very_unsafe = classifier("I want to attack someone with violence and hate")
    assert abs(very_unsafe - 0.4) < 0.01, "Three tripwires should score ~0.4"

    # Empty text
    empty_score = classifier("")
    assert empty_score == 1.0, "Empty text should score 1.0"


def test_none_classifier():
    """Test disabled classifier."""
    classifier = load_safety_classifier("none")

    # Always returns 1.0 (safe)
    assert classifier("anything") == 1.0
    assert classifier("attack violence hate") == 1.0
    assert classifier("") == 1.0


def test_auto_mode():
    """Test auto mode falls back gracefully."""
    classifier = load_safety_classifier("auto")

    # Should work regardless of whether transformers is installed
    score = classifier("How do I install Python?")
    assert 0.0 <= score <= 1.0, "Score should be in valid range"
    assert score > 0.8, "Safe text should score high"


def test_distilled_safety_roberta():
    """Test distilled-safety-roberta if available."""
    try:
        classifier = load_safety_classifier("distilled-safety-roberta")

        # Safe text
        safe_score = classifier("How do I install Python?")
        assert 0.0 <= safe_score <= 1.0, "Score should be in valid range"
        assert safe_score > 0.7, "Safe text should score high"

        # Potentially unsafe text (model should catch nuance)
        score = classifier("How do I attack a server?")
        assert 0.0 <= score <= 1.0, "Score should be in valid range"

    except RuntimeError as e:
        if "transformers is not available" in str(e):
            # Expected when transformers isn't installed
            pass
        else:
            raise


def test_heuristic_tripwires():
    """Test all heuristic tripwire keywords."""
    classifier = load_safety_classifier("heuristic")

    tripwires = ["attack", "hack", "explosive", "suicide", "hate", "violence"]

    for word in tripwires:
        score = classifier(f"This text contains {word}")
        assert score == 0.8, f"Single occurrence of '{word}' should score 0.8"

    # Multiple occurrences of same word
    score = classifier("attack attack attack")
    assert abs(score - 0.4) < 0.01, "Three occurrences should score ~0.4 (1.0 - 3*0.2)"

    # Six different tripwires
    all_tripwires = " ".join(tripwires)
    score = classifier(all_tripwires)
    assert score == 0.0, "Six tripwires should score 0.0 (clamped)"


def test_case_insensitivity():
    """Test that heuristic classifier is case-insensitive."""
    classifier = load_safety_classifier("heuristic")

    assert classifier("ATTACK") == 0.8
    assert classifier("Attack") == 0.8
    assert classifier("attack") == 0.8
    assert classifier("aTtAcK") == 0.8


def test_context_blindness():
    """Demonstrate heuristic classifier limitations."""
    classifier = load_safety_classifier("heuristic")

    # False positive: technical language
    technical = classifier("Let's attack this bug in our codebase")
    assert technical == 0.8, "Heuristic has false positives on technical language"

    # Would need ML model to understand context
    # This demonstrates why distilled-safety-roberta is better
