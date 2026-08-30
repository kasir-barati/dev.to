---
title: 'RabbitMQ Consumer as a Separate Worker Service'
published: true
description: 'A short description of the post.'
tags:
  - nodejs
  - python
  - systemdesign
  - architecture
cover_image: https://raw.githubusercontent.com/kasir-barati/dev.to/refs/heads/main/articles/assets/rabbitmq-consumer-as-a-separate-worker-service/cover.png
series: System Design
---

I come from a NodeJS background and honestly there we usually consume messages in the same NestJS app. But 2 years ago (2024) when I started to develop Backend APIs in Python I realized there is a difference in programming language paradigms. In Python I had to either use [asyncio](https://docs.python.org/3/library/asyncio.html)/[threads](https://docs.python.org/3/library/threading.html)/[processes](https://docs.python.org/3/library/multiprocessing.html).

Here is an "at scale" alternative to the multithreading I wrote about [here](https://github.com/kasir-barati/python/blob/main/tips/multithreading.md) in particular (but I believe you can get some inspiration even if you have a subprocess) instead of a background thread living inside a GraphQL API process, the RabbitMQ consumer has its own container, and its own set of configuration. So the flow would look like this:

```flow
┌─────────────────────────┐
│ RabbitMQ                │
└─────────────────────────┘
        |
        ▼
┌─────────────────────────┐
| Worker process          |
└─────────────────────────┘
        |
        ▼
┌─────────────────────────┐
| Fetch/create user       |
└─────────────────────────┘
        |
        | "At least once" delivery guarantee
        ▼
┌─────────────────────────┐
| Redis pub/sub           |
└─────────────────────────┘
        |
        ▼
┌─────────────────────────┐
| Strawberry subscription |
└─────────────────────────┘
        |
        ▼
┌─────────────────────────┐
| GraphQL client          |
└─────────────────────────┘
```

## Why Split It Out at All?

A thread, or subprocess, or asyncio tasks in the GraphQL API process consumer ties three things together that don't actually belong together:

- **Scaling dimension.** HTTP replica count and RabbitMQ consumer count become the same number. If you need 10 API replicas for request load but only 2 consumers' worth of queue throughput, you either over-consume or under-provision HTTP, because one knob controls both. You can only twiddle one knob to adjust two different thing.
- **Failure domain.** An unhandled exception, a slow leak, or an OOM in message processing takes the HTTP server down with it (or vice versa: redeploying the API for an unrelated change restarts the consumer too, with all the reconnect/redelivery churn that implies).
- **Resource shape.** A CPU-heavy message handler competes with request handling for the same GIL when we create a thread to process RabbitMQ messages. And the same container's CPU/memory limits is shared between the two, instead of getting their own, independently sized deployment.

[A standalone worker process](https://github.com/kasir-barati/python/tree/34b5d750e15c055ed25f8cd5848b2668cbdde615/tips/examples/rabbitmq-worker-service#consumer) decouples all 3: scale it on queue depth, deploy/restart it without touching the API, and size its container for the work it actually does.

> 💡 **Takeaway**
>
> This more about provisioning, maintaining, horizontal scaling, and monitoring.

## "But in NodeJS/[Express](https://www.npmjs.com/package/express)/[Fastify](https://www.npmjs.com/package/fastify)/[NestJS](https://nestjs.com/) we just run it alongside the app"

That's a fair observation, and it works for a while for the same reason the same approach would works for a while in Python: at low volume, none of the three couplings above are painful yet. A few things make it look more tenable in Node than it might seem in Python:

- NodeJS's single-threaded, non-blocking I/O model means an `async` RabbitMQ handler naturally interleaves with request handling without needing an  extra thread or process at all, so there's no GIL-contention story like there is with a *blocking* library such as `pika` running in a Python thread.
- Frameworks like NestJS ship first-class support for bolting a message consumer onto the same app (`@nestjs/microservices`' hybrid application mode), so it is the path of least resistance, not something bolted on.

None of that removes the scaling/failure-domain coupling, though: a NodeJS/NestJS process consuming RabbitMQ inline still ties consumer count to HTTP replica count, and a handler that blocks the event loop (a CPU-bound computation, a synchronous call, a bad regex) stalls HTTP requests exactly like it would in any single-process design. NodeJS/NestJS teams that hit real throughput or correctness requirements make the same move shown here, usually via a distinct `@MessagePattern` microservice or a queue-specific worker deployment rather than the main HTTP app.

So this isn't a Python-specific lesson, it's what happens once "a background thing riding along in the API process" needs to be reasoned about as infrastructure rather than as an implementation detail.

## The Rule of Shared Libraries

Set up a monorepo whenever you need to share models/services/repositories. For example you can have an [`api`](https://github.com/kasir-barati/python/tree/34b5d750e15c055ed25f8cd5848b2668cbdde615/tips/examples/rabbitmq-worker-service/api) and a [`worker`](https://github.com/kasir-barati/python/tree/34b5d750e15c055ed25f8cd5848b2668cbdde615/tips/examples/rabbitmq-worker-service/worker) in the same monorepo. They are separately deployables, but they share one database and one set of SQLAlchemy models/repositories, defined once in [`shared`](https://github.com/kasir-barati/python/tree/34b5d750e15c055ed25f8cd5848b2668cbdde615/tips/examples/rabbitmq-worker-service/shared) and imported by both.

## [At Least Once Delivery](https://www.systemoverflow.com/learn/design-fundamentals/communication-patterns/idempotency-at-least-once-delivery-and-the-outbox-inbox-pattern) Guarantee 

In [the linked example](https://github.com/kasir-barati/python/tree/34b5d750e15c055ed25f8cd5848b2668cbdde615/tips/examples/rabbitmq-worker-service) we have two separate hops, because they have very different guarantees.

### Hop 1: RabbitMQ → Worker → Postgres

- At-least-once delivery comes from RabbitMQ fundamentals: durable queue + persistent messages + manual ack. Nothing is acked until it's fully processed, so a crash mid-flight just means redelivery to whoever reconnects.
- Idempotency comes from the domain itself, not a deduplication table: [`UserRepository.get_or_create`](https://github.com/kasir-barati/python/blob/34b5d750e15c055ed25f8cd5848b2668cbdde615/tips/examples/rabbitmq-worker-service/shared/src/shared/db/user/repository.py#L20-L27) is naturally idempotent because "does a user with this email exist" is a deterministic query independent of how many times you ask. That's "idempotent by construction", which is a lighter-weight cousin of the inbox pattern (a real inbox pattern would track message IDs in a deduplication table for handlers whose side effects aren't naturally idempotent. E.g. "increment balance by $10"). Here you don't need that machinery because the operation happens to collapse to the same result on replay.
- No outbox table either. A classic transactional outbox would write "email to publish" into a DB table in the same transaction as the user upsert, then a separate relay process drains that table into RabbitMQ/Redis. Instead, this worker does DB commit → Redis publish → RabbitMQ ack, non-transactionally, and covers the gap by not acking until both steps succeed. If it crashes after commit but before ack, whole process (DB write + Redis publish) reruns. That's why the [README's crash table](https://github.com/kasir-barati/python/tree/34b5d750e15c055ed25f8cd5848b2668cbdde615/tips/examples/rabbitmq-worker-service#important-note-about-db-transaction--order-of-actions) shows the DB write as safe (idempotent) but explicitly flags Redis as possibly duplicated. The ack-gating is doing the job an outbox table would normally do, at the cost of allowing duplicate publishes **instead of** guaranteeing exactly-once.

So: at-least-once + idempotent handler, achieved via ack ordering, not via outbox/inbox infrastructure, a genuinely solid and simple implementation.

### Hop 2: Worker → Redis pub/sub → GraphQL Subscription

This is the part that isn't gracefully handled, and your instinct is right.

- Duplicates from hop 1 leak straight through. When the worker crashes after redis.publish but before `basic_ack`, the redelivery causes a second publish of the same email to any subscriber.
- There's currently no way for a client to tell besides treating the email address as some sort of message ID, or sequence number, or more commonly known as idempotency key.

> **Could you add an idempotency key over the websocket?**
>
> Yes, nothing about GraphQL subscriptions or graphql-ws prevents it, it's just app-level payload shape. You'd:
>
> 1. Give each RabbitMQ message a stable ID, derive one deterministically (e.g. hash of the email, or client whom is initiating this whole pipeline can send one, or we could simply use the ID generated and returned by database engine) so that a crash-retry reproduces the same ID rather than minting a new one.
> 2. Carry that ID through: RabbitMQ message → Redis publish payload (as JSON: {"id": ..., "email": ...} instead of a bare string) → the Subscription.queue_messages yield → the GraphQL client.
> 3. The GraphQL client keeps a small set/LRU of recently-seen IDs and drops repeats — that's effectively an _inbox pattern_ implemented at the client, since the server-side pub/sub layer has no persistence to build a server-side inbox against.
> 
> Whether it's worth doing depends on how much a duplicate matters to your subscribers. Since the downstream effect here is "a user row exists", a duplicate push is currently harmless if the client is also just doing an upsert-style process. It only becomes a real problem if a client does something non-idempotent in response to the subscription event (e.g., "send a welcome email every time this fires").
