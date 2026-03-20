# Technology: vLLM

## Classification
- Primary: [[Model Inference Server]]
- Contains: a server-embedded [[Model Inference Engine]]

## What it is (in this architecture)
vLLM is used as the default **server-side inference server** for the MVP1 path. Its main value is high GPU utilization under concurrent workloads (eval runs, multi-user traffic).

## Key capabilities mapped to concepts
- **Server scheduling**: token-level scheduling/continuous batching (high throughput)
- **Admission control**: caps like maximum active sequences (protects KV cache / VRAM)
- **API surface**: commonly used in OpenAI-compatible serving mode (works well with DeepEval)

## When to choose it
- DeepEval runs with parallelism and/or large models/contexts
- You need throughput and predictable tail latency under load

## Risks / drift sources for evaluation
- Sampling defaults and chat template differences vs in-process generation
- Context truncation (`max_model_len`) and stop conditions

## Notes for this repo
- The architecture’s MVP1 path uses vLLM as the default under-test and/or judge server to exercise server scheduling + admission control.
