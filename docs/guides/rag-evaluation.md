# Evaluating Retrieval-Augmented Assistants

Brand voice, safety, and stability describe *how* an assistant speaks. A
retrieval-augmented assistant — one that answers from documents it was given —
has a fourth question that matters more than any of those: **is what it said
actually in the documents, and is it right?**

Alignmenter ships two scorers for that, and a seam for your own.

| Scorer | Needs | Answers |
| --- | --- | --- |
| `grounding` | nothing (offline, deterministic) | Are the *figures* in the answer traceable to the retrieved passages? Are the `[n]` citations real? |
| `faithfulness` | an LLM judge | Which *claims* do the passages support? Is the answer correct for the question? Could it hurt someone? |
| `custom` | a class you write | Whatever your product needs — resolution rate, latency, contribution … |

Both built-ins read the retrieval context the provider attached to each
assistant turn. Neither runs unless you ask for it.

## 1. Attach the context

Your provider's `chat()` returns a `ChatResponse`. Put what the model was shown
in `context`:

```python
from alignmenter.providers.base import ChatResponse

def chat(self, messages, **kwargs) -> ChatResponse:
    question = messages[-1]["content"]
    excerpts = self.retriever.search(question)          # your retrieval
    answer = self.model.answer(question, excerpts)      # your generation
    return ChatResponse(
        text=answer,
        usage={"prompt_tokens": 1200, "completion_tokens": 300},
        context={
            "question": question,
            "excerpts": [
                {"title": e.title, "section": e.section, "text": e.text}
                for e in excerpts
            ],
            "latency_ms": 1840,
        },
    )
```

The runner writes it to the turn as `metadata["context"]`, so it is also in the
saved transcript and you can re-score later without re-generating. Excerpts may
be dicts (`text` plus optional `title` / `section`) or plain strings, under any of
the keys `excerpts`, `passages`, `documents`, `sources`, `context`. Keep them in
the order the model saw them so `[n]` citations line up.

If you score recorded transcripts rather than generating, the same shape works
in the dataset JSONL: an assistant turn with `metadata.context.excerpts`.

## 2. Grounding (offline)

```yaml
scorers:
  grounding:
    enabled: true
    units_only: true     # default: only quantities that carry a unit are judged
    threshold_fail: 0.85
```

or `alignmenter run --grounding …`.

Every quantity in the answer (`5 drops`, `40 minutes`, `70 °C`, `500 mg`) must
appear in the passages, after unit normalisation (`litres` = `liters` = `l`,
`1.0` = `1`). List numbering and citation digits are stripped first. Bare
integers are ignored by default: they are almost always layout, and the claims a
reader acts on carry units.

Unsupported quantities are split two ways because they need different fixes:

* **invented** — the passages gave no figure in that unit at all. The model
  filled a gap. Fix the prompt ("say the library does not specify").
* **contradicted** — the passages gave a figure in that unit and the answer's
  differs. Fix retrieval or comprehension.

A citation that points past the end of the excerpt list is counted as invalid.

Payload:

| Field | Meaning |
| --- | --- |
| `score` | supported ÷ checked quantities, across all grounded turns |
| `invented`, `contradicted` | counts of unsupported quantities by kind |
| `citation_validity` | 1 − invalid ÷ total citations |
| `violations` | the worst answers first: question, the unsupported figures, how many excerpts it had |

Grounding is a proxy. It says nothing about whether the answer was correct or
whether the right passages were retrieved. That is what the judge is for.

## 3. Faithfulness and correctness (judge)

```yaml
scorers:
  faithfulness:
    enabled: true
    judge: anthropic:claude-sonnet-5      # or openai:…, or a local endpoint (below)
    budget: 200                            # max judge calls this run
    domain: an offline survival and first-aid reference
    threshold_warn: 0.9
thresholds:
  dangerous:
    fail: 0                                # any answer that could hurt someone fails the run
```

For each grounded answer the judge sees the question, the numbered passages,
and the answer, and returns:

* the answer's factual claims, each `supported` / `unsupported` /
  `contradicted`, with the passage phrase as evidence;
* a correctness rating 0–10, judged against the passages first and expert
  knowledge second — a fluent answer with a wrong figure scores low, an honest
  "the material does not cover this" scores high when true;
* whether it answered the question, whether it abstained and whether that was
  appropriate;
* a `dangerous` flag with a specific reason, reserved for answers that could
  plausibly cause serious harm if followed.

Tell the judge what the product is with `domain`; "dangerous" means different
things for a survival reference and a recipe assistant.

Payload:

| Field | Meaning |
| --- | --- |
| `score` | faithfulness: supported ÷ all claims, averaged per answer (an appropriate abstention with no claims scores 1) |
| `correctness` | mean judge rating on 0–1 |
| `dangerous` | count of answers flagged dangerous |
| `dangerous_answers` | those answers, with the judge's reason — read these first |
| `unfaithful_answers` | answers with unsupported or contradicted claims, weakest first |
| `claims`, `claims_supported`, `claims_unsupported`, `claims_contradicted` | totals |
| `abstentions`, `abstentions_appropriate` | how often it said "not covered", and how often that was right |
| `judge_calls`, `judge_calls_skipped`, `judge_cost_spent`, `judge_parse_failures` | budget accounting |

Gate on `dangerous`, not on the mean. A product with a 0.95 faithfulness score
and one answer that tells someone to drink undiluted bleach is not ready; the
`thresholds.dangerous.fail: 0` line above makes the run exit non-zero.

### Judging without sending transcripts anywhere

Any OpenAI-compatible endpoint can be the judge:

```yaml
scorers:
  faithfulness:
    judge: local:http://127.0.0.1:8080/v1|qwen3.5-32b
```

Start `llama-server`, vLLM, Ollama, or LM Studio with a model large enough to
audit claims reliably — the judge should be clearly stronger than the model it
is judging. Judge calls are cached per prompt within a run.

## 4. Your own scorers

Anything with an `id` and `score(sessions) -> dict` can be loaded from your
product's code:

```yaml
scorers:
  custom:
    - my_product.eval.scorers:ContributionScorer
    - my_product.eval.scorers:ResolutionRate
```

or `--custom-scorer my_product.eval.scorers:ContributionScorer` (repeatable).
`score` receives the same session objects as the built-ins; assistant turns
carry `metadata["context"]` when the provider attached one. A numeric `score`
key gets the standard report treatment.

## 5. Reading the report

The HTML report lists, under each scorer, the answers behind the number:
dangerous answers first, then unfaithful ones with their problem claims, then
grounding violations split into invented and contradicted figures. The same
lists are in `results.json`. Start at the top of those lists; the mean is the
last thing to look at.

## Two things the numbers cannot tell you

* **Whether the right passages were retrieved.** Both scorers judge the answer
  against what the model *was shown*. A perfectly faithful answer to the wrong
  passage is still wrong. Keep a retrieval eval beside this one.
* **Whether a supported claim is true.** Passages can be wrong or outdated.
  Faithfulness measures fidelity to the library; curate the library.
