---
title: "Observability & Telemetry Retention Policy"
published: true
description: "A pragmatic telemetry retention strategy for early-stage projects: start with 14 days, scale when needed, and avoid vendor lock-in with OpenTelemetry."
tags:
  - observability
  - opentelemetry
  - cloudinfrastructure
  - devops
cover_image: "https://raw.githubusercontent.com/kasir-barati/dev.to/refs/heads/main/articles/assets/observability-and-telemetry-retention-policy/cover.png"
series: System Design
---

## tl;dr

Use **OpenTelemetry (OTel)** for application observability and start with **Grafana Cloud Free** as the backend. I love both of them. They offer everything you will be needing when you have a bug ticket.

Grafana Cloud Free currently provides **14-day retention** for metrics, logs, traces, profiles, and k6 performance tests, with 50 GB each of logs and traces included. It is explicitly intended for personal projects and early-stage startups.

**14 days is sufficient for most applications in beta/MVP.** Incidents usually are investigated within hours or days, not months. Increase retention only when there is a demonstrated operational, business, security, or compliance need.

---

## Think About Telemetry in Layers

Not all telemetry needs the same retention period.

```text
                 ┌──────────────────────────┐
                 │      Long-lived data     │
                 │                          │
                 │ Metrics / trends         │
                 │ Audit & security events  │
                 │ Business-critical events │
                 └──────────────────────────┘
                              ▲
                              │
                       retain longer
                              │
                 ┌──────────────────────────┐
                 │     Short-lived data     │
                 │                          │
                 │ Application logs         │
                 │ Traces                   │
                 │ Debug information        │
                 └──────────────────────────┘
```

### Initial policy

| Telemetry                |                 Retention | Rationale                                                       |
| ------------------------ | ------------------------: | --------------------------------------------------------------- |
| Logs                     |               **14 days** | Enough for normal debugging and incident investigation          |
| Traces                   |               **14 days** | Primarily useful for investigating recent requests/errors       |
| Metrics                  |     **14 days initially** | Sufficient during beta/MVP; increase later for long-term trends |
| Debug logs               | **As short as practical** | High volume and usually low long-term value                     |
| Security/audit events    |       **Separate policy** | May require significantly longer retention                      |
| Business-critical events |      **Separate storage** | Should not depend on observability retention                    |

The goal is **not** to keep everything forever. The goal is to retain the information for as long as it is useful.

## When Should Retention Increase

Increase retention when we have a concrete reason, for example:

- A bug occurs less frequently than the current retention window.
- We need to investigate incidents discovered weeks later.
- We need historical performance/capacity trends.
- Security or compliance requirements require longer retention.
- The application becomes business-critical and historical investigation becomes important.

For example:

```text
Beta:
  Logs/Traces ─────────────── 14 days

Growing production:
  Logs/Traces ─────────────── 30–90 days
  Metrics ─────────────────── 6–13+ months
  Audit/Security ──────────── separate policy

Compliance/security:
  Audit data ──────────────── potentially years
```

Do **not** automatically increase raw-log retention just because the application grows. Long-term trends are often better represented by metrics, while important audit/business events can be archived separately.

## Avoid Vendor Lock-in

The application should **never depend directly on a vendor-specific observability SDK or API**.

Use:

```text
Application
    │
    │ OpenTelemetry
    ▼
OTel Collector
    │
    ├──────────► Grafana Cloud
    │
    ├──────────► Honeycomb
    │
    └──────────► Other OTel backend
```

The OpenTelemetry Collector is specifically designed to receive, process, and export telemetry to one or more backends. This means changing providers should primarily be a **Collector configuration/deployment change**, rather than an application rewrite. Use **OTLP**, the standard OpenTelemetry protocol, for the application → Collector boundary.

Also avoid making provider-specific dashboards, alerts, queries, and metadata a critical part of the application architecture until there is a reason to commit to them.

## Why OpenTelemetry?

OTel is a **vendor-neutral, open-source observability framework** for generating, collecting, and exporting logs, metrics, and traces. It is supported by a broad ecosystem of observability vendors.

Adopting OTel gives us:

- Vendor portability.
- Consistent telemetry semantics.
- Logs ↔ traces ↔ metrics correlation.
- Centralized sampling/filtering.
- The ability to change observability backends later.
- The option to send telemetry to multiple backends.

**Principle:**

> Instrument once with OpenTelemetry. Choose the observability backend independently.

## Read More

- [OpenTelemetry documentation](https://opentelemetry.io/docs/?utm_source=chatgpt.com)
- [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/?utm_source=chatgpt.com)
- [OTLP specification](https://opentelemetry.io/docs/specs/otlp/?utm_source=chatgpt.com)
- [Grafana Cloud Free](https://grafana.com/products/cloud/free-tier/?utm_source=chatgpt.com)
