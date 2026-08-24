---
title: Debugging with Coding Agents -- A Systematic Strategy That Actually Works
published: true
description: 'A step-by-step approach to AI‑assisted debugging: from quick wins to disciplined investigation, and knowing when to switch models.'
tags:
  - ai
  - debugging
  - claude
  - productivity
cover_image: 'https://raw.githubusercontent.com/kasir-barati/dev.to/refs/heads/main/articles/assets/debugging-with-coding-agents-systematic/cover.png'
series: Agentic Programming
id: 4471195
date: '2026-08-24T03:51:32Z'
---

If you've spent any time with any **coding agent** (Claude, Codex, OpenCode, etc), you know the feeling: you're cruising along, it makes a fix, and then suddenly you're in **tangent city**. The model goes off the rails, rewrites half your codebase, and you're left wondering what happened 🥲.

I've been there more times than I care to admit. But over time, I've landed on a **systematic debugging strategy** that consistently pulls me out of the fire. It's a blend of quick wins, disciplined investigation, and crucially knowing when to pull the ripcord and try a different approach.

---

## tl;dr

Debugging with LLMs is not magic, it's a partnership. The models are incredibly capable, but they need structure and critical oversight. By following these steps you can be more productive while using LLMs to debug:

1. Take a snapshot (`git commit`/`git checkout -b`) first.
2. **For small bugs/issues** just copypaste and repeat.
3. Reproduce, add logs, gather evidence/data, form hypotheses, search, and finally jot them down in a markdown file.
4. Sanity-check every hypothesis.
5. Prove the root cause.
6. Bring in a second pair of eyes.
7. Document lessons learned in `AGENTS.md`.

---

## 1. Take a Snapshot -- `git commit`/`git checkout -b` First

Before you do **anything** else, commit your current state or create a new branch. Not just a mental note, an actual Git commit.

**Why?** Because features such as rewind in Claude only backs out direct file edits. It **cannot** undo side effects from running scripts, installing packages, or other non‑file changes. A Git commit is your true safety net.

```bash
git add . && git commit -m "chore: checkpoint before debugging"
```

This is the single most important piece of advice. It sounds obvious, but when you're in the heat of debugging, it's easy to skip. Having a clean snapshot gives you the confidence to let the AI experiment aggressively because you know you can always revert.

## 2. Quick & Dirty: Copy, Paste, Repeat

**For small issues**, the ones that feel like a simple wall bump. Just copy the stack trace or error message and paste it directly into your coding agent. No context, no explanation. Just the error.

This works surprisingly well **for straightforward problems**. Coding agents "gets the joke" (as the saying goes), understands the context from your codebase, and often fixes it in one or two tries.

- Efficiency first: Copy → paste → repeat. Don't overthink it.
- If it works: Great! You're done in seconds.
- If it makes things worse: Revert to your commit and move to step 3.

## 3. The Disciplined Approach -- `DEBUG.md`

When it is complicated bug, or you absolutely has no idea why it fails, or LLM is simply making it worse. It's time to shift gears. This is where the real debugging discipline begins.

Create a markdown file called `DEBUG.md`: guide coding agent through a structured investigation:

1. Reproduce consistently: ask LLM to reproduce the issue every time, and document the exact steps in `DEBUG.md`.
2. Investigate deeply: ask LLM to add extra logging, examine logs, gather all available data.
3. Form hypotheses: ask LLM to come up with plausible causes and write them down.
4. Web search: have coding agent search for similar issues online, but with a critical eye.

> ⚠️ **Warning**
>
> When LLM says "I found it, this is a known issue". Challenge it!
>
> Because sometimes it says with certainty it has found the issue, but when you ask it to give you the link to where the response comes from iy gives you a link to single Stackoverflow QA from x years ago a single developer had a similar problem 🤦. Or even worse is when it hallucinate or just simply make up stuff.

## 4. Sanity-Check Every Hypothesis

This is where you need to be the adult in the room. LLMs love to latch onto the first plausible explanation and run with it. It'll say things with **breathtaking confidence even when it's completely wrong**.

- **Ask for evidence**, prompt it:
  ```
  Is this a common issue? How many people reported it?
  ```
- **Demand proof**, ask it:
  ```
  Can you demonstrate that this is actually the root cause?
  ```
- **Watch for fiction**, LLMs might **invent non‑existent limitations** and restructure the entire codebase around that false premise.

If you catch it going down a rabbit hole, stop, revert to your last commit, and tell it:

```
This is not the problem. Try again.
```

## 5. Prove the Root Cause

Once LLM has a hypothesis it believes in, make it prove it. Document the proof in `DEBUG.md`. **This isn't optional**, it's the difference between guessing and knowing 😉.

- **Reproduce consistently**: show that the issue happens every time under specific conditions.
- **Apply the fix**: make the change and confirm the issue is resolved.
- **Verify consistency**: prove that the fix works reliably, not just once.

## 6. Bring in a Second Pair of Eyes

If you're still stuck after all of this, it's time to call in reinforcements. And by reinforcements, I mean a different LLM/colleague.

1. Fire up Codex, Antigravity, or any other model you have access to. Give it the same assignment and walk it through the same disciplined process.
   - Each model has a different training experience and different biases.
   - What Claude misses, another model might spot immediately.
2. If that did NOT work either and you have colleagues, try to consult them. Or simply [rubber duck](https://en.wikipedia.org/wiki/Rubber_duck_debugging)!

Usually adding a different LLM would solve most issues as long as you try to approach it with an open mind.

## 7. Document Lessons Learned -- `AGENTS.md`

This is the step that most people skip, including me and it's a huge mistake. Once the issue is fixed, have LLM write a lessons learned section in a `AGENTS.md`. It's like a memory bank for the AI. Include:

- What the root cause was.
- How you identified it.
- What you'd do differently next time.
- Any project-specific tips to avoid repeating the mistake.

**Why?** Because once you clear the conversation or a compact happens, coding agent forgets. And it will make the same mistake again. Documenting it breaks that cycle.

---

## Systematic Debugging Skill

Try to install [this](https://github.com/obra/superpowers/blob/b36e0829c6d0140e93cfef2ca599b1b07d4a7797/skills/systematic-debugging/SKILL.md) skill in your coding agent and use it. It formulates a lot of what I've described here, with extra emphasis on web searches and "The Iron Law" of proving the root cause.


