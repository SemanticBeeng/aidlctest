# Technology: Lemonade Server

## Classification
- Primary: [[Model Inference Server]]
- Contains: a server-embedded [[Model Inference Engine]]

## What it is (in this architecture)
Lemonade Server is treated as a lightweight OpenAI-compatible inference server option for developer machines and low-parallelism scenarios.

## When to choose it
- Local development / quick experiments
- Low concurrency DeepEval runs where operational simplicity dominates

## When not to choose it
- High concurrency evaluation workloads where token-level scheduling and KV-cache admission control are primary constraints (prefer vLLM/SGLang/TensorRT-LLM-derived serving).
