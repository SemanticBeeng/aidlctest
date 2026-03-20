# Technology: NVIDIA NIM

## Classification
- Primary: [[Model Inference Server]] (packaged microservice)
- Internals: embeds a [[Model Inference Engine]] such as TensorRT-LLM, vLLM, SGLang depending on the NIM distribution

## What it is (in this architecture)
NIM is a packaging and operationalization layer: prebuilt inference microservices exposing industry-standard APIs.

## When to choose it
- You want a supported, packaged server deployment with standard APIs
- You want to swap engines (vLLM/SGLang/TensorRT-LLM) via deployment choices rather than rewriting integrations

## Evaluation notes
- Same as any server: evaluation measures the system including its config.
