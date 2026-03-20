# Concept: Model Inference Server

## Definition
A **model inference server** is a networked service that exposes a model inference capability through an API (often OpenAI-compatible). It typically embeds a [[Model Inference Engine]] but adds operational and multi-request concerns.

## Responsibilities
- Expose inference via a network API (HTTP/gRPC/WebSocket)
- Multi-request handling: request routing, queueing, cancellations
- Admission control: concurrency caps (e.g., max active sequences), backpressure
- Scheduling/batching policy across requests (may include token-level scheduling)
- Observability: metrics, logs, tracing hooks
- Operational integration: deployments, health checks, autoscaling

## Server scheduling vs session partitioning
A server can:
- use **token-level scheduling** (interleaving decode work across requests), and/or
- use **session partitioning/admission control** (caps, queues, per-tenant quotas)

In practice, most production systems combine both: a high-utilization engine scheduler plus server-level admission control.

## Interfaces
- Commonly OpenAI-compatible endpoints (e.g., `/v1/chat/completions`, `/v1/models`)
- Some servers provide additional endpoints for embeddings, multimodal, or tool calling.

## Evaluation implications
When evaluation calls a server (instead of in-process inference), the evaluation measures a *system*:
- model + engine + server scheduling + server configuration

This can be desirable for realism (TTFT, tail latency, concurrency) but introduces drift sources (templates, truncation policies, sampling defaults).
