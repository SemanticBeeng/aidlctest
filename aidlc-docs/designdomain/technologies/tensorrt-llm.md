# Technology: TensorRT-LLM

## Classification
- Primary: [[Model Inference Engine]]
- Can be packaged as: a [[Model Inference Server]] via online serving (`trtllm-serve`) or via NIM packaging

## What it is (in this architecture)
TensorRT-LLM is an NVIDIA GPU inference optimization runtime. In this architecture it represents the “engine-level” path for low-latency/high-throughput GPU inference when you want kernel-level optimizations.

## Key capabilities mapped to concepts
- Engine optimizations: custom kernels, inflight batching, paged KV cache, quantization, speculative decoding
- Server mode: when deployed via `trtllm-serve`, it becomes a model inference server (API + scheduling)

## When to choose it
- Latency/throughput optimization becomes the dominant requirement
- You need strong quantization + kernel optimization on NVIDIA GPUs

## Evaluation notes
- If used behind a server, the evaluation measures the system (engine + server config). Ensure prompts/sampling/templates are held constant when comparing.
