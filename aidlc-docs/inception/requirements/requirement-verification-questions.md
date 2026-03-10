# Requirements Clarification Questions

Please answer all questions by placing your selected option letter after each `[Answer]:` tag.

## Question 1
Which mobile platforms must be supported in the first release?

A) Android only
B) iOS only
C) Both Android and iOS
X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 2
What is the primary app use case for this hybrid LLM inference system?

A) Chat assistant
B) Domain-specific copilot (enterprise/workflow)
C) Offline-first knowledge assistant
D) Voice assistant
X) Other (please describe after [Answer]: tag below)

[Answer]: X Domain specific shopping planning assistant. 

## Question 3
How should routing between on-device and server inference be decided?

A) On-device by default; server fallback on low confidence/capability
B) Server by default; on-device when offline
C) User-selectable mode (device/server/auto)
D) Rule-based by prompt category (privacy/latency/complexity)
X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 4
What is the latency target for first token response?

A) <= 500 ms
B) <= 1 second
C) <= 2 seconds
D) Best effort (no strict target)
X) Other (please describe after [Answer]: tag below)

[Answer]: D

## Question 5
What privacy/data policy should be enforced for prompts and responses?

A) Strict on-device for sensitive prompts; no server transmission
B) Server allowed with encryption and audit logging
C) User consent per request before sending to server
D) Full server processing allowed
X) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 6
What should the server-side inference stack target initially?

A) Python FastAPI + vLLM
B) Python FastAPI + llama.cpp server
C) Node.js + Python inference worker
D) Rust/C++ inference service
X) Other (please describe after [Answer]: tag below)

[Answer]: X llm-d and maybe even chutes.ai 

## Question 7
How should Cactus inference integration be delivered on mobile in v1?

A) Native mobile wrapper around Cactus engine only
B) Hybrid wrapper with optional fallback to bundled lightweight runtime
C) Plugin-style abstraction to swap engines later
X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 8
What model sizing/quantization should be targeted on-device for Qwen3 in v1?

A) 0.5B-1.5B quantized model (memory-constrained devices)
B) 3B-4B quantized model (mid/high devices)
C) Multi-tier model packs selected by device capability
D) You decide best practical default
X) Other (please describe after [Answer]: tag below)

[Answer]: X Decide based on iterative efficient fine tuning (QAT), evaluations on server side using deepevals and performance benchmarks on device.

## Question 9
What level of production hardening is expected now?

A) MVP/prototype (minimal security and ops)
B) Production-ready baseline (auth, rate limit, observability, CI checks)
C) Enterprise-grade (advanced compliance/security controls)
X) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 10: Security Extensions
Should security extension rules be enforced for this project?

A) Yes — enforce all SECURITY rules as blocking constraints (recommended for production-grade applications)
B) No — skip all SECURITY rules (suitable for PoCs, prototypes, and experimental projects)
X) Other (please describe after [Answer]: tag below)

[Answer]: Skip security for now but design server using Edgeless Systems Contrast as confidential AI solution. 
