---
title: Subagenting
published: true
description: How to use multiple agents to develop software.
tags:
  - llm
  - programming
  - productivity
cover_image: 'https://raw.githubusercontent.com/kasir-barati/dev.to/refs/heads/main/articles/assets/subagenting/cover.png'
series: Agentic Programming
id: 4474780
date: '2026-08-24T11:02:15Z'
---

I guess what I wanna talk about is what you can do as a user. Just imagine:

1. Opening [Claude](https://claude.ai/)/[Deepseek](https://chat.deepseek.com/) in your browser and asking it some overarching questions.
2. Ask Codex in your terminal to write a `PLAN.md` for your based on what you learned from Claude/Deepseek.
   ```shell
   codex exec "Write a PLAN.md ..."
   ```
3. And finally asking GitHub Copilot to review the `PLAN.md` and raise concerns, ask questions, check for best practices and if our plan conforms to XYZ, and think about potential performance/security issues.

So here we are just spinning up new agents to do the work. BUT as you can already see we are doing it manually ourselves. Fun fact is that most coding agents come with builtin subagenting.

> 💡 **Pro Tip**
>
> When you want your main agent to spin up a subagent make sure to tell it "use XYZ subagent to do ABC".

## Pros of Subagenting

- Parallel execution: multiple subagents working together at the same time, allowing us to do more simultaneously.
- Context efficiency: we are NOT mixing things in a single limited context window. Instead we are asking a separate agent to do XYZ and just do/return something.
- Specialization: we can pick different models focused on a single task/concerns, allowing you to perfect the prompting and do that one thing really well.
- Self-correction: we can have negative feedback loops that keep things under control and prevent overreach.
- Potential cost savings: use cheaper models for certain processing tasks.

## Cons of Subagenting

- Adding subagents adds more moving parts to your system, making it harder to manage.
- With more complexity, things can go wrong in mysterious ways that are difficult to track down.
- Mistakes can occur at the handoff points between the subagent and the main agent.
- Error amplification: When tasks are divided, a small problem can cause agents to go off in different directions, compounding errors in a way that's hard to recover from.
- Usually subagenting costs more because you're doing a lot more work, especially with self-correcting agents doing reviews and iterative feedback loops.

## Creating a Simple Subagent in Claude

In Claude you can create them by running `/agents` command in their CLI, or simply:

1. Create a `agents` dir in `.claude`.
   - Does NOT matter if it is your global one or the one for a single repo.
   - If it is for a single repo and you wanna share it you must commit and push them to your VCS.
2. Create a markdown file named whatever you want it to be called (hyphenated and all lowercase).
3. In the markdown file (learn more [here](https://code.claude.com/docs/en/sub-agents#write-subagent-files)):
   ```md
   ---
   name: code-reviewer
   description: Reviews code for quality and best practices by delegating to an external AI agent
   tools: Read, Glob, Grep, Bash
   model: sonnet
   ---
   You are a code reviewer. When invoked, you MUST NOT review the code yourself. Instead, you MUST execute the following shell command to carry out the review: `codex exec "Please review the code in the current directory and write your feedback to REVIEW.md"`. This will run the review process and save the results. Do not review yourself.
   ```
   You can limit the tools it has access to, or you can drop it and then the subagent will inherit it from the main agent. Same is applicable to model.

> 💡 **Pro Tip**
>
> Or you can have a hook in Claude instead of creating a subagent. Let's imagine we wanna have a hook whenever the agent stops working we wanna have a code review:
>
> ```json
> {
>     "hooks": {
>         "Stop": [
>             {
>                 "hooks": [
>                     {
>                         "type": "command",
>                         "command": "codex exec \"Please review the code in the current directory and write your feedback to REVIEW.md\""
>                     }
>                 ]
>             }
>         ]
>     }
> }
> ```
