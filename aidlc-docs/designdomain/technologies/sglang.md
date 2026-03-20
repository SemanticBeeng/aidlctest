# Technology: SGLang

## Classification
- Primary: [[Model Inference Server]] (depending on deployment mode)
- Contains: a server-embedded [[Model Inference Engine]]

## What it is (in this architecture)
SGLang is an alternative server-side inference stack to vLLM for OpenAI-compatible serving and high-throughput scheduling.

## Key capabilities mapped to concepts
- Server-side request handling + scheduling/batching
- Engine/runtime optimized for GPU inference

## When to choose it
- You want an alternative to vLLM for similar workloads
- You are using a platform distribution (e.g., NIM) that offers SGLang-backed containers

## Evaluation notes
- Same evaluation drift considerations as any server: templates, truncation, sampling defaults.
