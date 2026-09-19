---
title: What Matters in Agentic Programming
published: true
description: 'Stop chasing autonomous agents. Learn the practical principles for building reliable, production-ready AI systems. From focusing on business problems to the critical habit of checking your traces.'
tags:
  - agents
  - llm
  - softwaredevelopment
cover_image: 'https://raw.githubusercontent.com/kasir-barati/dev.to/refs/heads/main/articles/assets/what-matters-in-agentic-programming/cover.png?v=aee822b'
series: Agentic Programming
id: 4696122
date: '2026-09-19T20:55:08Z'
---

## 1. Focus on the Problem, Not the Solution

If you wanna build an AI agent for X, you're setting up yourself for failure or if not failure a lot of back and forth. When building agentic AI systems, **focus on the problem first, not the solution.** Fix a real-world business problem. Start with "I have this problem that needs solving." The technology should serve the problem, not the other way around.

## 2. Measure What Matters

Whatever problem you're solving, make sure you can measure it, ideally with a real-world business outcome. Finding the right metric can be hard. It takes time and analysis. But that's exactly why it's worth solving. Without measurement, you're flying blind.

## 3. Orchestrate with Code First

Start your baseline by orchestrating with code, call `runner.run`, check the output with an `if` statement, then call `runner.run` again. At production you want **predictability**, **reliability**, and **more workflow than true autonomy**. Everyone should be able to understand and reason about it. Once you have a resilient, bulletproof baseline, then you can experiment with more autonomy. But start from a robust point.

## 4. Go Bottom-Up, Not Top-Down

Rather than starting with your big problem and a complex agent architecture diagram, start with the smallest possible problem. Solve that first. Then gradually work your way up to the bigger challenge. This is not really new, remember, we have [divide and conquer algorithms](https://en.wikipedia.org/wiki/Divide-and-conquer_algorithm).

## 5. Start Simple, Really Simple

Start with one LLM call. Get results. Then, if it makes sense, divide into two LLM calls or two agents. But only if it gets better outcomes. Be driven by data and metrics, not by architectural ambition.

## 6. Start with a Big Model, Then Optimize

Bigger models are more reliable when there's ambiguity. Start there. Once your prompts are perfected and the system works reliably, experiment with smaller models to reduce costs. Starting small often leads to a painful, unreliable experience.

## 7. Think Broadly About Context

Don't just focus on memory. Think about **context engineering**, all the information and resources you could equip your model with. Ask yourself: what context would help this LLM produce the best possible outcome?

## 8. Iterate on Your Prompts

**A huge percentage** of problems are solved simply by iterating on prompts. Before looking for fancy explanations for strange behavior. Just experimentation until you get what you want.

## 9. Check Your Traces -- Observability

It's so easy to trust that things are working. You're getting good answers, so you let it be. Then you look at the traces and discover it didn't call any tools. It just invented an answer. Or it simply assumed the wrong conjecture. Make checking traces a habit. Get into the discipline of always reviewing them while building. Then surface that observability information in your UI or admin dashboard if you have one.

## 10. Be Both Engineer and Scientist

There's no shortcut to R&D. Success in this field means wearing your science hat often, experimenting, and iterating.

---

## Enjoy the Process

Perhaps the most important point of all: **enjoy the journey**. The experimentation to get better outcomes is the magical part of working with LLMs. It can feel frustrating when you're not making progress, but then you'll have a breakthrough. As long as you iterate on those prompts, as long as you do the R&D, you're going to get great outcomes.
