---
title: Pay Attention to Field Order in Structured Output
published: true
description: Why the order of fields in a Pydantic/JSON schema can change whether an LLM reasons before deciding or just rationalizes after.
tags:
  - llm
  - pydantic
  - programming
  - contextengineering
cover_image: "https://raw.githubusercontent.com/kasir-barati/dev.to/refs/heads/main/articles/assets/pay-attention-to-field-order-in-structured-output/cover.png?v=49ea727"
series: Agentic Programming
id: 4688512
date: "2026-09-18T21:57:02Z"
---

It started with a simple schema:

```python
from pydantic import BaseModel, Field


class WebSearchItem(BaseModel):
    reason: str = Field(description="Why this search is important to the query.")
    query: str = Field(description="The search term to use.")
```

The question was "does putting `reason` before `query` actually change how the model generates the output? Or is that just superstition?"

[LLMs generate structured output autoregressively](https://medium.com/@zaiinn440/autoregressive-models-for-natural-language-processing-b95e5f933e1f), one token at a time, and each token can only attend to tokens generated _before_ it (or at least what I think is correct). So if I `reason` first in my Pydantic schema, the model has to write its reasoning before it commits to a query.

So the query can actually be conditioned on that reasoning. Flip the order, and the model commits to `query` first; whatever it writes in `reason` afterward is generated with the query already fixed in context, making it structurally more likely to be a justification for a decision already made rather than a cause of it.

This is the same mechanism that makes [chain-of-thought prompting](https://www.ibm.com/think/topics/chain-of-thoughts) work in general, letting the model output intermediate reasoning before a final answer lets that reasoning causally shape the answer.

**This is a documented, recommended pattern.** [Structured queries with Weaviate explicitly shows a `reasoning` field placed before the `final_answer` field](https://docs.weaviate.io/query-agent/reference/structured_outputs#example-reasoning), noting that schema order is preserved during generation. [Agent-framework docs go further](https://docs.beam.ai/02-building-agents/agent-configuration/structured-outputs/structured-outputs#reason-first), suggesting to put reasoning/analysis fields before extraction or conclusion fields, because it enables the later LLM calls to see the rationale behind it.

**A controlled test backs the effect up.** One experiment on LiveBench reasoning questions, aptly titled ["Structured outputs: don't put the cart before the horse"](https://dylancastillo.co/posts/llm-pydantic-order-matters.html), found that field order in the schema measurably affected accuracy. **But it's not universal.** [A separate experiment](https://case-studies.getcoai.com/news/why-field-order-may-not-improve-model-reasoning/) using `pydantic-evals` across several GPT models on a classification task found close to no difference between reasoning-first and reasoning-last schemas.

The effect seems to depend heavily on task difficulty and model strength. A hard, open-ended task benefits more than a simple classification, and a strong model can already do "in its head" regardless of field order.

**And it's not guaranteed by every provider.** A [Google AI forum thread](https://discuss.ai.google.dev/t/structured-outputs-propertyordering-field-not-respected-when-using-the-openai-compatible-api-gemini-2-flash/86790) documents Gemini's OpenAI-compatible endpoint ignoring explicit property ordering, returning fields in effectively random order which silently breaks this whole technique for that setup. But it might have been fixed already since they said they will work on it. Not sure if they fixed it. Let me know in the comments if they did.

## The Practical Rule

Order fields by causal dependency: the field you want the model to _decide on_ goes last; anything that should inform that decision goes before it. It's a strong default, not a law. You can of course try to see if that does make a difference in your situation, but sticking to this rule won't cost you anything either IMO.

But if you wanna test it yourself, here's a minimal PydanticAI check: run the same prompt through both field orderings and eyeball whether the reasoning actually looks like it's driving the query, or just rationalizing it after the fact.

```python
import asyncio
from pydantic import BaseModel, Field
from pydantic_ai import Agent

class ReasonFirst(BaseModel):
    reason: str = Field(description="Why this search matters for the query.")
    query: str = Field(description="The search term to use.")

class QueryFirst(BaseModel):
    query: str = Field(description="The search term to use.")
    reason: str = Field(description="Why this search matters for the query.")

prompt = "I want to know if it will rain in Bremen this weekend."

agent_reason_first = Agent("openai:gpt-4o-mini", output_type=ReasonFirst)
agent_query_first = Agent("openai:gpt-4o-mini", output_type=QueryFirst)

async def main():
    r1 = await agent_reason_first.run(prompt)
    r2 = await agent_query_first.run(prompt)
    print("reason-first :", r1.output)
    print("query-first  :", r2.output)

asyncio.run(main())
```

Run it a few dozen times with each ordering on a task that's genuinely ambiguous (not a simple lookup) and compare: does the `reason` field in the query-first version read like an explanation that was decided _before_ the query, or a caption written _after_ it?

---

## Pro Tip

In your LLM-powered application always keep a `reason` field in the output schema. So this way we have clear observability into why LLM generated certain output. Also make sure to explain it very well so LLM knows what it should write for that field.
