# Contributing

We welcome contributions from the community! This guide will help you get started.

## Ways to Contribute

- **🐛 Bug Reports**: File issues with reproducible examples
- **✨ Feature Requests**: Propose new scorers, providers, or workflows
- **📝 Documentation**: Improve guides, add examples
- **🧪 Tests**: Expand test coverage
- **🎨 Persona Packs**: Share brand voice configs for common use cases
- **💻 Code**: Fix bugs or implement features

## Development Setup

### 1. Fork and Clone

```bash
git clone https://github.com/justinGrosvenor/alignmenter.git
cd alignmenter
```

### 2. Create Virtual Environment

```bash
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
```

### 3. Install with Dev Dependencies

```bash
pip install -e .[dev,safety]
```

This installs:
- Main package in editable mode
- Test tools (pytest, pytest-cov)
- Linters (ruff, black)
- Type checker (mypy)
- Offline safety classifier

### 4. Run Tests

```bash
pytest
```

You should see all tests passing:
```
===== 103 passed in 2.34s =====
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/my-feature
```

Branch naming:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation
- `test/` - Test improvements

### 2. Make Changes

Follow the coding conventions in `AGENTS.md`:

**✅ Good**:
- Small, composable functions
- Type hints on all functions
- Docstrings for public APIs
- Unit tests for new code

**❌ Avoid**:
- Functions > 50 lines
- Untyped dict returns (use dataclasses)
- Global state
- Tight coupling

### 3. Run Linter

```bash
ruff check src/ tests/
```

Fix any issues:
```bash
ruff check src/ tests/ --fix
```

### 4. Format Code

```bash
black src/ tests/
```

### 5. Run Tests

```bash
pytest

# With coverage
pytest --cov=alignmenter --cov-report=html
```

### 6. Commit

```bash
git add .
git commit -m "Add feature: description"
```

Commit message format:
```
<type>: <short summary>

<detailed description>

Fixes #123
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`

### 7. Push and Create PR

```bash
git push origin feature/my-feature
```

Then create a Pull Request on GitHub.

## Code Style

### Functions

```python
def calculate_authenticity_score(
    response: str,
    persona: Persona,
    embeddings: np.ndarray
) -> float:
    """Calculate authenticity score for a response.

    Args:
        response: The AI-generated response text
        persona: Persona definition with voice and examples
        embeddings: Pre-computed sentence embeddings

    Returns:
        Authenticity score between 0.0 and 1.0

    Example:
        >>> score = calculate_authenticity_score(
        ...     "Our baseline shows improvement",
        ...     persona,
        ...     embeddings
        ... )
        >>> assert 0.0 <= score <= 1.0
    """
    # Implementation...
```

### Dataclasses over Dicts

```python
# ❌ Bad
def get_scores(session: dict) -> dict:
    return {"authenticity": 0.8, "safety": 0.9}

# ✅ Good
@dataclass
class ScoreSummary:
    authenticity: float
    safety: float
    stability: float

def get_scores(session: Session) -> ScoreSummary:
    return ScoreSummary(
        authenticity=0.8,
        safety=0.9,
        stability=0.85
    )
```

### Error Handling

```python
# ✅ Good - specific exceptions
try:
    result = api_call()
except OpenAIError as e:
    logger.error("OpenAI API failed: %s", e)
    raise EvaluationError(f"Model call failed: {e}") from e
```

## Testing

### Unit Tests

```python
def test_authenticity_with_perfect_match():
    """Test authenticity scorer with identical text."""
    persona = Persona(
        id="test",
        examples=["Our baseline shows improvement"]
    )

    scorer = AuthenticityScorer(persona)
    score = scorer.score_response("Our baseline shows improvement")

    assert score > 0.95  # Should be very high
```

### Fixtures

```python
@pytest.fixture
def sample_persona():
    return Persona(
        id="test-persona",
        voice=Voice(
            tone=["professional"],
            formality="business_casual",
            lexicon=Lexicon(
                preferred=["baseline", "signal"],
                avoided=["lol", "hype"]
            )
        ),
        examples=["Our baseline analysis shows strong signal."]
    )

def test_with_fixture(sample_persona):
    scorer = AuthenticityScorer(sample_persona)
    # Test using fixture...
```

## Documentation

### Docstrings

Use Google style:

```python
def evaluate_session(
    session_id: str,
    turns: list[Turn],
    persona: Persona
) -> SessionAnalysis:
    """Evaluate a conversation session for brand voice alignment.

    Args:
        session_id: Unique identifier for this session
        turns: List of conversation turns (user/assistant pairs)
        persona: Brand voice definition to evaluate against

    Returns:
        SessionAnalysis with scores and detailed feedback

    Raises:
        EvaluationError: If session is empty or invalid

    Example:
        >>> turns = [Turn(user="Hello", assistant="Hi there!")]
        >>> analysis = evaluate_session("s001", turns, persona)
        >>> assert 0.0 <= analysis.authenticity <= 1.0
    """
```

### User Docs

When adding features, update:
- `docs/getting-started/` - If it affects basic usage
- `docs/guides/` - If it's a new workflow
- `docs/reference/` - Always update CLI/API reference

## PR Checklist

Before submitting:

- [ ] Tests pass (`pytest`)
- [ ] Linter passes (`ruff check`)
- [ ] Code formatted (`black`)
- [ ] Type hints added
- [ ] Docstrings written
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (if applicable)
- [ ] Commit messages follow format

## Release Process

(For maintainers)

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Tag release: `git tag v0.3.1`
4. Push: `git push origin v0.3.1`
5. GitHub Actions builds and publishes to PyPI

## Community

- **GitHub Issues**: [Report bugs and request features](https://github.com/justinGrosvenor/alignmenter/issues)
- **Discussions**: [Ask questions](https://github.com/justinGrosvenor/alignmenter/discussions)

## License

By contributing, you agree that your contributions will be licensed under Apache 2.0.
