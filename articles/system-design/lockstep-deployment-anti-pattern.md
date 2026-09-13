---
title: Lockstep Deployment Anti-pattern
published: true
description: How two independently deployable services quietly become impossible to ship separately and a concrete fix for the coupling that causes it.
tags:
  - systemdesign
  - microservices
  - coupling
  - antipattern
cover_image: 'https://raw.githubusercontent.com/kasir-barati/dev.to/refs/heads/main/articles/assets/lockstep-deployment-anti-pattern/cover.png?v=9e8341a'
series: System Design
id: 4645353
date: '2026-09-13T20:16:50Z'
---

Lockstep deployment is what happens when two services that are supposed to be independently deployable quietly stop being that. On paper they're separate repos, separate release cycles, separate teams even. In practice, you can't ship a change to one without also shipping a matching change to the other, in the same window, or something breaks.

The deployments aren't literally forced to happen at the same instant, but the _changes_ have to land together, or there's a period (sometimes seconds, sometimes days) where the system is broken or silently wrong.

It creeps in gradually. Nobody designs a system to require lockstep deploys 😉. It happens because two services agree to share more than they meant to.

## Why and When It Happens

The common thread is one service reaching into the other's internal implementation details instead of a stable, versioned contract. And do NOT use a feature flag to gate the new sages.

- **Shared vocabulary instead of a shared contract.** Service A defines an enum, a set of string literals, a status code list and imagine they service A does something that's really "the set of things it currently does internally". Service B, instead of treating that set as opaque, hardcodes it too: a switch statement, a validator. Now A adds/delete/update a value, and B is susceptible to ignoring/mishandling the value.
- **Implicit ordering assumptions across a boundary that doesn't preserve order.** Two independent processes (or the same service under concurrency) each get to notify a consumer, and the consumer assumes whatever arrives first _is_ first, logically. This might work by coincidence and breaks the instant timing shifts under a network hiccup, etc. Actually this was what happened in my [Beatrice](https://github.com/kasir-barati/smart-novel-beatrice/issues/4) and [smart-novel](https://github.com/kasir-barati/smart-novel) app.
- **A schema snapshot instead of a live contract.** One side keeps a checked-in copy of the other's schema/types and code-gens against it. If the copy isn't regenerated for a given change, things typecheck against stale/wrong interfaces. So I decided to improve this by what I did [here](https://github.com/kasir-barati/smart-novel/commit/a1c609e17693e61352caab24616d1cf6288ba176), essentially I am [downloading the schema based on the version of Beatrice form a URL at build time](https://github.com/kasir-barati/smart-novel-beatrice/issues/12).
- **Database or message shape shared directly** rather than through a service boundary, e.g. B reads a table A owns, or B parses a message body whose shape A can change unilaterally.
- **Pressure to move fast early on.** In the early life of a two-service system, it's often genuinely faster to let B "just know" about A's internals. No versioning ceremony, no abstraction to design, one team can even own both repos. The coupling is invisible until the day someone tries to change one side alone and can't.

## Why It's an Anti-Pattern

The entire point of splitting a system into separate services is independent deployability: separate release cadences, separate rollback, separate ownership, separate failure domains, logical separation of domains.concerns. Lockstep coupling quietly deletes that benefit while keeping all of its costs:

- **You lose independent rollback.** If B rolled forward assuming A's new behavior and A needs to roll back, B is now broken too, even though B itself has no bug.
- **You lose independent ownership.** Every change to A's internal state machine, error taxonomy, or vocabulary now requires a coordinated PR review, a coordinated release, and someone remembering both sides exist. A "small internal refactor" in A becomes a two-repo change with its own coordination tax.
- **The coupling is invisible until it's expensive.** Nobody notices the two services are welded together until someone tries to change one independently, ships it, and something downstream breaks in a way that's hard to trace back to "the two of us disagree about what a shared enum means", especially when the failure is a silent behavioral drift rather than a hard error.

  In fact I experienced this first-hand, and it is such a pain to keep all that in mind when developing new features and or fix bugs. I know that using [feature flags](https://hub.docker.com/repository/docker/9109679196/flagd-nestjs/general) is a completely valid approach to this issue of service A deployment being coupled to service B's deployment.

  So we put new features or bug fixes behind a feature flag (maybe you can skip the feature flag for some bug fixes though). But still you will be soon flooded with feature flags which you are responsible for maintaining them.

  Ah, and before I forget to mention, it is very much possible in your team you have silos of knowledge and expertise. And it can even get worse when the person who knows about the coupling of service A and service B will be in high demand by almost everyone. Then good luck getting things done 😬.

- **It defeats the reason you paid the cost of having two services at all.** If two components must always move together, the honest thing is for them to be one deployable unit. Keeping them as two separate repos/services while requiring lockstep changes gives you the operational overhead of a distributed system (network calls, partial failure, version skew) with none of the benefit (independent evolution).
- **It concentrates failure at exactly the moment it's least convenient**, under load, under a partial failure, at 2am, or when your Go To Market team is demoing the product 🥲 because of those _implicit_ assumption (ordering, shared vocabulary, shared schema, nontransparent logic) suddenly violated.

## A Real Example -- Beatrice and smart-novel's TTS Status Callbacks

[Beatrice](https://github.com/Ponos-OS/smart-novel-beatrice) is a GraphQL service. It owns TTS synthesis: it queues a `generateAudio` job onto RabbitMQ, and reports progress back to [smart-novel](https://github.com/Ponos-OS/smart-novel)'s backend via HTTP callbacks (smart-novel has a endpoint which Beatrice will call). Beatrice will send something like this to the callback as request body:

```js
{
  "status": "queued" | "generating" | "uploading" | "completed" | "failed",
  "jobId": "...",
  ...
}
```

[Over on smart-novel's side, I was essentially validating what is the value of `status`](https://github.com/Ponos-OS/smart-novel/blob/4cfa3037c04110c1a6d2cd41595d08f5e302a653/apps/backend/src/modules/tts-callbacks/dtos/tts-status-callback.dto.ts#L28):

```ts
@IsIn(['queued', 'generating', 'uploading', 'completed', 'failed'])
status!: 'queued' | 'generating' | 'uploading' | 'completed' | 'failed';
```

This is smart-novel hardcoding Beatrice's _internal pipeline stages_ <small>(implementation detail of states we have in Beatrice)</small> into its own validation schema. If Beatrice's synthesis pipeline changes shape tomorrow (say, a new `normalizing` stage is inserted before `generating`, or `uploading` is split into `uploading` and `verifying`), smart-novel's DTO rejects the new value outright, and the two repos now have to ship in the same window: Beatrice can't add a stage without smart-novel updating its enum first (or the callback gets dropped as invalid).

The second half of issue was a bug or rather how Beatrice was working internally. Basically Beatrice was saying that the statuses send from Beatrice to smart-novel arrive "in order: queued, generating, uploading, then completed. And it can be failed at any time when it fails to do something so we are reporting back failures".

You're still with me, right? And the issue was because [the `queued` status was sent synchronously](https://github.com/Ponos-OS/smart-novel-beatrice/blob/78168922ccf593c17f9e05f7bb8a377e73c5f73e/src/modules/audio/resolver.py#L196-L202) from Beatrice's resolver, [_after_ it publishes the job to RabbitMQ](https://github.com/Ponos-OS/smart-novel-beatrice/blob/78168922ccf593c17f9e05f7bb8a377e73c5f73e/src/modules/audio/resolver.py#L191-L195).

**BUT** [Beatrice sends the `generating` status independently](https://github.com/Ponos-OS/smart-novel-beatrice/blob/78168922ccf593c17f9e05f7bb8a377e73c5f73e/src/modules/audio/worker.py#L98-L104), and that is happening inside the worker we have for RabbitMQ.

Under normal load this ordering assumption happens to hold, because the worker is usually busy with a backlog. So by the time a new job's `queued` status is sent, the message is still waiting in the queue. But test locally with an empty queue and a single job in flight, and the worker can dequeue and fire `generating` before the resolver's `queued` HTTP call completes.

Neither side has any concept of sequence, so whichever callback's network round-trip finishes last simply overwrites the state in smart-novel. If that's `queued`, then [our subscription](https://github.com/Ponos-OS/smart-novel/blob/b16fb53cc2c267f43e8ec356e9defa46a936065e/apps/backend/src/modules/novel/resolvers/chapter-narration.resolver.ts#L61) was sending that as the last value to the frontend.

Thus you could see UI stuck in "Queued..." state, even though synthesis was already being generated and uploaded. So essentially it was a race condition between the worker and the resolver.

Both issues (race condition issue and the validation) share the same underlying problem:

- smart-novel is coupled to Beatrice's implementation details (its exact stage vocabulary).
- We did not have a stable and opaque contract.

Neither repo intended this; it accreted from what seemed like a reasonable, low-ceremony way to pass progress information across the boundary.

## The Explored Options, and Why Each Was Discarded

I guess some of them will even sound absurd to you, but believe me when I was discussing this with my coding agent it was suggesting them and I had to reason and explain why each one was not a good idea.

- **Hardcode a rank per known stage name in smart-novel's own DTO**, i.e. `queued: 1, generating: 2, uploading: 3`. But essentially this is no different from the original issue just with numbers bolted on: smart-novel still has to know Beatrice's complete, current stage vocabulary.
- **Beatrice will ensures `queued` will be reported back before `generating` state by moving the progress report call before queuing the job**. I guess this was the most logical thing to do, especially considering [what Beatrice was claiming (search for "in order:")](https://ponos-os.github.io/smart-novel-beatrice/v3.1.0/#mutation-generateAudio). But I did not do it. It is basically the same as saying if the message was not pushed to RabbitMQ, Beatrice still gonna tell smart-novel the job was queued.
- **A Postgres-row-backed state machine**, with the job's current stage stored as a row and advanced only via an atomic compare-and-swap (transition from stage A to B only if the row is still at A), firing the callback as a side effect of a successful transition. This is the textbook "correct" way to build a real state machine with enforced legal transitions but Beatrice has no database at all today.

  Standing one up solely to arbitrate ordering for a callback is a large, disproportionate piece of new infrastructure for what's fundamentally a small ordering problem.

- **Restructure Beatrice into an explicit queue-per-stage pipeline** (a dedicated queue and worker per pipeline stage, each stage only starting once the previous one finishes and hands the message off, [essentially a pipeline pattern](https://dev.to/kasir-barati/the-pipeline-pattern-15j5)), which gives free, structural ordering. Whoever whose processing the message is the only process that can report on it at any given moment.

  This is a genuinely good pattern in general, and came out of reasoning about a _hypothetical_ future stage (a "sanitizing" step). So I reached this solution in search of an answer for what if Beatrice's pipeline grows? But at the moment it is not. So instead of restructuring Beatrice and ending up with feature creep, I decided to find a simpler solution.

  **Just to be sure we are on the same page**, this is a very much good implementation but I do not need it.

- **A shared "centralized progress reporter"**: so at first in Beatrice I had duplicated code for sending status report back to smart-novel. So having one module inside Beatrice that both the resolver and the worker call into, sounded like a really good move. But on its own it doesn't solve the actual bug: centralizing _code_ doesn't centralize _runtime coordination_ between two calls made from two different OS processes or two different instances.

## What I Landed On, and Why It's the Better Trade-off

Every non-terminal status callback (`queued`, `generating`, `uploading`) now carries a small integer, `progress`, assigned by [a rank table that lives entirely inside Beatrice's new shared reporting module](https://github.com/Ponos-OS/smart-novel-beatrice/blob/78168922ccf593c17f9e05f7bb8a377e73c5f73e/src/modules/audio/progress.py#L20). `completed` and `failed` carry no `progress` at all, they apply unconditionally and end the sequence for that job.

smart-novel's entire change is: [track the last `progress` value seen per job](https://github.com/Ponos-OS/smart-novel/blob/b16fb53cc2c267f43e8ec356e9defa46a936065e/apps/backend/src/modules/novel/services/chapter-narration.service.ts#L223-L226), and [ignore any callback that isn't strictly greater than it](https://github.com/Ponos-OS/smart-novel/blob/b16fb53cc2c267f43e8ec356e9defa46a936065e/apps/backend/src/modules/novel/services/chapter-narration.service.ts#L214-L221).

I chose this because:

- **No new infrastructure.** No Redis, no Postgres, no new GraphQL schema surface. A well contained change.
- **It actually fixes the bug regardless of which process wins the race**.
- **The coupling that remains is the minimum necessary for correctness, and nothing more.** smart-novel agrees to exactly one thing with Beatrice: "a bigger `progress` number happened later, for this job". It doesn't know how many stages exist, what they're called, or what order they're introduced in.
- Beatrice must assign `progress` correctly and monotonically per job, including across its own retries and that's an invariant Beatrice enforces internally, in one module, never surfaced to smart-novel and never something smart-novel has to be updated to keep matching.

The only issue I have with my approach is that I am still coupling Beatrice's vocabulary in smart-novel when I am handling `completed` and `failed` states.

## Other Real-World Examples

- **Two microservices sharing a database schema instead of an API.** Service B queries tables Service A owns directly instead of through A's API. A can no longer run a migration, rename a column, or change a data type without coordinating a simultaneous change in B. This can happen specially when decomposing a feature from service A and moving it to service B.

  But there is a nice trick to handle this gracefully, I am talking now only if you wanna decompose a feature from service A to service B in a safe, easy to test and maintain way. So you will:

  1. Create a nice API for it in the service B.
  2. Then you need a new feature flag.
     - Whenever the feature flag is one:
       - You will start moving data from service A to service B in the background (steady data migration).
       - Service B will serve the clients now (but it will be writing the data in the database of both services, you can handle this in the repository layer).
       - Service A will forward all requests to service B.
     - Whenever the feature flag is off:
       - Service A will serve the clients directly (but its repository layer will still write in the database of both services).
       - Service B does nothing in this scenario.
       - No data migration either.

  This is better IMO, no separate data migration is needed, you can essentially go back and forth and test the feature in the new service at any time with peace of mind. But please share your thoughts on this if you believe my approach is more work.

- **A frontend and backend sharing GraphQL/REST types by hand-copying them** rather than generating from a single source of truth or a versioned schema registry. Just look at how smart-novel is auto generating the types for the UI from the backend's GraphQL schema at build time. No manual work required.
- **Protobuf field reuse without following wire-compatibility rules.** A team repurposes a numbered field instead of adding a new one, or changes a field's type in a way that isn't wire-compatible. For more info [read more about `reserved` in Protobuf](https://protobuf.dev/programming-guides/proto3/#reserved).
- **A message queue consumer assuming producer-side ordering that the broker doesn't guarantee.** Multiple producer instances (or partitions, or retries) publish to a queue/topic, and a downstream consumer assumes messages arrive in the order they were logically generated. This works until a retry, a partition rebalance, or multiple producer replicas cause reordering, and the consumer having no explicit sequencing will make its own wrong assumptions about the order of messages.
