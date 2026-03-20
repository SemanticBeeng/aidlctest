# Concept: Model Inference Engine

## Definition
A **model inference engine** is the component that **executes model inference**: it loads (or is given) model weights, runs the forward pass, and drives decoding/generation (including KV-cache management and sampling) to produce tokens.

It can be embedded **in-process** (library/runtime called from the application) or embedded **inside a server**.

## Responsibilities
- Load/own model weights and tokenizer (or accept them as inputs)
- Execute prefill + decode loops
- Manage **KV cache** and memory
- Apply sampling / decoding strategies (greedy, top-p, beam, speculative decoding, guided decoding)
- Use hardware backends (CPU, GPU, NPU) and optimized kernels

## Non-responsibilities
A model inference engine does **not** inherently:
- expose a network API
- provide multi-tenant admission control
- provide request queuing, rate limits, authn/authz
- provide access logging/observability (beyond what the library offers)

Those are responsibilities of a [[Model Inference Server]].

## Common properties (evaluation-relevant)
- **Determinism**: seed control, reproducible decoding
- **Compatibility**: model formats, tokenizer behavior, chat templates
- **Performance**: throughput (tokens/s), TTFT, VRAM/RAM profile
- **Concurrency limiters**: KV-cache growth, max active sequences

## Examples
- In-process engines/runtimes: ExecuTorch runtime, Apple MLX runtime, a Python runtime that runs generation locally.
- Server-embedded engines: vLLM engine inside the vLLM server; TensorRT-LLM runtime inside `trtllm-serve`; SGLang runtime inside an SGLang server.
