---
title: Coding Agents & Workflows
published: true
description: 'Practical patterns for working with AI coding agents, from skills and plugins to context management and code review discipline.'
tags:
  - llm
  - programming
  - productivity
  - workflow
cover_image: 'https://raw.githubusercontent.com/kasir-barati/dev.to/refs/heads/main/articles/assets/coding-agent-and-workflows/cover.png'
series: Agentic Programming
---

If you're working with coding agents like Claude Code, GitHub Copilot, or any other AI assistant, you've probably noticed something: they can generate code faster than you can review it. This creates a new set of challenges that traditional development workflows weren't designed to handle.

Here is what I believe will help you. BTW before reading this post try to:

1. Clone a large open-source project which you feel comfortable working with.
2. Find a TODO or bug in the code.
3. Ask your coding agent to fix it.
4. Apply whatever principles you *currently* have when working with a coding agent (whatever that looks like today).
5. Save the results in a separate branch. If you like you can also track how much you spend on it (time and LLM bills).

Keep that branch around, once you've read the post, you'll go back and redo the same task with the principles below applied, so you can compare the two results yourself.

## Know Your Tools, Know Yourself

Your choice of tools depends on your experience level, and that choice shapes the whole workflow you're about to build:

- **Seasoned pros**: tend to gravitate toward CLI-based tools. And let's not forget that most of the times CLI offers more features.
- **Beginners**: often find IDEs more comfortable and approachable.

Whichever you pick, you need to learn to be patient with LLMs. They usually tend to generate a ton of text, and rushing past it defeats the point of reviewing it at all.

---

## Give Your Agent Context, Deliberately

When you code, you have a ton of context in your head. So if you are expecting a coding agent to deliver good results you need to give it **enough** context but beware of [context dilution](https://diffray.ai/blog/context-dilution/).

### Plugins

- Browse official plugins.
- Pick the most popular or relevant ones for your project type.
- Examples:
  - [feature-dev](https://claude.com/plugins/feature-dev) for building features efficiently.
  - [code-simplifier](https://claude.com/plugins/code-simplifier) to clean up and refactor.
  - [frontend-design](https://claude.com/plugins/frontend-design) for professional UI/UX work.

> ⚠️ **Warning**
>
> If you install [superpowers](https://claude.com/plugins/superpowers) plugin get ready for it to spin up subagents and burn a ton of tokens in the process. Personally I downloaded their brainstorming, and systematic-debugging skill and removed the plugin.

### MCP Servers Worth Knowing About

Consider using **MCP servers** (like [Contact7](https://context7mcp.com/claude/)) if they offer exactly what you need. Some plugins may already cover the same functionality, so try to avoid overlap. Commit them to git so everyone has access.

> 💡 **Pro Tip**
>
> Install Context7, it is so useful since LLMs do not have always the latest documentations for a library. You can enforce it by adding a `.mcp.json`:
>
> ```json
> {
>   "mcpServers": {
>     "context7": {
>       "command": "npx",
>       "args": [
>         "-y",
>         "@upstash/context7-mcp@latest"
>       ]
>     }
>   }
> }
> ```

### Case Study: Why Skills Matter

Rather than relying on general knowledge, develop skills tailored to your project. Imagine you are building the backend checkout service for a massive e-commerce platform (think Shopify, Amazon, or a large retail enterprise). This service handles:

- Cart finalization with 10+ items.
- Inventory reservation (not just decrementing a number, but holding stock across multiple warehouses).
- Tax calculation (different rules per US state, VAT for EU, GST for Australia).
- Payment orchestration (Stripe/Paddle/Braintree with 3D Secure fallbacks).
- Fraud scoring (an internal ML model that returns a risk score).
- Promotions & gift cards (stacking rules).
- Event emission (RabbitMQ events for shipping, analytics, and receipts).

Now an engineer on your team asks the coding agent to:

> We are releasing a 'Flash Sale' feature tomorrow. We need a new endpoint that accepts a list of product IDs and quantities, bypasses the user's shopping cart, and goes straight to the checkout/payment page. Ensure it validates the flash sale time window."

**What happens WITHOUT a skill:** the agent reads the prompt, sees **"bypass cart"** and **"straight to payment"**, and happily writes something like this (LLMs try to follow your instructions as much as possible):

```py
@app.post("/flash-checkout")
def flash_checkout(products, user_id):
    total = 0
    for p in products:
        # 🚨 UNSAFE: Direct DB hit.
        # Inventory is immediately deducted, even if the user's credit card fails (loss of stock).
        db.inventory.update_one({"_id": p.id}, {"$inc": {"stock": -p.qty}}) 
        total += p.price * p.qty

    # 🚨 WRONG: Hardcodes US tax, ignores EU and other regions
    # This is a contrived example and most top LLMs would ask you about it
    total *= 1.08
    
    # 🚨 BREAKS STATE MACHINE: Direct status update
    # State machine is broken, so the shipping service never picks it up.
    db.orders.insert_one({"user": user_id, "status": "COMPLETED", "total": total})
    
    # 🚨 NO IDEMPOTENCY: User double-clicking charges them twice
    stripe.charge(amount=total)
    return {"success": True}
```

Now imagine what would have happened if you had a skill like this in `.claude/skills/checkout-orchestration-skill/SKILL.md`:

```md
---
name: checkout-orchestration-skill
description: 'Enforces the distributed saga pattern for the e-commerce checkout pipeline. Use this skill whenever implementing or modifying order placement, payment flows, or cart finalization. It mandates idempotency (Redis), inventory reservation (never direct deduction), strict order state machine transitions (OrderStateMachine), tax aggregation (TaxJar/Vertex routing), async fraud handling (800ms timeout), and Kafka event emission (order_placed topic) for eventual consistency.'
---

## Core Architectural Rules

**NEVER** treat checkout as a single CRUD update. It is a **distributed saga**.

1. **Idempotency First**: Every checkout request must include an `idempotency_key`. If the key exists in Redis, return the cached result immediately. 
2. **Reserve, Do Not Deduct**: Never write directly to `inventory` table. Always call `InventoryReservationService.reserve()` which holds stock for 15 minutes (timeout period). Only finalize deduction after `PAYMENT_CONFIRMED` event.
3. **State Machine Only**: The `Order` entity has a strict state machine: `PENDING -> FRAUD_CHECK -> AUTHORIZED -> PAYMENT_CAPTURED -> FULFILLMENT_QUEUE` Never skip states. Never manually set `order.status = 'completed'`. Use `OrderStateMachine.transition('CAPTURE')`.
4. **Tax Agnosticism**: We use TaxJar for US/CA, and Vertex for EU. Always call `TaxAggregator.get_tax()` which handles the routing under the hood. Do NOT hardcode tax rates.
5. **Fraud Timeout**: The fraud check is async. If it takes > 800ms, we proceed with `FRAUD_PENDING` status and place a dead-letter retry, but we do NOT block the user.
6. **Eventual Consistency**: After capturing payment, push exactly one event to the `order_placed` Kafka topic. Must include the `correlation_id` for tracing.
```

And now if you send the same prompt to the coding agent, it generates real, production-grade, domain-aware code:

```py
@app.post("/flash-checkout")
def flash_checkout(products, user_id, idempotency_key):
    # 1. Enforce Idempotency
    cached = redis.get(idempotency_key)
    if cached: return cached

    # 2. Validate Flash Sale window (domain logic)
    if not timezone.now() in flash_sale_window:
        raise HTTPException(400, "Flash sale not active")

    # 3. Build line items
    line_items = [LineItem(p.id, p.qty) for p in products]

    # 4. Reserve inventory using the domain service (DOES NOT deduct yet)
    reservation_ids = InventoryReservationService.reserve_bulk(line_items)

    # 5. Get tax through the aggregator (handles US/EU routing)
    tax = TaxAggregator.get_tax(line_items, user_id)

    # 6. Initiate state machine
    order = OrderStateMachine.create(
        user_id=user_id, 
        line_items=line_items, 
        tax=tax,
        status="PENDING"
    )
    
    # 7. Fraud check (async, non-blocking)
    fraud_score = FraudScorer.submit_async(order.id)

    # 8. Authorization (not capture, just auth to check funds)
    auth_token = PaymentGateway.authorize(order.total, user.payment_method)

    # 9. Transition to authorized state
    OrderStateMachine.transition(order.id, "AUTHORIZE", context={"auth_token": auth_token})

    # 10. Emit Kafka event for downstream processing
    event_bus.publish("order_placed", {
        "order_id": order.id, 
        "correlation_id": request.headers["X-Correlation-ID"]
    })

    response = {"order_id": order.id, "status": "AUTHORIZED"}
    redis.setex(idempotency_key, 3600, json.dumps(response))
    return response
```

### Add Commands

You can e.g. create a command for labeling GitHub issues:

```shell
mkdir -p .claude/commands
cat > .claude/commands/label-github-issue.md << 'EOF'
---
description: Fetch a GitHub issue and apply appropriate labels using gh
argument-hint: <github-issue-url>
allowed-tools: Bash(gh issue view:*), Bash(gh label list:*), Bash(gh issue edit:*), Bash(gh repo view:*)
---

You are labeling a GitHub issue. The issue URL is: $ARGUMENTS

Steps:
1. Parse the URL to extract the owner, repo, and issue number.
2. Run `gh issue view <number> --repo <owner>/<repo> --json title,body,labels` to read the issue's current title, body, and existing labels.
3. Run `gh label list --repo <owner>/<repo>` to see which labels actually exist in this repo. Only use labels from this list, if you strongly believe we lack certain label just let the user know as a side note, do NOT stop here even if you believe certain labels are missing.
4. Based on the issue's title and body, decide which existing labels best apply (e.g. bug, enhancement, documentation, question, good first issue, priority levels, area/* labels, etc).
5. Apply the chosen labels with `gh issue edit <number> --repo <owner>/<repo> --add-label "label1,label2"`.
6. Report back to the user: which labels you applied and a one-line reason for each. Also report back the labels which you believe are good to add with a single line as to why.

If the issue already has labels that are still appropriate, leave them and only add what's missing. If no labels in the repo genuinely fit, say so instead of forcing one on.
EOF
```

And ensure you are committing them so others will be using the same commands when needed!

### `AGENTS.md`: Your Agent's Navigation System

The most important investment you can make is in documenting a navigation system for your AI agents. You wanna commit and push this documentation to your VCS. And I believe you already know it but I usually just link to `AGENTS.md` in `CLAUDE.md`. This way I do not have to copypaste or maintain both.

Also you can have a `AGENTS.local.md`/`CLAUDE.local.md` for your local setup which is not committed to git. So in `AGENTS.md` we usually put stuff such as:

- Bash commands.
- Common MCP tools.
- Style guides, this can be:
  - Frontend UX.
  - Best practices and design patterns.
  - Testing strategies (although you can move this to a separate markdown file and just link it).
- Architectural decisions.
- A link to important files.

Basically anything you usually need to work on that codebase. But make sure to keep it short and concise since if it is too long then it just take up space in your context window with no real benefits.

> ❗ **Note**
>
> You can have a `AGENTS.md`/`CLAUDE.md` in subdirectories of a project, and coding agents load them when reading and working with that directory's files. So there you can be more meticulous with your instructions.
>
> I would also like to make it crystal clear that LLMs love to optimize for coverage percentages. They'll often write brittle tests that:
>
> - Overly mock dependencies.
> - Test every code path without regard to actual functionality.
> - Break when you refactor.
>
> But what we want from our test suite cases are:
>
> - **Good tests**: Test the functionality you're building.
> - **Refactoring-safe**: Shouldn't break when you reimplement. NOTE, we are assuming the APIs remain the same.
> - **Logic-catching**: Should break when logic breaks.

---

## Process Discipline

### Embrace Trial and Error

- Adopt an **experimenter's mindset**.
- Start a task, see how it goes.
- If it doesn't work, abandon it and try another approach.
- *This flexibility is critical, don't be afraid to throw away what doesn't serve you.*

### Manage Context Proactively

- Check how much of the context is filled, e.g. in Cloud Code, you must use `/context` frequently.
- Don't always wait for coding agent to compact the context. You can do it yourself too if for example you need a fresh start and just wanted to summarize the current state in a more controlled manner.
- Clear your context with `/clear` and start fresh when needed.
- Write summaries to markdown to preserve important info before clearing. This is where a `PLAN.md` or similar progress log earns its keep: treat it as your project memory and communication log, not just a one-off note.
- Work in bite-sized chunks. So instead of:
  ```
  Hey agent, refactor this 50-person project's entire codebase.
  ```
  Try to ask LLM:
  ```
  Break this large task into 10 small, specific steps. Where each step should be independently:
  - Specifiable.
  - Testable.
  - Reviewable by a human.
  ```

### Explore, Plan, Confirm, Then Code

It is a good practice to start with writing a `PLAN.md` to brainstorm what you wanna do. In fact, that's why I downloaded [the brainstorming skill from the superpowers plugin](https://github.com/obra/superpowers/tree/b36e0829c6d0140e93cfef2ca599b1b07d4a7797/skills/brainstorming). So next time you wanna develop a feature which is big enough for the LLM to derail or misunderstand how it should work, first ask it to brainstorm and write a plan for you. Review and work on that plan, then start with implementing it. So if I wanted to visualize this:

```
[Explore] => [Plan] => [Confirm] => [Code] => [Commit]
```

The prompt would be:

> Figure out the root cause for issue #983, then propose a few fixes. Let me choose an approach before you code. ultrathink

> 💡 **Pro Tip**
>
> "ultrathink" is a special "magic keyword" you can add anywhere in your prompt to trigger a maximum reasoning depth mode for that specific request.

### Give It Acceptance Criteria

If you give your coding agent a way to measure how good it did, the results would be closer to what you wanted since it will iterate over it. For this usually we can:

1. Write tests => commit => code => iterate => code:
   > Write tests for @utils/markdown.ts to make sure links render properly (note the tests won't pass yet, since links aren't yet implemented). Then commit. Then update the code to make the tests pass.
2. Write code => screenshot results => iterate:
   > Implement [mock.png]. Then screenshot it with Puppeteer and iterate until it looks like the mock.
3. Write acceptance criteria in a markdown files similar to what you usually get in a Jira ticket written by a product owner:
   > Take @specs/payment-flow.md as the source of truth. Write e2e integration tests that mirror each acceptance scenario exactly. Run the tests, and they should fail initially. Then implement the @api/payment/ module and keep iterating until every test passes. Let me know which ACs were tricky or ambiguous.
   Or you can e.g. write
   > Let's work on https://acmecorp.atlassian.net/browse/PAY-842. Treat each bullet point in acceptance criteria section as a hard pass/fail criterion. Build the @app/checkout feature, then simulate a full user journey through the UI (using Playwright) and check each block. If a step fails, pause, fix, and re-run until the entire ticket is green. Do not mark the ticket as done until all checks pass.

---

## Ownership & the Safety Net

### Use Git Heavily

- Git is your safety net.
- Commit often.
- Branch freely.
- Roll back with confidence.

### You Own Every Line You Push

- **No AI slop**, look out for:
  - Long, rambling files that are hard to review.
  - Overly defensive code (excessive error handling, validation).
  - Generated code that's "technically correct" but architecturally poor.
- Avoid:
  - Unnecessary tests.
  - Extra READMEs.
  - Emojis.
- Be ruthless about code quality.
- Ensure everything you push is clean, purposeful, and well-written.

Remember I have already talked about it [here](https://dev.to/kasir-barati/pragmatic-agentic-programmer-994). This is code you stand behind.

> **Key Takeaway**
>
> Create a culture of rejecting mediocre AI-generated code.

---

## Bonus: Use Your Agent to Onboard, Not Just to Code

It is always a good idea to have another engineer to onboard you. But nowadays you can simply try to utilize LLMs and coding agents to help you with that as well. Ask questions such as:

- How is @RoutingController.py used?
- How do I make a new @app/services/ValidationTemplateFactory?
- Why does `recoverFromException` take so many arguments? Look through git history to answer.
- I'm new to the codebase. Give me a mental model of the @core/ folder, what are the primary responsibilities of each subdirectory, and which one should I touch if I need to modify the logging behavior?

Or you can ask other questions outside of onboarding process:

- Why did we fix issue #18363 by adding the `if/else` in @src/login.ts API?
- In which version did we release the new @api/ext/PreHooks.php API?
- Look at PR #9383, then carefully verify which app versions were impacted.
- What did I ship last week?
- If I deprecate the @utils/legacyParser.ts function, which modules across the entire monorepo are still relying on it? Show me the call stack in each case.
- Why was the @api/middleware/AuthGuard implemented as a class instead of a factory function? Look at the original PR and the team's discussion history to explain the trade-offs.

So your coding agent, if it is smart enough, will be able to look at git history whenever needed, and let's imagine you have an MCP server to return your microservice architecture. Then it will use it to gain a deeper understanding of how service A interacts with service B. Sometimes you have to be specific so it knows it must use the MCP server. And there are times it can figure that out itself.

---

## The Asymmetry Problem

It's becoming increasingly easy to generate tons of code, and the burden is shifting to humans to review it all. Everything above is really one answer to this same problem, combat it with:

- Disciplined review processes.
- Challenging agents to write succinct, clean code.
- Making sure agents don't overwhelm reviewers.

Now go back to that first branch you made. Apply what you've read:

- Write a detailed `AGENTS.md`.
- Use plugins where they fit.
- Break the work into small, reviewable steps.
- Review the output critically.

Save the results in a separate branch, and compare it against your first attempt. That difference is the whole point of this post.

---

## References:

[Mastering Claude Code in 30 minutes](https://www.youtube.com/live/6eBSHbLKuN0?si=Yy7r9-5OFapkoXuJ).