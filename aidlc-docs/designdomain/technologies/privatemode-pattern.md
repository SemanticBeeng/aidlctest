# Technology/Pattern: PrivatemodeAI-style Privacy Proxy

## Classification
- Primary: deployment/policy pattern layered on top of a [[Model Inference Server]]

## What it is (in this architecture)
A privacy/encryption proxy in front of an inference server. It does not change the underlying model inference engine; it adds confidentiality and policy enforcement.

## When to use it
- Sensitive deployments where requests/responses require encryption and policy controls

## Evaluation notes
- Can be inserted transparently between DeepEval and the inference server, but may impact latency and error modes.
